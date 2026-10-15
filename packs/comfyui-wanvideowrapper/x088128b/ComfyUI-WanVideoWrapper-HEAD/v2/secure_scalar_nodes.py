"""Static pack-owned Wan settings/parser nodes; full pack remains pending."""
from comfy_api.latest import io

MAX_TEXT_BYTES = 65536
MAX_BLOCK_ENTRIES = 10001

def _bound_strings(values):
    for value in values:
        if isinstance(value, str) and len(value.encode('utf-8', errors='surrogatepass')) > MAX_TEXT_BYTES:
            raise ValueError('Wan configuration text exceeds 64 KiB')


class WanVideoEnhanceAVideo(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoEnhanceAVideo', display_name='WanVideo Enhance-A-Video',
            category='WanVideoWrapper', description='https://github.com/NUS-HPC-AI-Lab/Enhance-A-Video',
            is_experimental=False,
            inputs=[
                io.Float.Input('weight', default=2.0, min=0, max=100, step=0.01, tooltip='The feta Weight of the Enhance-A-Video'),
                io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percentage of the steps to apply Enhance-A-Video'),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percentage of the steps to apply Enhance-A-Video')
            ], outputs=[io.Custom('FETAARGS').Output(display_name='feta_args')],
        )

    @classmethod
    def execute(cls, **kwargs):
        _bound_strings(kwargs.values())
        return io.NodeOutput(kwargs)

class WanVideoBlockList(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoBlockList', display_name='WanVideo Block List',
            category='WanVideoWrapper', description="Comma separated list of blocks to apply block swap to, can also use ranges like '0-5' or '0,2,3-5' etc., can be connected to the dense_blocks input of 'WanVideoSetRadialAttention' node",
            is_experimental=False,
            inputs=[
                io.String.Input('blocks', default='1', multiline=True)
            ], outputs=[io.Int.Output(display_name='block_list')],
        )

    @classmethod
    def execute(cls, blocks):
        _bound_strings([blocks])
        block_list = []
        for line in blocks.splitlines():
            for part in line.split(','):
                part = part.strip()
                if not part:
                    continue
                if '-' in part:
                    try:
                        start, end = map(int, part.split('-', 1))
                        if len(block_list) + max(0, end - start + 1) > MAX_BLOCK_ENTRIES:
                            raise ValueError('Wan block list exceeds 10001 entries')
                        block_list.extend(range(start, end + 1))
                    except Exception:
                        raise ValueError(f"Invalid range: '{part}'")
                else:
                    try:
                        block_list.append(int(part))
                    except Exception:
                        raise ValueError(f"Invalid integer: '{part}'")
        if len(block_list) > MAX_BLOCK_ENTRIES:
            raise ValueError('Wan block list exceeds 10001 entries')
        return io.NodeOutput(block_list)

class WanVideoSLG(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoSLG', display_name='WanVideo SLG',
            category='WanVideoWrapper', description='Skips uncond on the selected blocks',
            is_experimental=False,
            inputs=[
                io.String.Input('blocks', default='10', tooltip='Blocks to skip uncond on, separated by comma, index starts from 0'),
                io.Float.Input('start_percent', default=0.1, min=0.0, max=1.0, step=0.01, tooltip='Start percent of the control signal'),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percent of the control signal')
            ], outputs=[io.Custom('SLGARGS').Output(display_name='slg_args')],
        )

    @classmethod
    def execute(cls, blocks, start_percent, end_percent):
        _bound_strings([blocks, start_percent, end_percent])
        slg_block_list = [int(x.strip()) for x in blocks.split(',')]
        slg_args = {'blocks': slg_block_list, 'start_percent': start_percent, 'end_percent': end_percent}
        return io.NodeOutput(slg_args)

class WanVideoLoopArgs(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoLoopArgs', display_name='WanVideo Loop Args',
            category='WanVideoWrapper', description='Looping through latent shift as shown in https://github.com/YisuiTT/Mobius/',
            is_experimental=False,
            inputs=[
                io.Int.Input('shift_skip', default=6, min=0, tooltip='Skip step of latent shift'),
                io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, tooltip='Start percent of the looping effect'),
                io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='End percent of the looping effect')
            ], outputs=[io.Custom('LOOPARGS').Output(display_name='loop_args')],
        )

    @classmethod
    def execute(cls, **kwargs):
        _bound_strings(kwargs.values())
        return io.NodeOutput(kwargs)

class WanVideoExperimentalArgs(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoExperimentalArgs', display_name='WanVideo Experimental Args',
            category='WanVideoWrapper', description='Experimental stuff',
            is_experimental=True,
            inputs=[
                io.String.Input('video_attention_split_steps', default='', tooltip='Steps to split self attention when using multiple prompts'),
                io.Boolean.Input('cfg_zero_star', default=False, tooltip='https://github.com/WeichenFan/CFG-Zero-star'),
                io.Boolean.Input('use_zero_init', default=False),
                io.Int.Input('zero_star_steps', default=0, min=0, tooltip='Steps to split self attention when using multiple prompts'),
                io.Boolean.Input('use_fresca', default=False, tooltip='https://github.com/WikiChao/FreSca'),
                io.Float.Input('fresca_scale_low', default=1.0, min=0.0, max=10.0, step=0.01),
                io.Float.Input('fresca_scale_high', default=1.25, min=0.0, max=10.0, step=0.01),
                io.Int.Input('fresca_freq_cutoff', default=20, min=0, max=10000, step=1),
                io.Boolean.Input('use_tcfg', default=False, tooltip='https://arxiv.org/abs/2503.18137 TCFG: Tangential Damping Classifier-free Guidance. CFG artifacts reduction.'),
                io.Float.Input('raag_alpha', default=0.0, min=0.0, max=10.0, step=0.01, tooltip='Alpha value for RAAG, 1.0 is default, 0.0 is disabled.'),
                io.Boolean.Input('bidirectional_sampling', default=False, tooltip='Enable bidirectional sampling, based on https://github.com/ff2416/WanFM'),
                io.Boolean.Input('temporal_score_rescaling', default=False, tooltip='Enable temporal score rescaling: https://github.com/temporalscorerescaling/TSR/'),
                io.Float.Input('tsr_k', default=0.95, min=0.0, max=100.0, step=0.01, tooltip='The sampling temperature'),
                io.Float.Input('tsr_sigma', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='How early TSR steer the sampling process')
            ], outputs=[io.Custom('EXPERIMENTALARGS').Output(display_name='exp_args')],
        )

    @classmethod
    def execute(cls, **kwargs):
        _bound_strings(kwargs.values())
        return io.NodeOutput(kwargs)

class WanVideoFreeInitArgs(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoFreeInitArgs', display_name='WanVideo Free Init Args',
            category='WanVideoWrapper', description='https://github.com/TianxingWu/FreeInit; FreeInit, a concise yet effective method to improve temporal consistency of videos generated by diffusion models',
            is_experimental=True,
            inputs=[
                io.Int.Input('freeinit_num_iters', default=3, min=1, max=10, tooltip='Number of FreeInit iterations'),
                io.Combo.Input('freeinit_method', options=['butterworth', 'ideal', 'gaussian', 'none'], default='ideal', tooltip='Frequency filter type'),
                io.Int.Input('freeinit_n', default=4, min=1, max=10, tooltip='Butterworth filter order (only for butterworth)'),
                io.Float.Input('freeinit_d_s', default=1.0, min=0.0, max=10.0, step=0.01, tooltip='Spatial filter cutoff'),
                io.Float.Input('freeinit_d_t', default=1.0, min=0.0, max=10.0, step=0.01, tooltip='Temporal filter cutoff')
            ], outputs=[io.Custom('FREEINITARGS').Output(display_name='freeinit_args')],
        )

    @classmethod
    def execute(cls, **kwargs):
        _bound_strings(kwargs.values())
        return io.NodeOutput(kwargs)

class WanVideoRoPEFunction(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoRoPEFunction', display_name='WanVideo RoPE Function',
            category='WanVideoWrapper', description='',
            is_experimental=True,
            inputs=[
                io.Combo.Input('rope_function', options=['default', 'comfy', 'comfy_chunked'], default='comfy'),
                io.Float.Input('ntk_scale_f', default=1.0, min=0.0, max=100.0, step=0.01),
                io.Float.Input('ntk_scale_h', default=1.0, min=0.0, max=100.0, step=0.01),
                io.Float.Input('ntk_scale_w', default=1.0, min=0.0, max=100.0, step=0.01)
            ], outputs=[io.Combo.Output(display_name='rope_function', options=['default', 'comfy', 'comfy_chunked'])],
        )

    @classmethod
    def execute(cls, rope_function, ntk_scale_f, ntk_scale_h, ntk_scale_w):
        _bound_strings([rope_function, ntk_scale_f, ntk_scale_h, ntk_scale_w])
        if ntk_scale_f != 1.0 or ntk_scale_h != 1.0 or ntk_scale_w != 1.0:
            rope_func_dict = {'rope_function': rope_function, 'ntk_scale_f': ntk_scale_f, 'ntk_scale_h': ntk_scale_h, 'ntk_scale_w': ntk_scale_w}
            return io.NodeOutput(rope_func_dict)
        return io.NodeOutput(rope_function)

class WanVideoBlockSwap(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoBlockSwap', display_name='WanVideo Block Swap',
            category='WanVideoWrapper', description='Settings for block swapping, reduces VRAM use by swapping blocks to CPU memory',
            is_experimental=False,
            inputs=[
                io.Int.Input('blocks_to_swap', default=20, min=0, max=48, step=1, tooltip='Number of transformer blocks to swap, the 14B model has 40, while the 1.3B and 5B models have 30 blocks. LongCat-video has 48'),
                io.Boolean.Input('offload_img_emb', default=False, tooltip='Offload img_emb to offload_device'),
                io.Boolean.Input('offload_txt_emb', default=False, tooltip='Offload time_emb to offload_device'),
                io.Boolean.Input('use_non_blocking', default=False, tooltip='Use non-blocking memory transfer for offloading, reserves more RAM but is faster', optional=True),
                io.Int.Input('vace_blocks_to_swap', default=0, min=0, max=15, step=1, tooltip='Number of VACE blocks to swap, the VACE model has 15 blocks', optional=True),
                io.Int.Input('prefetch_blocks', default=0, min=0, max=40, step=1, tooltip='Number of blocks to prefetch ahead, can speed up processing but increases memory usage. 1 is usually enough to offset speed loss from block swapping, use the debug option to confirm it for your system', optional=True),
                io.Boolean.Input('block_swap_debug', default=False, tooltip='Enable debug logging for block swapping', optional=True)
            ], outputs=[io.Custom('BLOCKSWAPARGS').Output(display_name='block_swap_args')],
        )

    @classmethod
    def execute(cls, **kwargs):
        _bound_strings(kwargs.values())
        return io.NodeOutput(kwargs)

class WanVideoVRAMManagement(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoVRAMManagement', display_name='WanVideo VRAM Management',
            category='WanVideoWrapper', description='Alternative offloading method from DiffSynth-Studio, more aggressive in reducing memory use than block swapping, but can be slower',
            is_experimental=False,
            inputs=[
                io.Float.Input('offload_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='Percentage of parameters to offload')
            ], outputs=[io.Custom('VRAM_MANAGEMENTARGS').Output(display_name='vram_management_args')],
        )

    @classmethod
    def execute(cls, **kwargs):
        _bound_strings(kwargs.values())
        return io.NodeOutput(kwargs)

class WanVideoTorchCompileSettings(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoTorchCompileSettings', display_name='WanVideo Torch Compile Settings',
            category='WanVideoWrapper', description='torch.compile settings, when connected to the model loader, torch.compile of the selected layers is attempted. Requires Triton and torch > 2.7.0 is recommended',
            is_experimental=False,
            inputs=[
                io.Combo.Input('backend', options=['inductor', 'cudagraphs'], default='inductor'),
                io.Boolean.Input('fullgraph', default=False, tooltip='Enable full graph mode'),
                io.Combo.Input('mode', options=['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead'], default='default'),
                io.Boolean.Input('dynamic', default=False, tooltip='Enable dynamic mode'),
                io.Int.Input('dynamo_cache_size_limit', default=64, min=0, max=1024, step=1, tooltip='torch._dynamo.config.cache_size_limit'),
                io.Boolean.Input('compile_transformer_blocks_only', default=True, tooltip='Compile only the transformer blocks, usually enough and can make compilation faster and less error prone'),
                io.Int.Input('dynamo_recompile_limit', default=128, min=0, max=1024, step=1, tooltip='torch._dynamo.config.recompile_limit', optional=True),
                io.Boolean.Input('force_parameter_static_shapes', default=False, tooltip='torch._dynamo.config.force_parameter_static_shapes', optional=True),
                io.Boolean.Input('allow_unmerged_lora_compile', default=False, tooltip='Allow LoRA application to be compiled with torch.compile to avoid graph breaks, causes issues with some LoRAs, mostly dynamic ones', optional=True)
            ], outputs=[io.Custom('WANCOMPILEARGS').Output(display_name='torch_compile_args')],
        )

    @classmethod
    def execute(cls, backend, fullgraph, mode, dynamic, dynamo_cache_size_limit, compile_transformer_blocks_only, dynamo_recompile_limit=128, force_parameter_static_shapes=True, allow_unmerged_lora_compile=False):
        _bound_strings([backend, fullgraph, mode, dynamic, dynamo_cache_size_limit, compile_transformer_blocks_only, dynamo_recompile_limit, force_parameter_static_shapes, allow_unmerged_lora_compile])
        compile_args = {'backend': backend, 'fullgraph': fullgraph, 'mode': mode, 'dynamic': dynamic, 'dynamo_cache_size_limit': dynamo_cache_size_limit, 'dynamo_recompile_limit': dynamo_recompile_limit, 'compile_transformer_blocks_only': compile_transformer_blocks_only, 'force_parameter_static_shapes': force_parameter_static_shapes, 'allow_unmerged_lora_compile': allow_unmerged_lora_compile}
        return io.NodeOutput(compile_args)

class WanVideoLoraBlockEdit(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoLoraBlockEdit', display_name='WanVideo Lora Block Edit',
            category='WanVideoWrapper', description='',
            is_experimental=False,
            inputs=[
                io.Boolean.Input('blocks.0.', default=True),
                io.Boolean.Input('blocks.1.', default=True),
                io.Boolean.Input('blocks.2.', default=True),
                io.Boolean.Input('blocks.3.', default=True),
                io.Boolean.Input('blocks.4.', default=True),
                io.Boolean.Input('blocks.5.', default=True),
                io.Boolean.Input('blocks.6.', default=True),
                io.Boolean.Input('blocks.7.', default=True),
                io.Boolean.Input('blocks.8.', default=True),
                io.Boolean.Input('blocks.9.', default=True),
                io.Boolean.Input('blocks.10.', default=True),
                io.Boolean.Input('blocks.11.', default=True),
                io.Boolean.Input('blocks.12.', default=True),
                io.Boolean.Input('blocks.13.', default=True),
                io.Boolean.Input('blocks.14.', default=True),
                io.Boolean.Input('blocks.15.', default=True),
                io.Boolean.Input('blocks.16.', default=True),
                io.Boolean.Input('blocks.17.', default=True),
                io.Boolean.Input('blocks.18.', default=True),
                io.Boolean.Input('blocks.19.', default=True),
                io.Boolean.Input('blocks.20.', default=True),
                io.Boolean.Input('blocks.21.', default=True),
                io.Boolean.Input('blocks.22.', default=True),
                io.Boolean.Input('blocks.23.', default=True),
                io.Boolean.Input('blocks.24.', default=True),
                io.Boolean.Input('blocks.25.', default=True),
                io.Boolean.Input('blocks.26.', default=True),
                io.Boolean.Input('blocks.27.', default=True),
                io.Boolean.Input('blocks.28.', default=True),
                io.Boolean.Input('blocks.29.', default=True),
                io.Boolean.Input('blocks.30.', default=True),
                io.Boolean.Input('blocks.31.', default=True),
                io.Boolean.Input('blocks.32.', default=True),
                io.Boolean.Input('blocks.33.', default=True),
                io.Boolean.Input('blocks.34.', default=True),
                io.Boolean.Input('blocks.35.', default=True),
                io.Boolean.Input('blocks.36.', default=True),
                io.Boolean.Input('blocks.37.', default=True),
                io.Boolean.Input('blocks.38.', default=True),
                io.Boolean.Input('blocks.39.', default=True),
                io.String.Input('layer_filter', default='', multiline=True, optional=True)
            ], outputs=[io.Custom('SELECTEDBLOCKS').Output(display_name='blocks', tooltip='The modified lora model')],
        )

    @classmethod
    def execute(cls, layer_filter=[], **kwargs):
        if isinstance(layer_filter, str) and layer_filter.count(',') >= 4096:
            raise ValueError('Wan layer filter exceeds 4096 entries')
        if len(kwargs) > 4096:
            raise ValueError('Wan selected blocks exceeds 4096 keys')
        _bound_strings([layer_filter, *kwargs.keys()])
        _bound_strings(kwargs.values())
        selected_blocks = {k: v for k, v in kwargs.items() if v is True and isinstance(v, bool)}
        print('Selected blocks LoRA: ', selected_blocks)
        selected = {'selected_blocks': selected_blocks, 'layer_filter': [x.strip() for x in layer_filter.split(',')]}
        return io.NodeOutput(selected)

class WanVideoSigmaToStep(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='WanVideoSigmaToStep', display_name='WanVideo Sigma To Step',
            category='WanVideoWrapper', description='Simply passes a float value as an integer, used to set start/end steps with sigma threshold',
            is_experimental=False,
            inputs=[
                io.Float.Input('sigma', default=0.9, min=0.0, max=1.0, step=0.001)
            ], outputs=[io.Int.Output(display_name='step')],
        )

    @classmethod
    def execute(cls, sigma):
        _bound_strings([sigma])
        return io.NodeOutput(sigma)

NODE_CLASS_MAPPINGS = {
    'WanVideoEnhanceAVideo': WanVideoEnhanceAVideo,
    'WanVideoBlockList': WanVideoBlockList,
    'WanVideoSLG': WanVideoSLG,
    'WanVideoLoopArgs': WanVideoLoopArgs,
    'WanVideoExperimentalArgs': WanVideoExperimentalArgs,
    'WanVideoFreeInitArgs': WanVideoFreeInitArgs,
    'WanVideoRoPEFunction': WanVideoRoPEFunction,
    'WanVideoBlockSwap': WanVideoBlockSwap,
    'WanVideoVRAMManagement': WanVideoVRAMManagement,
    'WanVideoTorchCompileSettings': WanVideoTorchCompileSettings,
    'WanVideoLoraBlockEdit': WanVideoLoraBlockEdit,
    'WanVideoSigmaToStep': WanVideoSigmaToStep,
}
