import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

/**
 * Video Overlay 节点的视频预览扩展
 * 实现鼠标悬停播放功能（类似 VideoHelperSuite）
 */

console.log("[VideoOverlay] Extension loading...");

app.registerExtension({
    name: "VideoOverlay.Preview",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        console.log("[VideoOverlay] Checking node:", nodeData.name);

        // 只处理 VideoOverlayNode 和 VideoOverlayWithSubtitlesNode
        if (nodeData.name !== "VideoOverlayNode" && nodeData.name !== "VideoOverlayWithSubtitlesNode") {
            return;
        }

        console.log("[VideoOverlay] Registering preview for:", nodeData.name);

        // 在节点创建时添加预览widget
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function() {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

            console.log("[VideoOverlay] Node created, adding preview widget");

            const previewNode = this;

            // 创建预览容器
            const element = document.createElement("div");
            element.style.width = "100%";
            element.style.minHeight = "100px";

            const previewWidget = this.addDOMWidget("videopreview", "preview", element, {
                serialize: false,
                hideOnZoom: false,
            });

            // 实现computeSize方法 - 根据视频宽高比自动调整高度
            previewWidget.computeSize = function(width) {
                if (this.aspectRatio && !element.hidden) {
                    // 根据节点宽度和视频宽高比计算高度
                    // 减去20是为了留出边距，加10是为了info区域
                    let height = (previewNode.size[0] - 20) / this.aspectRatio + 60;
                    if (!(height > 0)) {
                        height = 0;
                    }
                    this.computedHeight = height;
                    return [width, height];
                }
                // 没有加载视频时，widget不占空间
                return [width, -4];
            };

            // 保存引用
            this.videoPreviewWidget = previewWidget;
            this.videoPreviewElement = element;

            return r;
        };

        // 在节点执行完成后更新预览
        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function(message) {
            console.log("[VideoOverlay] onExecuted called:", message);
            console.log("[VideoOverlay] Message structure:", JSON.stringify(message, null, 2));

            if (onExecuted) {
                onExecuted.apply(this, arguments);
            }

            // 处理视频预览 - 检查 videos 或 gifs 键
            const videosArray = message?.videos || message?.gifs;
            if (videosArray && videosArray.length > 0) {
                console.log("[VideoOverlay] Found videos:", videosArray);
                this.updateVideoPreview(videosArray);
            } else {
                console.warn("[VideoOverlay] No videos found in message. Message keys:", Object.keys(message || {}));
            }
        };

        /**
         * 更新视频预览
         */
        nodeType.prototype.updateVideoPreview = function(videos) {
            console.log("[VideoOverlay] Updating video preview");

            if (!this.videoPreviewElement) {
                console.error("[VideoOverlay] No preview element found!");
                return;
            }

            const videoFilename = videos[0];
            const videoUrl = api.apiURL(`/view?filename=${encodeURIComponent(videoFilename)}&type=output&subfolder=&rand=${Math.random()}`);

            // 清除旧内容
            this.videoPreviewElement.innerHTML = "";

            const container = this.videoPreviewElement;

            // 设置容器样式
            container.style.width = "100%";
            container.style.minHeight = "100px";
            container.style.position = "relative";
            container.style.overflow = "hidden";
            container.style.borderRadius = "4px";

            // 创建视频元素
            const videoEl = document.createElement("video");
            videoEl.src = videoUrl;
            videoEl.controls = false;  // 隐藏默认controls，使用自定义进度条
            videoEl.loop = true;
            videoEl.muted = true;  // 默认静音
            videoEl.preload = "metadata";  // 预加载元数据
            videoEl.style.width = "100%";
            videoEl.style.height = "auto";
            videoEl.style.objectFit = "contain";
            videoEl.style.backgroundColor = "#000";
            videoEl.style.display = "block";
            videoEl.style.borderRadius = "4px 4px 0 0";  // 只有顶部圆角

            // 监听视频元数据加载 - 自动调整节点大小
            videoEl.addEventListener("loadedmetadata", () => {
                console.log("[VideoOverlay] Video metadata loaded:", videoEl.videoWidth, "x", videoEl.videoHeight);

                // 计算宽高比
                this.videoPreviewWidget.aspectRatio = videoEl.videoWidth / videoEl.videoHeight;

                // 调整节点大小以适应视频
                this.setSize([
                    Math.max(this.size[0], 350),  // 最小宽度350
                    this.computeSize()[1]
                ]);

                // 标记canvas需要重绘
                if (this.graph) {
                    this.graph.setDirtyCanvas(true, true);
                }
            });

            // 监听视频加载错误
            videoEl.addEventListener("error", () => {
                console.error("[VideoOverlay] Video loading failed");
                // 隐藏预览widget
                this.videoPreviewElement.hidden = true;
                this.setSize([this.size[0], this.computeSize()[1]]);
                if (this.graph) {
                    this.graph.setDirtyCanvas(true, true);
                }
            });

            // 创建自定义进度条（简洁样式）
            const progressContainer = document.createElement("div");
            progressContainer.style.width = "100%";
            progressContainer.style.height = "3px";
            progressContainer.style.backgroundColor = "rgba(255,255,255,0.2)";
            progressContainer.style.cursor = "pointer";
            progressContainer.style.position = "relative";
            progressContainer.style.transition = "height 0.2s ease";

            const progressBar = document.createElement("div");
            progressBar.style.width = "0%";
            progressBar.style.height = "100%";
            progressBar.style.backgroundColor = "#4a9eff";
            progressBar.style.transition = "width 0.1s linear";

            progressContainer.appendChild(progressBar);

            // 鼠标悬停在进度条上时变粗
            progressContainer.addEventListener("mouseenter", () => {
                progressContainer.style.height = "5px";
            });

            progressContainer.addEventListener("mouseleave", () => {
                progressContainer.style.height = "3px";
            });

            // 更新进度条
            videoEl.addEventListener("timeupdate", () => {
                if (videoEl.duration) {
                    const progress = (videoEl.currentTime / videoEl.duration) * 100;
                    progressBar.style.width = progress + "%";
                }
            });

            // 点击进度条跳转
            progressContainer.addEventListener("click", (e) => {
                e.stopPropagation();
                const rect = progressContainer.getBoundingClientRect();
                const pos = (e.clientX - rect.left) / rect.width;
                videoEl.currentTime = pos * videoEl.duration;
            });

            // 鼠标悬停播放功能（参考 VideoHelperSuite）
            videoEl.addEventListener("mouseenter", () => {
                // 取消静音并播放
                videoEl.muted = false;
                videoEl.play().catch(err => {
                    console.warn("Video autoplay failed, retrying with muted:", err);
                    // 如果自动播放失败（浏览器策略），保持静音重试
                    videoEl.muted = true;
                    videoEl.play().catch(e => {
                        console.error("Video play failed:", e);
                    });
                });
            });

            videoEl.addEventListener("mouseleave", () => {
                // 暂停并静音
                videoEl.pause();
                videoEl.muted = true;
            });

            // 点击视频切换播放/暂停
            videoEl.addEventListener("click", (e) => {
                e.stopPropagation();
                if (videoEl.paused) {
                    videoEl.play();
                } else {
                    videoEl.pause();
                }
            });

            // 加载状态提示 - 放在视频下方，不遮挡内容
            const loadingDiv = document.createElement("div");
            loadingDiv.textContent = "⏳ 加载中...";
            loadingDiv.style.fontSize = "12px";
            loadingDiv.style.color = "#888";
            loadingDiv.style.padding = "5px 8px";
            loadingDiv.style.textAlign = "center";
            loadingDiv.style.backgroundColor = "rgba(0,0,0,0.2)";
            loadingDiv.style.display = "none";

            videoEl.addEventListener("loadstart", () => {
                loadingDiv.textContent = "⏳ 加载中...";
                loadingDiv.style.color = "#888";
                loadingDiv.style.backgroundColor = "rgba(0,0,0,0.2)";
                loadingDiv.style.display = "block";
            });

            videoEl.addEventListener("loadeddata", () => {
                loadingDiv.style.display = "none";
            });

            videoEl.addEventListener("error", (e) => {
                console.error("Video loading error:", e);
                loadingDiv.textContent = "❌ 视频加载失败";
                loadingDiv.style.color = "#f88";
                loadingDiv.style.backgroundColor = "rgba(255,0,0,0.2)";
                loadingDiv.style.display = "block";
            });

            // 添加提示信息
            const infoDiv = document.createElement("div");
            infoDiv.style.fontSize = "11px";
            infoDiv.style.color = "#aaa";
            infoDiv.style.padding = "8px";
            infoDiv.style.textAlign = "center";
            infoDiv.style.backgroundColor = "rgba(0,0,0,0.3)";
            infoDiv.style.borderBottomLeftRadius = "4px";
            infoDiv.style.borderBottomRightRadius = "4px";
            infoDiv.innerHTML = `
                <span style="color: #4a9eff;">🎬 ${videoFilename}</span><br>
                <span style="color: #888;">鼠标悬停播放 | 点击暂停/继续</span>
            `;

            // 组装 DOM - 顺序：视频、进度条、加载提示、文件信息
            container.appendChild(videoEl);
            container.appendChild(progressContainer);
            container.appendChild(loadingDiv);
            container.appendChild(infoDiv);

            // 保存视频元素引用
            this.videoElement = videoEl;

            console.log(`[VideoOverlay] Video preview updated: ${videoFilename}`);
        };

        /**
         * 清理资源
         */
        const onRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function() {
            if (this.videoElement) {
                this.videoElement.pause();
                this.videoElement.src = "";
                this.videoElement = null;
            }
            if (onRemoved) {
                onRemoved.apply(this, arguments);
            }
        };

        /**
         * 序列化时保存状态
         */
        const onSerialize = nodeType.prototype.onSerialize;
        nodeType.prototype.onSerialize = function(o) {
            if (onSerialize) {
                onSerialize.apply(this, arguments);
            }
            // 可以在这里保存额外状态
        };
    }
});
