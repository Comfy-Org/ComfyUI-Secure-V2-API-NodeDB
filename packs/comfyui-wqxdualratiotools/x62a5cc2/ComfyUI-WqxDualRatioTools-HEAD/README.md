# ComfyUI-WqxDualRatioTools
> 作者：wqx805818332ac

**Wqx DualRatioCalc：单比例统一配置，同时输出主采、二采两套分辨率。**

解决二采重绘/视频工作流痛点：只设置一次画面比例，主采样、二次采样保持完全相同宽高比，两套可以使用不同长边尺寸、不同对齐倍数(divisible_by)，避免两边比例不一致导致画面拉伸变形。

## ✨节点特性
- 一处设置比例 `ratio_w / ratio_h`，主采、二采同步生效，支持 `16:9 / 9:16 / 21:9 / 1:1` 任意比例
- 主采、二采独立长边像素控制
- 两套独立对齐倍数：适配 SDXL(64) / Flux(16) / WAN2.2视频模型(16)
- 输出浮点比例，方便调试校验实际画面比例
- 菜单分类：`WqxTools/Resolution`

## 📥安装方式
### 方式1：ComfyUI‑Manager（推荐）
1. 打开 `ComfyUI‑Manager` → `Install via Git URL`
2. 填入仓库地址：
`https://github.com/wqx805818332ac/ComfyUI-WqxDualRatioTools.git`
3. 点击安装，**完全重启 ComfyUI**。

### 方式2：手动 Git Clone
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/wqx805818332ac/ComfyUI-WqxDualRatioTools.git
