from typing import Any

from comfyui_jh_misc_nodes import jh_types


class JHNWaySwitchNode:
    @classmethod
    def INPUT_TYPES(cls) -> jh_types.JHInputTypesType:
        # fmt: off
        return {
            "required": {},
            "optional":  {
                "input_1": (
                    jh_types.JHAnyType("*"), {}
                ),
            },
            "hidden": {},
        }
        # fmt: on

    RETURN_TYPES = (jh_types.JHAnyType("*"),)
    FUNCTION = "do_switch"
    CATEGORY = "JH Misc Nodes"
    OUTPUT_NODE = False
    EXPERIMENTAL = True

    # It's generally bad practice to use `Any` this way, but in this case we
    # have to because the inputs and outputs can literally be any data type.
    def do_switch(self, **kwargs) -> Any:  # noqa: ANN401,ANN003
        for _, value in kwargs.items():
            if value is not None:
                return (value,)

        return (None,)


class JHTwoWaySwitchNode(JHNWaySwitchNode):
    @classmethod
    def INPUT_TYPES(cls) -> jh_types.JHInputTypesType:
        # fmt: off
        return {
            "required": {},
            "optional":  {
                "input_1": (
                    jh_types.JHAnyType("*"), {}
                ),
                "input_2": (
                    jh_types.JHAnyType("*"), {}
                ),
            },
            "hidden": {},
        }
        # fmt: on

    def do_switch(self, **kwargs) -> Any:  # noqa: ANN401,ANN003
        return super().do_switch(**kwargs)


class JHThreeWaySwitchNode(JHNWaySwitchNode):
    @classmethod
    def INPUT_TYPES(cls) -> jh_types.JHInputTypesType:
        # fmt: off
        return {
            "required": {},
            "optional":  {
                "input_1": (
                    jh_types.JHAnyType("*"), {}
                ),
                "input_2": (
                    jh_types.JHAnyType("*"), {}
                ),
                "input_3": (
                    jh_types.JHAnyType("*"), {}
                ),
            },
            "hidden": {},
        }
        # fmt: on

    def do_switch(self, **kwargs) -> Any:  # noqa: ANN401,ANN003
        return super().do_switch(**kwargs)
