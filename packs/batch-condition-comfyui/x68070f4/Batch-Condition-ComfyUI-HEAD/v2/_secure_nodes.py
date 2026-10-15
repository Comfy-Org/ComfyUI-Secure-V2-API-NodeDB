"""Pinned batch conditioning math; opaque CLIP and bounded fresh tensor data."""
import math
import torch
from comfy_api.latest import io, sdk

MAX_TEXTS = 64
MAX_TEXT_BYTES = 1024 * 1024
MAX_LCM = 65536
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_WORK_BYTES = 192 * 1024 * 1024

def text_bound(text):
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    size = len(text.encode("utf-8"))
    if size > MAX_TEXT_BYTES:
        raise ValueError("text byte budget exceeded")
    return size

def texts_bound(texts):
    if not isinstance(texts, (list, tuple)):
        raise TypeError("texts must be a sequence")
    if len(texts) > MAX_TEXTS:
        raise ValueError("text count budget exceeded")
    if sum(text_bound(text) for text in texts) > MAX_TEXT_BYTES:
        raise ValueError("aggregate text byte budget exceeded")

def tensor_bytes(tensor):
    if not isinstance(tensor, torch.Tensor) or tensor.layout != torch.strided:
        raise TypeError("dense encoding tensor required")
    return max(tensor.numel() * tensor.element_size(), tensor.untyped_storage().nbytes())

def repeat_batch(conds, pooleds):
    # Preserve the native empty-list IndexError and zero-length division error.
    lengths = [cond.shape[1] for cond in conds]
    common = lengths[0]
    for length in lengths[1:]:
        common = common * length // math.gcd(common, length)
        if common > MAX_LCM:
            raise ValueError("LCM token budget exceeded")
    if common > MAX_LCM:
        raise ValueError("LCM token budget exceeded")
    repeats = [common // length for length in lengths]
    input_bytes = sum(tensor_bytes(t) for t in (*conds, *pooleds))
    projected = sum(cond.numel() * repeat * cond.element_size()
                    for cond, repeat in zip(conds, repeats))
    projected += sum(pool.numel() * pool.element_size() for pool in pooleds)
    if input_bytes > MAX_INPUT_BYTES or projected > MAX_OUTPUT_BYTES:
        raise ValueError("embedding input/output byte budget exceeded")
    if input_bytes + 3 * projected > MAX_WORK_BYTES:
        raise ValueError("embedding workspace byte budget exceeded")
    result = torch.cat([cond.repeat(1, repeat, 1)
                        for cond, repeat in zip(conds, repeats)])
    pool = torch.cat(pooleds)
    return [[result, {"pooled_output": pool}]]

class CLIPTextEncodeBatch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="CLIP Text Encode (Batch)", category="conditioning_batch",
                         inputs=[io.Clip.Input("clip"), io.Custom("BATCH_STRING").Input("texts")],
                         outputs=[io.Conditioning.Output()])

    @classmethod
    async def execute(cls, clip, texts):
        texts_bound(texts)
        conds, pooleds = [], []
        collected_bytes = 0
        for text in texts:
            tokens = await clip.tokenize(text)
            encoded = await clip.encode_from_tokens(tokens)
            row = (await encoded.value())[0]
            cond, pool = row[0], row[1]["pooled_output"]
            collected_bytes += tensor_bytes(cond) + tensor_bytes(pool)
            if collected_bytes > MAX_INPUT_BYTES:
                raise ValueError("embedding input byte budget exceeded")
            conds.append(cond)
            pooleds.append(pool)
        return io.NodeOutput(await sdk.CondRef.from_value(repeat_batch(conds, pooleds)))

class StringInput(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="String Input", category="conditioning_batch",
                         inputs=[io.String.Input("text", multiline=True)],
                         outputs=[io.String.Output()])

    @classmethod
    def execute(cls, text):
        text_bound(text)
        return io.NodeOutput(text)

class BatchString(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="Batch String", category="conditioning_batch", inputs=[],
                         outputs=[io.Custom("BATCH_STRING").Output()], accept_all_inputs=True)

    @classmethod
    def execute(cls, **kwargs):
        if len(kwargs) > MAX_TEXTS:
            raise ValueError("text count budget exceeded")
        texts = [kwargs[f"text{i+1}"] for i in range(len(kwargs))]
        texts_bound(texts)
        return io.NodeOutput(texts)

NODE_CLASS_MAPPINGS = {"CLIP Text Encode (Batch)": CLIPTextEncodeBatch,
                       "String Input": StringInput, "Batch String": BatchString}
