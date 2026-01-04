## 数据加载与I/O 优化
*
并行读取 CSV 文件：目前 get_waveforms 逐个文件顺序读取 CSV，并将数据拼接。对于大量小文件，这种串行读取会造成显著的 I/O 瓶颈。建议利用并行技术（如 ThreadPoolExecutor 或 joblib）同时读取多个文件，提高磁盘吞吐和 CPU 利用率。例如，可改用已有的 parse_and_stack_files 方法，其内部已支持多线程/多进程并行解析。这样在读取每个通道文件列表时，可将 n_jobs 设置为通道数，实现各通道文件并行加载。并行读取可以减少总耗时，充分利用多核 CPU 资源。

分块读取与流式处理：为降低内存峰值占用，可采用流式分块读取。在当前实现中，每个通道的所有 CSV 内容被一次性载入并堆叠成大数组。这在数据量很大时会占用大量内存。建议使用项目中提供的生成器式解析函数 parse_files_generator，逐块yield数据GitHub
。这样可以一边读取一边处理波形，避免将所有数据同时驻留内存。文档中架构设计也强调了“流式处理”，通过生成器按块处理可显著降低内存占用。例如，可按每1000行数据块读取处理，然后丢弃已处理块，再读取下一块，实现pipeline的边读边算。

利用高效数据格式：目前原始数据以CSV纯文本存储和加载，解析开销较大。可考虑在首次导入后，将波形数据转换为高效的二进制格式以供重复使用。例如，可将未结构化波形数据保存为NumPy .npy、Apache Feather/Parquet或HDF5格式，并在后续分析中直接加载。Pandas 已经在输出阶段使用了 Parquet 保存配对结果，同理也可以在中间步骤缓存DataFrame为 Parquet/Feather供重复载入。利用 PyArrow 提供的 Feather/Parquet 实现，可以加快读写速度并降低空间占用。此外，PyArrow CSV 读取或 Polars 库也可以用于更快地解析CSV（它们用底层优化的C++实现CSV读取）。如果转换原始数据格式成本过高，也可考虑利用 内存映射（memory mapping）：例如将拼接后的大NumPy数组保存为 .dat 文件并使用 numpy.memmap 加载，从而实现零拷贝的数据访问，减少重复I/O开销。*
## 内存占用与缓存优化

按需保存与释放波形数据：为降低内存占用，当前 WaveformDataset 提供了 load_waveforms=False 选项，仅加载特征不保留波形（声称节省70-80%内存）。然而，当 load_waveforms=False 时，目前特征计算流程实际上被跳过（因为没有波形数据输入）
。建议改进这一模式：当用户选择不保留完整波形时，可以在提取特征时边读边算。例如，不经过 self.waveforms 缓存，直接在 extract_waveforms 中读取文件时计算峰值和电荷并存入 self.peaks/self.charges，而不保存完整波形数组。这样既实现了跳过波形存储又仍能得到特征值。实现方法可参考使用 pandas 的 chunk 或者自行解析CSV逐行计算需要的特征值，然后立即丢弃波形。如果必须保留部分数据（如为了支持 get_waveform_at 查看原始波形），也可在特征提取后通过选项释放不再需要的属性：例如在 build_dataframe 之后，将 self.st_waveforms 和 self.waveforms 清空（或转为磁盘缓存）以释放内存。总之，应确保在计算完成后及时释放大块内存，必要时提供API让用户选择释放（例如 dataset.clear_waveforms()）。

利用缓存避免重复计算：项目已经实现了按步骤缓存机制（内存字典 _cache 和磁盘持久化），并提供了 set_step_cache 接口配置GitHub
。目前缓存使用 Python 的 pickle 序列化，缓存大量 NumPy 数据时可能占用时间和空间。建议充分利用 joblib 后端对大数组更高效的序列化：事实上，在新版 CacheManager.save_data 中已经支持选择 backend 为 "joblib"。可以将默认持久化改为 joblib，从而利用 joblib 对 NumPy数组的mmap保存和压缩功能，提升缓存写读性能。此外，可考虑在特征计算后将关键中间结果（如结构化波形数组、DataFrame）缓存为列式存储格式（如 Feather）而非pickle。例如，将 self.df 和 self.df_events 保存为 Feather，有需要时再快速加载。缓存机制也应确保易于失效和更新：项目架构文档提到通过输入文件签名和参数变更来判定缓存有效性，实际实现中可引入文件hash或mtime监测，以防使用过期缓存。