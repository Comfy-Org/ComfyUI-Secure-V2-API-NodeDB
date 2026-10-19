"""Source-extracted node computations; host operations use the public SDK."""
from __future__ import annotations
import torch
import numpy as np
import random
from PIL import Image, ImageDraw, ImageFont
from comfy_api.latest import sdk
from ._ops import *

class ttNxyPlot:

    def __init__(self, xyPlotData, save_prefix, image_output, prompt, extra_pnginfo, my_unique_id):
        self.x_node_type, self.x_type = ttNsampler.safe_split(xyPlotData.get('x_axis'), ': ')
        self.y_node_type, self.y_type = ttNsampler.safe_split(xyPlotData.get('y_axis'), ': ')
        self.x_values = xyPlotData.get('x_vals') if self.x_type != 'None' else []
        self.y_values = xyPlotData.get('y_vals') if self.y_type != 'None' else []
        self.grid_spacing = xyPlotData.get('grid_spacing')
        self.latent_id = xyPlotData.get('latent_id')
        self.output_individuals = xyPlotData.get('output_individuals')
        self.x_label, self.y_label = ([], [])
        self.max_width, self.max_height = (0, 0)
        self.latents_plot = []
        self.image_list = []
        self.num_cols = len(self.x_values) if len(self.x_values) > 0 else 1
        self.num_rows = len(self.y_values) if len(self.y_values) > 0 else 1
        self.total = self.num_cols * self.num_rows
        self.num = 0
        self.save_prefix = save_prefix
        self.image_output = image_output
        self.prompt = prompt
        self.extra_pnginfo = extra_pnginfo
        self.my_unique_id = my_unique_id

    @staticmethod
    def define_variable(plot_image_vars, value_type, value, index):
        value_label = f'{value}'
        if value_type == 'seed':
            seed = int(plot_image_vars['seed'])
            if index != 0:
                index = 1
            if value == 'increment':
                plot_image_vars['seed'] = seed + index
                value_label = f"{plot_image_vars['seed']}"
            elif value == 'decrement':
                plot_image_vars['seed'] = seed - index
                value_label = f"{plot_image_vars['seed']}"
            elif value == 'randomize':
                plot_image_vars['seed'] = random.randint(0, 18446744073709551615)
                value_label = f"{plot_image_vars['seed']}"
        else:
            plot_image_vars[value_type] = value
        if value_type in ['steps', 'cfg', 'denoise', 'clip_skip', 'lora1_model_strength', 'lora1_clip_strength', 'lora2_model_strength', 'lora2_clip_strength', 'lora3_model_strength', 'lora3_clip_strength']:
            value_label = f'{value_type}: {value}'
        if value_type in ['lora_model&clip_strength', 'lora1_model&clip_strength', 'lora2_model&clip_strength', 'lora3_model&clip_strength']:
            loraNum = value_type.split('_')[0]
            plot_image_vars[loraNum + '_model_strength'] = value
            plot_image_vars[loraNum + '_clip_strength'] = value
            type_label = value_type.replace('_model&clip', '')
            value_label = f'{type_label}: {value}'
        elif value_type == 'positive_token_normalization':
            value_label = f'(+) token norm.: {value}'
        elif value_type == 'positive_weight_interpretation':
            value_label = f'(+) weight interp.: {value}'
        elif value_type == 'negative_token_normalization':
            value_label = f'(-) token norm.: {value}'
        elif value_type == 'negative_weight_interpretation':
            value_label = f'(-) weight interp.: {value}'
        elif value_type == 'positive':
            value_label = f'pos prompt {index + 1}'
        elif value_type == 'negative':
            value_label = f'neg prompt {index + 1}'
        return (plot_image_vars, value_label)

    @staticmethod
    def get_font(font_size):
        return pack_font(font_size)

    @staticmethod
    def update_label(label, value, num_items):
        if len(label) < num_items:
            return [*label, value]
        return label

    @staticmethod
    def rearrange_tensors(latent, num_cols, num_rows):
        new_latent = []
        for i in range(num_rows):
            for j in range(num_cols):
                index = j * num_rows + i
                new_latent.append(latent[index])
        return new_latent

    def calculate_background_dimensions(self):
        border_size = int(self.max_width // 8 * 1.5) if self.y_type != 'None' or self.x_type != 'None' else 0
        bg_width = self.num_cols * (self.max_width + self.grid_spacing) - self.grid_spacing + border_size * (self.y_type != 'None')
        bg_height = self.num_rows * (self.max_height + self.grid_spacing) - self.grid_spacing + border_size * (self.x_type != 'None')
        x_offset_initial = border_size if self.y_type != 'None' else 0
        y_offset = border_size if self.x_type != 'None' else 0
        return (bg_width, bg_height, x_offset_initial, y_offset)

    def adjust_font_size(self, text, initial_font_size, label_width):
        font = self.get_font(initial_font_size)
        left, _, right, _ = font.getbbox(text)
        text_width = right - left
        scaling_factor = 0.9
        if text_width > label_width * scaling_factor:
            return int(initial_font_size * (label_width / text_width) * scaling_factor)
        else:
            return initial_font_size

    def create_label(self, img, text, initial_font_size, is_x_label=True, max_font_size=70, min_font_size=10):
        label_width = img.width if is_x_label else img.height
        font_size = self.adjust_font_size(text, initial_font_size, label_width)
        font_size = min(max_font_size, font_size)
        font_size = max(min_font_size, font_size)
        label_height = int(font_size * 1.5) if is_x_label else font_size
        label_bg = Image.new('RGBA', (label_width, label_height), color=(255, 255, 255, 0))
        d = ImageDraw.Draw(label_bg)
        font = self.get_font(font_size)
        try:
            if d.textsize(text, font=font)[0] > label_width:
                while d.textsize(text + '...', font=font)[0] > label_width and len(text) > 0:
                    text = text[:-1]
                text = text + '...'
        except:
            if d.textlength(text, font=font) > label_width:
                while d.textlength(text + '...', font=font) > label_width and len(text) > 0:
                    text = text[:-1]
                text = text + '...'
        text_lines = text.split('\n')
        try:
            text_widths, text_heights = zip(*[d.textsize(line, font=font) for line in text_lines])
        except:
            text_widths, text_heights = zip(*[(d.textlength(line, font=font), font_size) for line in text_lines])
        max_text_width = max(text_widths)
        total_text_height = sum(text_heights)
        lines_positions = []
        current_y = 0
        for line, line_width, line_height in zip(text_lines, text_widths, text_heights):
            text_x = (label_width - line_width) // 2
            text_y = current_y + (label_height - total_text_height) // 2
            current_y += line_height
            lines_positions.append((line, (text_x, text_y)))
        for line, (text_x, text_y) in lines_positions:
            d.text((text_x, text_y), line, fill='black', font=font)
        return label_bg

    async def sample_plot_image(self, plot_image_vars, samples, preview_latent, latents_plot, image_list, disable_noise, start_step, last_step, force_full_denoise):
        model, clip, vae, positive, negative = (None, None, None, None, None)
        if plot_image_vars['x_node_type'] == 'loader' or plot_image_vars['y_node_type'] == 'loader':
            model, clip, vae = await loader.load_checkpoint(plot_image_vars['ckpt_name'])
            if plot_image_vars['lora1_name'] != 'None':
                model, clip = await loader.load_lora(plot_image_vars['lora1_name'], model, clip, plot_image_vars['lora1_model_strength'], plot_image_vars['lora1_clip_strength'])
            if plot_image_vars['lora2_name'] != 'None':
                model, clip = await loader.load_lora(plot_image_vars['lora2_name'], model, clip, plot_image_vars['lora2_model_strength'], plot_image_vars['lora2_clip_strength'])
            if plot_image_vars['lora3_name'] != 'None':
                model, clip = await loader.load_lora(plot_image_vars['lora3_name'], model, clip, plot_image_vars['lora3_model_strength'], plot_image_vars['lora3_clip_strength'])
            if plot_image_vars['vae_name'] not in ['Baked-VAE', 'Baked VAE']:
                vae = await loader.load_vae(plot_image_vars['vae_name'])
            if not clip:
                raise Exception('No CLIP found')
            clip = clip
            clip = await clip_layer(clip, plot_image_vars['clip_skip'])
            positive, positive_pooled = await advanced_encode(clip, plot_image_vars['positive'], plot_image_vars['positive_token_normalization'], plot_image_vars['positive_weight_interpretation'], w_max=1.0, apply_to_pooled='enable')
            positive = [[positive, {'pooled_output': positive_pooled}]]
            negative, negative_pooled = await advanced_encode(clip, plot_image_vars['negative'], plot_image_vars['negative_token_normalization'], plot_image_vars['negative_weight_interpretation'], w_max=1.0, apply_to_pooled='enable')
            negative = [[negative, {'pooled_output': negative_pooled}]]
        model = model if model is not None else plot_image_vars['model']
        clip = clip if clip is not None else plot_image_vars['clip']
        vae = vae if vae is not None else plot_image_vars['vae']
        positive = positive if positive is not None else plot_image_vars['positive_cond']
        negative = negative if negative is not None else plot_image_vars['negative_cond']
        seed = plot_image_vars['seed']
        steps = plot_image_vars['steps']
        cfg = plot_image_vars['cfg']
        sampler_name = plot_image_vars['sampler_name']
        scheduler = plot_image_vars['scheduler']
        denoise = plot_image_vars['denoise']
        if plot_image_vars['lora_name'] not in ('None', None):
            model, clip = await loader.load_lora(plot_image_vars['lora_name'], model, clip, plot_image_vars['lora_model_strength'], plot_image_vars['lora_clip_strength'])
        samples = await sampler.common_ksampler(model, seed, steps, cfg, sampler_name, scheduler, positive, negative, samples, denoise=denoise, disable_noise=disable_noise, preview_latent=preview_latent, start_step=start_step, last_step=last_step, force_full_denoise=force_full_denoise)
        latent = samples['samples']
        latents_plot.append(latent)
        image = await vae_decode(vae, latent)
        if self.output_individuals in [True, 'True']:
            ttN_save = ttNsave(self.my_unique_id, self.prompt, self.extra_pnginfo)
            await ttN_save.images(image, self.save_prefix, self.image_output, group_id=self.num)
        pil_image = ttNsampler.tensor2pil(image)
        image_list.append(pil_image)
        self.max_width = max(self.max_width, pil_image.width)
        self.max_height = max(self.max_height, pil_image.height)
        return (image_list, self.max_width, self.max_height, latents_plot)

    def validate_xy_plot(self):
        if self.x_type == 'None' and self.y_type == 'None':
            ttNl('No Valid Plot Types - Reverting to default sampling...').t(f'pipeKSampler[{self.my_unique_id}]').warn().p()
            return False
        else:
            return True

    def plot_images_and_labels(self):
        bg_width, bg_height, x_offset_initial, y_offset = self.calculate_background_dimensions()
        background = Image.new('RGBA', (int(bg_width), int(bg_height)), color=(255, 255, 255, 255))
        for row_index in range(self.num_rows):
            x_offset = x_offset_initial
            for col_index in range(self.num_cols):
                index = col_index * self.num_rows + row_index
                img = self.image_list[index]
                background.paste(img, (x_offset, y_offset))
                if row_index == 0 and self.x_type != 'None':
                    label_bg = self.create_label(img, self.x_label[col_index], int(48 * img.width / 512))
                    label_y = (y_offset - label_bg.height) // 2
                    background.alpha_composite(label_bg, (x_offset, label_y))
                if col_index == 0 and self.y_type != 'None':
                    label_bg = self.create_label(img, self.y_label[row_index], int(48 * img.height / 512), False)
                    label_bg = label_bg.rotate(90, expand=True)
                    label_x = (x_offset - label_bg.width) // 2
                    label_y = y_offset + (img.height - label_bg.height) // 2
                    background.alpha_composite(label_bg, (label_x, label_y))
                x_offset += img.width + self.grid_spacing
            y_offset += img.height + self.grid_spacing
        return sampler.pil2tensor(background)

    def get_latent(self, samples, latent_id):
        latent_image_tensor = samples['samples']
        image_tensors = torch.split(latent_image_tensor, 1, dim=0)
        latent_list = [{'samples': image} for image in image_tensors]
        if latent_id >= len(latent_list):
            ttNl(f'The selected latent_id ({latent_id}) is out of range.').t(f'pipeKSampler[{self.my_unique_id}]').warn().p()
            ttNl(f'Automatically setting the latent_id to the last image in the list (index: {len(latent_list) - 1}).').t(f'pipeKSampler[{self.my_unique_id}]').warn().p()
            latent_id = len(latent_list) - 1
        return latent_list[latent_id]

    async def get_labels_and_sample(self, plot_image_vars, latent_image, preview_latent, start_step, last_step, force_full_denoise, disable_noise):
        for x_index, x_value in enumerate(self.x_values):
            plot_image_vars, x_value_label = self.define_variable(plot_image_vars, self.x_type, x_value, x_index)
            self.x_label = self.update_label(self.x_label, x_value_label, len(self.x_values))
            if self.y_type != 'None':
                for y_index, y_value in enumerate(self.y_values):
                    self.num += 1
                    plot_image_vars, y_value_label = self.define_variable(plot_image_vars, self.y_type, y_value, y_index)
                    self.y_label = self.update_label(self.y_label, y_value_label, len(self.y_values))
                    ttNl(f'{CC.GREY}X: {x_value_label}, Y: {y_value_label}').t(f'Plot Values {self.num}/{self.total} ->').p()
                    self.image_list, self.max_width, self.max_height, self.latents_plot = await self.sample_plot_image(plot_image_vars, latent_image, preview_latent, self.latents_plot, self.image_list, disable_noise, start_step, last_step, force_full_denoise)
            else:
                self.num += 1
                ttNl(f'{CC.GREY}X: {x_value_label}').t(f'Plot Values {self.num}/{self.total} ->').p()
                self.image_list, self.max_width, self.max_height, self.latents_plot = await self.sample_plot_image(plot_image_vars, latent_image, preview_latent, self.latents_plot, self.image_list, disable_noise, start_step, last_step, force_full_denoise)
        self.latents_plot = self.rearrange_tensors(self.latents_plot, self.num_cols, self.num_rows)
        self.latents_plot = torch.cat(self.latents_plot, dim=0)
        return self.latents_plot

class ttN_XYPlot:
    version = '1.2.0'

    def __init__(self):
        pass
    rejected = ['None', '---------------------']

    def plot(self, grid_spacing, latent_id, output_individuals, flip_xy, x_axis, x_values, y_axis, y_values):

        def clean_values(values):
            original_values = values.split('; ')
            cleaned_values = []
            for value in original_values:
                cleaned_value = value.strip(';').strip()
                if cleaned_value == '':
                    continue
                try:
                    cleaned_value = int(cleaned_value)
                except ValueError:
                    try:
                        cleaned_value = float(cleaned_value)
                    except ValueError:
                        pass
                cleaned_values.append(cleaned_value)
            return cleaned_values
        if x_axis in self.rejected:
            x_axis = 'None'
            x_values = []
        else:
            x_values = clean_values(x_values)
        if y_axis in self.rejected:
            y_axis = 'None'
            y_values = []
        else:
            y_values = clean_values(y_values)
        if flip_xy == 'True':
            x_axis, y_axis = (y_axis, x_axis)
            x_values, y_values = (y_values, x_values)
        xy_plot = {'x_axis': x_axis, 'x_vals': x_values, 'y_axis': y_axis, 'y_vals': y_values, 'grid_spacing': grid_spacing, 'latent_id': latent_id, 'output_individuals': output_individuals}
        return (xy_plot,)

class ttN_pipe_IN:
    version = '1.1.0'

    def __init__(self):
        pass

    def flush(self, model, pos=0, neg=0, latent=0, vae=0, clip=0, image=0, seed=0):
        pipe = {'model': model, 'positive': pos, 'negative': neg, 'vae': vae, 'clip': clip, 'refiner_model': None, 'refiner_positive': None, 'refiner_negative': None, 'refiner_vae': None, 'refiner_clip': None, 'samples': latent, 'images': image, 'seed': seed, 'loader_settings': {}}
        return (pipe,)

class ttN_pipe_OUT:
    version = '1.1.0'

    def __init__(self):
        pass

    def flush(self, pipe):
        model = pipe.get('model')
        pos = pipe.get('positive')
        neg = pipe.get('negative')
        latent = pipe.get('samples')
        vae = pipe.get('vae')
        clip = pipe.get('clip')
        image = pipe.get('images')
        seed = pipe.get('seed')
        return (model, pos, neg, latent, vae, clip, image, seed, pipe)

class ttN_TSC_pipeLoader:
    version = '1.1.2'

    async def adv_pipeloader(self, ckpt_name, config_name, vae_name, clip_skip, lora1_name, lora1_model_strength, lora1_clip_strength, lora2_name, lora2_model_strength, lora2_clip_strength, lora3_name, lora3_model_strength, lora3_clip_strength, positive, positive_token_normalization, positive_weight_interpretation, negative, negative_token_normalization, negative_weight_interpretation, empty_latent_width, empty_latent_height, batch_size, seed, model_override=None, clip_override=None, optional_lora_stack=None, prompt=None, my_unique_id=None):
        model = None
        clip = None
        vae = None
        latent = sampler.emptyLatent(None, batch_size, empty_latent_width, empty_latent_height)
        samples = {'samples': latent}
        model, clip, vae = await loader.load_checkpoint(ckpt_name, config_name)
        if model_override is not None:
            model = model_override
        if clip_override is not None:
            clip = clip_override
        if optional_lora_stack is not None:
            for lora in optional_lora_stack:
                model, clip = await loader.load_lora(lora[0], model, clip, lora[1], lora[2])
        if lora1_name != 'None':
            model, clip = await loader.load_lora(lora1_name, model, clip, lora1_model_strength, lora1_clip_strength)
        if lora2_name != 'None':
            model, clip = await loader.load_lora(lora2_name, model, clip, lora2_model_strength, lora2_clip_strength)
        if lora3_name != 'None':
            model, clip = await loader.load_lora(lora3_name, model, clip, lora3_model_strength, lora3_clip_strength)
        if vae_name != 'Baked VAE':
            vae = await loader.load_vae(vae_name)
        if not clip:
            raise Exception('No CLIP found')
        clipped = clip
        if clip_skip != 0:
            clipped = await clip_layer(clipped, clip_skip)
        positive = await loader.nsp_parse(positive, seed, title='pipeLoader Positive', my_unique_id=my_unique_id)
        positive_embeddings_final, positive_pooled = await advanced_encode(clipped, positive, positive_token_normalization, positive_weight_interpretation, w_max=1.0, apply_to_pooled='enable')
        positive_embeddings_final = [[positive_embeddings_final, {'pooled_output': positive_pooled}]]
        negative = await loader.nsp_parse(negative, seed, title='pipeLoader Negative', my_unique_id=my_unique_id)
        negative_embeddings_final, negative_pooled = await advanced_encode(clipped, negative, negative_token_normalization, negative_weight_interpretation, w_max=1.0, apply_to_pooled='enable')
        negative_embeddings_final = [[negative_embeddings_final, {'pooled_output': negative_pooled}]]
        image = ttNsampler.pil2tensor(Image.new('RGB', (1, 1), (0, 0, 0)))
        pipe = {'model': model, 'positive': positive_embeddings_final, 'negative': negative_embeddings_final, 'vae': vae, 'clip': clip, 'samples': samples, 'images': image, 'seed': seed, 'loader_settings': {'ckpt_name': ckpt_name, 'vae_name': vae_name, 'lora1_name': lora1_name, 'lora1_model_strength': lora1_model_strength, 'lora1_clip_strength': lora1_clip_strength, 'lora2_name': lora2_name, 'lora2_model_strength': lora2_model_strength, 'lora2_clip_strength': lora2_clip_strength, 'lora3_name': lora3_name, 'lora3_model_strength': lora3_model_strength, 'lora3_clip_strength': lora3_clip_strength, 'refiner_ckpt_name': None, 'refiner_vae_name': None, 'refiner_lora1_name': None, 'refiner_lora1_model_strength': None, 'refiner_lora1_clip_strength': None, 'refiner_lora2_name': None, 'refiner_lora2_model_strength': None, 'refiner_lora2_clip_strength': None, 'clip_skip': clip_skip, 'positive': positive, 'positive_l': None, 'positive_g': None, 'positive_token_normalization': positive_token_normalization, 'positive_weight_interpretation': positive_weight_interpretation, 'positive_balance': None, 'negative': negative, 'negative_l': None, 'negative_g': None, 'negative_token_normalization': negative_token_normalization, 'negative_weight_interpretation': negative_weight_interpretation, 'negative_balance': None, 'empty_latent_width': empty_latent_width, 'empty_latent_height': empty_latent_height, 'batch_size': batch_size, 'seed': seed, 'empty_samples': samples}}
        return (pipe, model, positive_embeddings_final, negative_embeddings_final, samples, vae, clip, seed)

class ttN_TSC_pipeKSampler:
    version = '1.0.5'
    upscale_methods = ['None', 'nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos', 'bislerp']
    crop_methods = ['disabled', 'center']

    def __init__(self):
        pass

    async def sample(self, pipe, lora_name, lora_model_strength, lora_clip_strength, sampler_state, steps, cfg, sampler_name, scheduler, image_output, save_prefix, denoise=1.0, optional_model=None, optional_positive=None, optional_negative=None, optional_latent=None, optional_vae=None, optional_clip=None, seed=None, xyPlot=None, upscale_method=None, factor=None, crop=None, prompt=None, extra_pnginfo=None, my_unique_id=None, start_step=None, last_step=None, force_full_denoise=False, disable_noise=False):
        my_unique_id = int(my_unique_id)
        ttN_save = ttNsave(my_unique_id, prompt, extra_pnginfo)
        samp_model = optional_model if optional_model is not None else pipe['model']
        samp_positive = optional_positive if optional_positive is not None else pipe['positive']
        samp_negative = optional_negative if optional_negative is not None else pipe['negative']
        samp_samples = optional_latent if optional_latent is not None else pipe['samples']
        samp_vae = optional_vae if optional_vae is not None else pipe['vae']
        samp_clip = optional_clip if optional_clip is not None else pipe['clip']
        if seed in (None, 'undefined'):
            samp_seed = pipe['seed']
        else:
            samp_seed = seed

        async def process_sample_state(pipe, samp_model, samp_clip, samp_samples, samp_vae, samp_seed, samp_positive, samp_negative, lora_name, lora_model_strength, lora_clip_strength, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, prompt, extra_pnginfo, my_unique_id, preview_latent, disable_noise=disable_noise):
            if lora_name not in (None, 'None'):
                samp_model, samp_clip = await loader.load_lora(lora_name, samp_model, samp_clip, lora_model_strength, lora_clip_strength)
            samp_samples = await sampler.handle_upscale(samp_samples, upscale_method, factor, crop)
            samp_samples = await sampler.common_ksampler(samp_model, samp_seed, steps, cfg, sampler_name, scheduler, samp_positive, samp_negative, samp_samples, denoise=denoise, preview_latent=preview_latent, start_step=start_step, last_step=last_step, force_full_denoise=force_full_denoise, disable_noise=disable_noise)
            latent = samp_samples['samples']
            samp_images = await vae_decode(samp_vae, latent)
            results = await ttN_save.images(samp_images, save_prefix, image_output)
            sampler.update_value_by_id('results', my_unique_id, results)
            new_pipe = {'model': samp_model, 'positive': samp_positive, 'negative': samp_negative, 'vae': samp_vae, 'clip': samp_clip, 'samples': samp_samples, 'images': samp_images, 'seed': samp_seed, 'loader_settings': pipe['loader_settings']}
            sampler.update_value_by_id('pipe_line', my_unique_id, new_pipe)
            del pipe
            if image_output in ('Hide', 'Hide/Save'):
                return sampler.get_output(new_pipe)
            return {'ui': {'images': results}, 'result': sampler.get_output(new_pipe)}

        def process_hold_state(pipe, image_output, my_unique_id):
            raise RuntimeError('Hold is unavailable in the current secure profile: prior render pipe and preview results are not retained across executions. Select Sample to generate a new result.')
            last_pipe = sampler.init_state(my_unique_id, 'pipe_line', pipe)
            last_results = sampler.init_state(my_unique_id, 'results', list())
            if image_output in ('Hide', 'Hide/Save'):
                return sampler.get_output(last_pipe)
            return {'ui': {'images': last_results}, 'result': sampler.get_output(last_pipe)}

        async def process_xyPlot(pipe, samp_model, samp_clip, samp_samples, samp_vae, samp_seed, samp_positive, samp_negative, lora_name, lora_model_strength, lora_clip_strength, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, prompt, extra_pnginfo, my_unique_id, preview_latent, xyPlot):
            random.seed(seed)
            sampleXYplot = ttNxyPlot(xyPlot, save_prefix, image_output, prompt, extra_pnginfo, my_unique_id)
            if not sampleXYplot.validate_xy_plot():
                return await process_sample_state(pipe, lora_name, lora_model_strength, lora_clip_strength, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, prompt, extra_pnginfo, my_unique_id, preview_latent)
            plot_image_vars = {'x_node_type': sampleXYplot.x_node_type, 'y_node_type': sampleXYplot.y_node_type, 'lora_name': lora_name, 'lora_model_strength': lora_model_strength, 'lora_clip_strength': lora_clip_strength, 'steps': steps, 'cfg': cfg, 'sampler_name': sampler_name, 'scheduler': scheduler, 'denoise': denoise, 'seed': samp_seed, 'model': samp_model, 'vae': samp_vae, 'clip': samp_clip, 'positive_cond': samp_positive, 'negative_cond': samp_negative, 'ckpt_name': pipe['loader_settings']['ckpt_name'], 'vae_name': pipe['loader_settings']['vae_name'], 'clip_skip': pipe['loader_settings']['clip_skip'], 'lora1_name': pipe['loader_settings']['lora1_name'], 'lora1_model_strength': pipe['loader_settings']['lora1_model_strength'], 'lora1_clip_strength': pipe['loader_settings']['lora1_clip_strength'], 'lora2_name': pipe['loader_settings']['lora2_name'], 'lora2_model_strength': pipe['loader_settings']['lora2_model_strength'], 'lora2_clip_strength': pipe['loader_settings']['lora2_clip_strength'], 'lora3_name': pipe['loader_settings']['lora3_name'], 'lora3_model_strength': pipe['loader_settings']['lora3_model_strength'], 'lora3_clip_strength': pipe['loader_settings']['lora3_clip_strength'], 'positive': pipe['loader_settings']['positive'], 'positive_token_normalization': pipe['loader_settings']['positive_token_normalization'], 'positive_weight_interpretation': pipe['loader_settings']['positive_weight_interpretation'], 'negative': pipe['loader_settings']['negative'], 'negative_token_normalization': pipe['loader_settings']['negative_token_normalization'], 'negative_weight_interpretation': pipe['loader_settings']['negative_weight_interpretation']}
            latent_image = sampleXYplot.get_latent(pipe['samples'])
            latents_plot = await sampleXYplot.get_labels_and_sample(plot_image_vars, latent_image, preview_latent, start_step, last_step, force_full_denoise, disable_noise)
            samp_samples = {'samples': latents_plot}
            images = sampleXYplot.plot_images_and_labels()
            if xyPlot['output_individuals']:
                results = await ttN_save.images(images, save_prefix, image_output)
            else:
                results = await ttN_save.images(images[-1], save_prefix, image_output)
            sampler.update_value_by_id('results', my_unique_id, results)
            new_pipe = {'model': samp_model, 'positive': samp_positive, 'negative': samp_negative, 'vae': samp_vae, 'clip': samp_clip, 'samples': samp_samples, 'images': images, 'seed': samp_seed, 'loader_settings': pipe['loader_settings']}
            sampler.update_value_by_id('pipe_line', my_unique_id, new_pipe)
            del pipe
            if image_output in ('Hide', 'Hide/Save'):
                return sampler.get_output(new_pipe)
            return {'ui': {'images': results}, 'result': sampler.get_output(new_pipe)}
        preview_latent = True
        if image_output in ('Hide', 'Hide/Save'):
            preview_latent = False
        if sampler_state == 'Sample' and xyPlot is None:
            return await process_sample_state(pipe, samp_model, samp_clip, samp_samples, samp_vae, samp_seed, samp_positive, samp_negative, lora_name, lora_model_strength, lora_clip_strength, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, prompt, extra_pnginfo, my_unique_id, preview_latent)
        elif sampler_state == 'Sample' and xyPlot is not None:
            return await process_xyPlot(pipe, samp_model, samp_clip, samp_samples, samp_vae, samp_seed, samp_positive, samp_negative, lora_name, lora_model_strength, lora_clip_strength, steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, prompt, extra_pnginfo, my_unique_id, preview_latent, xyPlot)
        elif sampler_state == 'Hold':
            return process_hold_state(pipe, image_output, my_unique_id)

class ttN_pipeKSamplerAdvanced:
    version = '1.0.5'
    upscale_methods = ['None', 'nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos', 'bislerp']
    crop_methods = ['disabled', 'center']

    def __init__(self):
        pass

    async def sample(self, pipe, lora_name, lora_model_strength, lora_clip_strength, sampler_state, add_noise, steps, cfg, sampler_name, scheduler, image_output, save_prefix, denoise=1.0, noise_seed=None, optional_model=None, optional_positive=None, optional_negative=None, optional_latent=None, optional_vae=None, optional_clip=None, xyPlot=None, upscale_method=None, factor=None, crop=None, prompt=None, extra_pnginfo=None, my_unique_id=None, start_at_step=None, end_at_step=None, return_with_leftover_noise=False):
        force_full_denoise = True
        if return_with_leftover_noise == 'enable':
            force_full_denoise = False
        disable_noise = False
        if add_noise == 'disable':
            disable_noise = True
        out = await ttN_TSC_pipeKSampler.sample(self, pipe, lora_name, lora_model_strength, lora_clip_strength, sampler_state, steps, cfg, sampler_name, scheduler, image_output, save_prefix, denoise, optional_model, optional_positive, optional_negative, optional_latent, optional_vae, optional_clip, noise_seed, xyPlot, upscale_method, factor, crop, prompt, extra_pnginfo, my_unique_id, start_at_step, end_at_step, force_full_denoise, disable_noise)
        return out

class ttN_pipeLoaderSDXL:
    version = '1.1.2'

    async def adv_pipeloader(self, ckpt_name, vae_name, lora1_name, lora1_model_strength, lora1_clip_strength, lora2_name, lora2_model_strength, lora2_clip_strength, refiner_ckpt_name, refiner_vae_name, refiner_lora1_name, refiner_lora1_model_strength, refiner_lora1_clip_strength, refiner_lora2_name, refiner_lora2_model_strength, refiner_lora2_clip_strength, clip_skip, positive, positive_token_normalization, positive_weight_interpretation, negative, negative_token_normalization, negative_weight_interpretation, empty_latent_width, empty_latent_height, batch_size, seed, prompt=None, my_unique_id=None):

        async def SDXL_loader(ckpt_name, vae_name, lora1_name, lora1_model_strength, lora1_clip_strength, lora2_name, lora2_model_strength, lora2_clip_strength, positive, positive_token_normalization, positive_weight_interpretation, negative, negative_token_normalization, negative_weight_interpretation):
            model = None
            clip = None
            vae = None
            model, clip, vae = await loader.load_checkpoint(ckpt_name)
            if lora1_name != 'None':
                model, clip = await loader.load_lora(lora1_name, model, clip, lora1_model_strength, lora1_clip_strength)
            if lora2_name != 'None':
                model, clip = await loader.load_lora(lora2_name, model, clip, lora2_model_strength, lora2_clip_strength)
            if vae_name not in ['Baked VAE', 'Baked-VAE']:
                vae = await loader.load_vae(vae_name)
            if not clip:
                raise Exception('No CLIP found')
            clipped = clip
            if clip_skip != 0:
                clipped = await clip_layer(clipped, clip_skip)
            positive = await loader.nsp_parse(positive, seed, title='pipeLoaderSDXL positive', my_unique_id=my_unique_id)
            positive_embeddings_final, positive_pooled = await advanced_encode(clipped, positive, positive_token_normalization, positive_weight_interpretation, w_max=1.0, apply_to_pooled='enable')
            positive_embeddings_final = [[positive_embeddings_final, {'pooled_output': positive_pooled}]]
            negative = await loader.nsp_parse(negative, seed)
            negative_embeddings_final, negative_pooled = await advanced_encode(clipped, negative, negative_token_normalization, negative_weight_interpretation, w_max=1.0, apply_to_pooled='enable')
            negative_embeddings_final = [[negative_embeddings_final, {'pooled_output': negative_pooled}]]
            return (model, positive_embeddings_final, negative_embeddings_final, vae, clip)
        latent = sampler.emptyLatent(None, batch_size, empty_latent_width, empty_latent_height)
        samples = {'samples': latent}
        model, positive_embeddings, negative_embeddings, vae, clip = await SDXL_loader(ckpt_name, vae_name, lora1_name, lora1_model_strength, lora1_clip_strength, lora2_name, lora2_model_strength, lora2_clip_strength, positive, positive_token_normalization, positive_weight_interpretation, negative, negative_token_normalization, negative_weight_interpretation)
        if refiner_ckpt_name != 'None':
            refiner_model, refiner_positive_embeddings, refiner_negative_embeddings, refiner_vae, refiner_clip = await SDXL_loader(refiner_ckpt_name, refiner_vae_name, refiner_lora1_name, refiner_lora1_model_strength, refiner_lora1_clip_strength, refiner_lora2_name, refiner_lora2_model_strength, refiner_lora2_clip_strength, positive, positive_token_normalization, positive_weight_interpretation, negative, negative_token_normalization, negative_weight_interpretation)
        else:
            refiner_model, refiner_positive_embeddings, refiner_negative_embeddings, refiner_vae, refiner_clip = (None, None, None, None, None)
        image = ttNsampler.pil2tensor(Image.new('RGB', (1, 1), (0, 0, 0)))
        pipe = {'model': model, 'positive': positive_embeddings, 'negative': negative_embeddings, 'vae': vae, 'clip': clip, 'refiner_model': refiner_model, 'refiner_positive': refiner_positive_embeddings, 'refiner_negative': refiner_negative_embeddings, 'refiner_vae': refiner_vae, 'refiner_clip': refiner_clip, 'samples': samples, 'images': image, 'seed': seed, 'loader_settings': {'ckpt_name': ckpt_name, 'vae_name': vae_name, 'lora1_name': lora1_name, 'lora1_model_strength': lora1_model_strength, 'lora1_clip_strength': lora1_clip_strength, 'lora2_name': lora2_name, 'lora2_model_strength': lora2_model_strength, 'lora2_clip_strength': lora2_clip_strength, 'lora3_name': None, 'lora3_model_strength': None, 'lora3_clip_strength': None, 'refiner_ckpt_name': refiner_ckpt_name, 'refiner_vae_name': refiner_vae_name, 'refiner_lora1_name': refiner_lora1_name, 'refiner_lora1_model_strength': refiner_lora1_model_strength, 'refiner_lora1_clip_strength': refiner_lora1_clip_strength, 'refiner_lora2_name': refiner_lora2_name, 'refiner_lora2_model_strength': refiner_lora2_model_strength, 'refiner_lora2_clip_strength': refiner_lora2_clip_strength, 'clip_skip': clip_skip, 'positive_balance': None, 'positive': positive, 'positive_l': None, 'positive_g': None, 'positive_token_normalization': positive_token_normalization, 'positive_weight_interpretation': positive_weight_interpretation, 'negative_balance': None, 'negative': negative, 'negative_l': None, 'negative_g': None, 'negative_token_normalization': negative_token_normalization, 'negative_weight_interpretation': negative_weight_interpretation, 'empty_latent_width': empty_latent_width, 'empty_latent_height': empty_latent_height, 'batch_size': batch_size, 'seed': seed, 'empty_samples': samples}}
        return (pipe, model, positive_embeddings, negative_embeddings, vae, clip, refiner_model, refiner_positive_embeddings, refiner_negative_embeddings, refiner_vae, refiner_clip, samples, seed)

class ttN_pipeKSamplerSDXL:
    version = '1.0.2'
    upscale_methods = ['None', 'nearest-exact', 'bilinear', 'area', 'bicubic', 'lanczos', 'bislerp']
    crop_methods = ['disabled', 'center']

    def __init__(self):
        pass

    async def sample(self, sdxl_pipe, sampler_state, base_steps, refiner_steps, cfg, sampler_name, scheduler, image_output, save_prefix, denoise=1.0, optional_model=None, optional_positive=None, optional_negative=None, optional_latent=None, optional_vae=None, optional_clip=None, optional_refiner_model=None, optional_refiner_positive=None, optional_refiner_negative=None, optional_refiner_vae=None, seed=None, xyPlot=None, upscale_method=None, factor=None, crop=None, prompt=None, extra_pnginfo=None, my_unique_id=None, start_step=None, last_step=None, force_full_denoise=False, disable_noise=False):
        sdxl_pipe = {**sdxl_pipe}
        my_unique_id = int(my_unique_id)
        ttN_save = ttNsave(my_unique_id, prompt, extra_pnginfo)
        sdxl_samples = optional_latent if optional_latent is not None else sdxl_pipe['samples']
        sdxl_model = optional_model if optional_model is not None else sdxl_pipe['model']
        sdxl_positive = optional_positive if optional_positive is not None else sdxl_pipe['positive']
        sdxl_negative = optional_negative if optional_negative is not None else sdxl_pipe['negative']
        sdxl_vae = optional_vae if optional_vae is not None else sdxl_pipe['vae']
        sdxl_clip = optional_clip if optional_clip is not None else sdxl_pipe['clip']
        sdxl_refiner_model = optional_refiner_model if optional_refiner_model is not None else sdxl_pipe['refiner_model']
        sdxl_refiner_positive = optional_refiner_positive if optional_refiner_positive is not None else sdxl_pipe['refiner_positive']
        sdxl_refiner_negative = optional_refiner_negative if optional_refiner_negative is not None else sdxl_pipe['refiner_negative']
        sdxl_refiner_vae = optional_refiner_vae if optional_refiner_vae is not None else sdxl_pipe['refiner_vae']
        sdxl_refiner_clip = sdxl_pipe['refiner_clip']
        if seed in (None, 'undefined'):
            sdxl_seed = sdxl_pipe['seed']
        else:
            sdxl_seed = seed

        async def process_sample_state(sdxl_pipe, sdxl_samples, sdxl_model, sdxl_positive, sdxl_negative, sdxl_vae, sdxl_clip, sdxl_seed, sdxl_refiner_model, sdxl_refiner_positive, sdxl_refiner_negative, sdxl_refiner_vae, sdxl_refiner_clip, base_steps, refiner_steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, prompt, my_unique_id, preview_latent, disable_noise=disable_noise):
            total_steps = base_steps + refiner_steps
            sdxl_samples = await sampler.handle_upscale(sdxl_samples, upscale_method, factor, crop)
            if refiner_steps > 0 and sdxl_refiner_model not in [None, 'None']:
                sdxl_samples = await sampler.common_ksampler(sdxl_model, sdxl_seed, total_steps, cfg, sampler_name, scheduler, sdxl_positive, sdxl_negative, sdxl_samples, denoise=denoise, preview_latent=preview_latent, start_step=0, last_step=base_steps, force_full_denoise=force_full_denoise, disable_noise=disable_noise)
                sdxl_samples = await sampler.common_ksampler(sdxl_refiner_model, sdxl_seed, total_steps, cfg, sampler_name, scheduler, sdxl_refiner_positive, sdxl_refiner_negative, sdxl_samples, denoise=denoise, preview_latent=preview_latent, start_step=base_steps, last_step=10000, force_full_denoise=True, disable_noise=True)
                latent = sdxl_samples['samples']
                sdxl_images = await vae_decode(sdxl_refiner_vae, latent)
                del latent
            else:
                sdxl_samples = await sampler.common_ksampler(sdxl_model, sdxl_seed, base_steps, cfg, sampler_name, scheduler, sdxl_positive, sdxl_negative, sdxl_samples, denoise=denoise, preview_latent=preview_latent, start_step=0, last_step=base_steps, force_full_denoise=True, disable_noise=disable_noise)
                latent = sdxl_samples['samples']
                sdxl_images = await vae_decode(sdxl_vae, latent)
                del latent
            results = await ttN_save.images(sdxl_images, save_prefix, image_output)
            sampler.update_value_by_id('results', my_unique_id, results)
            new_sdxl_pipe = {'model': sdxl_model, 'positive': sdxl_positive, 'negative': sdxl_negative, 'vae': sdxl_vae, 'clip': sdxl_clip, 'refiner_model': sdxl_refiner_model, 'refiner_positive': sdxl_refiner_positive, 'refiner_negative': sdxl_refiner_negative, 'refiner_vae': sdxl_refiner_vae, 'refiner_clip': sdxl_refiner_clip, 'samples': sdxl_samples, 'images': sdxl_images, 'seed': sdxl_seed, 'loader_settings': sdxl_pipe['loader_settings']}
            del sdxl_pipe
            sampler.update_value_by_id('pipe_line', my_unique_id, new_sdxl_pipe)
            if image_output in ('Hide', 'Hide/Save'):
                return sampler.get_output_sdxl(new_sdxl_pipe)
            return {'ui': {'images': results}, 'result': sampler.get_output_sdxl(new_sdxl_pipe)}

        def process_hold_state(sdxl_pipe, image_output, my_unique_id):
            raise RuntimeError('Hold is unavailable in the current secure profile: prior render pipe and preview results are not retained across executions. Select Sample to generate a new result.')
            ttNl('Held').t(f'pipeKSamplerSDXL[{my_unique_id}]').p()
            last_pipe = sampler.init_state(my_unique_id, 'pipe_line', sdxl_pipe)
            last_results = sampler.init_state(my_unique_id, 'results', list())
            if image_output in ('Hide', 'Hide/Save'):
                return sampler.get_output_sdxl(last_pipe)
            return {'ui': {'images': last_results}, 'result': sampler.get_output_sdxl(last_pipe)}
        preview_latent = True
        if image_output in ('Hide', 'Hide/Save'):
            preview_latent = False
        if sampler_state == 'Sample' and xyPlot is None:
            return await process_sample_state(sdxl_pipe, sdxl_samples, sdxl_model, sdxl_positive, sdxl_negative, sdxl_vae, sdxl_clip, sdxl_seed, sdxl_refiner_model, sdxl_refiner_positive, sdxl_refiner_negative, sdxl_refiner_vae, sdxl_refiner_clip, base_steps, refiner_steps, cfg, sampler_name, scheduler, denoise, image_output, save_prefix, prompt, my_unique_id, preview_latent)
        elif sampler_state == 'Hold':
            return process_hold_state(sdxl_pipe, image_output, my_unique_id)
