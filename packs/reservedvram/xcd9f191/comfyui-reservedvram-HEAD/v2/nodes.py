"""Secure Nodes V2 conversion of comfyui-reservedvram (windecay, pin cd9f1911).

One output node, ReservedVRAMSetter ("Set Reserved VRAM(GB) ⚙️"). The original (pristine nodes.py) optionally frees GPU
memory, then sets ComfyUI's extra reserved VRAM to a manual value or, in auto mode, to the GPU's used memory plus an
offset. It returns its optional input, the seed and the value it set.

V2, in the same order as the original's set_vram:
  * clean_gpu_before: the original's gc.collect(), unload_all_models() and soft_empty_cache() (pristine :155-159) run on
    the host through the public SDK verb models.memory_cleanup, one call per operation so the order is kept
    (permission models.manage).
  * auto mode: the original reads GPU 0's total and used memory through NVML, else through torch.cuda.mem_get_info
    (pristine :31-57). V2 reads the host's primary device through system.stats (permission system.stats). It computes
    used = total - (free - torch_free), which is exactly mem_get_info's (total - free): Core reports
    free = mem_get_info free + torch's reserved-but-inactive bytes. A primary device that is not CUDA gives
    (None, None), as in the original without a GPU.
  * The reservation itself (pristine :59-67, model_management.set_extra_reserved_vram / EXTRA_RESERVED_VRAM): a
    sandboxed pack cannot change the host's memory policy, and the SDK has no verb for it. V2 computes and returns the
    same value and prints the original's message, then says the host setting was not changed (SECURE_CONVERSION.md,
    known difference 1; API ask).
  * output: the optional input comes back unchanged (host handles as the same object). With nothing connected, the
    original returns ComfyUI's ExecutionBlocker(None) (pristine :198-199), which V2 gets from graph.block (permission
    graph.block).
  * IS_CHANGED becomes fingerprint_inputs. Seed -1 draws a new seed from the pack's own time-seeded random state,
    leaving the global random state untouched, as the original does (pristine :24-28, :88-96, :143-148). Any other
    seed is returned as it is.
"""

import random
import time

from comfy_api.latest import io, sdk

_GIB = 1024 * 1024 * 1024

# pristine :24-28: a private random state seeded from the clock, without disturbing the global one
_initial_random_state = random.getstate()
random.seed(time.time())
_reserved_vram_random_state = random.getstate()
random.setstate(_initial_random_state)


def new_random_seed():
    """pristine :88-96"""
    global _reserved_vram_random_state
    prev_random_state = random.getstate()
    random.setstate(_reserved_vram_random_state)
    seed = random.randint(1, 1125899906842624)
    _reserved_vram_random_state = random.getstate()
    random.setstate(prev_random_state)
    return seed


async def get_gpu_memory_info():
    """The host's primary device as (total GB, used GB), or (None, None) when it is not a CUDA device."""
    try:
        stats = await sdk.ctx().system.stats()
        devices = stats.get("devices") or []
        if devices and devices[0].get("type") == "cuda":
            device = devices[0]
            total = int(device["vram_total"])
            free = int(device["vram_free"]) - int(device["torch_vram_free"])
            return total / _GIB, (total - free) / _GIB
    except Exception as e:  # the original prints and falls back (pristine :55-56)
        print(f"[ReservedVRAM]获取GPU信息出错(torch): {e}")
    return None, None


def _host_setting_unchanged(reserved_gb):
    print(f"[ReservedVRAM]Secure Nodes V2: the host's reserved VRAM is not changed by this node "
          f"(requested {max(0.0, float(reserved_gb))}GB); see SECURE_CONVERSION.md")


class ReservedVRAMSetter(io.ComfyNode):
    # The passthrough value travels as a host handle, so it comes back as the same object.
    SDK_REFS = True
    SDK_PERMISSIONS = ("models.manage", "system.stats", "graph.block")

    @classmethod
    def define_schema(cls):
        # pristine :105-134; the original's "display" option strings are kept verbatim for the frontend
        return io.Schema(
            node_id="ReservedVRAMSetter",
            display_name="Set Reserved VRAM(GB) ⚙️",
            category="VRAM",
            inputs=[
                io.Float.Input("reserved", default=0.6, min=-2.0, step=0.1,
                               extra_dict={"display": "reserved (GB)"}),
                io.Combo.Input("mode", options=["manual", "auto"], default="auto",
                               extra_dict={"display": "Mode"}),
                io.Int.Input("seed", default=0, min=-1, max=1125899906842624),
                io.Float.Input("auto_max_reserved", default=0.0, min=0.0, step=0.1,
                               extra_dict={"display": "Auto Max Reserved (GB, 0=no limit)"}),
                io.Boolean.Input("clean_gpu_before", default=True),
                io.AnyType.Input("anything", optional=True),
            ],
            outputs=[
                io.AnyType.Output("output", display_name="output"),
                io.Int.Output("SEED", display_name="SEED"),
                io.Float.Output("Reserved_GB", display_name="Reserved(GB)"),
            ],
            hidden=[io.Hidden.unique_id, io.Hidden.extra_pnginfo],
            is_output_node=True,
        )

    @classmethod
    def fingerprint_inputs(cls, seed=0, **kwargs):
        # pristine :143-148
        if seed == -1:
            return new_random_seed()
        return seed

    @classmethod
    async def execute(cls, reserved, mode="auto", seed=0, auto_max_reserved=0.0, clean_gpu_before=True,
                      anything=None):
        # pristine :160-201, line for line; only the host operations go through the SDK
        if clean_gpu_before:
            print("[ReservedVRAM]执行前置GPU显存清理...")
            models = sdk.ctx().models
            # cleanGPUUsedForce (pristine :155-159): gc.collect(), unload_all_models(), soft_empty_cache()
            await models.memory_cleanup(empty_cache=False, collect_cycles=True, unload_all_models=False)
            await models.memory_cleanup(empty_cache=False, collect_cycles=False, unload_all_models=True)
            await models.memory_cleanup(empty_cache=True, collect_cycles=False, unload_all_models=False)
            print("[ReservedVRAM]GPU显存清理完成")

        final_reserved_vram = 0.0

        if mode == "auto":
            total, used = await get_gpu_memory_info()
            if total is not None and used is not None:
                auto_reserved = used + reserved
                auto_reserved = max(0, auto_reserved)
                if auto_max_reserved > 0:
                    auto_reserved = min(auto_reserved, auto_max_reserved)
                    print(f'[ReservedVRAM]set EXTRA_RESERVED_VRAM={auto_reserved:.2f}GB (自动模式: 总显存={total:.2f}GB, 已用={used:.2f}GB, 最大限制值{auto_max_reserved:.2f}GB)')
                else:
                    print(f'[ReservedVRAM]set EXTRA_RESERVED_VRAM={auto_reserved:.2f}GB (自动模式: 总显存={total:.2f}GB, 已用={used:.2f}GB)')
                _host_setting_unchanged(auto_reserved)
                final_reserved_vram = round(auto_reserved, 2)
            else:
                manual_reserved = max(0, reserved)
                _host_setting_unchanged(manual_reserved)
                print(f'[ReservedVRAM]set EXTRA_RESERVED_VRAM={manual_reserved}GB (自动模式不可用，使用手动值)')
                final_reserved_vram = round(manual_reserved, 2)
        else:
            reserved = max(0, reserved)
            _host_setting_unchanged(reserved)
            print(f'[ReservedVRAM]set EXTRA_RESERVED_VRAM={reserved}GB (手动模式)，忽略最大限制值')
            final_reserved_vram = round(reserved, 2)

        output_value = anything if anything is not None else await sdk.ctx().graph.block(None)

        return io.NodeOutput(output_value, seed, final_reserved_vram)


NODE_CLASS_MAPPINGS = {
    "ReservedVRAMSetter": ReservedVRAMSetter,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ReservedVRAMSetter": "Set Reserved VRAM(GB) ⚙️",
}
