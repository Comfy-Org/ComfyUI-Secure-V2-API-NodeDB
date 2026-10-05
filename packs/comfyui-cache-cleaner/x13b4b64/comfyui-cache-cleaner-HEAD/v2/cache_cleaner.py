"""Permissioned cache cleanup without loopback HTTP or server disclosure."""

from comfy_api.latest import io, sdk


class CacheCleaner(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models.manage",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="CacheCleaner",
            display_name="Cache Cleaner",
            category="utils/system",
            description=(
                "Free model and application memory when requested, while "
                "passing optional workflow values through unchanged."
            ),
            inputs=[
                io.Boolean.Input("clean_cache", default=True),
                io.AnyType.Input("anything", optional=True),
                io.Image.Input("image_pass", optional=True),
                io.Model.Input("model_pass", optional=True),
            ],
            outputs=[
                io.AnyType.Output("anything"),
                io.Image.Output("image_pass"),
                io.Model.Output("model_pass"),
                io.String.Output("status"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        clean_cache: bool,
        anything=None,
        image_pass=None,
        model_pass=None,
    ) -> io.NodeOutput:
        if clean_cache:
            try:
                await sdk.ctx().models.memory_cleanup(
                    empty_cache=True,
                    collect_cycles=True,
                    unload_all_models=True,
                )
                message = "Cache cleaned successfully"
            except Exception as error:
                message = f"Error: Failed to clean cache - {error}"
        else:
            message = "Cache cleaning skipped"

        # The legacy node disclosed PromptServer's bind address in this status.
        # Secure/cloud guests intentionally cannot discover it. Keep the two-line
        # human-readable result while identifying the brokered boundary instead.
        status = f"Status: {message}\nServer address: managed by secure host"
        return io.NodeOutput(anything, image_pass, model_pass, status)


NODE_CLASS_MAPPINGS = {"CacheCleaner": CacheCleaner}
NODE_DISPLAY_NAME_MAPPINGS = {"CacheCleaner": "Cache Cleaner"}
