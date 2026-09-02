from comfy_api.latest import io

# Upstream registered an ON_LOAD callback that reached into the live model
# (``base_model.diffusion_model.blocks``, ``.text_embedding``, ``.img_emb``)
# and called ``.to(device)`` on each module. A sandboxed pack has no model
# object to reach into, and the reaching was never the useful part -- the
# POLICY was: keep the last N transformer blocks resident and park the rest in
# system RAM so a large WAN video model fits on a consumer card.
#
# That policy is ``block_swap`` in the host transform table (D34). Core owns
# which modules the numbers refer to, so this node keeps working when an
# architecture's module names change, and other video architectures get the
# same behaviour without another pack copying this file.
#
# Upstream also hardcoded ``torch.device('cuda')``, which raises on Apple
# Silicon and CPU-only hosts. The host resolves the active compute device
# instead; on CUDA it is identical.


class WanVideoBlockSwap(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ("models",)

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="wanBlockSwap",
            display_name="WanVideoBlockSwap",
            category="ComfyUI-wanBlockswap",
            inputs=[
                io.Model.Input("model"),
                io.Int.Input(
                    "blocks_to_swap", default=20, min=0, max=40, step=1,
                    tooltip="Number of transformer blocks to swap, the 14B "
                            "model has 40, while the 1.3B model has 30 blocks"),
                io.Boolean.Input(
                    "offload_img_emb", default=False,
                    tooltip="Offload img_emb to offload_device"),
                io.Boolean.Input(
                    "offload_txt_emb", default=False,
                    tooltip="Offload txt_emb to offload_device"),
                io.Boolean.Input(
                    "use_non_blocking", default=False,
                    tooltip="Use non-blocking memory transfer for offloading, "
                            "reserves more RAM but is faster"),
            ],
            outputs=[io.Model.Output()],
        )

    @classmethod
    async def execute(
        cls, model, blocks_to_swap, offload_img_emb, offload_txt_emb,
        use_non_blocking,
    ) -> io.NodeOutput:
        # ``patch`` clones host-side, so the caller's model is untouched --
        # the same guarantee upstream's ``model.clone()`` provided.
        return io.NodeOutput(await model.patch(
            "block_swap",
            blocks_to_swap=int(blocks_to_swap),
            offload_img_emb=bool(offload_img_emb),
            offload_txt_emb=bool(offload_txt_emb),
            use_non_blocking=bool(use_non_blocking),
        ))


NODE_CLASS_MAPPINGS = {
    "wanBlockSwap": WanVideoBlockSwap
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "wanBlockSwap": "WanVideoBlockSwap"
}
