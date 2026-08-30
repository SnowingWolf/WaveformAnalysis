"""Curated plugin documentation categories and default profiles."""

# 插件类别映射规则
CATEGORY_KEYWORDS = {
    "data_loading": ["raw", "files", "loader", "reader"],
    "peaks": ["peaklet"],
    "waveform_processing": ["waveform", "st_waveform", "filtered", "wave"],
    "feature_extraction": ["feature", "peak", "hit", "charge", "height", "width"],
    "event_analysis": ["event", "group", "pair", "coincidence"],
    "data_export": ["dataframe", "df", "export", "frame"],
    "signal_processing": ["filter", "signal", "fft", "smooth"],
    "cache_analysis": ["cache", "storage", "analysis"],
    "records": ["record"],
}

# 类别显示名称
CATEGORY_DISPLAY_NAMES = {
    "data_loading": "数据加载",
    "waveform_processing": "波形处理",
    "peaks": "峰构建",
    "feature_extraction": "特征提取",
    "event_analysis": "事件分析",
    "data_export": "数据导出",
    "signal_processing": "信号处理",
    "cache_analysis": "缓存分析",
    "records": "记录处理",
    "other": "其他",
}

# 插件集合描述：每个 plugin_set 的职责与组成
PLUGIN_SET_DESCRIPTIONS = {
    "io": "扫描数据目录并按通道号分组原始文件，是处理链路的输入入口。",
    "waveform": "波形结构化、可选滤波与 records/wave_pool 构建；波形与记录插件必须同集合注册，依赖关系随 adapter 自动调整。",
    "hit": "Hit 检测与合并：阈值检测、记录掩码（不对称/探测器/veto）、hit 合并与聚类、hit_merged 特征。",
    "peaks": "Peaklet 构建与 peak 分类：peaklet 组件、peaklets、波形、pool、特征、通道、peaks、波形宽度、S1/S2 分类与 peak 分类。",
    "basic_features": "基础特征提取：从波形计算高度、面积、最大绝对差等特征。",
    "tabular": "表格输出（DataFrame、表）：构建单通道事件 DataFrame 与分组/配对事件表。",
    "events": "事件级处理：S1-S2 配对候选与最终选择、位置重建、完整事件重建与按时间窗口分组的事件。",
}

PLUGIN_SET_COLORS = {
    "io": ("#e8f1fb", "#3b78b8", "#c9dff5"),
    "waveform": ("#e5f5ee", "#278a5b", "#c8ead9"),
    "hit": ("#fff0df", "#c76b20", "#f8d5ab"),
    "peaks": ("#f1e9fb", "#8054b5", "#dfcdf4"),
    "basic_features": ("#fdf5d8", "#a98219", "#f2e3a6"),
    "tabular": ("#e6f4f6", "#287e88", "#c8e8eb"),
    "events": ("#fae8ed", "#bb4666", "#f3cad5"),
    "other": ("#eef1f2", "#63727b", "#d9e0e3"),
}

# 插件集合配图：集合名 -> 资产相对路径（相对于输出 assets/），由 generate_web 从模板资产复制。
PLUGIN_SET_IMAGES = {
    "io": "plugin-sets/io.png",
    "waveform": "plugin-sets/waveform.png",
    "hit": "plugin-sets/hit.png",
    "peaks": "plugin-sets/peaks.png",
    "basic_features": "plugin-sets/basic_features.png",
    "tabular": "plugin-sets/tabular.png",
    "events": "plugin-sets/events.png",
}

DOCUMENTATION_DEFAULT_PROFILE = {
    "wave_source": "records",
    "use_filtered": False,
    "daq_adapter": "vx2730",
}
DOCUMENTATION_DEFAULT_PROFILE_NAME = "documentation-default-v1"
DOCUMENTATION_PLUGIN_DEFAULTS = {
    "hit_threshold": {"asymmetry_cut_enabled": True},
}
STANDALONE_PLUGIN_OUTPUTS = frozenset({"cache_analysis"})
CORE_TERMINAL_OUTPUT = "events"
MAIN_LINEAGE_PATH = (
    "raw_files",
    "records",
    "hit_threshold",
    "hit_merged",
    "peaklets",
    "peaks",
    "peak_classification",
    "s1_s2_pair_candidates",
    "s1_s2_pairs",
    "position_reconstruction",
    "events",
)
MAIN_LINEAGE_EDGES = frozenset(zip(MAIN_LINEAGE_PATH, MAIN_LINEAGE_PATH[1:], strict=False))
