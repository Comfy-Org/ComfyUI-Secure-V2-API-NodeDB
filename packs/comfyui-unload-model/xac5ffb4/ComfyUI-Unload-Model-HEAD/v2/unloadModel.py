from comfy_api.latest import io, sdk

# Upstream reached into ``comfy.model_management`` and ``torch.cuda`` directly.
# Freeing application memory is a whole-application effect, so in V2 it is one
# closed broker operation gated on the ``models.manage`` permission plus
# per-pack user consent. The guest never sees the host's loaded-model registry.
#
# Upstream also hand-rolled ``AnyType("*")`` to build a wildcard socket string;
# ``io.AnyType`` is that wire type, so the shim is gone.


async def _free_application_memory() -> None:
    """Ask the host to release model memory. Nothing is returned to the guest."""
    await sdk.ctx().models.memory_cleanup(
        empty_cache=True,
        collect_cycles=True,
        unload_all_models=True,
    )


class UnloadModelNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models.manage",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="UnloadModel",
            display_name="Unload Model",
            category="Unload Model",
            description=(
                "Free model memory at this point in the workflow, passing "
                "`value` through unchanged."
            ),
            inputs=[
                io.AnyType.Input("value"),
                io.AnyType.Input("model", optional=True),
            ],
            outputs=[io.AnyType.Output("value")],
        )

    @classmethod
    async def execute(cls, value, model=None) -> io.NodeOutput:
        # ``model`` is still accepted so existing workflows keep their link,
        # but it selects nothing -- and it never did. Upstream passed
        # ``loaded_models()`` (a list of ModelPatchers) as ``free_memory``'s
        # ``keep_loaded``, which is membership-tested against LoadedModel
        # wrappers. ``LoadedModel.__eq__`` is ``self.model is other.model``,
        # comparing a ModelPatcher against a ModelPatcher's ``.model``, so the
        # test is always False and upstream already frees every model on the
        # device. test_unload_model_pack_conversion.py pins that against the
        # real core classes.
        await _free_application_memory()
        return io.NodeOutput(value)


class UnloadAllModelsNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models.manage",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="UnloadAllModels",
            display_name="Unload All Models",
            category="Unload Model",
            description=(
                "Free all model memory at this point in the workflow, passing "
                "`value` through unchanged."
            ),
            inputs=[io.AnyType.Input("value")],
            outputs=[io.AnyType.Output("value")],
        )

    @classmethod
    async def execute(cls, value) -> io.NodeOutput:
        await _free_application_memory()
        return io.NodeOutput(value)


NODE_CLASS_MAPPINGS = {
    "UnloadModel": UnloadModelNode,
    "UnloadAllModels": UnloadAllModelsNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "UnloadModel": "Unload Model",
    "UnloadAllModels": "Unload All Models",
}
