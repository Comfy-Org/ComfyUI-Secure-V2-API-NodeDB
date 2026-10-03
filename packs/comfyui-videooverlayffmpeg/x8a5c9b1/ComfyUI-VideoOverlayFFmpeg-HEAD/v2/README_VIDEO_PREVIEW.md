# 视频预览功能说明

## 🎬 功能概述

Video Overlay 节点现在支持在 ComfyUI 界面中直接预览合成后的视频，并实现了**鼠标悬停播放**功能（参考 VideoHelperSuite 插件）。

## ✨ 主要特性

### 1. **自动视频预览** 📺
- 节点执行完成后自动显示视频预览
- 无需手动打开输出文件夹
- 直接在节点内查看合成结果

### 2. **鼠标悬停播放** 🖱️
- **鼠标移入**：自动播放并取消静音
- **鼠标移出**：自动暂停并静音
- **点击视频**：手动切换播放/暂停

### 3. **智能加载** ⚡
- 显示加载状态
- 预加载视频元数据
- 错误提示

## 🎯 使用方法

### 基础使用

1. 运行 `VideoOverlayNode` 或 `VideoOverlayWithSubtitlesNode`
2. 节点执行完成后，自动在节点底部显示视频预览
3. 鼠标悬停在视频上即可播放

### 交互方式

| 操作 | 效果 |
|------|------|
| 鼠标移入视频 | 自动播放 + 取消静音 |
| 鼠标移出视频 | 自动暂停 + 静音 |
| 点击视频 | 切换播放/暂停 |
| 使用控制条 | 标准视频控制（进度、音量等） |

## 📋 支持的节点

- ✅ `VideoOverlayNode` (画中画合成)
- ✅ `VideoOverlayWithSubtitlesNode` (画中画+字幕)

## 🔧 技术实现

### 前端扩展 (web/video_preview.js)

```javascript
// 注册扩展
app.registerExtension({
    name: "VideoOverlay.Preview",

    // 在节点执行后自动创建预览
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        // 处理视频预览显示
        nodeType.prototype.displayVideoPreview = function(videos) {
            // 创建视频元素
            // 添加鼠标事件监听
            // 自动调整节点大小
        }
    }
});
```

### 后端返回格式

```python
return {
    "ui": {
        "videos": [output_filename]  # 文件名列表
    },
    "result": (output_path,)  # 完整路径
}
```

## 🎨 界面展示

```
┌─────────────────────────────────────┐
│  VideoOverlayWithSubtitlesNode      │
├─────────────────────────────────────┤
│  [参数输入区域]                      │
│                                     │
├─────────────────────────────────────┤
│  ┌───────────────────────────────┐  │
│  │                               │  │
│  │     [视频预览区域]             │  │
│  │                               │  │
│  │     鼠标悬停即可播放           │  │
│  │                               │  │
│  └───────────────────────────────┘  │
│  🎬 overlay_subtitle_12ab34cd.mp4  │
│  鼠标悬停播放 | 点击暂停/继续        │
└─────────────────────────────────────┘
```

## 📊 与 VideoHelperSuite 对比

| 功能 | VideoHelperSuite | Video Overlay |
|------|------------------|---------------|
| 鼠标悬停播放 | ✅ | ✅ |
| 自动静音控制 | ✅ | ✅ |
| 视频控制条 | ✅ | ✅ |
| 加载状态显示 | ✅ | ✅ |
| 循环播放 | ✅ | ✅ |
| 错误处理 | ✅ | ✅ |
| 节点自适应大小 | ✅ | ✅ |

## 🐛 常见问题

### Q: 视频不自动播放？
A: 某些浏览器有自动播放策略限制。解决方案：
- 鼠标悬停会自动重试播放
- 如果还是失败，会自动切换为静音播放
- 也可以手动点击播放按钮

### Q: 鼠标移开后视频还在播放？
A: 检查是否鼠标仍在视频区域内。视频控制条也算视频区域的一部分。

### Q: 预览视频加载很慢？
A:
- 视频文件较大时需要时间加载
- 可以看到"加载中..."提示
- 等待加载完成后即可正常播放

### Q: 视频显示"加载失败"？
A: 可能原因：
- 视频文件损坏
- 浏览器不支持该视频格式
- 网络问题
- 检查浏览器控制台的详细错误信息

## 🔧 自定义配置

### 修改最大视频高度

编辑 `web/video_preview.js`:

```javascript
videoEl.style.maxHeight = "400px";  // 改为你想要的高度
```

### 禁用自动播放

```javascript
// 注释掉 mouseenter 事件监听
// videoEl.addEventListener("mouseenter", () => { ... });
```

### 修改默认音量

```javascript
videoEl.muted = true;   // true = 静音, false = 有声
videoEl.volume = 0.5;   // 0.0 - 1.0
```

## 📝 文件结构

```
ComfyUI-VideoOverlayFFmpeg/
├── web/
│   └── video_preview.js        # 前端视频预览扩展
├── video_overlay_node.py        # 后端节点定义
├── __init__.py                  # WEB_DIRECTORY 配置
└── README_VIDEO_PREVIEW.md      # 本文档
```

## 🚀 性能优化

1. **预加载策略**: `preload="metadata"` 只加载元数据，不预加载完整视频
2. **按需播放**: 只在鼠标悬停时播放，节省资源
3. **自动暂停**: 鼠标移出立即暂停，释放资源
4. **错误恢复**: 播放失败自动重试

## 💡 提示

- 视频会自动循环播放
- 默认静音，鼠标悬停时取消静音
- 支持所有标准视频格式 (MP4, WebM, MKV 等)
- 预览视频来自 ComfyUI 的 output 目录
- 每次生成新视频时，预览会自动更新

## 📄 许可证

与 ComfyUI 主项目相同
