# -*- coding: utf-8 -*-
"""
物理拟合模型 - 波形数据的高级拟合工具

本模块提供用于波形分析的物理模型拟合器，特别是 Landau-Gaussian 卷积拟合。

主要功能:
- Landau-Gaussian 卷积拟合（基于 JAX 实现）
- 高斯分布和 Landau 分布的数值近似
- 使用 iminuit 进行参数优化
- 支持 GPU 加速（通过 JAX）

典型应用场景:
- SiPM/PMT 信号的能量谱拟合
- 粒子探测器的电荷响应拟合
- 闪烁体光输出曲线分析

Examples:
    >>> from waveform_analysis.fitting.models import LandauGaussFitter
    >>> fitter = LandauGaussFitter(x_data, y_data)
    >>> fitter.fit()
    >>> print(fitter.params)

Note:
    本模块需要安装 JAX 和 iminuit:
    pip install jax jaxlib iminuit
"""
from iminuit import Minuit
import jax
import jax.numpy as jnp
import numpy as np
from pyDAW import BaseFitter


def gauss(x, mu, sigma, amp=1.0):
    """
    高斯分布（归一化形式乘以振幅）
    返回 amp * N(mu, sigma)(x)
    """
    return amp * np.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))


def landau_pdf_approx(x, mpv, eta):
    """
    Landau PDF 近似（不依赖 ROOT）
    基于 ROOT 的标准参数化：L(x; mpv, eta)
    使用常见的数值逼近
    """
    y = (x - mpv) / eta
    # 标准 Landau PDF：exp(-0.5*(y + exp(-y)))  / eta
    return jnp.exp(-0.5 * (y + jnp.exp(-y))) / eta


def landau_gauss_jax(x, mpv, eta, sigma, n_steps=100):
    """
    用 JAX 实现的 Landau ⊗ Gaussian 卷积（修复版）

    参数：
        x       : array，求值点 (1D)
        mpv     : Landau 的最可能值 (标量)
        eta     : Landau 宽度参数 (标量)
        sigma   : 高斯宽度 (标量)
        n_steps : 积分步数 (标量)

    返回：
        array，卷积后的 PDF 值 (与 x 同形状)
    """
    # 积分范围：[-5σ, +5σ]
    x_min = -5.0 * sigma
    x_max = 5.0 * sigma
    dt = (x_max - x_min) / n_steps

    # 生成积分节点：shape = (n_steps,)
    t_nodes = jnp.linspace(x_min, x_max, n_steps)

    # 初始化结果数组
    result = jnp.zeros_like(x, dtype=jnp.float32)

    # 对每个 x 值和每个 t 节点计算被积函数
    # x[:, None] shape = (len(x), 1)
    # t_nodes[None, :] shape = (1, n_steps)
    # 广播后：shape = (len(x), n_steps)

    x_expanded = x[:, None]  # (N, 1)
    t_expanded = t_nodes[None, :]  # (1, n_steps)

    # Landau PDF 在 (x - t) 处的值
    landau_vals = landau_pdf_approx(x_expanded - t_expanded, mpv, eta)  # (N, n_steps)

    # Gaussian 核
    gauss_kernel = jnp.exp(-0.5 * (t_expanded / sigma) ** 2) / (
        sigma * jnp.sqrt(2 * jnp.pi)
    )  # (1, n_steps)

    # 卷积：对 t 轴求和
    convolved = jnp.sum(landau_vals * gauss_kernel * dt, axis=1)  # (N,)

    return convolved


class LandauGaussFitter(BaseFitter):
    def __init__(self, x, y, fit_range, param):
        """
        初始化 Landau-Gauss 拟合器（JAX 版本）

        拟合 Landau ⊗ Gaussian 卷积加额外高斯峰的模型。

        Args:
            x: X 轴数据（能量/电荷）
            y: Y 轴数据（计数）
            fit_range: 拟合范围 (xmin, xmax)
            param: 初始参数 [mpv, eta, sigma, const, mu2, sigma2, A2]

        初始化内容:
        - 设置 Landau-Gauss 参数
        - 转换为 JAX 数组以加速计算
        """
        super().__init__(x, y, fit_range, param)
        self.mpv = param[0]
        self.eta = param[1]
        self.sigma = param[2]
        self.const = param[3]
        self.mu2 = param[4] if len(param) > 4 else 400
        self.sigma2 = param[5] if len(param) > 5 else 80
        self.A2 = param[6] if len(param) > 6 else 1e5

        # 转换为 JAX array
        self.x_jax = jnp.asarray(x, dtype=jnp.float32)
        self.y_jax = jnp.asarray(y, dtype=jnp.float32)

    def fit_func_jax(self, x, mpv, eta, sigma, const, mu2, sigma2, A2):
        """JAX 版本的拟合函数"""
        # Landau ⊗ Gaussian 部分
        conv_part = const * landau_gauss_jax(x, mpv, eta, sigma, n_steps=1000)

        # 额外的高斯峰
        extra_gauss = A2 * jnp.exp(-0.5 * ((x - mu2) / sigma2) ** 2)

        return conv_part + extra_gauss

    def fit_func(self, x, mpv, eta, sigma, const, mu2, sigma2, A2):
        """numpy 调用接口"""
        x_jax = jnp.asarray(x, dtype=jnp.float32)
        result = self.fit_func_jax(x_jax, mpv, eta, sigma, const, mu2, sigma2, A2)
        return np.asarray(result)

    # def fit(self):
    #     """执行拟合，并返回拟合参数及误差"""
    #     # JIT 编译 fit_func_jax 以加速计算
    #     self.fit_func_jax = jax.jit(self.fit_func_jax)

    #     def objective(*params):
    #         return self.nll(params=params)

    #     self.m = Minuit(objective, *self.param)
    #     self.set_limits(self.m)

    #     self.m.strategy = 2  # 使用更精确的策略以提高收敛性
    #     self.m.tol = 1e-8  # 设置更严格的容差
    #     self.m.print_level = 1
    #     self.m.migrad()
    #     self.m.hesse()

    #     if not self.m.valid:
    #         print(
    #             "Warning: Fit did not converge. Check parameter limits or initial values."
    #         )
    #     else:
    #         print("Fit converged successfully.")

    #     return self.m.values, self.m.errors
    def fit(self):
        """执行拟合，使用自定义 chi2（LeastSquares 风格），返回拟合参数及误差"""
        # 保留 jitted jax 版本以便其它地方调用
        self.fit_func_jax = jax.jit(self.fit_func_jax)

        # 在 fit_range 内取数据
        mask = (self.x_jax >= self.fit_range[0]) & (self.x_jax <= self.fit_range[1])
        x_masked = np.asarray(self.x_jax[mask])
        y_masked = np.asarray(self.y_jax[mask])

        if x_masked.size == 0 or y_masked.size == 0:
            raise RuntimeError("No data points in fit range")

        # 为 chi2 准备 sigma（泊松：sqrt(y)，对 0 做保护）
        sigma = np.sqrt(np.maximum(y_masked, 1.0))
        sigma[sigma == 0] = 1.0

        # 定义 chi2 callable（用于 Minuit）
        def chi2(*params):
            # 预测值
            y_pred = self.fit_func(x_masked, *params)

            # 数值保护：替换 NaN/inf，保证非负
            y_pred = np.nan_to_num(y_pred, nan=1e-9, posinf=1e9, neginf=1e-9)
            y_pred = np.clip(y_pred, 0.0, None)

            # 残差与 chi2
            resid = (y_masked - y_pred) / sigma
            val = np.sum(resid * resid)

            # 防止返回非有限值
            if not np.isfinite(val):
                return 1e30
            return float(val)

        # 用 chi2 创建 Minuit
        self.m = Minuit(chi2, *self.param)
        self.set_limits(self.m)

        # LeastSquares 对应 errordef = 1
        self.m.errordef = 1.0

        # 显式设置初始步长（帮助收敛）
        for i, p in enumerate(self.param):
            name = f"x{i}"
            step = max(abs(p) * 0.1, 1e-3)
            try:
                self.m.errors[name] = float(step)
            except Exception:
                pass

        # 优化参数
        self.m.strategy = 2
        self.m.tol = 1e-6
        self.m.print_level = 1

        # 执行拟合
        self.m.migrad()
        try:
            self.m.hesse()
        except Exception:
            pass

        if not self.m.valid:
            print("Warning: Fit did not converge. 检查初值、范围或 sigma 设置。")
        else:
            print("Fit converged successfully.")

        return self.m.values, self.m.errors

    # ...existing code...

    def nll(self, params=None):
        """Poisson NLL with numerical stability"""
        if params is None:
            params = self.param

        mpv, eta, sigma, const, mu2, sigma2, A2 = params

        # 计算模型值
        model_jax = self.fit_func_jax(
            self.x_jax, mpv, eta, sigma, const, mu2, sigma2, A2
        )

        # 数值保护
        eps = 1e-14
        model_jax = jnp.maximum(model_jax, eps)

        # 选择拟合范围
        mask = (self.x_jax >= self.fit_range[0]) & (self.x_jax <= self.fit_range[1])
        y_masked = self.y_jax[mask]
        mu_masked = model_jax[mask]

        # Poisson NLL: -sum(y*ln(mu) - mu)
        nll_value = -jnp.sum(y_masked * jnp.log(mu_masked) - mu_masked)

        return float(nll_value)

    def set_limits(self, minuit):
        """设置参数范围"""
        minuit.limits = [
            (self.mpv - 100, self.mpv + 100),
            (100, 300),
            (0.01, 200),
            (2e6, None),
            (320, 500),
            (50, 200),
            (1e3, 3e3),
        ]


class LandauGaussFitter2(BaseFitter):
    def __init__(self, x, y, fit_range, param):
        """
        初始化 Landau-Gauss 拟合器（简化版本）

        使用近似的 Landau-Gauss 乘积形式（而非卷积）。

        Args:
            x: X 轴数据（能量/电荷）
            y: Y 轴数据（计数）
            fit_range: 拟合范围 (xmin, xmax)
            param: 初始参数 [mpv, eta, sigma, const]

        Note:
            此版本使用乘积近似，计算更快但精度较低。
        """
        super().__init__(x, y, fit_range, param)
        self.mpv = param[0]

    def fit_func(self, x, mpv, eta, sigma, const):
        """
        Landau-Gauss 分布的具体实现
        """
        xi = (x - mpv) / eta
        landau_part = np.exp(-0.5 * (xi + np.exp(-xi))) / eta
        gauss_part = np.exp(-0.5 * ((x - mpv) / sigma) ** 2) / (
            sigma * np.sqrt(2 * np.pi)
        )
        return const * landau_part * gauss_part

    def set_limits(self, minuit):
        """
        自定义参数的限制
        """
        minuit.limits = [
            (self.mpv - 100, self.mpv + 100),  # mpv 的限制
            (1e-3, None),  # eta 的下限
            (1e-3, None),  # sigma 的下限
            (1e6, None),
        ]
