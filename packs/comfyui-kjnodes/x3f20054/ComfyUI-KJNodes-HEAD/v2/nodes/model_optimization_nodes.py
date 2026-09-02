from __future__ import annotations
from comfy_api.latest import io as _intent_a_io

class PatchModelPatcherOrderSecure(_intent_a_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _intent_a_io.Schema:
        return _intent_a_io.Schema(node_id='PatchModelPatcherOrderSecure', display_name='🔒 Patch Model Patcher Order (secure)', category='KJNodes/deprecated', description='NO LONGER NECESSARY OR FUNCTIONAL, keeping node for backwards compatibility. Use the TorchCompileModelAdvanced to use LoRA with torch.compile.', is_deprecated=True, inputs=[_intent_a_io.Model.Input('model'), _intent_a_io.Combo.Input('patch_order', options=['object_patch_first', 'weight_patch_first'], default='weight_patch_first', tooltip='Patch the comfy patch_model function to load weight patches (LoRAs) before compiling the model'), _intent_a_io.Combo.Input('full_load', options=['enabled', 'disabled', 'auto'], default='auto', tooltip='Disabling may help with memory issues when loading large models, when changing this you should probably force model reload to avoid issues!')], outputs=[_intent_a_io.Model.Output(display_name='MODEL')])

    @classmethod
    async def execute(cls, model, patch_order, full_load) -> _intent_a_io.NodeOutput:
        return _intent_a_io.NodeOutput(model)

class WanVideoTeaCacheKJSecure(_intent_a_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _intent_a_io.Schema:
        return _intent_a_io.Schema(node_id='WanVideoTeaCacheKJSecure', display_name='🔒 WanVideo Tea Cache (KJ) (secure)', category='KJNodes/deprecated', description="DEPRECATED, use the native EasyCache or alternative custom node that's up to date instead of this.", is_deprecated=True, is_experimental=True, inputs=[_intent_a_io.Model.Input('model'), _intent_a_io.Float.Input('rel_l1_thresh', default=0.275, min=0.0, max=10.0, step=0.001, tooltip='Threshold for to determine when to apply the cache, compromise between speed and accuracy. When using coefficients a good value range is something between 0.2-0.4 for all but 1.3B model, which should be about 10 times smaller, same as when not using coefficients.'), _intent_a_io.Float.Input('start_percent', default=0.1, min=0.0, max=1.0, step=0.01, tooltip='The start percentage of the steps to use with TeaCache.'), _intent_a_io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, tooltip='The end percentage of the steps to use with TeaCache.'), _intent_a_io.Combo.Input('cache_device', options=['main_device', 'offload_device'], default='offload_device', tooltip='Device to cache to'), _intent_a_io.Combo.Input('coefficients', options=['disabled', '1.3B', '14B', 'i2v_480', 'i2v_720'], default='i2v_480', tooltip='Coefficients for rescaling the relative l1 distance, if disabled the threshold value should be about 10 times smaller than the value used with coefficients.')], outputs=[_intent_a_io.Model.Output(display_name='model')])

    @classmethod
    async def execute(cls, model, rel_l1_thresh, start_percent, end_percent, cache_device, coefficients) -> _intent_a_io.NodeOutput:
        return _intent_a_io.NodeOutput(model)
from comfy_api.latest import io as _model_transforms_io

class ModelPatchTorchSettingsSecure(_model_transforms_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _model_transforms_io.Schema:
        return _model_transforms_io.Schema(node_id='ModelPatchTorchSettingsSecure', display_name='🔒 Model Patch Torch Settings (secure)', category='KJNodes/experimental', description="Sets fp16 matmul accumulation for this model's sampling run.", is_experimental=True, inputs=[_model_transforms_io.Model.Input('model'), _model_transforms_io.Boolean.Input('enable_fp16_accumulation', default=False, tooltip='Enable torch fp16 matmul accumulation during the run.')], outputs=[_model_transforms_io.Model.Output(display_name='model')])

    @classmethod
    async def execute(cls, model, enable_fp16_accumulation) -> _model_transforms_io.NodeOutput:
        return _model_transforms_io.NodeOutput(await model.patch('matmul_fp16_accumulation', enabled=enable_fp16_accumulation))

class ModelMemoryUsageFactorOverrideSecure(_model_transforms_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _model_transforms_io.Schema:
        return _model_transforms_io.Schema(node_id='ModelMemoryUsageFactorOverrideSecure', display_name='🔒 Model Memory Usage Factor Override (secure)', category='KJNodes/memory', description='Overrides the model memory estimate during sampling.', is_experimental=True, inputs=[_model_transforms_io.Model.Input('model'), _model_transforms_io.Float.Input('memory_usage_factor', default=1.0, min=0.0, max=100.0, step=0.001)], outputs=[_model_transforms_io.Model.Output(display_name='model')])

    @classmethod
    async def execute(cls, model, memory_usage_factor) -> _model_transforms_io.NodeOutput:
        return _model_transforms_io.NodeOutput(await model.patch('memory_usage_factor', factor=memory_usage_factor))

class WanChunkFeedForwardSecure(_model_transforms_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _model_transforms_io.Schema:
        return _model_transforms_io.Schema(node_id='WanChunkFeedForwardSecure', display_name='🔒 Wan Chunk FeedForward (secure)', category='KJNodes/wan', description='Chunks Wan feed-forward activations to reduce peak VRAM.', is_experimental=True, inputs=[_model_transforms_io.Model.Input('model'), _model_transforms_io.Int.Input('chunks', default=2, min=1, max=100, step=1), _model_transforms_io.Int.Input('dim_threshold', default=4096, min=1024, max=16384, step=256)], outputs=[_model_transforms_io.Model.Output(display_name='model')])

    @classmethod
    async def execute(cls, model, chunks, dim_threshold) -> _model_transforms_io.NodeOutput:
        if chunks == 1:
            return _model_transforms_io.NodeOutput(model)
        return _model_transforms_io.NodeOutput(await model.patch('ffn_chunking', chunks=chunks, dim_threshold=dim_threshold))
import os as _remaining_k_os
from comfy_api.latest import io as _remaining_k_io
_remaining_k_BACKENDS = ['inductor', 'cudagraphs']
_remaining_k_MODES = ['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead']

class _remaining_k_CompileTransformProbe:
    SDK_REFS = True

    @classmethod
    async def execute(cls, model, backend, mode, fullgraph, dynamic) -> _remaining_k_io.NodeOutput:
        patched = await model.patch('compile', backend=backend, mode=mode, fullgraph=fullgraph, dynamic=dynamic)
        return _remaining_k_io.NodeOutput(patched, _remaining_k_os.getpid())

class TorchCompileModelAdvancedSecure(_remaining_k_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_k_io.Schema:
        return _remaining_k_io.Schema(node_id='TorchCompileModelAdvancedSecure', display_name='🔒 Torch Compile Model Advanced (secure)', category='KJNodes/torchcompile', description='Advanced torch.compile patching for diffusion models.', is_experimental=True, inputs=[_remaining_k_io.Model.Input('model'), _remaining_k_io.Combo.Input('backend', options=_remaining_k_BACKENDS, default='inductor'), _remaining_k_io.Boolean.Input('fullgraph', default=False), _remaining_k_io.Combo.Input('mode', options=_remaining_k_MODES, default='default'), _remaining_k_io.Combo.Input('dynamic', options=['auto', 'true', 'false'], default='false'), _remaining_k_io.Boolean.Input('compile_transformer_blocks_only', default=True), _remaining_k_io.Int.Input('dynamo_cache_size_limit', default=64, min=0, max=1024, step=1), _remaining_k_io.Boolean.Input('debug_compile_keys', default=False), _remaining_k_io.Boolean.Input('disable_dynamic_vram', default=False, optional=True)], outputs=[_remaining_k_io.Model.Output(display_name='MODEL')])

    @classmethod
    async def execute(cls, model, backend, fullgraph, mode, dynamic, compile_transformer_blocks_only, dynamo_cache_size_limit, debug_compile_keys, disable_dynamic_vram=False) -> _remaining_k_io.NodeOutput:
        dynamic_value = {'auto': None, 'true': True, 'false': False}[dynamic]
        try:
            patched = await model.patch('compile', backend=backend, mode=mode, fullgraph=fullgraph, dynamic=dynamic_value, scope='known_transformer_blocks' if compile_transformer_blocks_only else 'whole', dynamo_cache_size_limit=dynamo_cache_size_limit, dynamic_vram='disable' if disable_dynamic_vram else 'stabilize', guard_filter=True, debug_compile_keys=debug_compile_keys)
        except Exception as exc:
            raise RuntimeError('Failed to compile model') from exc
        return _remaining_k_io.NodeOutput(patched)

class TorchCompileModelFluxAdvancedV2Secure(_remaining_k_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_k_io.Schema:
        return _remaining_k_io.Schema(node_id='TorchCompileModelFluxAdvancedV2Secure', display_name='🔒 Torch Compile Model Flux Advanced V2 (secure)', category='KJNodes/torchcompile', description='Deprecated, use TorchCompileModelAdvanced instead.', is_experimental=True, is_deprecated=True, inputs=[_remaining_k_io.Model.Input('model'), _remaining_k_io.Combo.Input('backend', options=_remaining_k_BACKENDS, default='inductor'), _remaining_k_io.Boolean.Input('fullgraph', default=False), _remaining_k_io.Combo.Input('mode', options=_remaining_k_MODES, default='default'), _remaining_k_io.Boolean.Input('double_blocks', default=True), _remaining_k_io.Boolean.Input('single_blocks', default=True), _remaining_k_io.Boolean.Input('dynamic', default=False), _remaining_k_io.Int.Input('dynamo_cache_size_limit', default=64, min=0, max=1024, step=1, optional=True), _remaining_k_io.Boolean.Input('force_parameter_static_shapes', default=True, optional=True)], outputs=[_remaining_k_io.Model.Output(display_name='MODEL')])

    @classmethod
    async def execute(cls, model, backend, fullgraph, mode, double_blocks, single_blocks, dynamic, dynamo_cache_size_limit=64, force_parameter_static_shapes=True) -> _remaining_k_io.NodeOutput:
        try:
            patched = await model.patch('compile', backend=backend, mode=mode, fullgraph=fullgraph, dynamic=dynamic, scope='flux_blocks', double_blocks=double_blocks, single_blocks=single_blocks, dynamo_cache_size_limit=dynamo_cache_size_limit, force_parameter_static_shapes=force_parameter_static_shapes, dynamic_vram='preserve', default_mode='explicit')
        except Exception as exc:
            raise RuntimeError('Failed to compile model') from exc
        return _remaining_k_io.NodeOutput(patched)

class TorchCompileModelWanVideoV2Secure(_remaining_k_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_k_io.Schema:
        return _remaining_k_io.Schema(node_id='TorchCompileModelWanVideoV2Secure', display_name='🔒 Torch Compile Model Wan Video V2 (secure)', category='KJNodes/torchcompile', description='Deprecated, use TorchCompileModelAdvanced instead.', is_experimental=True, is_deprecated=True, inputs=[_remaining_k_io.Model.Input('model'), _remaining_k_io.Combo.Input('backend', options=_remaining_k_BACKENDS, default='inductor'), _remaining_k_io.Boolean.Input('fullgraph', default=False), _remaining_k_io.Combo.Input('mode', options=_remaining_k_MODES, default='default'), _remaining_k_io.Boolean.Input('dynamic', default=False), _remaining_k_io.Boolean.Input('compile_transformer_blocks_only', default=True), _remaining_k_io.Int.Input('dynamo_cache_size_limit', default=64, min=0, max=1024, step=1), _remaining_k_io.Boolean.Input('force_parameter_static_shapes', default=True, optional=True)], outputs=[_remaining_k_io.Model.Output(display_name='MODEL')])

    @classmethod
    async def execute(cls, model, backend, fullgraph, mode, dynamic, compile_transformer_blocks_only, dynamo_cache_size_limit, force_parameter_static_shapes=True) -> _remaining_k_io.NodeOutput:
        try:
            patched = await model.patch('compile', backend=backend, mode=mode, fullgraph=fullgraph, dynamic=dynamic, scope='wan_blocks' if compile_transformer_blocks_only else 'whole', dynamo_cache_size_limit=dynamo_cache_size_limit, force_parameter_static_shapes=force_parameter_static_shapes, dynamic_vram='preserve', default_mode='explicit')
        except Exception as exc:
            raise RuntimeError('Failed to compile model') from exc
        return _remaining_k_io.NodeOutput(patched)
from comfy_api.latest import io as _remaining_za_io, sdk as _remaining_za_sdk

class CFGZeroStarAndInitSecure(_remaining_za_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_za_io.Schema:
        return _remaining_za_io.Schema(node_id='CFGZeroStarAndInitSecure', display_name='🔒 CFG-Zero* And Init (secure)', category='KJNodes/experimental', description='Applies CFG-Zero* with optional initial-step zeroing.', is_experimental=True, inputs=[_remaining_za_io.Model.Input('model'), _remaining_za_io.Boolean.Input('use_zero_init', default=True), _remaining_za_io.Int.Input('zero_init_steps', default=0, min=0)], outputs=[_remaining_za_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, use_zero_init, zero_init_steps) -> _remaining_za_io.NodeOutput:
        return _remaining_za_io.NodeOutput(await model.patch('cfg_zero_star', use_zero_init=use_zero_init, zero_init_steps=zero_init_steps))

class PiDColorBiasCorrectionSecure(_remaining_za_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_za_io.Schema:
        return _remaining_za_io.Schema(node_id='PiDColorBiasCorrectionSecure', display_name='🔒 PiD Color Bias Correction (secure)', category='KJNodes/experimental', description='Applies the calibrated Flux2 PiD first-step color correction.', is_experimental=True, inputs=[_remaining_za_io.Model.Input('model'), _remaining_za_io.Float.Input('strength', default=1.0, min=-20.0, max=20.0, step=0.01), _remaining_za_io.Combo.Input('backbone', options=['flux2'], default='flux2')], outputs=[_remaining_za_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, strength, backbone) -> _remaining_za_io.NodeOutput:
        return _remaining_za_io.NodeOutput(await model.patch('pid_color_bias', strength=strength, backbone=backbone))

class ModelMemoryUseReportPatchSecure(_remaining_za_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_za_io.Schema:
        return _remaining_za_io.Schema(node_id='ModelMemoryUseReportPatchSecure', display_name='🔒 Model Memory Use Report Patch (secure)', category='KJNodes/memory', description='Reports peak accelerator memory after sampling.', is_experimental=True, inputs=[_remaining_za_io.Model.Input('model')], outputs=[_remaining_za_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model) -> _remaining_za_io.NodeOutput:
        return _remaining_za_io.NodeOutput(await model.patch('sampling_memory_report'))
from comfy_api.latest import io as _remaining_zd_io

class SkipLayerGuidanceWanVideoSecure(_remaining_zd_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zd_io.Schema:
        return _remaining_zd_io.Schema(node_id='SkipLayerGuidanceWanVideoSecure', display_name='🔒 Skip Layer Guidance Wan Video (secure)', category='advanced/guidance', description='Skips unconditional computation on selected Wan double blocks.', is_experimental=True, is_deprecated=True, inputs=[_remaining_zd_io.Model.Input('model'), _remaining_zd_io.String.Input('blocks', default='10'), _remaining_zd_io.Float.Input('start_percent', default=0.2, min=0.0, max=1.0, step=0.001), _remaining_zd_io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.001)], outputs=[_remaining_zd_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, blocks, start_percent, end_percent) -> _remaining_zd_io.NodeOutput:
        block_indices = [int(value.strip()) for value in blocks.split(',')]
        patched = await model.patch('wan_skip_layer_guidance', blocks=block_indices, start_percent=start_percent, end_percent=end_percent)
        return _remaining_zd_io.NodeOutput(patched)
from comfy_api.latest import io as _remaining_zg_io, sdk as _remaining_zg_sdk
_remaining_zg_WEIGHT_DTYPES = ['default', 'fp8_e4m3fn', 'fp8_e4m3fn_fast', 'fp8_e5m2', 'fp16', 'bf16', 'fp32']
_remaining_zg_COMPUTE_DTYPES = ['default', 'fp16', 'bf16', 'fp32']
_remaining_zg_SAGE_MODES = ['disabled', 'auto', 'sageattn_qk_int8_pv_fp16_cuda', 'sageattn_qk_int8_pv_fp16_triton', 'sageattn_qk_int8_pv_fp8_cuda', 'sageattn_qk_int8_pv_fp8_cuda++', 'sageattn3', 'sageattn3_per_block_mean']

def _remaining_zg_validate_catalogue_name(name, field):
    if not isinstance(name, str) or not name:
        return f'{field} must be a non-empty catalogue name'
    logical = name.replace('\\', '/')
    if '\x00' in logical or logical.startswith('/') or (len(logical) > 1 and logical[1] == ':') or any((part == '..' for part in logical.split('/'))):
        return f'{field} must be a confined catalogue name'
    return True

async def _remaining_zg_apply_runtime_policy(model, sage_attention, enable_fp16_accumulation):
    model = await model.patch('matmul_fp16_accumulation', enabled=enable_fp16_accumulation)
    return await model.patch('sage_attention_variant', mode=sage_attention, allow_compile=False)

def _remaining_zg_loader_inputs(name, route):
    return [_remaining_zg_io.Combo.Input(name, options=[], remote=_remaining_zg_io.RemoteOptions(route=route, refresh_button=True)), _remaining_zg_io.Combo.Input('weight_dtype', options=_remaining_zg_WEIGHT_DTYPES, default='default'), _remaining_zg_io.Combo.Input('compute_dtype', options=_remaining_zg_COMPUTE_DTYPES, default='default'), _remaining_zg_io.Boolean.Input('patch_cublaslinear', default=False), _remaining_zg_io.Combo.Input('sage_attention', options=_remaining_zg_SAGE_MODES, default='disabled'), _remaining_zg_io.Boolean.Input('enable_fp16_accumulation', default=False)]

class CheckpointLoaderKJSecure(_remaining_zg_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls):
        return _remaining_zg_io.Schema(node_id='CheckpointLoaderKJSecure', display_name='Checkpoint Loader KJ (secure)', category='KJNodes/model_loaders', description='Load a catalogued checkpoint while model, CLIP, VAE, and filesystem paths remain in the trusted process.', is_experimental=True, inputs=_remaining_zg_loader_inputs('ckpt_name', '/models/checkpoints'), outputs=[_remaining_zg_io.Model.Output('model'), _remaining_zg_io.Clip.Output('clip'), _remaining_zg_io.Vae.Output('vae')])

    @classmethod
    def validate_inputs(cls, ckpt_name):
        return _remaining_zg_validate_catalogue_name(ckpt_name, 'ckpt_name')

    @classmethod
    async def execute(cls, ckpt_name, weight_dtype, compute_dtype, patch_cublaslinear, sage_attention, enable_fp16_accumulation):
        model, clip, vae = await _remaining_zg_sdk.ctx().models.load_checkpoint(ckpt_name, weight_dtype=weight_dtype, compute_dtype=compute_dtype, cublas_linear=patch_cublaslinear)
        model = await _remaining_zg_apply_runtime_policy(model, sage_attention, enable_fp16_accumulation)
        return _remaining_zg_io.NodeOutput(model, clip, vae)

class DiffusionModelSelectorSecure(_remaining_zg_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls):
        return _remaining_zg_io.Schema(node_id='DiffusionModelSelectorSecure', display_name='Diffusion Model Selector (secure)', category='KJNodes/model_loaders', description='Select a logical diffusion or connector model name without exposing its host filesystem path.', is_experimental=True, inputs=[_remaining_zg_io.Combo.Input('model_name', options=[], remote=_remaining_zg_io.RemoteOptions(route='/models/diffusion_models/choices', refresh_button=True))], outputs=[_remaining_zg_io.String.Output(display_name='model_name')])

    @classmethod
    def validate_inputs(cls, model_name):
        return _remaining_zg_validate_catalogue_name(model_name, 'model_name')

    @classmethod
    async def execute(cls, model_name):
        choices = await _remaining_zg_sdk.ctx().models.list_diffusion_models(include_connectors=True)
        if model_name not in choices:
            raise ValueError(f'unknown diffusion model selection {model_name!r}')
        return _remaining_zg_io.NodeOutput(model_name)

class DiffusionModelLoaderKJSecure(_remaining_zg_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls):
        return _remaining_zg_io.Schema(node_id='DiffusionModelLoaderKJSecure', display_name='Diffusion Model Loader KJ (secure)', category='KJNodes/model_loaders', description='Load a catalogued diffusion model and optional connector while model weights and paths remain host-owned.', is_experimental=True, inputs=[*_remaining_zg_loader_inputs('model_name', '/models/diffusion_models'), _remaining_zg_io.String.Input('extra_state_dict', optional=True, force_input=True, tooltip='A logical name from Diffusion Model Selector; never a host filesystem path.')], outputs=[_remaining_zg_io.Model.Output()])

    @classmethod
    def validate_inputs(cls, model_name, extra_state_dict=None):
        checked = _remaining_zg_validate_catalogue_name(model_name, 'model_name')
        if checked is not True or extra_state_dict is None:
            return checked
        return _remaining_zg_validate_catalogue_name(extra_state_dict, 'extra_state_dict')

    @classmethod
    async def execute(cls, model_name, weight_dtype, compute_dtype, patch_cublaslinear, sage_attention, enable_fp16_accumulation, extra_state_dict=None):
        model = await _remaining_zg_sdk.ctx().models.load_diffusion_model(model_name, extra_name=extra_state_dict, weight_dtype=weight_dtype, compute_dtype=compute_dtype, cublas_linear=patch_cublaslinear)
        model = await _remaining_zg_apply_runtime_policy(model, sage_attention, enable_fp16_accumulation)
        return _remaining_zg_io.NodeOutput(model)
from comfy_api.latest import io as _remaining_zh_io
_remaining_zh_SAGE_MODES = ['disabled', 'auto', 'sageattn_qk_int8_pv_fp16_cuda', 'sageattn_qk_int8_pv_fp16_triton', 'sageattn_qk_int8_pv_fp8_cuda', 'sageattn_qk_int8_pv_fp8_cuda++', 'sageattn3', 'sageattn3_per_block_mean']

class PathchSageAttentionKJSecure(_remaining_zh_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zh_io.Schema:
        return _remaining_zh_io.Schema(node_id='PathchSageAttentionKJSecure', display_name='🔒 Patch Sage Attention KJ (secure)', category='KJNodes/experimental', description='Selects an exact SageAttention kernel for this model.', is_experimental=True, inputs=[_remaining_zh_io.Model.Input('model'), _remaining_zh_io.Combo.Input('sage_attention', options=_remaining_zh_SAGE_MODES, default='disabled'), _remaining_zh_io.Boolean.Input('allow_compile', default=False, optional=True)], outputs=[_remaining_zh_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, sage_attention, allow_compile=False) -> _remaining_zh_io.NodeOutput:
        patched = await model.patch('sage_attention_variant', mode=sage_attention, allow_compile=allow_compile)
        return _remaining_zh_io.NodeOutput(patched)

class PatchFlashAttentionKJSecure(_remaining_zh_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zh_io.Schema:
        return _remaining_zh_io.Schema(node_id='PatchFlashAttentionKJSecure', display_name='🔒 Patch Flash Attention KJ (secure)', category='KJNodes/experimental', description='Uses FlashAttention 2 or 3 without a silent SDPA fallback.', is_experimental=True, inputs=[_remaining_zh_io.Model.Input('model'), _remaining_zh_io.Boolean.Input('allow_compile', default=False, optional=True)], outputs=[_remaining_zh_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, allow_compile=False) -> _remaining_zh_io.NodeOutput:
        patched = await model.patch('strict_flash_attention', allow_compile=allow_compile)
        return _remaining_zh_io.NodeOutput(patched)
from comfy_api.latest import io as _remaining_zi_io, sdk as _remaining_zi_sdk
_remaining_zi_PERMISSION = ('profiling.cuda_memory',)

class StartRecordCUDAMemoryHistorySecure(_remaining_zi_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = _remaining_zi_PERMISSION

    @classmethod
    def define_schema(cls) -> _remaining_zi_io.Schema:
        return _remaining_zi_io.Schema(node_id='StartRecordCUDAMemoryHistorySecure', display_name='🔒 Start Recording CUDA Memory History (secure)', category='KJNodes/memory', description='Starts bounded, process-owned CUDA allocation-history recording through the profiling broker.', inputs=[_remaining_zi_io.AnyType.Input('input'), _remaining_zi_io.Combo.Input('enabled', options=['all', 'state', 'None'], default='all'), _remaining_zi_io.Combo.Input('context', options=['all', 'state', 'alloc', 'None'], default='all'), _remaining_zi_io.Combo.Input('stacks', options=['python', 'all'], default='all'), _remaining_zi_io.Int.Input('max_entries', default=100000, min=1000, max=10000000)], outputs=[_remaining_zi_io.AnyType.Output('input', display_name='input')])

    @classmethod
    async def execute(cls, input, enabled, context, stacks, max_entries) -> _remaining_zi_io.NodeOutput:
        await _remaining_zi_sdk.ctx().profiling.cuda_memory_start(enabled=enabled, context=context, stacks=stacks, max_entries=max_entries)
        return _remaining_zi_io.NodeOutput(input)

class EndRecordCUDAMemoryHistorySecure(_remaining_zi_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = _remaining_zi_PERMISSION

    @classmethod
    def define_schema(cls) -> _remaining_zi_io.Schema:
        return _remaining_zi_io.Schema(node_id='EndRecordCUDAMemoryHistorySecure', display_name='🔒 End Recording CUDA Memory History (secure)', category='KJNodes/memory', description='Stops CUDA allocation-history recording and publishes a snapshot under the logical output catalogue.', inputs=[_remaining_zi_io.AnyType.Input('input'), _remaining_zi_io.String.Input('output_path', default='comfy_cuda_memory_history', tooltip='Logical snapshot prefix inside the memory_history output folder.')], outputs=[_remaining_zi_io.AnyType.Output('input', display_name='input'), _remaining_zi_io.String.Output('output_path', display_name='output_path')])

    @classmethod
    async def execute(cls, input, output_path) -> _remaining_zi_io.NodeOutput:
        logical_name = await _remaining_zi_sdk.ctx().profiling.cuda_memory_end(filename_prefix=output_path)
        return _remaining_zi_io.NodeOutput(input, logical_name)

class VisualizeCUDAMemoryHistorySecure(_remaining_zi_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = _remaining_zi_PERMISSION

    @classmethod
    def define_schema(cls) -> _remaining_zi_io.Schema:
        return _remaining_zi_io.Schema(node_id='VisualizeCUDAMemoryHistorySecure', display_name='🔒 Visualize CUDA Memory History (secure)', category='KJNodes/memory', description='Renders a broker-created CUDA memory snapshot to a confined HTML output and returns its logical view URL.', inputs=[_remaining_zi_io.String.Input('snapshot_path')], outputs=[_remaining_zi_io.String.Output('output_path', display_name='output_path')], is_output_node=True)

    @classmethod
    async def execute(cls, snapshot_path) -> _remaining_zi_io.NodeOutput:
        url = await _remaining_zi_sdk.ctx().profiling.cuda_memory_visualize(snapshot_path)
        return _remaining_zi_io.NodeOutput(url)
from comfy_api.latest import io as _remaining_zj_io

class NABLAAttentionKJSecure(_remaining_zj_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zj_io.Schema:
        return _remaining_zj_io.Schema(node_id='NABLAAttentionKJSecure', display_name='🔒 NABLA Attention KJ (secure)', category='KJNodes/experimental', description="Applies KJ's NABLA sparse-attention policy for video models.", is_experimental=True, inputs=[_remaining_zj_io.Model.Input('model'), _remaining_zj_io.Latent.Input('latent'), _remaining_zj_io.Int.Input('window_time', default=11, min=1), _remaining_zj_io.Int.Input('window_width', default=3, min=1), _remaining_zj_io.Int.Input('window_height', default=3, min=1), _remaining_zj_io.Float.Input('sparsity', default=0.9, min=0.0, max=1.0, step=0.01), _remaining_zj_io.Boolean.Input('torch_compile', default=True)], outputs=[_remaining_zj_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, latent, window_time, window_width, window_height, sparsity, torch_compile) -> _remaining_zj_io.NodeOutput:
        patched = await model.patch('nabla_sparse_attention', latent=latent, window_time=window_time, window_width=window_width, window_height=window_height, sparsity=sparsity, compile_attention=torch_compile)
        return _remaining_zj_io.NodeOutput(patched)
from comfy_api.latest import io as _remaining_zl_io

class WanVideoEnhanceAVideoKJSecure(_remaining_zl_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zl_io.Schema:
        return _remaining_zl_io.Schema(node_id='WanVideoEnhanceAVideoKJSecure', display_name='🔒 Wan Video Enhance-A-Video KJ (secure)', category='KJNodes/wan', description="Applies KJ's temporal Enhance-A-Video attention.", is_experimental=True, inputs=[_remaining_zl_io.Model.Input('model'), _remaining_zl_io.Latent.Input('latent'), _remaining_zl_io.Float.Input('weight', default=2.0, min=0.0, max=10.0, step=0.001)], outputs=[_remaining_zl_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, latent, weight) -> _remaining_zl_io.NodeOutput:
        return _remaining_zl_io.NodeOutput(await model.patch('enhance_a_video', latent=latent, architecture='wan', weight=weight))

class LTXVEnhanceAVideoKJSecure(_remaining_zl_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zl_io.Schema:
        return _remaining_zl_io.Schema(node_id='LTXVEnhanceAVideoKJSecure', display_name='🔒 LTXV Enhance-A-Video KJ (secure)', category='KJNodes/ltxv', description="Applies KJ's temporal Enhance-A-Video attention.", is_experimental=True, inputs=[_remaining_zl_io.Model.Input('model'), _remaining_zl_io.Latent.Input('latent'), _remaining_zl_io.Float.Input('weight', default=4.0, min=0.0, max=100.0, step=0.001)], outputs=[_remaining_zl_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, latent, weight) -> _remaining_zl_io.NodeOutput:
        return _remaining_zl_io.NodeOutput(await model.patch('enhance_a_video', latent=latent, architecture='ltx', weight=weight))
from comfy_api.latest import io as _remaining_zm_io

class WanVideoNAGSecure(_remaining_zm_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zm_io.Schema:
        return _remaining_zm_io.Schema(node_id='WanVideoNAGSecure', display_name='🔒 Wan Video NAG (secure)', category='KJNodes/wan', description="Applies KJ's normalized-attention guidance to Wan models.", is_experimental=True, inputs=[_remaining_zm_io.Model.Input('model'), _remaining_zm_io.Conditioning.Input('conditioning'), _remaining_zm_io.Float.Input('nag_scale', default=11.0, min=0.0, max=100.0, step=0.001), _remaining_zm_io.Float.Input('nag_alpha', default=0.25, min=0.0, max=1.0, step=0.001), _remaining_zm_io.Float.Input('nag_tau', default=2.5, min=0.0, max=10.0, step=0.001), _remaining_zm_io.Combo.Input('input_type', options=['default', 'batch'], default='default', optional=True), _remaining_zm_io.Boolean.Input('inplace', default=False, optional=True)], outputs=[_remaining_zm_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, conditioning, nag_scale, nag_alpha, nag_tau, input_type='default', inplace=False) -> _remaining_zm_io.NodeOutput:
        return _remaining_zm_io.NodeOutput(await model.patch('wan_video_nag', conditioning=conditioning, nag_scale=nag_scale, nag_alpha=nag_alpha, nag_tau=nag_tau, input_type=input_type, inplace=inplace))
import re as _remaining_zn_re
from comfy_api.latest import io as _remaining_zn_io
_remaining_zn_IM_START = 151644
_remaining_zn_USER = 872
_remaining_zn_NEWLINE = 198
_remaining_zn_IM_END = 151645
_remaining_zn_WEIGHT_PATTERN = _remaining_zn_re.compile('\\(([^():]+):(-?\\d*\\.?\\d+)\\)')

def _remaining_zn_user_content_span(ids):
    for index in range(len(ids) - 2):
        if ids[index] == _remaining_zn_IM_START and ids[index + 1] == _remaining_zn_USER and (ids[index + 2] == _remaining_zn_NEWLINE):
            start = index + 3
            end = start
            while end < len(ids) and ids[end] != _remaining_zn_IM_END:
                end += 1
            return (start, end)
    return (None, None)

def _remaining_zn_find_subsequence(sequence, subsequence, start, end):
    matches = []
    size = len(subsequence)
    if size == 0:
        return matches
    for index in range(start, end - size + 1):
        if sequence[index:index + size] == subsequence:
            matches.append(index)
    return matches

def _remaining_zn_token_ids(tokens):
    key = next(iter(tokens))
    return [item[0] for item in tokens[key][0]]

class Krea2PromptWeightSecure(_remaining_zn_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zn_io.Schema:
        return _remaining_zn_io.Schema(node_id='Krea2PromptWeightSecure', display_name='🔒 Krea2 Prompt Weight (secure)', category='KJNodes/experimental', description='Applies Krea2 per-token attention weighting and returns the matching conditioning.', is_experimental=True, inputs=[_remaining_zn_io.Clip.Input('clip'), _remaining_zn_io.Model.Input('model'), _remaining_zn_io.String.Input('text', default='', multiline=True), _remaining_zn_io.Float.Input('strength', default=1.0, min=0.0, max=4.0, step=0.05)], outputs=[_remaining_zn_io.Model.Output('model'), _remaining_zn_io.Conditioning.Output('conditioning')])

    @classmethod
    async def execute(cls, clip, model, text, strength) -> _remaining_zn_io.NodeOutput:
        terms = [(match.group(1).strip(), float(match.group(2))) for match in _remaining_zn_WEIGHT_PATTERN.finditer(text)]
        clean = _remaining_zn_WEIGHT_PATTERN.sub(lambda match: match.group(1), text)
        tokens = await clip.tokenize(clean)
        ids = _remaining_zn_token_ids(tokens)
        conditioning = await clip.encode_from_tokens_scheduled(tokens)
        conditioning_length = await conditioning.sequence_length()
        visible_start = len(ids) - conditioning_length
        start, end = _remaining_zn_user_content_span(ids)
        if start is None:
            start, end = (visible_start, len(ids))
        weights = []
        for phrase, weight in terms:
            if weight > 1.0:
                value_factor = 1.0
                key_bias = strength * (weight - 1.0) * 2.0
            else:
                value_factor = 1.0 + strength * (weight - 1.0)
                key_bias = 0.0
            positions = []
            for variant in (' ' + phrase, phrase):
                phrase_ids = _remaining_zn_token_ids(await clip.tokenize(variant))
                phrase_start, phrase_end = _remaining_zn_user_content_span(phrase_ids)
                if phrase_start is None:
                    continue
                phrase_ids = phrase_ids[phrase_start:phrase_end]
                matches = _remaining_zn_find_subsequence(ids, phrase_ids, start, end)
                if matches:
                    for match in matches:
                        positions.extend((match + offset - visible_start for offset in range(len(phrase_ids))))
                    break
            for position in positions:
                if 0 <= position < conditioning_length:
                    weights.append((position, value_factor, key_bias))
        if weights:
            model = await model.patch('krea2_token_weights', weights=weights)
        return _remaining_zn_io.NodeOutput(model, conditioning)
from comfy_api.latest import io as _remaining_zs_io

class Ideogram4OptimizationsKJSecure(_remaining_zs_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zs_io.Schema:
        return _remaining_zs_io.Schema(node_id='Ideogram4OptimizationsKJSecure', display_name='🔒 Ideogram4 Optimizations KJ (secure)', category='KJNodes/experimental', description='Bound Ideogram4 feed-forward and rotary activation memory.', is_experimental=True, inputs=[_remaining_zs_io.Model.Input('model'), _remaining_zs_io.Boolean.Input('chunk_ffn', default=True), _remaining_zs_io.Int.Input('ffn_chunks', default=2, min=1, max=64, step=1), _remaining_zs_io.Int.Input('ffn_seq_threshold', default=1024, min=256, max=65536, step=256), _remaining_zs_io.Boolean.Input('bf16_rope', default=True)], outputs=[_remaining_zs_io.Model.Output('model')])

    @classmethod
    async def execute(cls, model, chunk_ffn, ffn_chunks, ffn_seq_threshold, bf16_rope) -> _remaining_zs_io.NodeOutput:
        return _remaining_zs_io.NodeOutput(await model.patch('ideogram4_optimizations', chunk_ffn=chunk_ffn, ffn_chunks=ffn_chunks, ffn_seq_threshold=ffn_seq_threshold, bf16_rope=bf16_rope))
from comfy_api.latest import io as _remaining_zu_io, sdk as _remaining_zu_sdk
_remaining_zu_DTYPES = ['default', 'target', 'float32', 'float16', 'bfloat16']
_remaining_zu_ATTENTION = ['none', 'sdpa', 'sageattn', 'xformers', 'flashattn']
_remaining_zu_ATTENTION_TRANSFORMS = {'sdpa': 'pytorch', 'sageattn': 'sage', 'xformers': 'xformers', 'flashattn': 'flash'}

def _remaining_zu_validate_name(name, field, *, allow_none=False):
    if allow_none and name in (None, 'none'):
        return True
    if not isinstance(name, str) or not name:
        return f'{field} must be a non-empty catalogue name'
    logical = name.replace('\\', '/')
    if '\x00' in logical or logical.startswith('/') or (len(logical) > 1 and logical[1] == ':') or any((part == '..' for part in logical.split('/'))):
        return f'{field} must be a confined catalogue name'
    return True

class GGUFLoaderKJSecure(_remaining_zu_io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls) -> _remaining_zu_io.Schema:
        return _remaining_zu_io.Schema(node_id='GGUFLoaderKJSecure', display_name='GGUF Loader KJ (secure)', category='KJNodes/model_loaders', description='Load a catalogued GGUF model through the fixed host GGUF module while paths, quantized weights, and patcher stay inside the trusted process.', is_experimental=True, inputs=[_remaining_zu_io.Combo.Input('model_name', options=[], remote=_remaining_zu_io.RemoteOptions(route='/models/gguf/choices', refresh_button=True)), _remaining_zu_io.Combo.Input('extra_model_name', options=['none'], default='none', remote=_remaining_zu_io.RemoteOptions(route='/models/gguf/extra_choices', refresh_button=True)), _remaining_zu_io.Combo.Input('dequant_dtype', options=_remaining_zu_DTYPES, default='default'), _remaining_zu_io.Combo.Input('patch_dtype', options=_remaining_zu_DTYPES, default='default'), _remaining_zu_io.Boolean.Input('patch_on_device', default=False), _remaining_zu_io.Boolean.Input('enable_fp16_accumulation', default=False), _remaining_zu_io.Combo.Input('attention_override', options=_remaining_zu_ATTENTION, default='none')], outputs=[_remaining_zu_io.Model.Output()])

    @classmethod
    def validate_inputs(cls, model_name, extra_model_name='none'):
        checked = _remaining_zu_validate_name(model_name, 'model_name')
        if checked is not True:
            return checked
        return _remaining_zu_validate_name(extra_model_name, 'extra_model_name', allow_none=True)

    @classmethod
    async def execute(cls, model_name, extra_model_name, dequant_dtype, patch_dtype, patch_on_device, enable_fp16_accumulation, attention_override) -> _remaining_zu_io.NodeOutput:
        model = await _remaining_zu_sdk.ctx().models.load_gguf_model(model_name, extra_name=extra_model_name, dequant_dtype=dequant_dtype, patch_dtype=patch_dtype, patch_on_device=patch_on_device)
        if attention_override != 'none':
            model = await model.patch('attention_impl', mode=_remaining_zu_ATTENTION_TRANSFORMS[attention_override], allow_compile=True)
        model = await model.patch('matmul_fp16_accumulation', enabled=enable_fp16_accumulation)
        return _remaining_zu_io.NodeOutput(model)
from comfy_api.latest import io as _remaining_zw_io, sdk as _remaining_zw_sdk

def _remaining_zw_closed_stochastic_steps(input_mode):
    if not isinstance(input_mode, dict):
        raise TypeError('input_mode must be a dynamic-combo mapping')
    step_map = {}
    if 'stochastic_plan' in input_mode:
        plan_str = input_mode['stochastic_plan']
        if not isinstance(plan_str, str):
            raise TypeError('stochastic_plan must be a string')
        for range_spec in plan_str.split(','):
            range_spec = range_spec.strip()
            if not range_spec:
                continue
            try:
                range_part, steps_part = range_spec.split(':')
                start, end = range_part.split('-')
                start, end, steps = (int(start), int(end), int(steps_part))
                for index in range(start, end + 1):
                    step_map[index] = steps
            except ValueError:
                raise ValueError(f"Invalid format in stochastic_plan: '{range_spec}'. Expected format: 'start-end:steps'")
    else:
        range_keys = [key for key in input_mode if isinstance(key, str) and key.startswith('start_step')]
        for start_key in range_keys:
            index = start_key.replace('start_step', '')
            start = input_mode.get(f'start_step{index}')
            end = input_mode.get(f'end_step{index}')
            steps = input_mode.get(f'steps_{index}')
            if start is not None and end is not None and (steps is not None):
                for step in range(start, end + 1):
                    step_map[step] = steps
    return [{'step': step, 'anneal_steps': anneal_steps} for step, anneal_steps in step_map.items()]

def _remaining_zw_input_options():
    defaults = [(2, 5, 3), (6, 14, 1)]
    range_inputs_2 = []
    for index in range(1, 3):
        start, end, steps = defaults[index - 1]
        range_inputs_2.extend([_remaining_zw_io.Int.Input(f'start_step{index}', default=start, min=0, max=999, step=1, tooltip=f'Start step for range {index}'), _remaining_zw_io.Int.Input(f'end_step{index}', default=end, min=0, max=999, step=1, tooltip=f'End step for range {index}'), _remaining_zw_io.Int.Input(f'steps_{index}', default=steps, min=1, max=100, step=1, tooltip=f'Number of P&P steps for range {index}')])
    start, end, steps = defaults[0]
    range_inputs_1 = [_remaining_zw_io.Int.Input('start_step1', default=start, min=0, max=999, step=1, tooltip='Start step for range 1'), _remaining_zw_io.Int.Input('end_step1', default=end, min=0, max=999, step=1, tooltip='End step for range 1'), _remaining_zw_io.Int.Input('steps_1', default=steps, min=1, max=100, step=1, tooltip='Number of P&P steps for range 1')]
    return [_remaining_zw_io.DynamicCombo.Option(key='2 ranges', inputs=range_inputs_2), _remaining_zw_io.DynamicCombo.Option(key='1 range', inputs=range_inputs_1), _remaining_zw_io.DynamicCombo.Option(key='from_string', inputs=[_remaining_zw_io.String.Input('stochastic_plan', default='2-5:3,6-14:1', multiline=True, tooltip="Format: 'start-end:steps,start-end:steps' e.g. '2-5:3,6-14:1'")])]

class SamplerSelfRefineVideoSecure(_remaining_zw_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zw_io.Schema:
        return _remaining_zw_io.Schema(node_id='SamplerSelfRefineVideoSecure', display_name='🔒 Sampler SelfRefineVideo (secure)', category='KJNodes/samplers', description='Construct the experimental Self-Refine Video sampler as an opaque host-owned sampler.', is_experimental=True, inputs=[_remaining_zw_io.DynamicCombo.Input('input_mode', options=_remaining_zw_input_options(), tooltip='How to configure the step plan'), _remaining_zw_io.Float.Input('certain_percentage', default=0.999, min=0.0, max=1.0, step=0.001, round=False, tooltip='Percentage of certain pixels needed to stop refinement.'), _remaining_zw_io.Float.Input('uncertainty_threshold', default=0.2, min=0.0, max=1.0, step=0.01, round=False, tooltip='Uncertainty threshold for a certain pixel.'), _remaining_zw_io.Boolean.Input('verbose', default=False, tooltip='Enable verbose logging during sampling'), _remaining_zw_io.Latent.Input('latent', optional=True, tooltip='Optional latent used only for LTX2 video shape.'), _remaining_zw_io.Int.Input('seed', default=0, min=0, max=18446744073709551615, step=1, tooltip='Seed for stochastic sampling')], outputs=[_remaining_zw_io.Sampler.Output('sampler')])

    @classmethod
    async def execute(cls, input_mode, certain_percentage, uncertainty_threshold, seed, verbose, latent=None) -> _remaining_zw_io.NodeOutput:
        sampler = await _remaining_zw_sdk.SamplerRef.self_refine_video(stochastic_steps=_remaining_zw_closed_stochastic_steps(input_mode), certain_percentage=certain_percentage, uncertainty_threshold=uncertainty_threshold, seed=seed, verbose=verbose, latent=latent)
        return _remaining_zw_io.NodeOutput(sampler)
from comfy_api.latest import io as _remaining_zy_io
_remaining_zy_BACKENDS = ['inductor', 'cudagraphs']
_remaining_zy_MODES = ['default', 'max-autotune', 'max-autotune-no-cudagraphs', 'reduce-overhead']

class TorchCompileVAESecure(_remaining_zy_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zy_io.Schema:
        return _remaining_zy_io.Schema(node_id='TorchCompileVAESecure', display_name='🔒 Torch Compile VAE (secure)', category='KJNodes/torchcompile', is_experimental=True, inputs=[_remaining_zy_io.Vae.Input('vae'), _remaining_zy_io.Combo.Input('backend', options=_remaining_zy_BACKENDS, default='inductor'), _remaining_zy_io.Boolean.Input('fullgraph', default=False), _remaining_zy_io.Combo.Input('mode', options=_remaining_zy_MODES, default='default'), _remaining_zy_io.Boolean.Input('compile_encoder', default=True), _remaining_zy_io.Boolean.Input('compile_decoder', default=True)], outputs=[_remaining_zy_io.Vae.Output(display_name='VAE')])

    @classmethod
    async def execute(cls, vae, backend, fullgraph, mode, compile_encoder, compile_decoder) -> _remaining_zy_io.NodeOutput:
        try:
            compiled = await vae.compile(backend=backend, mode=mode, fullgraph=fullgraph, encoder=compile_encoder, decoder=compile_decoder)
        except Exception as exc:
            raise RuntimeError('Failed to compile model') from exc
        return _remaining_zy_io.NodeOutput(compiled)

class TorchCompileControlNetSecure(_remaining_zy_io.ComfyNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> _remaining_zy_io.Schema:
        return _remaining_zy_io.Schema(node_id='TorchCompileControlNetSecure', display_name='🔒 Torch Compile ControlNet (secure)', category='KJNodes/torchcompile', is_experimental=True, inputs=[_remaining_zy_io.ControlNet.Input('controlnet'), _remaining_zy_io.Combo.Input('backend', options=_remaining_zy_BACKENDS, default='inductor'), _remaining_zy_io.Boolean.Input('fullgraph', default=False), _remaining_zy_io.Combo.Input('mode', options=_remaining_zy_MODES, default='default')], outputs=[_remaining_zy_io.ControlNet.Output(display_name='CONTROL_NET')])

    @classmethod
    async def execute(cls, controlnet, backend, fullgraph, mode) -> _remaining_zy_io.NodeOutput:
        try:
            compiled = await controlnet.compile(backend=backend, mode=mode, fullgraph=fullgraph)
        except Exception as exc:
            raise RuntimeError('Failed to compile model') from exc
        return _remaining_zy_io.NodeOutput(compiled)

NODE_CLASS_MAPPINGS = {
    'PatchModelPatcherOrderSecure': PatchModelPatcherOrderSecure,
    'WanVideoTeaCacheKJSecure': WanVideoTeaCacheKJSecure,
    'ModelPatchTorchSettingsSecure': ModelPatchTorchSettingsSecure,
    'ModelMemoryUsageFactorOverrideSecure': ModelMemoryUsageFactorOverrideSecure,
    'WanChunkFeedForwardSecure': WanChunkFeedForwardSecure,
    'TorchCompileModelAdvancedSecure': TorchCompileModelAdvancedSecure,
    'TorchCompileModelFluxAdvancedV2Secure': TorchCompileModelFluxAdvancedV2Secure,
    'TorchCompileModelWanVideoV2Secure': TorchCompileModelWanVideoV2Secure,
    'CFGZeroStarAndInitSecure': CFGZeroStarAndInitSecure,
    'PiDColorBiasCorrectionSecure': PiDColorBiasCorrectionSecure,
    'ModelMemoryUseReportPatchSecure': ModelMemoryUseReportPatchSecure,
    'SkipLayerGuidanceWanVideoSecure': SkipLayerGuidanceWanVideoSecure,
    'CheckpointLoaderKJSecure': CheckpointLoaderKJSecure,
    'DiffusionModelSelectorSecure': DiffusionModelSelectorSecure,
    'DiffusionModelLoaderKJSecure': DiffusionModelLoaderKJSecure,
    'PathchSageAttentionKJSecure': PathchSageAttentionKJSecure,
    'PatchFlashAttentionKJSecure': PatchFlashAttentionKJSecure,
    'StartRecordCUDAMemoryHistorySecure': StartRecordCUDAMemoryHistorySecure,
    'EndRecordCUDAMemoryHistorySecure': EndRecordCUDAMemoryHistorySecure,
    'VisualizeCUDAMemoryHistorySecure': VisualizeCUDAMemoryHistorySecure,
    'NABLAAttentionKJSecure': NABLAAttentionKJSecure,
    'WanVideoEnhanceAVideoKJSecure': WanVideoEnhanceAVideoKJSecure,
    'LTXVEnhanceAVideoKJSecure': LTXVEnhanceAVideoKJSecure,
    'WanVideoNAGSecure': WanVideoNAGSecure,
    'Krea2PromptWeightSecure': Krea2PromptWeightSecure,
    'Ideogram4OptimizationsKJSecure': Ideogram4OptimizationsKJSecure,
    'GGUFLoaderKJSecure': GGUFLoaderKJSecure,
    'SamplerSelfRefineVideoSecure': SamplerSelfRefineVideoSecure,
    'TorchCompileVAESecure': TorchCompileVAESecure,
    'TorchCompileControlNetSecure': TorchCompileControlNetSecure,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    'PatchModelPatcherOrderSecure': '🔒 Patch Model Patcher Order (secure)',
    'WanVideoTeaCacheKJSecure': '🔒 WanVideo Tea Cache (KJ) (secure)',
    'ModelPatchTorchSettingsSecure': '🔒 Model Patch Torch Settings (secure)',
    'ModelMemoryUsageFactorOverrideSecure': '🔒 Model Memory Usage Factor Override (secure)',
    'WanChunkFeedForwardSecure': '🔒 Wan Chunk FeedForward (secure)',
    'TorchCompileModelAdvancedSecure': '🔒 Torch Compile Model Advanced (secure)',
    'TorchCompileModelFluxAdvancedV2Secure': '🔒 Torch Compile Model Flux Advanced V2 (secure)',
    'TorchCompileModelWanVideoV2Secure': '🔒 Torch Compile Model Wan Video V2 (secure)',
    'CFGZeroStarAndInitSecure': '🔒 CFG-Zero* And Init (secure)',
    'PiDColorBiasCorrectionSecure': '🔒 PiD Color Bias Correction (secure)',
    'ModelMemoryUseReportPatchSecure': '🔒 Model Memory Use Report Patch (secure)',
    'SkipLayerGuidanceWanVideoSecure': '🔒 Skip Layer Guidance Wan Video (secure)',
    'CheckpointLoaderKJSecure': 'Checkpoint Loader KJ (secure)',
    'DiffusionModelSelectorSecure': 'Diffusion Model Selector (secure)',
    'DiffusionModelLoaderKJSecure': 'Diffusion Model Loader KJ (secure)',
    'PathchSageAttentionKJSecure': '🔒 Patch Sage Attention KJ (secure)',
    'PatchFlashAttentionKJSecure': '🔒 Patch Flash Attention KJ (secure)',
    'StartRecordCUDAMemoryHistorySecure': '🔒 Start Recording CUDA Memory History (secure)',
    'EndRecordCUDAMemoryHistorySecure': '🔒 End Recording CUDA Memory History (secure)',
    'VisualizeCUDAMemoryHistorySecure': '🔒 Visualize CUDA Memory History (secure)',
    'NABLAAttentionKJSecure': '🔒 NABLA Attention KJ (secure)',
    'WanVideoEnhanceAVideoKJSecure': '🔒 Wan Video Enhance-A-Video KJ (secure)',
    'LTXVEnhanceAVideoKJSecure': '🔒 LTXV Enhance-A-Video KJ (secure)',
    'WanVideoNAGSecure': '🔒 Wan Video NAG (secure)',
    'Krea2PromptWeightSecure': '🔒 Krea2 Prompt Weight (secure)',
    'Ideogram4OptimizationsKJSecure': '🔒 Ideogram4 Optimizations KJ (secure)',
    'GGUFLoaderKJSecure': 'GGUF Loader KJ (secure)',
    'SamplerSelfRefineVideoSecure': '🔒 Sampler SelfRefineVideo (secure)',
    'TorchCompileVAESecure': '🔒 Torch Compile VAE (secure)',
    'TorchCompileControlNetSecure': '🔒 Torch Compile ControlNet (secure)',
}
