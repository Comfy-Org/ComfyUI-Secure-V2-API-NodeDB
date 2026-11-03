"""Secure Nodes V2 conversion of ComfyLiterals operations.py (M1kep, pin bdddb08c).

The arithmetic, the type selection and the error behaviour are the original's lines. Only the declaration changes.
"""

from comfy_api.latest import io


class Operation(io.ComfyNode):
    # Pure value node: inputs arrive as plain values, and it uses no host capability.
    SDK_REFS = False
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Operation",
            display_name="Operation",
            category="Literals",
            inputs=[
                io.Combo.Input("A Type", options=["Int", "Float"]),
                io.Combo.Input("B Type", options=["Int", "Float"]),
                io.Combo.Input("Operation", options=["A+B", "A-B", "A*B", "A/B"]),
                io.Int.Input("A - Int", force_input=True, optional=True),
                io.Float.Input("A - Float", force_input=True, optional=True),
                io.Int.Input("B - Int", force_input=True, optional=True),
                io.Float.Input("B - Float", force_input=True, optional=True),
            ],
            outputs=[io.Int.Output(), io.Float.Output()],
        )

    @staticmethod
    def _do_addition(a_val, b_val):
        return (int(a_val + b_val), float(a_val + b_val))

    @staticmethod
    def _do_subtraction(a_val, b_val):
        return (int(a_val - b_val), float(a_val - b_val))

    @staticmethod
    def _do_multiplication(a_val, b_val):
        return (int(a_val * b_val), float(a_val * b_val))

    @staticmethod
    def _do_division(a_val, b_val):
        return (int(a_val / b_val), float(a_val / b_val))

    @classmethod
    def execute(cls, **kwargs):
        print(f"PrintNode: {kwargs}")
        is_a_int = kwargs["A Type"] == "Int"
        is_b_int = kwargs["B Type"] == "Int"
        a_val = kwargs["A - Int"] if is_a_int else kwargs["A - Float"]
        b_val = kwargs["B - Int"] if is_b_int else kwargs["B - Float"]

        if kwargs["Operation"] == "A+B":
            return io.NodeOutput(*cls._do_addition(a_val, b_val))
        elif kwargs["Operation"] == "A-B":
            return io.NodeOutput(*cls._do_subtraction(a_val, b_val))
        elif kwargs["Operation"] == "A*B":
            return io.NodeOutput(*cls._do_multiplication(a_val, b_val))
        elif kwargs["Operation"] == "A/B":
            return io.NodeOutput(*cls._do_division(a_val, b_val))
        else:
            raise Exception("Invalid operation provided")
