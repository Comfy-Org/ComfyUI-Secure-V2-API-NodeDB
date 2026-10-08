# Mechanically retained pinned video math. See extraction receipt.
import json
import re
import posixpath
from types import SimpleNamespace
import cv2
import numpy as np
import torch
os = SimpleNamespace(path=posixpath)
class VideoAlgorithms:

    def get_concise_display_info(self, metadata_raw):
        """Extracts specific fields for the CONCISE NODE DISPLAY (UI)."""
        info = {'model': 'N/A', 'seed': 'N/A', 'steps': 'N/A', 'cfg': 'N/A', 'sampler': 'N/A', 'scheduler': 'N/A'}
        if not metadata_raw:
            return info
        try:
            if metadata_raw.strip().startswith('Prompt:'):
                metadata_raw = metadata_raw.strip()[7:]
            data = json.loads(metadata_raw)
            if 'nodes' in data and isinstance(data['nodes'], list):
                for node in data['nodes']:
                    nt = node.get('type', '').lower()
                    if 'lora' in nt or 'clip' in nt or 'control' in nt or ('vae' in nt):
                        continue
                    if 'checkpoint' in nt or 'loader' in nt:
                        vals = node.get('widgets_values')
                        if vals and isinstance(vals, list) and (len(vals) > 0):
                            val = str(vals[0]).lower()
                            if '.safetensors' in val or '.ckpt' in val or '.gguf' in val or ('.pt' in val):
                                info['model'] = vals[0]
                                break
            if info['model'] == 'N/A':
                for k, v in data.items():
                    ct = v.get('class_type', '').lower()
                    if 'lora' in ct or 'clip' in ct or 'control' in ct or ('vae' in ct):
                        continue
                    inputs = v.get('inputs', {})
                    if 'ckpt_name' in inputs:
                        info['model'] = inputs['ckpt_name']
                        break
                    if 'unet_name' in inputs:
                        info['model'] = f"{inputs['unet_name']} (UNET)"
                        break
                    if 'gguf_name' in inputs:
                        info['model'] = f"{inputs['gguf_name']} (GGUF)"
                        break
                    if 'model_name' in inputs:
                        info['model'] = inputs['model_name']
                        break
                    if 'checkpoint' in inputs and isinstance(inputs['checkpoint'], str):
                        info['model'] = inputs['checkpoint']
                        break
            if isinstance(data, dict) and 'nodes' not in data:
                for k, v in data.items():
                    if 'Sampler' in v.get('class_type', ''):
                        inputs = v.get('inputs', {})
                        info['seed'] = inputs.get('seed', inputs.get('noise_seed', 'N/A'))
                        info['steps'] = inputs.get('steps', 'N/A')
                        info['cfg'] = inputs.get('cfg', 'N/A')
                        info['sampler'] = inputs.get('sampler_name', 'N/A')
                        info['scheduler'] = inputs.get('scheduler', 'N/A')
                        break
        except:
            pass
        return info

    def extract_full_readable_text(self, metadata_raw, include_emojis=True):
        """Generates the FULL DETAILED text output for the STRING output."""
        if not metadata_raw:
            return 'No metadata found.'
        try:
            if metadata_raw.strip().startswith('Prompt:'):
                metadata_raw = metadata_raw.strip()[7:]
            data = json.loads(metadata_raw)
            lines = []
            emoji_map = {'models': '🧠', 'sampling': '🎯', 'prompts': '📝', 'lora': '🎨'} if include_emojis else {k: '' for k in ['models', 'sampling', 'prompts', 'lora']}
            info = self.get_concise_display_info(metadata_raw)
            lines.append(f"{emoji_map['models']} MODEL: {info['model']}\n")
            if isinstance(data, dict) and 'nodes' not in data:
                for k, v in data.items():
                    if 'Sampler' in v.get('class_type', ''):
                        inputs = v['inputs']
                        lines.append(f"{emoji_map['sampling']} SAMPLING SETTINGS:")
                        lines.append(f" Seed      : {inputs.get('seed', inputs.get('noise_seed', 'N/A'))}")
                        lines.append(f" Steps     : {inputs.get('steps', 'N/A')}")
                        lines.append(f" CFG Scale : {inputs.get('cfg', 'N/A')}")
                        lines.append(f" Sampler   : {inputs.get('sampler_name', 'N/A')}")
                        lines.append(f" Scheduler : {inputs.get('scheduler', 'N/A')}\n")
                        break
            lines.append(f"{emoji_map['prompts']} PROMPTS:")
            pos, neg = ([], [])
            if isinstance(data, dict) and 'nodes' not in data:
                for k, v in data.items():
                    if 'CLIPTextEncode' in v.get('class_type', ''):
                        t = v['inputs'].get('text', '').strip()
                        if 'negative' in v.get('_meta', {}).get('title', '').lower():
                            neg.append(t)
                        else:
                            pos.append(t)
            lines.append(f" Positive: {(', '.join(pos) if pos else '(empty)')}")
            lines.append(f" Negative: {(', '.join(neg) if neg else '(empty)')}\n")
            lines.append(f"{emoji_map['models']} MODELS & COMPONENTS:")
            if isinstance(data, dict) and 'nodes' not in data:
                for k, v in data.items():
                    ct = v.get('class_type', '')
                    inputs = v.get('inputs', {})
                    if 'CheckpointLoader' in ct:
                        lines.append(f" Checkpoint: {inputs.get('ckpt_name')}")
                    if 'LoaderGGUF' in ct:
                        lines.append(f" GGUF: {inputs.get('gguf_name')}")
                    if 'LoraLoader' in ct:
                        lines.append(f" LoRA: {inputs.get('lora_name')} (Str: {inputs.get('strength_model')})")
                    if 'VAELoader' in ct:
                        lines.append(f" VAE: {inputs.get('vae_name')}")
            return '\n'.join(lines)
        except:
            return metadata_raw

    def extract_individual_params(self, metadata_raw):
        pos, neg, seed = ('', '', 0)
        try:
            if metadata_raw and metadata_raw.strip().startswith('{'):
                data = json.loads(metadata_raw)
                if isinstance(data, dict) and 'nodes' not in data:
                    for k, v in data.items():
                        if 'Sampler' in v.get('class_type', ''):
                            seed = int(v['inputs'].get('seed', v['inputs'].get('noise_seed', 0)))
                            break
                    for k, v in data.items():
                        if 'CLIPTextEncode' in v.get('class_type', ''):
                            inputs = v.get('inputs', {})
                            title = v.get('_meta', {}).get('title', '').lower()
                            text = inputs.get('text', '')
                            if 'negative' in title:
                                neg += text + ' '
                            else:
                                pos += text + ' '
        except:
            pass
        return (pos.strip(), neg.strip(), seed)

    def gcd(self, a, b):
        while b:
            a, b = (b, a % b)
        return a

    def find_closest_standard_ratio(self, decimal_ratio):
        standard_ratios = [(1.0, '1:1'), (1.25, '5:4'), (1.33333, '4:3'), (1.5, '3:2'), (1.6, '16:10'), (1.77778, '16:9'), (2.33333, '21:9')]
        closest, min_diff = (None, float('inf'))
        for val, lbl in standard_ratios:
            diff = abs(val - decimal_ratio)
            if diff < min_diff:
                min_diff, closest = (diff, lbl)
        return closest if min_diff <= 0.05 else None

    def load_video_analyze(self, video, force_rate, max_frames, resize_long_edge, emoji_in_readable_text=True):
        video_path = self.decode_path
        cap = self.open_capture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f'Could not open video: {video_path}')
        original_fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frames = []
        step = 1
        if force_rate > 0 and force_rate < original_fps:
            step = max(1, int(original_fps / force_rate))
        effective_fps = original_fps / step if step > 1 else original_fps
        if force_rate > 0:
            effective_fps = force_rate
        count = 0
        output_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if count % step == 0:
                if resize_long_edge > 0:
                    h, w = frame.shape[:2]
                    if max(h, w) > resize_long_edge:
                        scale = resize_long_edge / max(h, w)
                        frame = self.resize_frame(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
                frame = cv2.cvtColor(self.selected_frame(frame), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                frames.append(torch.from_numpy(frame))
                output_count += 1
                if max_frames > 0 and output_count >= max_frames:
                    break
            count += 1
        cap.release()
        if not frames:
            raise RuntimeError('No frames extracted.')
        output_frames = torch.stack(frames)
        mask = torch.ones((output_frames.shape[0], output_frames.shape[1], output_frames.shape[2]), dtype=torch.float32)
        resolution_mp = width * height / 1000000
        try:
            file_size_mb = len(self.source_bytes) / (1024 * 1024)
        except:
            file_size_mb = 0.0
        divisor = self.gcd(width, height)
        ar_dec = width / height
        std_ratio = self.find_closest_standard_ratio(ar_dec)
        ratio_str = f'{width // divisor}:{height // divisor}'
        if std_ratio and std_ratio != ratio_str:
            ratio_str += f' or {std_ratio}'
        else:
            ratio_str += f' or {ar_dec:.2f}:1'
        metadata_raw = self.extract_raw_video_metadata(video_path)
        gen_info = self.get_concise_display_info(metadata_raw)
        ui_lines = []
        ui_lines.append(f'{width}x{height} | {resolution_mp:.2f}MP')
        ui_lines.append(f'Ratio: {ratio_str}')
        ui_lines.append(f'File Size: {file_size_mb:.2f}MB')
        ui_lines.append('')
        ui_lines.append(f"Model: {gen_info['model']}")
        ui_lines.append(f"Seed: {gen_info['seed']} | Steps: {gen_info['steps']} | CFG: {gen_info['cfg']}")
        ui_lines.append(f"Sampler: {gen_info['sampler']} | Scheduler: {gen_info['scheduler']}")
        full_readable_text = f'=== Video Information ===\nFilename: {posixpath.basename(self.input_label)}\n{width}x{height} | {resolution_mp:.2f}MP | {file_size_mb:.2f}MB\nFPS: {int(effective_fps)} | Duration: {(count / original_fps if original_fps else 0):.1f}s\n\n'
        if metadata_raw:
            full_readable_text += self.extract_full_readable_text(metadata_raw, emoji_in_readable_text)
        else:
            full_readable_text += '(No embedded ComfyUI generation metadata detected in file)'
        pos, neg, seed = self.extract_individual_params(metadata_raw)
        return {'ui': {'text': ui_lines}, 'result': (full_readable_text, output_frames, mask, len(frames), int(effective_fps), posixpath.basename(self.input_label), metadata_raw if metadata_raw else '', pos, neg, seed)}
