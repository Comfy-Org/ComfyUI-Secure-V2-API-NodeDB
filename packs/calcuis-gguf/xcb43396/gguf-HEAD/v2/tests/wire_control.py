"""Synthetic technical probes, NOT registered production nodes/model evidence."""
import json
import torch
from comfy_api.latest import io, sdk


class StateDictWireControl(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw", "output")

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="StateDictWireControl", inputs=[], outputs=[io.String.Output()])

    @classmethod
    async def execute(cls):
        state = {"vector": torch.arange(6, dtype=torch.float32).reshape(2, 3), "scalar": torch.tensor(7, dtype=torch.int64)}
        ref = await sdk.ValueRef.from_value(state)
        reread = await ref.value()
        if set(reread) != set(state) or any(not torch.equal(reread[k], state[k]) for k in state):
            raise AssertionError("public structured ref changed tensor values")
        artifact = await sdk.ctx().output.save_state_dict(ref, "moe-synthetic-gguf-wire", metadata={"probe": "synthetic-only"})
        return io.NodeOutput(json.dumps({"artifact": artifact, "ref_kind": ref.kind, "tensor_keys": sorted(state)}))


class RangeWireControl(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("assets",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="RangeWireControl", inputs=[], outputs=[io.String.Output()])

    @classmethod
    async def execute(cls):
        asset = await sdk.ctx().assets.resolve("checkpoints", "fixture.gguf")
        size = await sdk.ctx().assets.size(asset)
        value = await sdk.ctx().assets.read_range(asset, 3, 5)
        return io.NodeOutput(json.dumps({"size": size, "bytes": list(value), "return_type": type(value).__name__}))


class ExistingModelBoundaryControl(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('models',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='ExistingModelBoundaryControl', inputs=[], outputs=[io.String.Output()])

    @classmethod
    async def execute(cls):
        observed = {}
        attempts = (
            ('gguf_service', lambda: sdk.ctx().models.load_gguf_model('synthetic.gguf')),
            ('gguf_device_argument', lambda: sdk.ctx().models.load_gguf_text_encoders(['synthetic.gguf'], 'stable_diffusion', device='cpu')),
            ('audio_public_member', lambda: sdk.ctx().models.load_audio_encoder('synthetic.safetensors')),
        )
        for name, call in attempts:
            try:
                await call()
            except Exception as error:
                observed[name] = {'exception': type(error).__name__, 'message': str(error)}
            else:
                raise AssertionError('unexpected success must be reviewed, not called compatible')
        return io.NodeOutput(json.dumps(observed))
