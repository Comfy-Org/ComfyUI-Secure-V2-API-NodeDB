"""Secure Nodes V2 registration of ComfyUI-SeedVR2_VideoUpscaler (pin 4490bd1f, v2.5.24).

The pack's four V3 nodes keep their ids and schemas. The schemas are literals in _seedvr2_schemas.py
(see SECURE_CONVERSION.md for the single-GPU device menus). Each node runs upstream's own execute
in the guest:
- SeedVR2TorchCompileSettings: unchanged;
- SeedVR2LoadDiTModel / SeedVR2LoadVAEModel: unchanged, with the executing node id from the SDK
  (src/_sn_context.py);
- SeedVR2VideoUpscaler: before upstream's execute, the two checkpoints its configs name and the
  pack's two text embeddings are fetched through the SDK as declared, sha256-pinned weights and
  supplied to upstream (src/_sn_weights.py).
Upstream modules are imported inside execute, after the pack's compatibility module, in the order
the pack's own __init__.py uses.
"""

from comfy_api.latest import io, sdk

from . import _seedvr2_schemas as schemas
from .src import _sn_weights

DIT_OPTIONS = (
    "seedvr2_ema_3b-Q4_K_M.gguf", "seedvr2_ema_3b-Q8_0.gguf", "seedvr2_ema_3b_fp8_e4m3fn.safetensors",
    "seedvr2_ema_3b_fp16.safetensors", "seedvr2_ema_7b-Q4_K_M.gguf",
    "seedvr2_ema_7b_fp8_e4m3fn_mixed_block35_fp16.safetensors", "seedvr2_ema_7b_fp16.safetensors",
    "seedvr2_ema_7b_sharp-Q4_K_M.gguf", "seedvr2_ema_7b_sharp_fp8_e4m3fn_mixed_block35_fp16.safetensors",
    "seedvr2_ema_7b_sharp_fp16.safetensors",
)


def _upstream():
    """Import the pack the way its __init__.py does: compatibility first, then the nodes."""
    from .src.optimization.compatibility import ensure_triton_compat  # noqa: F401
    from .src import interfaces
    return interfaces


class SeedVR2TorchCompileSettings(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return schemas.SeedVR2TorchCompileSettings_schema()

    @classmethod
    def execute(cls, backend, mode, fullgraph, dynamic, dynamo_cache_size_limit,
                dynamo_recompile_limit):
        return _upstream().SeedVR2TorchCompileSettings.execute(
            backend=backend, mode=mode, fullgraph=fullgraph, dynamic=dynamic,
            dynamo_cache_size_limit=dynamo_cache_size_limit,
            dynamo_recompile_limit=dynamo_recompile_limit)


class SeedVR2LoadDiTModel(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("graph",)

    @classmethod
    def define_schema(cls):
        return schemas.SeedVR2LoadDiTModel_schema()

    @classmethod
    def validate_inputs(cls, model):
        # Taking `model` stops core's own menu check, so repeat it here.
        if model in _sn_weights.GGUF:
            return _sn_weights.gguf_refusal(model)
        if model not in DIT_OPTIONS:
            return f"Value not in list: model: '{model}' not in {list(DIT_OPTIONS)}"
        return True

    @classmethod
    async def execute(cls, model, device, offload_device="none", cache_model=False,
                      blocks_to_swap=0, swap_io_components=False, attention_mode="sdpa",
                      torch_compile_args=None):
        interfaces = _upstream()
        from .src import _sn_context
        node_id = await sdk.ctx().graph.current_node_id()
        with _sn_context.executing(node_id):
            return interfaces.SeedVR2LoadDiTModel.execute(
                model=model, device=device, offload_device=offload_device,
                cache_model=cache_model, blocks_to_swap=blocks_to_swap,
                swap_io_components=swap_io_components, attention_mode=attention_mode,
                torch_compile_args=torch_compile_args)


class SeedVR2LoadVAEModel(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("graph",)

    @classmethod
    def define_schema(cls):
        return schemas.SeedVR2LoadVAEModel_schema()

    @classmethod
    async def execute(cls, model, device, offload_device="none", cache_model=False,
                      encode_tiled=False, encode_tile_size=512, encode_tile_overlap=64,
                      decode_tiled=False, decode_tile_size=512, decode_tile_overlap=64,
                      tile_debug="false", torch_compile_args=None):
        interfaces = _upstream()
        from .src import _sn_context
        node_id = await sdk.ctx().graph.current_node_id()
        with _sn_context.executing(node_id):
            return interfaces.SeedVR2LoadVAEModel.execute(
                model=model, device=device, offload_device=offload_device,
                cache_model=cache_model, encode_tiled=encode_tiled,
                encode_tile_size=encode_tile_size, encode_tile_overlap=encode_tile_overlap,
                decode_tiled=decode_tiled, decode_tile_size=decode_tile_size,
                decode_tile_overlap=decode_tile_overlap, tile_debug=tile_debug,
                torch_compile_args=torch_compile_args)


class SeedVR2VideoUpscaler(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw", "assets", "models.download")
    SDK_REQUIRED_WEIGHTS = (tuple(_sn_weights.WEIGHTS.values())
                            + tuple(_sn_weights.EMBEDDING_WEIGHTS.values()))

    @classmethod
    def define_schema(cls):
        return schemas.SeedVR2VideoUpscaler_schema()

    @classmethod
    async def execute(cls, image, dit, vae, seed, resolution=1080, max_resolution=0, batch_size=5,
                      uniform_batch_size=False, temporal_overlap=0, prepend_frames=0,
                      color_correction="wavelet", input_noise_scale=0.0, latent_noise_scale=0.0,
                      offload_device="none", enable_debug=False):
        # Same defaults as upstream's execute signature: core omits optional inputs a prompt
        # leaves out, and upstream then uses these.
        interfaces = _upstream()
        names = [dit.get("model"), vae.get("model")] if isinstance(dit, dict) and isinstance(vae, dict) else []
        state_dicts = {}
        for name in names:
            if name not in state_dicts:
                state_dicts[name] = await _sn_weights.load(name)
        state_dicts.update(await _sn_weights.load_embeddings())
        with _sn_weights.supplied(state_dicts):
            return interfaces.SeedVR2VideoUpscaler.execute(
                image=image, dit=dit, vae=vae, seed=seed, resolution=resolution,
                max_resolution=max_resolution, batch_size=batch_size,
                uniform_batch_size=uniform_batch_size, temporal_overlap=temporal_overlap,
                prepend_frames=prepend_frames, color_correction=color_correction,
                input_noise_scale=input_noise_scale, latent_noise_scale=latent_noise_scale,
                offload_device=offload_device, enable_debug=enable_debug)


# Upstream's get_node_list() order (src/interfaces/__init__.py:19-24).
NODE_CLASS_MAPPINGS = {
    "SeedVR2VideoUpscaler": SeedVR2VideoUpscaler,
    "SeedVR2LoadDiTModel": SeedVR2LoadDiTModel,
    "SeedVR2LoadVAEModel": SeedVR2LoadVAEModel,
    "SeedVR2TorchCompileSettings": SeedVR2TorchCompileSettings,
}
