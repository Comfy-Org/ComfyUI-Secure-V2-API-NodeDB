"""
ComfyUI Video Overlay Node
视频画中画合成节点

安装方法:
1. 将此文件放到 ComfyUI/custom_nodes/video_overlay_node.py
2. pip install ffmpeg-python
3. 确保系统已安装 ffmpeg

功能:
- 将小视频（带mask）叠加到大视频上
- 支持透明度调节
- 支持位置调节
- 自动处理时长差异
- 输出可预览的视频
"""

import os
import ffmpeg
import folder_paths
from pathlib import Path
import uuid
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
# os.path.join(FONT_DIR, font_file)

def get_available_fonts():
    """获取可用的字体列表"""
    fonts = []

    # 1. 检查自定义字体目录
    if os.path.exists(FONT_DIR):
        for font_file in os.listdir(FONT_DIR):
            if font_file.endswith(('.ttf', '.otf', '.TTF', '.OTF')):
                fonts.append(font_file)

    # 2. 添加系统常用字体路径
    system_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
    ]

    for font_path in system_fonts:
        if os.path.exists(font_path) and font_path not in fonts:
            fonts.append(font_path)

    # 如果没有找到任何字体，返回默认路径
    if not fonts:
        fonts.append("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

    return fonts


class VideoOverlayNode:
    """视频画中画合成节点"""

    def apply_audio_speed(self, audio, speed):
        """
        应用音频调速
        atempo滤镜范围是0.5-2.0，超出范围需要链式调用
        """
        if speed == 1.0:
            return audio

        # atempo滤镜的有效范围是0.5-2.0
        # 如果速度超出范围，需要多次应用
        result = audio
        remaining_speed = speed

        while remaining_speed > 2.0:
            result = ffmpeg.filter(result, 'atempo', 2.0)
            remaining_speed /= 2.0

        while remaining_speed < 0.5:
            result = ffmpeg.filter(result, 'atempo', 0.5)
            remaining_speed /= 0.5

        if remaining_speed != 1.0:
            result = ffmpeg.filter(result, 'atempo', remaining_speed)

        return result

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "big_video_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                }),
                "small_video_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                }),
                "mask_video_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                }),
                "opacity": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "display": "slider",
                }),
                "position": (["right_bottom", "right_top", "left_bottom", "left_top", "center"], {
                    "default": "right_bottom"
                }),
                "margin_x": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 500,
                    "step": 1,
                }),
                "margin_y": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 500,
                    "step": 1,
                }),
                "size_ratio": ("FLOAT", {
                    "default": 0.25,
                    "min": 0.1,
                    "max": 1.0,
                    "step": 0.05,
                    "display": "slider",
                }),
                "big_video_audio_volume": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "display": "slider",
                }),
                "small_video_audio_volume": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "display": "slider",
                }),
                "big_video_speed": ("FLOAT", {
                    "default": 1.8,
                    "min": 0.25,
                    "max": 4.0,
                    "step": 0.1,
                    "display": "slider",
                }),
                "small_video_speed": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.25,
                    "max": 4.0,
                    "step": 0.1,
                    "display": "slider",
                }),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    FUNCTION = "overlay_videos"
    OUTPUT_NODE = True
    CATEGORY = "video"
    
    def get_video_info(self, video_path):
        """获取视频的时长和分辨率"""
        try:
            probe = ffmpeg.probe(video_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            
            width = int(video_info['width'])
            height = int(video_info['height'])
            duration = float(probe['format']['duration'])
            
            return width, height, duration
        except Exception as e:
            raise ValueError(f"无法读取视频信息: {video_path}\n错误: {e}")
    
    def get_overlay_position(self, position, big_w, big_h, overlay_w, overlay_h, margin_x, margin_y):
        """根据位置参数计算overlay的x, y坐标"""
        positions = {
            "right_bottom": (f"main_w-overlay_w-{margin_x}", f"main_h-overlay_h-{margin_y}"),
            "right_top": (f"main_w-overlay_w-{margin_x}", str(margin_y)),
            "left_bottom": (str(margin_x), f"main_h-overlay_h-{margin_y}"),
            "left_top": (str(margin_x), str(margin_y)),
            "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
        }
        return positions.get(position, positions["right_bottom"])
    
    def overlay_videos(self, big_video_path, small_video_path, mask_video_path,
                      opacity, position, margin_x, margin_y, size_ratio,
                      big_video_audio_volume, small_video_audio_volume,
                      big_video_speed, small_video_speed):
        """执行视频合成"""
        
        # 检查文件是否存在
        for path in [big_video_path, small_video_path, mask_video_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"文件不存在: {path}")
        
        # 获取视频信息
        print(f"[VideoOverlay] 正在分析视频信息...")
        big_w, big_h, big_dur = self.get_video_info(big_video_path)
        small_w, small_h, small_dur = self.get_video_info(small_video_path)
        
        print(f"[VideoOverlay] 大视频: {big_w}x{big_h}, {big_dur:.2f}秒")
        print(f"[VideoOverlay] 小视频: {small_w}x{small_h}, {small_dur:.2f}秒")
        
        # 计算小视频目标尺寸
        target_height = int(big_h * size_ratio)
        target_width = int(target_height * small_w / small_h)
        
        print(f"[VideoOverlay] 小视频目标尺寸: {target_width}x{target_height}")
        print(f"[VideoOverlay] 透明度: {opacity}, 位置: {position}")
        print(f"[VideoOverlay] 音频混合 - 大视频: {big_video_audio_volume}, 小视频: {small_video_audio_volume}")
        print(f"[VideoOverlay] 视频速度 - 大视频: {big_video_speed}x, 小视频: {small_video_speed}x")

        # 计算调速后的实际时长
        big_dur_adjusted = big_dur / big_video_speed
        small_dur_adjusted = small_dur / small_video_speed

        print(f"[VideoOverlay] 调速后时长 - 大视频: {big_dur_adjusted:.2f}秒, 小视频: {small_dur_adjusted:.2f}秒")

        # 计算overlay位置
        overlay_x, overlay_y = self.get_overlay_position(
            position, big_w, big_h, target_width, target_height, margin_x, margin_y
        )

        # 生成输出文件路径
        output_dir = folder_paths.get_output_directory()
        unique_id = str(uuid.uuid4())[:8]
        output_filename = f"overlay_{unique_id}.mp4"
        output_path = os.path.join(output_dir, output_filename)

        # 加载输入视频
        big_input = ffmpeg.input(big_video_path)
        small_input = ffmpeg.input(small_video_path)
        mask_input = ffmpeg.input(mask_video_path)

        max_dur = max(big_dur_adjusted, small_dur_adjusted)
        
        try:
            if big_dur_adjusted > small_dur_adjusted:
                print(f"[VideoOverlay] 大视频更长，冻结小视频最后一帧")
                pad_dur = big_dur_adjusted - small_dur_adjusted

                # 应用调速到大视频
                big_video = big_input.video
                if big_video_speed != 1.0:
                    big_video = ffmpeg.filter(big_video, 'setpts', f'{1.0/big_video_speed}*PTS')

                # 应用调速到小视频
                small_video = small_input.video
                if small_video_speed != 1.0:
                    small_video = ffmpeg.filter(small_video, 'setpts', f'{1.0/small_video_speed}*PTS')

                # 延长小视频
                small_padded = ffmpeg.filter(
                    small_video,
                    'tpad',
                    stop_mode='clone',
                    stop_duration=pad_dur
                )

                # 应用调速到mask（与小视频同步）
                mask_video = mask_input.video
                if small_video_speed != 1.0:
                    mask_video = ffmpeg.filter(mask_video, 'setpts', f'{1.0/small_video_speed}*PTS')

                # 延长mask
                mask_padded = ffmpeg.filter(
                    mask_video,
                    'tpad',
                    stop_mode='clone',
                    stop_duration=pad_dur
                )
                mask_gray = ffmpeg.filter(mask_padded, 'format', 'gray')
                
                # 缩放
                small_scaled = ffmpeg.filter(
                    small_padded,
                    'scale',
                    target_width,
                    target_height,
                    force_original_aspect_ratio='decrease'
                )
                mask_scaled = ffmpeg.filter(
                    mask_gray,
                    'scale',
                    target_width,
                    target_height,
                    force_original_aspect_ratio='decrease'
                )
                
                # 应用透明度到mask
                if opacity < 1.0:
                    mask_scaled = ffmpeg.filter(
                        mask_scaled,
                        'colorlevels',
                        romax=opacity
                    )
                
                # 合并alpha通道
                small_masked = ffmpeg.filter(
                    [small_scaled, mask_scaled],
                    'alphamerge'
                )

                # overlay
                video_out = ffmpeg.overlay(
                    big_video,
                    small_masked,
                    x=overlay_x,
                    y=overlay_y,
                    format='auto'
                )
                
                # 音频处理：混合两个音频
                # 大视频音频调速
                big_audio = big_input.audio
                if big_video_speed != 1.0:
                    big_audio = self.apply_audio_speed(big_audio, big_video_speed)
                big_audio = ffmpeg.filter(big_audio, 'volume', big_video_audio_volume)

                # 小视频音频调速后需要延长（冻结静音）
                small_audio = small_input.audio
                if small_video_speed != 1.0:
                    small_audio = self.apply_audio_speed(small_audio, small_video_speed)
                small_audio = ffmpeg.filter(small_audio, 'volume', small_video_audio_volume)
                small_audio_padded = ffmpeg.filter(
                    small_audio,
                    'apad',
                    pad_dur=pad_dur
                )
                
                # 混合音频
                if big_video_audio_volume > 0 and small_video_audio_volume > 0:
                    audio_out = ffmpeg.filter([big_audio, small_audio_padded], 'amix', inputs=2, duration='longest')
                elif big_video_audio_volume > 0:
                    audio_out = big_audio
                elif small_video_audio_volume > 0:
                    audio_out = small_audio_padded
                else:
                    # 两个音量都是0，使用静音
                    audio_out = ffmpeg.filter(big_audio, 'volume', 0)
                
            else:
                print(f"[VideoOverlay] 小视频更长，循环大视频")

                # 应用调速到大视频
                big_video = big_input.video
                if big_video_speed != 1.0:
                    big_video = ffmpeg.filter(big_video, 'setpts', f'{1.0/big_video_speed}*PTS')

                # 循环大视频
                big_loop = ffmpeg.filter(
                    big_video,
                    'loop',
                    loop=-1,
                    size=32767,
                    start=0
                )

                # 应用调速到小视频
                small_video = small_input.video
                if small_video_speed != 1.0:
                    small_video = ffmpeg.filter(small_video, 'setpts', f'{1.0/small_video_speed}*PTS')

                # 应用调速到mask（与小视频同步）
                mask_video = mask_input.video
                if small_video_speed != 1.0:
                    mask_video = ffmpeg.filter(mask_video, 'setpts', f'{1.0/small_video_speed}*PTS')

                # 处理mask
                mask_gray = ffmpeg.filter(mask_video, 'format', 'gray')

                # 缩放
                small_scaled = ffmpeg.filter(
                    small_video,
                    'scale',
                    target_width,
                    target_height,
                    force_original_aspect_ratio='decrease'
                )
                mask_scaled = ffmpeg.filter(
                    mask_gray,
                    'scale',
                    target_width,
                    target_height,
                    force_original_aspect_ratio='decrease'
                )
                
                # 应用透明度到mask
                if opacity < 1.0:
                    mask_scaled = ffmpeg.filter(
                        mask_scaled,
                        'colorlevels',
                        romax=opacity
                    )
                
                # 合并alpha通道
                small_masked = ffmpeg.filter(
                    [small_scaled, mask_scaled],
                    'alphamerge'
                )
                
                # overlay
                video_out = ffmpeg.overlay(
                    big_loop,
                    small_masked,
                    x=overlay_x,
                    y=overlay_y,
                    format='auto'
                )
                
                # 音频处理：混合两个音频
                # 大视频音频调速后需要循环
                big_audio = big_input.audio
                if big_video_speed != 1.0:
                    big_audio = self.apply_audio_speed(big_audio, big_video_speed)
                big_audio_loop = ffmpeg.filter(
                    big_audio,
                    'aloop',
                    loop=-1,
                    size=2e9  # 足够大的采样数
                )
                big_audio = ffmpeg.filter(big_audio_loop, 'volume', big_video_audio_volume)

                # 小视频音频调速
                small_audio = small_input.audio
                if small_video_speed != 1.0:
                    small_audio = self.apply_audio_speed(small_audio, small_video_speed)
                small_audio = ffmpeg.filter(small_audio, 'volume', small_video_audio_volume)
                
                # 混合音频
                if big_video_audio_volume > 0 and small_video_audio_volume > 0:
                    audio_out = ffmpeg.filter([big_audio, small_audio], 'amix', inputs=2, duration='longest')
                elif big_video_audio_volume > 0:
                    audio_out = big_audio
                elif small_video_audio_volume > 0:
                    audio_out = small_audio
                else:
                    # 两个音量都是0，使用静音
                    audio_out = ffmpeg.filter(small_audio, 'volume', 0)
            
            # 输出
            print(f"[VideoOverlay] 开始合成视频...")
            output_stream = ffmpeg.output(
                video_out,
                audio_out,
                output_path,
                t=max_dur,
                vcodec='libx264',
                preset='medium',
                crf=23,
                acodec='aac',
                **{'movflags': '+faststart'}  # 启用流式播放
            )
            
            # 执行
            ffmpeg.run(output_stream, overwrite_output=True, capture_stderr=True, quiet=True)
            
            print(f"[VideoOverlay] ✓ 合成完成: {output_filename}")

            # 获取视频帧率信息
            try:
                probe = ffmpeg.probe(output_path)
                video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
                fps_str = video_info.get('r_frame_rate', '24/1')
                num, denom = map(int, fps_str.split('/'))
                frame_rate = num / denom if denom != 0 else 24.0
            except:
                frame_rate = 24.0

            # 返回与 VideoCombine 一致的格式
            return {
                "ui": {
                    "gifs": [{
                        "type": "output",
                        "format": "video/h264-mp4",
                        "filename": output_filename,
                        "fullpath": output_path,
                        "subfolder": "",
                        "frame_rate": frame_rate
                    }]
                },
                "result": (output_path,)
            }
            
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            print(f"[VideoOverlay] ✗ FFmpeg错误:\n{error_msg}")
            raise RuntimeError(f"视频合成失败: {error_msg}")
        except Exception as e:
            print(f"[VideoOverlay] ✗ 处理失败: {e}")
            raise


class VideoOverlayWithSubtitlesNode:
    """视频画中画合成节点（带字幕）"""

    def apply_audio_speed(self, audio, speed):
        """
        应用音频调速
        atempo滤镜范围是0.5-2.0，超出范围需要链式调用
        """
        if speed == 1.0:
            return audio

        # atempo滤镜的有效范围是0.5-2.0
        # 如果速度超出范围，需要多次应用
        result = audio
        remaining_speed = speed

        while remaining_speed > 2.0:
            result = ffmpeg.filter(result, 'atempo', 2.0)
            remaining_speed /= 2.0

        while remaining_speed < 0.5:
            result = ffmpeg.filter(result, 'atempo', 0.5)
            remaining_speed /= 0.5

        if remaining_speed != 1.0:
            result = ffmpeg.filter(result, 'atempo', remaining_speed)

        return result

    @classmethod
    def INPUT_TYPES(cls):
        # 获取可用字体列表
        available_fonts = get_available_fonts()
        default_font = available_fonts[0] if available_fonts else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

        return {
            "required": {
                "big_video_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                }),
                "small_video_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                }),
                "mask_video_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                }),
                "opacity": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "display": "slider",
                }),
                "position": (["right_bottom", "right_top", "left_bottom", "left_top", "center"], {
                    "default": "right_bottom"
                }),
                "margin_x": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 500,
                    "step": 1,
                }),
                "margin_y": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 500,
                    "step": 1,
                }),
                "size_ratio": ("FLOAT", {
                    "default": 0.25,
                    "min": 0.1,
                    "max": 1.0,
                    "step": 0.05,
                    "display": "slider",
                }),
                "big_video_audio_volume": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "display": "slider",
                }),
                "small_video_audio_volume": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "display": "slider",
                }),
                "video_fps": ("FLOAT", {
                    "default": 24.0,
                    "min": 1.0,
                    "max": 120.0,
                    "step": 1.0,
                    "display": "number"
                }),
                "big_video_speed": ("FLOAT", {
                    "default": 1.8,
                    "min": 0.25,
                    "max": 4.0,
                    "step": 0.1,
                    "display": "slider",
                }),
                "small_video_speed": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.25,
                    "max": 4.0,
                    "step": 0.1,
                    "display": "slider",
                }),
            },
            "optional": {
                "alignment": ("whisper_alignment",),
                "font_path": (available_fonts, {
                    "default": default_font,
                }),
                "font_size": ("INT", {
                    "default": 48,
                    "min": 12,
                    "max": 200,
                    "step": 1,
                    "display": "number"
                }),
                "font_color": ("STRING", {
                    "default": "white",
                }),
                "x_position": ("INT", {
                    "default": 0,
                    "min": -1000,
                    "max": 3000,
                    "step": 10,
                    "display": "number"
                }),
                "y_position": ("INT", {
                    "default": 0,
                    "min": -1000,
                    "max": 3000,
                    "step": 10,
                    "display": "number"
                }),
                "subtitle_position": (["bottom_center", "top_center", "bottom_left", "bottom_right", "center", "custom"], {
                    "default": "bottom_center"
                }),
                "max_subtitle_width": ("INT", {
                    "default": 0,  # 0表示自动计算为视频宽度的80%
                    "min": 0,
                    "max": 4000,
                    "step": 10,
                    "display": "number"
                }),
                "subtitle_bg_opacity": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "display": "slider",
                }),
                "subtitle_bg_color": ("STRING", {
                    "default": "black",
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("video_path",)
    FUNCTION = "overlay_videos_with_subtitles"
    OUTPUT_NODE = True
    CATEGORY = "video"

    def get_video_info(self, video_path):
        """获取视频的时长和分辨率"""
        try:
            probe = ffmpeg.probe(video_path)
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')

            width = int(video_info['width'])
            height = int(video_info['height'])
            duration = float(probe['format']['duration'])

            # 尝试获取帧率
            fps_str = video_info.get('r_frame_rate', '24/1')
            num, denom = map(int, fps_str.split('/'))
            fps = num / denom if denom != 0 else 24.0

            return width, height, duration, fps
        except Exception as e:
            raise ValueError(f"无法读取视频信息: {video_path}\n错误: {e}")

    def get_overlay_position(self, position, big_w, big_h, overlay_w, overlay_h, margin_x, margin_y):
        """根据位置参数计算overlay的x, y坐标"""
        positions = {
            "right_bottom": (f"main_w-overlay_w-{margin_x}", f"main_h-overlay_h-{margin_y}"),
            "right_top": (f"main_w-overlay_w-{margin_x}", str(margin_y)),
            "left_bottom": (str(margin_x), f"main_h-overlay_h-{margin_y}"),
            "left_top": (str(margin_x), str(margin_y)),
            "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
        }
        return positions.get(position, positions["right_bottom"])

    def get_subtitle_position(self, position, x_custom, y_custom):
        """根据字幕位置参数计算x, y表达式"""
        positions = {
            "bottom_center": ("(w-text_w)/2", "h-th-50"),
            "top_center": ("(w-text_w)/2", "50"),
            "bottom_left": ("50", "h-th-50"),
            "bottom_right": ("w-text_w-50", "h-th-50"),
            "center": ("(w-text_w)/2", "(h-th)/2"),
            "custom": (str(x_custom), str(y_custom)),
        }
        return positions.get(position, positions["bottom_center"])

    def parse_alignment(self, alignment_input):
        """解析alignment为列表

        支持两种输入：
        1. whisper_alignment 类型（列表）
        2. JSON 字符串
        """
        # 如果是None或空，返回空列表
        if alignment_input is None:
            return []

        # 如果已经是列表，直接返回
        if isinstance(alignment_input, list):
            return alignment_input

        # 如果是字符串，尝试解析JSON
        if isinstance(alignment_input, str):
            if not alignment_input or alignment_input.strip() == "[]":
                return []
            try:
                import json
                alignment = json.loads(alignment_input)
                return alignment if isinstance(alignment, list) else []
            except:
                print("[VideoOverlay] 警告: 无法解析alignment，将不添加字幕")
                return []

        # 其他情况返回空列表
        return []

    def escape_ffmpeg_text(self, text):
        """转义FFmpeg drawtext滤镜中的特殊字符

        注意：换行符 \n 不需要转义，FFmpeg 会正确处理
        """
        # 先保存所有换行符
        lines = text.split('\n')

        # 对每一行进行转义
        escaped_lines = []
        for line in lines:
            # FFmpeg drawtext需要转义的字符（不包括换行符）
            replacements = {
                '\\': '\\\\',
                "'": "\\'",
                ':': '\\:',
                '%': '\\%',
            }
            for old, new in replacements.items():
                line = line.replace(old, new)
            escaped_lines.append(line)

        # 重新用换行符连接
        return '\n'.join(escaped_lines)

    def wrap_text(self, text, max_width, font_size):
        """
        智能文本换行算法
        根据字符数估算每行最大字符数，按单词边界分行
        """
        if max_width <= 0:
            return text

        # 粗略估算：英文字符平均宽度约为字体大小的0.5-0.6倍
        # 为了保险起见，使用0.65（稍微保守一点）
        # avg_char_width = font_size * 0.65
        avg_char_width = font_size * 0.65 *0.7             # 我自己乘以了0.7
        max_chars_per_line = int(max_width / avg_char_width)

        # 如果字符数限制太小，至少保证10个字符
        if max_chars_per_line < 10:
            max_chars_per_line = 10

        # 如果文本很短，不需要换行
        if len(text) <= max_chars_per_line:
            return text

        # 按空格分词（对英文有效）
        words = text.split(' ')
        lines = []
        current_line = []

        for word in words:
            # 测试加上这个词后的行长度
            test_line = ' '.join(current_line + [word])

            # 如果超过最大长度
            if len(test_line) > max_chars_per_line:
                if current_line:  # 如果当前行有内容，先保存当前行
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:  # 单个词太长，强制分行
                    lines.append(word)
            else:
                current_line.append(word)

        # 添加最后一行
        if current_line:
            lines.append(' '.join(current_line))

        # 用换行符连接
        return '\n'.join(lines)

    def overlay_videos_with_subtitles(self, big_video_path, small_video_path, mask_video_path,
                                     opacity, position, margin_x, margin_y, size_ratio,
                                     big_video_audio_volume, small_video_audio_volume,
                                     big_video_speed, small_video_speed,
                                     video_fps,
                                     alignment=None,
                                     font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                     font_size=48,
                                     font_color="white",
                                     x_position=0,
                                     y_position=0,
                                     subtitle_position="bottom_center",
                                     max_subtitle_width=0,
                                     subtitle_bg_opacity=0.7,
                                     subtitle_bg_color="black"):
        """执行视频合成和字幕添加"""

        # 检查文件是否存在
        for path in [big_video_path, small_video_path, mask_video_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"文件不存在: {path}")
        # 如果font是相对路径
        if not os.path.isabs(font_path):
            font_path=os.path.join(FONT_DIR, font_path)
            if not os.path.exists(font_path):
                raise FileNotFoundError(f"字体文件不存在: {font_path}")

        # 获取视频信息
        print(f"[VideoOverlay] 正在分析视频信息...")
        big_w, big_h, big_dur, big_fps = self.get_video_info(big_video_path)
        small_w, small_h, small_dur, small_fps = self.get_video_info(small_video_path)

        print(f"[VideoOverlay] 大视频: {big_w}x{big_h}, {big_dur:.2f}秒, {big_fps:.2f}fps")
        print(f"[VideoOverlay] 小视频: {small_w}x{small_h}, {small_dur:.2f}秒, {small_fps:.2f}fps")

        # 计算小视频目标尺寸
        target_height = int(big_h * size_ratio)
        target_width = int(target_height * small_w / small_h)

        print(f"[VideoOverlay] 小视频目标尺寸: {target_width}x{target_height}")
        print(f"[VideoOverlay] 透明度: {opacity}, 位置: {position}")
        print(f"[VideoOverlay] 音频混合 - 大视频: {big_video_audio_volume}, 小视频: {small_video_audio_volume}")
        print(f"[VideoOverlay] 视频速度 - 大视频: {big_video_speed}x, 小视频: {small_video_speed}x")

        # 计算调速后的实际时长
        big_dur_adjusted = big_dur / big_video_speed
        small_dur_adjusted = small_dur / small_video_speed

        print(f"[VideoOverlay] 调速后时长 - 大视频: {big_dur_adjusted:.2f}秒, 小视频: {small_dur_adjusted:.2f}秒")

        # 解析字幕
        alignment_list = self.parse_alignment(alignment)
        if alignment_list:
            print(f"[VideoOverlay] 找到 {len(alignment_list)} 条字幕")

        # 计算overlay位置
        overlay_x, overlay_y = self.get_overlay_position(
            position, big_w, big_h, target_width, target_height, margin_x, margin_y
        )

        # 生成输出文件路径
        output_dir = folder_paths.get_output_directory()
        unique_id = str(uuid.uuid4())[:8]
        output_filename = f"overlay_subtitle_{unique_id}.mp4"
        output_path = os.path.join(output_dir, output_filename)

        # 加载输入视频
        big_input = ffmpeg.input(big_video_path)
        small_input = ffmpeg.input(small_video_path)
        mask_input = ffmpeg.input(mask_video_path)

        max_dur = max(big_dur_adjusted, small_dur_adjusted)

        try:
            if big_dur_adjusted > small_dur_adjusted:
                print(f"[VideoOverlay] 大视频更长，冻结小视频最后一帧")
                pad_dur = big_dur_adjusted - small_dur_adjusted

                # 应用调速到大视频
                big_video = big_input.video
                if big_video_speed != 1.0:
                    big_video = ffmpeg.filter(big_video, 'setpts', f'{1.0/big_video_speed}*PTS')

                # 应用调速到小视频
                small_video = small_input.video
                if small_video_speed != 1.0:
                    small_video = ffmpeg.filter(small_video, 'setpts', f'{1.0/small_video_speed}*PTS')

                # 应用调速到mask（与小视频同步）
                mask_video = mask_input.video
                if small_video_speed != 1.0:
                    mask_video = ffmpeg.filter(mask_video, 'setpts', f'{1.0/small_video_speed}*PTS')

                # 延长小视频
                small_padded = ffmpeg.filter(
                    small_video,
                    'tpad',
                    stop_mode='clone',
                    stop_duration=pad_dur
                )

                # 延长mask
                mask_padded = ffmpeg.filter(
                    mask_video,
                    'tpad',
                    stop_mode='clone',
                    stop_duration=pad_dur
                )
                mask_gray = ffmpeg.filter(mask_padded, 'format', 'gray')

                # 缩放
                small_scaled = ffmpeg.filter(
                    small_padded,
                    'scale',
                    target_width,
                    target_height,
                    force_original_aspect_ratio='decrease'
                )
                mask_scaled = ffmpeg.filter(
                    mask_gray,
                    'scale',
                    target_width,
                    target_height,
                    force_original_aspect_ratio='decrease'
                )

                # 应用透明度到mask
                if opacity < 1.0:
                    mask_scaled = ffmpeg.filter(
                        mask_scaled,
                        'colorlevels',
                        romax=opacity
                    )

                # 合并alpha通道
                small_masked = ffmpeg.filter(
                    [small_scaled, mask_scaled],
                    'alphamerge'
                )

                # overlay
                video_out = ffmpeg.overlay(
                    big_video,
                    small_masked,
                    x=overlay_x,
                    y=overlay_y,
                    format='auto'
                )

                # 音频处理：混合两个音频
                # 大视频音频调速
                big_audio = big_input.audio
                if big_video_speed != 1.0:
                    big_audio = self.apply_audio_speed(big_audio, big_video_speed)
                big_audio = ffmpeg.filter(big_audio, 'volume', big_video_audio_volume)

                # 小视频音频调速后需要延长（冻结静音）
                small_audio = small_input.audio
                if small_video_speed != 1.0:
                    small_audio = self.apply_audio_speed(small_audio, small_video_speed)
                small_audio = ffmpeg.filter(small_audio, 'volume', small_video_audio_volume)
                small_audio_padded = ffmpeg.filter(
                    small_audio,
                    'apad',
                    pad_dur=pad_dur
                )

                if big_video_audio_volume > 0 and small_video_audio_volume > 0:
                    audio_out = ffmpeg.filter([big_audio, small_audio_padded], 'amix', inputs=2, duration='longest')
                elif big_video_audio_volume > 0:
                    audio_out = big_audio
                elif small_video_audio_volume > 0:
                    audio_out = small_audio_padded
                else:
                    audio_out = ffmpeg.filter(big_audio, 'volume', 0)

            else:
                print(f"[VideoOverlay] 小视频更长，循环大视频")

                # 应用调速到大视频
                big_video = big_input.video
                if big_video_speed != 1.0:
                    big_video = ffmpeg.filter(big_video, 'setpts', f'{1.0/big_video_speed}*PTS')

                # 循环大视频
                big_loop = ffmpeg.filter(
                    big_video,
                    'loop',
                    loop=-1,
                    size=32767,
                    start=0
                )

                # 应用调速到小视频
                small_video = small_input.video
                if small_video_speed != 1.0:
                    small_video = ffmpeg.filter(small_video, 'setpts', f'{1.0/small_video_speed}*PTS')

                # 应用调速到mask（与小视频同步）
                mask_video = mask_input.video
                if small_video_speed != 1.0:
                    mask_video = ffmpeg.filter(mask_video, 'setpts', f'{1.0/small_video_speed}*PTS')

                # 处理mask
                mask_gray = ffmpeg.filter(mask_video, 'format', 'gray')

                # 缩放
                small_scaled = ffmpeg.filter(
                    small_video,
                    'scale',
                    target_width,
                    target_height,
                    force_original_aspect_ratio='decrease'
                )
                mask_scaled = ffmpeg.filter(
                    mask_gray,
                    'scale',
                    target_width,
                    target_height,
                    force_original_aspect_ratio='decrease'
                )

                # 应用透明度到mask
                if opacity < 1.0:
                    mask_scaled = ffmpeg.filter(
                        mask_scaled,
                        'colorlevels',
                        romax=opacity
                    )

                # 合并alpha通道
                small_masked = ffmpeg.filter(
                    [small_scaled, mask_scaled],
                    'alphamerge'
                )

                # overlay
                video_out = ffmpeg.overlay(
                    big_loop,
                    small_masked,
                    x=overlay_x,
                    y=overlay_y,
                    format='auto'
                )

                # 音频处理：混合两个音频
                # 大视频音频调速后需要循环
                big_audio = big_input.audio
                if big_video_speed != 1.0:
                    big_audio = self.apply_audio_speed(big_audio, big_video_speed)
                big_audio_loop = ffmpeg.filter(
                    big_audio,
                    'aloop',
                    loop=-1,
                    size=2e9  # 足够大的采样数
                )
                big_audio = ffmpeg.filter(big_audio_loop, 'volume', big_video_audio_volume)

                # 小视频音频调速
                small_audio = small_input.audio
                if small_video_speed != 1.0:
                    small_audio = self.apply_audio_speed(small_audio, small_video_speed)
                small_audio = ffmpeg.filter(small_audio, 'volume', small_video_audio_volume)

                if big_video_audio_volume > 0 and small_video_audio_volume > 0:
                    audio_out = ffmpeg.filter([big_audio, small_audio], 'amix', inputs=2, duration='longest')
                elif big_video_audio_volume > 0:
                    audio_out = big_audio
                elif small_video_audio_volume > 0:
                    audio_out = small_audio
                else:
                    audio_out = ffmpeg.filter(small_audio, 'volume', 0)

            # 添加字幕
            if alignment_list:
                print(f"[VideoOverlay] 添加字幕到视频...")

                # 计算文本最大宽度
                text_width = max_subtitle_width if max_subtitle_width > 0 else int(big_w * 0.8)

                # 获取字幕位置
                sub_x, sub_y = self.get_subtitle_position(subtitle_position, x_position, y_position)

                # 为每个字幕段创建drawtext滤镜
                for idx, segment in enumerate(alignment_list):
                    # 先进行文本换行处理
                    wrapped_text = self.wrap_text(segment["value"], text_width, font_size)
                    # 再进行转义
                    text = self.escape_ffmpeg_text(wrapped_text)
                    start_time = segment["start"]
                    end_time = segment["end"]

                    # 构建drawtext参数
                    drawtext_params = {
                        'fontfile': font_path,
                        'text': text,
                        'fontsize': font_size,
                        'fontcolor': font_color,
                        'x': sub_x,
                        'y': sub_y,
                        'box': 1,
                        'boxcolor': f"{subtitle_bg_color}@{subtitle_bg_opacity}",
                        'boxborderw': 10,
                        'line_spacing': 5,
                        'enable': f"between(t,{start_time},{end_time})"
                    }

                    video_out = ffmpeg.filter(video_out, 'drawtext', **drawtext_params)

                    if (idx + 1) % 10 == 0:
                        print(f"[VideoOverlay] 已处理 {idx + 1}/{len(alignment_list)} 条字幕")

            # 输出
            print(f"[VideoOverlay] 开始合成视频...")
            output_stream = ffmpeg.output(
                video_out,
                audio_out,
                output_path,
                t=max_dur,
                vcodec='libx264',
                preset='medium',
                crf=23,
                acodec='aac',
                **{'movflags': '+faststart'}
            )

            # 执行
            ffmpeg.run(output_stream, overwrite_output=True, capture_stderr=True, quiet=True)

            print(f"[VideoOverlay] ✓ 合成完成: {output_filename}")

            # 获取视频帧率信息
            try:
                probe = ffmpeg.probe(output_path)
                video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
                fps_str = video_info.get('r_frame_rate', '24/1')
                num, denom = map(int, fps_str.split('/'))
                frame_rate = num / denom if denom != 0 else 24.0
            except:
                frame_rate = 24.0

            # 返回与 VideoCombine 一致的格式
            return {
                "ui": {
                    "gifs": [{
                        "type": "output",
                        "format": "video/h264-mp4",
                        "filename": output_filename,
                        "fullpath": output_path,
                        "subfolder": "",
                        "frame_rate": frame_rate
                    }]
                },
                "result": (output_path,)
            }

        except ffmpeg.Error as e:
            error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            print(f"[VideoOverlay] ✗ FFmpeg错误:\n{error_msg}")
            raise RuntimeError(f"视频合成失败: {error_msg}")
        except Exception as e:
            print(f"[VideoOverlay] ✗ 处理失败: {e}")
            raise


class Alignment2StringNode:
    """将 whisper_alignment 转换为字符串"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "alignment": ("whisper_alignment",),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("alignment_string",)
    FUNCTION = "alignment_to_string"
    CATEGORY = "whisper"

    def alignment_to_string(self, alignment):
        """将 alignment 转换为 JSON 字符串"""
        import json

        if alignment is None:
            return ("[]",)

        if isinstance(alignment, list):
            return (json.dumps(alignment, ensure_ascii=False, indent=2),)

        # 如果已经是字符串，直接返回
        if isinstance(alignment, str):
            return (alignment,)

        return ("[]",)


class String2AlignmentNode:
    """将字符串转换为 whisper_alignment"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "alignment_string": ("STRING", {
                    "default": "[]",
                    "multiline": True,
                }),
            }
        }

    RETURN_TYPES = ("whisper_alignment",)
    RETURN_NAMES = ("alignment",)
    FUNCTION = "string_to_alignment"
    CATEGORY = "whisper"

    def string_to_alignment(self, alignment_string):
        """将 JSON 字符串转换为 alignment"""
        import json

        if not alignment_string or alignment_string.strip() == "":
            return ([],)

        try:
            alignment = json.loads(alignment_string)
            if isinstance(alignment, list):
                return (alignment,)
            else:
                print("[String2Alignment] 警告: 解析的结果不是列表，返回空列表")
                return ([],)
        except json.JSONDecodeError as e:
            print(f"[String2Alignment] JSON 解析错误: {e}")
            return ([],)
        except Exception as e:
            print(f"[String2Alignment] 转换失败: {e}")
            return ([],)


# ComfyUI节点注册
NODE_CLASS_MAPPINGS = {
    "VideoOverlayNode": VideoOverlayNode,
    "VideoOverlayWithSubtitlesNode": VideoOverlayWithSubtitlesNode,
    "Alignment2StringNode": Alignment2StringNode,
    "String2AlignmentNode": String2AlignmentNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoOverlayNode": "Video Overlay (画中画合成)",
    "VideoOverlayWithSubtitlesNode": "Video Overlay with Subtitles (画中画+字幕)",
    "Alignment2StringNode": "Alignment to String (对齐数据转字符串)",
    "String2AlignmentNode": "String to Alignment (字符串转对齐数据)"
}