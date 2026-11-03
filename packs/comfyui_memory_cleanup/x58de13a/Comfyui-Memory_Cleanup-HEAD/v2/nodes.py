"""Secure Nodes V2 conversion of Comfyui-Memory_Cleanup (LAOGOU-666, pin 58de13a6).

Two output nodes. Each returns its optional ``anything`` input unchanged: host handles as the same object, plain
values equal (they cross the sandbox boundary by value).

* VRAMCleanup (pristine ``__init__.py:20-63``)
  - The original calls ``comfy.model_management.unload_all_models()`` when ``offload_model``, then ``gc.collect()``,
    ``soft_empty_cache()`` and the prompt queue's ``free_memory`` flag when ``offload_cache``.
  - V2 asks the host for the same operations, in the same order, through the public ``models.memory_cleanup`` verb
    (permission ``models.manage``): one call per operation, so the order unload, collect, empty is kept.
  - The guest has no PromptServer, so it cannot set the ``free_memory`` flag. See SECURE_CONVERSION.md.
* RAMCleanup (pristine ``:66-152``)
  - The original trims OS working sets and the file cache of host processes through ctypes/psutil, sleeping 1 s per
    retry.
  - A sandboxed pack cannot touch host processes, so V2 passes the value through and only reports that the trim was
    skipped (a known difference; outputs are unaffected).

Both nodes keep the original IS_CHANGED, which returns the current time (``:43-46``, ``:97-100``). The node therefore
re-executes on every queue, and so do the nodes downstream of it, exactly as with the original.
"""

import time

from comfy_api.latest import io, sdk

CATEGORY = "Memory Management"


def _hidden():
    # The original declares exactly these two hidden inputs (pristine :31-34, :85-88).
    return [io.Hidden.unique_id, io.Hidden.extra_pnginfo]


class VRAMCleanup(io.ComfyNode):
    # The passthrough value travels as a host handle, so it comes back as the same object.
    SDK_REFS = True
    SDK_PERMISSIONS = ("models.manage",)

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="VRAMCleanup",
            display_name="🎈VRAM-Cleanup",
            category=CATEGORY,
            inputs=[
                io.Boolean.Input("offload_model", default=True),
                io.Boolean.Input("offload_cache", default=True),
                io.AnyType.Input("anything", optional=True),
            ],
            outputs=[io.AnyType.Output("output", display_name="output")],
            hidden=_hidden(),
            is_output_node=True,
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        # Original IS_CHANGED: "return the current timestamp so it always executes".
        return float(time.time())

    @classmethod
    async def execute(cls, offload_model, offload_cache, anything=None):
        try:
            models = sdk.ctx().models
            if offload_model:
                await models.memory_cleanup(empty_cache=False, collect_cycles=False, unload_all_models=True)
            if offload_cache:
                await models.memory_cleanup(empty_cache=False, collect_cycles=True, unload_all_models=False)
                await models.memory_cleanup(empty_cache=True, collect_cycles=False, unload_all_models=False)
            print(f"VRAM清理完成 [卸载模型: {offload_model}, 清空缓存: {offload_cache}]")
        except Exception as e:  # the original swallows every failure and still passes the value through
            print(f"VRAM清理失败: {str(e)}")
        return io.NodeOutput(anything)


class RAMCleanup(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="RAMCleanup",
            display_name="🎈RAM-Cleanup",
            category=CATEGORY,
            inputs=[
                # The original passes a frontend "label" option with each widget; keep it byte-for-byte.
                io.Boolean.Input("clean_file_cache", default=True, extra_dict={"label": "清理文件缓存"}),
                io.Boolean.Input("clean_processes", default=True, extra_dict={"label": "清理进程内存"}),
                io.Boolean.Input("clean_dlls", default=True, extra_dict={"label": "清理未使用DLL"}),
                io.Int.Input("retry_times", default=3, min=1, max=10, step=1, extra_dict={"label": "重试次数"}),
                io.AnyType.Input("anything", optional=True),
            ],
            outputs=[io.AnyType.Output("output", display_name="output")],
            hidden=_hidden(),
            is_output_node=True,
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return float(time.time())

    @classmethod
    async def execute(cls, clean_file_cache, clean_processes, clean_dlls, retry_times, anything=None):
        print("RAM清理已跳过: Secure Nodes 运行时不允许插件清理宿主进程的系统内存 "
              "(OS-level RAM trimming is not available to sandboxed packs; value passed through)")
        return io.NodeOutput(anything)


NODE_CLASS_MAPPINGS = {
    "VRAMCleanup": VRAMCleanup,
    "RAMCleanup": RAMCleanup,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VRAMCleanup": "🎈VRAM-Cleanup",
    "RAMCleanup": "🎈RAM-Cleanup",
}
