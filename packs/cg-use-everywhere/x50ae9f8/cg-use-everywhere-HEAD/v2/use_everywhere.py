"""Secure backend nodes for CG Use Everywhere 7.8.

The pack's broadcast behavior lives in its sandboxed frontend supplier.  These
seven backend definitions deliberately remain the small value/pass-through
nodes from upstream; they do not need access to host graph internals.
"""
from __future__ import annotations

from comfy_api.latest import io


Anything = io.Custom("*")


class SecureNode(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    SDK_REQUIRED_WEIGHTS = ()


class ComboClone(SecureNode):

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Combo Clone",
            category="everywhere",
            display_name="Combo Clone",
            description=(
                "The combo on this node will replicate whatever the output "
                "is connected to"
            ),
            inputs=[
                io.Combo.Input(
                    "combo", options=["connect me to a combo widget"]
                )
            ],
            outputs=[Anything.Output("comboout")],
        )

    @classmethod
    def validate_inputs(cls, **kwargs) -> bool:
        return isinstance(kwargs.get("combo"), str)

    @classmethod
    async def execute(cls, combo) -> io.NodeOutput:
        return io.NodeOutput(combo)


class SimpleString(SecureNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Simple String",
            category="everywhere/deprecated",
            display_name="Simple String",
            description="Deprecated - use the core comfy string",
            is_deprecated=True,
            inputs=[io.String.Input("string", default="")],
            outputs=[io.String.Output("stringout")],
        )

    @classmethod
    async def execute(cls, string) -> io.NodeOutput:
        return io.NodeOutput(string)


class SeedEverywhere(SecureNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Seed Everywhere",
            category="everywhere/deprecated",
            display_name="Seed Everywhere",
            description="Deprecated - should automatically be replaced",
            is_deprecated=True,
            inputs=[
                io.Int.Input(
                    "seed", default=0, min=0, max=0xFFFFFFFFFFFFFFFF
                )
            ],
            outputs=[io.Int.Output("int")],
        )

    @classmethod
    async def execute(cls, seed) -> io.NodeOutput:
        return io.NodeOutput(seed)


class AnythingEverywhere(SecureNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Anything Everywhere",
            category="everywhere",
            display_name="Anything Everywhere",
            inputs=[Anything.Input("anything", optional=True)],
            outputs=[],
        )

    @classmethod
    async def execute(cls, **kwargs) -> io.NodeOutput:
        return io.NodeOutput()


class AnythingEverywherePrompts(SecureNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Prompts Everywhere",
            category="everywhere/deprecated",
            display_name="Anything Everywhere Prompts",
            description="Deprecated - should automatically be replaced",
            is_deprecated=True,
            inputs=[
                Anything.Input(
                    "positive", display_name="+ve", optional=True
                ),
                Anything.Input(
                    "negative", display_name="-ve", optional=True
                ),
            ],
            outputs=[],
        )

    @classmethod
    async def execute(cls, **kwargs) -> io.NodeOutput:
        return io.NodeOutput()


class AnythingEverywhereTriplet(SecureNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Anything Everywhere3",
            category="everywhere/deprecated",
            display_name="Anything Everywhere Triplet",
            description="Deprecated - should automatically be replaced",
            is_deprecated=True,
            inputs=[
                Anything.Input(
                    "anything", display_name="anything", optional=True
                ),
                Anything.Input(
                    "anything2", display_name="anything2", optional=True
                ),
                Anything.Input(
                    "anything3", display_name="anything3", optional=True
                ),
            ],
            outputs=[],
        )

    @classmethod
    async def execute(cls, **kwargs) -> io.NodeOutput:
        return io.NodeOutput()


class AnythingSomewhere(SecureNode):
    SDK_REFS = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="Anything Everywhere?",
            category="everywhere/deprecated",
            display_name="Anything Somewhere",
            description="Deprecated - should automatically be replaced",
            is_deprecated=True,
            inputs=[
                Anything.Input(
                    "anything", display_name="anything", optional=True
                ),
                io.String.Input("title_regex", default="", optional=True),
                io.String.Input("input_regex", default="", optional=True),
                io.String.Input("group_regex", default="", optional=True),
            ],
            outputs=[],
        )

    @classmethod
    async def execute(cls, **kwargs) -> io.NodeOutput:
        return io.NodeOutput()


NODE_CLASS_MAPPINGS = {
    "Anything Everywhere": AnythingEverywhere,
    "Anything Everywhere?": AnythingSomewhere,
    "Anything Everywhere3": AnythingEverywhereTriplet,
    "Combo Clone": ComboClone,
    "Prompts Everywhere": AnythingEverywherePrompts,
    "Seed Everywhere": SeedEverywhere,
    "Simple String": SimpleString,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    node_id: node_class.GET_SCHEMA().display_name
    for node_id, node_class in NODE_CLASS_MAPPINGS.items()
}
