   
`/home/wxy/anaconda3/envs/pyroot-kernel/bin/python` 这是我使用的 python 文件所在的地址。

为了便于运行测试，你可以使用仓库提供的脚本来自动激活 conda 环境并运行测试：

```bash
# 首次只需确保已安装 conda 并存在名为 pyroot-kernel 的环境
# 运行测试（脚本会自动 source conda.sh 并激活环境）
./scripts/run_tests.sh
# 或者通过 Makefile
make test
```

脚本默认激活 `pyroot-kernel`，也可以通过环境变量覆盖：

```bash
CONDA_ENV=my-env ./scripts/run_tests.sh -q
```
