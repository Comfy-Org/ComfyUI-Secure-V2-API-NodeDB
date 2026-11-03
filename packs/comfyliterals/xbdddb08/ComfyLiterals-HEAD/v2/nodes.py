"""Secure Nodes V2 conversion of ComfyLiterals nodes.py (M1kep, pin bdddb08c).

Every value-handling line is the original's; only the node declarations change (V1 INPUT_TYPES → V3 schemas).
The Checkpoint/Lora list literals pre-fill their text box with the host's checkpoint/LoRA file names when a new node is
created (pristine nodes.py:92, :120). A V2 schema is static, so the default is empty; saved workflows carry their own
text and parse exactly as before. See SECURE_CONVERSION.md.
"""

from comfy_api.latest import io


class IntLiteral(io.ComfyNode):
    # Pure value node: inputs arrive as plain values, and it uses no host capability.
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Int",
            display_name="Int",
            category="Literals",
            inputs=[io.String.Input("Number")],
            outputs=[io.Int.Output()],
        )

    @classmethod
    def execute(cls, Number):
        try:
            ret_val = int(Number)
        except Exception:
            raise Exception("Invalid value provided for INT")
        return io.NodeOutput(ret_val)


class FloatLiteral(io.ComfyNode):
    # Pure value node: inputs arrive as plain values, and it uses no host capability.
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Float",
            display_name="Float",
            category="Literals",
            inputs=[io.String.Input("Number")],
            outputs=[io.Float.Output()],
        )

    @classmethod
    def execute(cls, Number):
        try:
            ret_val = float(Number)
        except Exception:
            raise Exception("Invalid value provided for FLOAT")
        return io.NodeOutput(ret_val)


class StringLiteral(io.ComfyNode):
    # Pure value node: inputs arrive as plain values, and it uses no host capability.
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    NODE_ID = "String"
    DISPLAY_NAME = "String"

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=cls.NODE_ID,
            display_name=cls.DISPLAY_NAME,
            category="Literals",
            inputs=[io.String.Input("String", multiline=True)],
            outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, String):
        return io.NodeOutput(String)


class KepStringLiteral(io.ComfyNode):
    # The original registers the same StringLiteral class under a second id ("KepStringLiteral", shown as "String").
    # A standalone class, not a subclass: V3 caches schema-derived class attributes (RETURN_NAMES, CATEGORY, ...) on
    # the class, and a subclass would inherit the parent's cached values.
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="KepStringLiteral",
            display_name="String",
            category="Literals",
            inputs=[io.String.Input("String", multiline=True)],
            outputs=[io.String.Output()],
        )

    @classmethod
    def execute(cls, String):
        return io.NodeOutput(String)


class CheckpointListLiteral(io.ComfyNode):
    # Pure value node: inputs arrive as plain values, and it uses no host capability.
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    NODE_ID = "Checkpoint"
    OUTPUT_NAME = "Selected Checkpoints"

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id=cls.NODE_ID,
            display_name=cls.NODE_ID,
            category="List Stuff",
            inputs=[io.String.Input("literal", multiline=True, default="")],
            outputs=[io.AnyType.Output("output", display_name=cls.OUTPUT_NAME, is_output_list=True)],
        )

    @classmethod
    def execute(cls, literal):
        split = list(filter(None, literal.split("\n")))
        return io.NodeOutput(split)


class LoraListLiteral(io.ComfyNode):
    # Standalone for the same reason as KepStringLiteral.
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Lora",
            display_name="Lora",
            category="List Stuff",
            inputs=[io.String.Input("literal", multiline=True, default="")],
            outputs=[io.AnyType.Output("output", display_name="Selected Loras", is_output_list=True)],
        )

    @classmethod
    def execute(cls, literal):
        split = list(filter(None, literal.split("\n")))
        return io.NodeOutput(split)
