# waveform-cache 命令参考

**导航**: [文档中心](../README.md) > [命令行工具](README.md) > waveform-cache 命令参考

`waveform-cache` 是 WaveformAnalysis 的缓存管理工具，用于查看、诊断和清理缓存数据。

---

## 命令概述

`waveform-cache` 提供以下功能：
- `info` 查看缓存信息和统计
- `diagnose` 诊断缓存问题
- `clean` 清理缓存数据（支持多种策略）
- `list` 列出缓存条目

---

## 基本用法

```bash
waveform-cache [全局选项] <命令> [命令选项]
```

**重要**: 全局选项（如 `--storage-dir` 和 `--verbose`）**必须**在子命令之前指定。如果放在子命令之后，会被识别为未识别的参数。

**正确示例**:
```bash
# ✅ 正确：全局选项在子命令之前
waveform-cache --storage-dir ./outputs/_cache stats --detailed
waveform-cache --storage-dir ./outputs/_cache info
```

**错误示例**:
```bash
# ❌ 错误：全局选项在子命令之后（会导致错误）
waveform-cache stats --detailed --storage-dir ./outputs/_cache
```

---

## 全局选项

全局选项必须在子命令之前指定。

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--storage-dir` | - | str | "./strax_data" | 缓存存储目录。**必须在子命令之前指定** |
| `--verbose` | `-v` | flag | False | 显示详细信息。**必须在子命令之前指定** |

---

## 子命令

### 1. info - 显示缓存概览

显示缓存的总体信息。

```bash
waveform-cache info [选项]
```

**选项**:
- `--run <run_id>`: 仅显示指定运行
- `--detailed`: 显示详细信息

**示例**:
```bash
# 查看所有缓存的概览
waveform-cache info

# 查看指定运行的缓存
waveform-cache info --run run_001

# 显示详细信息
waveform-cache info --detailed

# 使用自定义存储目录（注意：--storage-dir 必须在 info 之前）
waveform-cache --storage-dir ./outputs/_cache info --detailed
```

---

### 2. stats - 显示缓存统计

显示缓存的统计信息，可以导出为 JSON 或 CSV。

```bash
waveform-cache stats [选项]
```

**选项**:
- `--run <run_id>`: 仅统计指定运行
- `--detailed`: 显示详细统计
- `--export <path>`: 导出统计到文件（.json 或 .csv）

**示例**:
```bash
# 基本统计
waveform-cache stats

# 详细统计
waveform-cache stats --detailed

# 导出统计
waveform-cache stats --export cache_stats.json
waveform-cache stats --export cache_stats.csv

# 使用自定义存储目录（注意：--storage-dir 必须在 stats 之前）
waveform-cache --storage-dir ./outputs/_cache stats --detailed
waveform-cache --storage-dir ./outputs/_cache stats --export cache_stats.json
```

---

### 3. diagnose - 诊断缓存问题

诊断缓存中的问题，如损坏文件、版本不匹配等。

```bash
waveform-cache diagnose [选项]
```

**选项**:
- `--run <run_id>`: 仅诊断指定运行
- `--fix`: 自动修复可修复的问题
- `--dry-run`: 仅预演修复操作（默认）
- `--no-dry-run`: 实际执行修复操作

**示例**:
```bash
# 诊断所有缓存
waveform-cache diagnose

# 诊断指定运行
waveform-cache diagnose --run run_001

# 预览修复操作
waveform-cache diagnose --fix --dry-run

# 实际执行修复
waveform-cache diagnose --fix --no-dry-run
```

---

### 4. clean - 清理缓存

清理缓存数据，支持多种清理策略。

```bash
waveform-cache clean [选项]
```

**选项**:
- `--strategy <策略>`: 清理策略（默认: lru）
  - `lru`: 最近最少使用
  - `oldest`: 最旧的数据
  - `largest`: 最大的文件
  - `version`: 版本不匹配
  - `integrity`: 完整性检查失败
- `--size-mb <MB>`: 目标释放空间（MB）
- `--days <N>`: 保留最近 N 天的数据
- `--run <run_id>`: 仅清理指定运行
- `--data-type <name>`: 仅清理指定数据类型
- `--dry-run`: 仅预演清理操作（默认）
- `--no-dry-run`: 实际执行清理操作
- `--max-entries <N>`: 最多删除的条目数

**示例**:
```bash
# 预览清理（LRU 策略，释放 500MB）
waveform-cache clean --strategy lru --size-mb 500

# 清理超过 30 天的数据
waveform-cache clean --strategy oldest --days 30 --no-dry-run

# 清理指定运行
waveform-cache clean --run run_001 --no-dry-run

# 清理指定数据类型
waveform-cache clean --data-type st_waveforms --no-dry-run
```

---

### 5. list - 列出缓存条目

列出缓存条目，支持多种过滤选项。

```bash
waveform-cache list [选项]
```

**选项**:
- `--run <run_id>`: 按运行过滤
- `--data-type <name>`: 按数据类型过滤
- `--min-size <bytes>`: 最小大小（字节）
- `--max-size <bytes>`: 最大大小（字节）
- `--limit <N>`: 最多显示条目数（默认: 50）

**示例**:
```bash
# 列出所有缓存条目
waveform-cache list

# 列出指定运行的缓存
waveform-cache list --run run_001

# 列出大于 100MB 的缓存
waveform-cache list --min-size 104857600

# 限制显示数量
waveform-cache list --limit 20
```

---

## 清理策略说明

### LRU (Least Recently Used)
删除最近最少使用的缓存条目。适合需要释放空间但保留常用数据。

### Oldest
删除最旧的数据。适合定期清理历史数据。

### Largest
删除最大的文件。适合快速释放大量空间。

### Version
删除版本不匹配的缓存。适合在插件版本更新后清理旧缓存。

### Integrity
删除完整性检查失败的缓存。适合清理损坏的数据。

---

## 安全特性

### Dry-Run 模式

所有清理和修复操作默认使用 `--dry-run` 模式，只会预览操作而不会实际执行：

```bash
# 预览清理操作
waveform-cache clean --strategy lru --size-mb 500

# 实际执行清理
waveform-cache clean --strategy lru --size-mb 500 --no-dry-run
```

---

## 使用示例

### 场景 1: 查看缓存使用情况

```bash
# 快速概览
waveform-cache info

# 详细统计
waveform-cache stats --detailed --export cache_report.json

# 使用自定义存储目录
waveform-cache --storage-dir ./outputs/_cache info
waveform-cache --storage-dir ./outputs/_cache stats --detailed --export cache_report.json
```

### 场景 2: 诊断和修复问题

```bash
# 诊断问题
waveform-cache diagnose --run run_001

# 预览修复
waveform-cache diagnose --fix --dry-run

# 执行修复
waveform-cache diagnose --fix --no-dry-run
```

### 场景 3: 清理缓存

```bash
# 释放 1GB 空间（预览）
waveform-cache clean --strategy lru --size-mb 1024

# 清理超过 60 天的数据
waveform-cache clean --strategy oldest --days 60 --no-dry-run

# 清理指定运行的旧数据
waveform-cache clean --run run_001 --strategy oldest --days 30 --no-dry-run
```

---

## 退出码

| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 错误 |
| 130 | 用户中断（Ctrl+C） |

---

## 错误处理

### 常见错误

1. **未识别的参数错误**
   ```
   waveform-cache: error: unrecognized arguments: --storage-dir ./outputs/_cache
   ```
   **原因**: `--storage-dir` 是全局选项，必须在子命令之前指定。

   **解决**: 将 `--storage-dir` 移到子命令之前：
   ```bash
   # ❌ 错误
   waveform-cache stats --detailed --storage-dir ./outputs/_cache

   # ✅ 正确
   waveform-cache --storage-dir ./outputs/_cache stats --detailed
   ```

2. **存储目录不存在**
   ```
   警告: 存储目录不存在: ./strax_data
   将创建空的缓存目录...
   ```
   解决: 工具会自动创建目录，或使用 `--storage-dir` 指定正确路径

3. **没有找到匹配的缓存条目**
   ```
   没有找到匹配的缓存条目
   ```
   解决: 检查过滤条件是否正确，或确认缓存目录中有数据

---

## 注意事项

1. **参数顺序**: **全局选项必须在子命令之前指定**。`--storage-dir` 和 `--verbose` 必须放在子命令（如 `stats`、`info`）之前，否则会出现"未识别的参数"错误。
2. **默认 Dry-Run**: 清理和修复操作默认是预览模式，需要 `--no-dry-run` 才会实际执行
3. **存储目录**: 确保 `--storage-dir` 指向正确的缓存目录
4. **数据安全**: 清理操作不可逆，建议先使用 `--dry-run` 预览
5. **性能**: 扫描大型缓存目录可能需要一些时间

---

**相关文档**:
[CLI 工具总览](README.md) |
[缓存机制](../features/context/DATA_ACCESS.md#缓存机制) |
[存储系统](../architecture/ARCHITECTURE.md)
