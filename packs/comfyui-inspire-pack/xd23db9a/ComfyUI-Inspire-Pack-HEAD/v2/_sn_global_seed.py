"""Global Seed (Inspire), Secure Nodes V2 (round 2).

The original node (inspire/prompt_support.py GlobalSeed) is an output node with no outputs whose `doit`
returns {}; the seeds are controlled around it, before the prompt runs. Here the node is the same: same id,
inputs, display name and category, and it does nothing when executed. The control itself is web/global_seed.js
(see SECURE_CONVERSION.md, "Round 2: Global Seed").
"""

from comfy_api.latest import io

ACTIONS = ["fixed", "increment", "decrement", "randomize",
           "increment for each node", "decrement for each node", "randomize for each node"]


class GlobalSeed(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="GlobalSeed //Inspire",
            display_name="Global Seed (Inspire)",
            category="InspirePack/Prompt",
            inputs=[
                io.Int.Input("value", default=0, min=0, max=0xffffffffffffffff),
                io.Boolean.Input("mode", default=True, label_on="control_before_generate",
                                 label_off="control_after_generate"),
                io.Combo.Input("action", options=ACTIONS),
                io.String.Input("last_seed", default=""),
            ],
            outputs=[],
            is_output_node=True,
        )

    @classmethod
    def execute(cls, value, mode, action, last_seed) -> io.NodeOutput:
        del value, mode, action, last_seed  # the original's doit(**kwargs) returns {}
        return io.NodeOutput()
