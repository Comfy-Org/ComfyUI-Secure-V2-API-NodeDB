"""Native Alpha/Zero conversion preparation; publication needs a real owner API."""
from dataclasses import dataclass
from .binary_writer import BinaryWriter
from .bounds import logical_name, state_bounds
from .encoding_math import detect_arch, handle_tensors
from .gguf_math.const import GGML_QUANT_VERSION, LlamaFileType
import json
import posixpath
from pathlib import Path
import torch

ZERO_ARCHITECTURE = json.loads(Path(__file__).with_name('version.json').read_text())[0]['TXT_ARCH_LIST'][0]


def alpha_state(state):
    """Exact legacy prefix priority, containment filter and replace-all behavior."""
    prefix = None
    for candidate in ('model.diffusion_model.', 'model.', 'net.'):
        if any(key.startswith(candidate) for key in state):
            prefix = candidate
            break
    result = {}
    for key, value in state.items():
        if prefix and prefix not in key:
            continue
        result[key.replace(prefix, '') if prefix else key] = value
    return result


@dataclass(frozen=True)
class ConversionArtifact:
    filename: str
    writer: BinaryWriter
    mode: str

    def close(self):
        self.writer.close()


def prepare_conversion(state, logical_source, *, mode):
    """Encode actual tensors; never claims that an artifact was committed.

    Zero architecture comes from this pack's immutable version.json, as native.
    """
    logical_name(logical_source)
    state_bounds(state)
    if mode == 'alpha':
        state = alpha_state(state)
        model_arch = detect_arch(state)
        architecture = model_arch.arch
    elif mode == 'zero':
        state = dict(state)
        architecture = model_arch = ZERO_ARCHITECTURE
    else:
        raise ValueError('conversion mode must be alpha or zero')
    # Preserve native first-tensor dtype selection after the existing state guard.
    bf16 = next(iter(state.values())).dtype == torch.bfloat16
    filename = posixpath.splitext(logical_source)[0] + ('-bf16.gguf' if bf16 else '-f16.gguf')
    writer = BinaryWriter(architecture)
    try:
        writer.add_quantization_version(GGML_QUANT_VERSION)
        writer.add_file_type(int(LlamaFileType.MOSTLY_BF16 if bf16 else LlamaFileType.MOSTLY_F16))
        handle_tensors(filename, writer, state, model_arch)
        return ConversionArtifact(filename, writer, mode)
    except BaseException:
        writer.close()
        raise
