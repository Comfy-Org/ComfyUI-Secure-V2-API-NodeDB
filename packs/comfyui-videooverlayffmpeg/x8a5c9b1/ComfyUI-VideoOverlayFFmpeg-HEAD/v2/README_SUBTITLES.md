# Video Overlay with Subtitles 节点使用说明

## 概述

`VideoOverlayWithSubtitlesNode` 是一个增强版的视频合成节点，在原有画中画功能的基础上，添加了强大的字幕支持。

## ✨ 主要特性

### 1. **智能文本换行** 📝
- 自动根据视频宽度计算最佳换行位置
- 按单词边界智能分行，不会截断单词
- 完全解决文字超出视频宽度的问题

### 2. **直接连线 whisper_alignment** 🔌
- 支持直接连接 whisper 转录节点的输出
- 无需手动复制粘贴 JSON
- 自动解析时间轴和文本内容

### 3. **丰富的字幕样式** 🎨
- 字体选择（支持系统字体和自定义字体）
- 字体大小（12-200px）
- 字体颜色（white, yellow, red 等）
- 背景框（半透明黑色背景，可调节透明度）
- 多种预设位置（底部居中、顶部居中等）

## 📋 输入参数说明

### 必需参数（与原节点相同）
- `big_video_path`: 大视频路径（背景视频）
- `small_video_path`: 小视频路径（叠加视频）
- `mask_video_path`: 遮罩视频路径
- `opacity`: 透明度 (0.0-1.0)
- `position`: 小视频位置（right_bottom, right_top, left_bottom, left_top, center）
- `margin_x`: 水平边距 (0-500px)
- `margin_y`: 垂直边距 (0-500px)
- `size_ratio`: 小视频尺寸比例 (0.1-1.0)
- `big_video_audio_volume`: 大视频音量 (0.0-2.0)
- `small_video_audio_volume`: 小视频音量 (0.0-2.0)
- `video_fps`: 视频帧率 (1.0-120.0)

### 可选参数（字幕相关）

#### alignment (whisper_alignment)
- **类型**: whisper_alignment 或 JSON 字符串
- **说明**: 字幕时间轴数据
- **格式**:
```json
[
    {
        "value": "One minute of Eldridge Cleaver is worth ten minutes of Roy Wilkins.",
        "start": 0.0,
        "end": 4.86
    },
    {
        "value": "The labor crisis settled...",
        "start": 6.02,
        "end": 12.9
    }
]
```

#### font_path (下拉选择)
- **默认**: 自动检测可用字体
- **说明**: 字体文件路径
- **支持**:
  - 系统字体（DejaVu, Liberation, Arial 等）
  - 自定义字体（放在 `fonts/` 目录）

#### font_size
- **默认**: 48
- **范围**: 12-200
- **说明**: 字体大小（像素）

#### font_color
- **默认**: "white"
- **示例**: "white", "yellow", "red", "#FFFFFF", "rgb(255,255,0)"
- **说明**: 字体颜色

#### subtitle_position
- **默认**: "bottom_center"
- **选项**:
  - `bottom_center`: 底部居中（最常用）
  - `top_center`: 顶部居中
  - `bottom_left`: 左下角
  - `bottom_right`: 右下角
  - `center`: 屏幕中央
  - `custom`: 自定义位置（使用 x_position 和 y_position）

#### x_position / y_position
- **默认**: 0
- **范围**: -1000 到 3000
- **说明**: 仅在 subtitle_position = "custom" 时生效

#### max_text_width
- **默认**: 0（自动计算为视频宽度的 80%）
- **范围**: 0-4000
- **说明**: 文本最大宽度（像素），超过此宽度会自动换行

#### background_opacity
- **默认**: 0.7
- **范围**: 0.0-1.0
- **说明**: 背景框透明度（0=完全透明，1=完全不透明）

#### background_color
- **默认**: "black"
- **说明**: 背景框颜色

## 🎯 使用示例

### 基础使用（从 whisper 节点连线）

```
WhisperTranscribe → alignment 输入
                  ↓
    VideoOverlayWithSubtitlesNode
                  ↓
              合成视频
```

### 自定义字幕样式

```python
# 参数设置示例
font_size = 60              # 较大字体
font_color = "yellow"       # 黄色字幕
subtitle_position = "bottom_center"
max_text_width = 1600       # 限制文本宽度
background_opacity = 0.8    # 稍微不透明的背景
```

### 长文本自动换行示例

**原始文本** (164 字符):
```
The labor crisis settled at the negotiating table is nothing compared to the confrontation that results in a strike, or better yet, violence along the picket lines.
```

**自动换行后**（1920x1080 视频，字体48px）:
```
The labor crisis settled at the negotiating table
is nothing compared to the confrontation that
results in a strike, or better yet, violence
along the picket lines.
```

## 🔧 字体配置

### 使用自定义字体

1. 在插件目录创建 `fonts` 文件夹
2. 将字体文件（.ttf 或 .otf）放入该文件夹
3. 重新加载 ComfyUI
4. 字体会自动出现在 `font_path` 下拉列表中

### 查看可用字体

节点会自动检测以下位置的字体：
- `./fonts/` (插件目录)
- `/usr/share/fonts/` (Linux)
- `/System/Library/Fonts/` (macOS)
- `C:\Windows\Fonts\` (Windows)

## ⚙️ 文本换行算法

### 工作原理

1. **估算字符宽度**: 英文字符约为字体大小的 0.65 倍
2. **计算每行字符数**: `max_chars = max_width / (font_size * 0.65)`
3. **智能分词**: 按空格分词，避免截断单词
4. **动态调整**: 自动适应不同视频分辨率

### 调优建议

- **视频 1920x1080**: 推荐 `font_size=48`, `max_text_width=1536` (默认)
- **视频 1280x720**: 推荐 `font_size=36`, `max_text_width=1024`
- **视频 3840x2160 (4K)**: 推荐 `font_size=96`, `max_text_width=3072`

## 📊 性能优化

- 使用 FFmpeg 原生 `drawtext` 滤镜，性能优异
- 批量处理多个字幕段，避免重复编码
- 支持硬件加速（如果系统支持）

## 🐛 常见问题

### Q: 字幕没有换行？
A: 检查 `max_text_width` 是否设置合理，建议设置为视频宽度的 70-80%

### Q: 字幕显示为乱码？
A: 检查字体是否支持你使用的语言（中文需要中文字体）

### Q: 字幕位置不对？
A: 尝试使用预设位置 `subtitle_position`，或使用 `custom` 并调整 x/y 坐标

### Q: 字幕背景太亮/太暗？
A: 调整 `background_opacity` 参数（0.5-0.9 之间效果较好）

## 🆚 与原节点对比

| 功能 | 原节点 | 新节点 |
|------|--------|--------|
| 文本换行 | ❌ 超出视频宽度 | ✅ 智能换行 |
| 输入方式 | ❌ 手动 JSON 文本框 | ✅ 直接连线 |
| 字体选择 | ❌ 手动输入路径 | ✅ 下拉选择 |
| 背景框 | ❌ 无 | ✅ 半透明背景 |
| 性能 | ❌ PIL 图像处理 | ✅ FFmpeg 原生 |
| 预设位置 | ❌ 无 | ✅ 6 种预设 |

## 📝 更新日志

### v1.0 (2025-01-19)
- ✅ 支持 whisper_alignment 直接连线
- ✅ 智能文本换行功能
- ✅ 字体下拉选择
- ✅ 半透明背景框
- ✅ 多种预设位置
- ✅ 自动转义特殊字符

## 💡 提示

- 长文本建议使用较小的 `font_size` (36-48px)
- 重要字幕可以使用醒目颜色（yellow, cyan）
- 背景视频较亮时，增加 `background_opacity`
- 中文字幕需要使用支持中文的字体

## 📄 许可证

与 ComfyUI 主项目相同
