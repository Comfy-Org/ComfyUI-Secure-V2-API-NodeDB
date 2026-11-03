"""Secure Nodes V2 conversion of the XTNodes prompt nodes (civitaiNodes/prompt_concatenate.py).

The value handling is the original's own code: this module imports civitaiNodes/prompt_concatenate.py unchanged and
calls its node methods. Only the node declarations change (V1 INPUT_TYPES -> V3 schemas).
"""
from comfy_api.latest import io

from .civitaiNodes import prompt_concatenate as _xt


def _prompt_options():
    # prompt_concatenate.py:16-27 (DEFAULT_PROMPT_INPUT_TYPES)
    return [
        io.Boolean.Input("remove_duplicates", default=True),
        io.Combo.Input("whitespace_style", options=["keep", "space", "underscore"], default="keep"),
    ]


def _node_output(result):
    # The original returns {"result": (result,), "ui": {"text": [result]}}.
    return io.NodeOutput(*result["result"], ui=result["ui"])


class CleanPrompt(io.ComfyNode):
    # Pure value node: inputs arrive as plain values, and it uses no host capability.
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        # prompt_concatenate.py:105-118
        return io.Schema(
            node_id="XTNodesCleanPrompt",
            display_name="Clean Prompt(XTNodes)",
            category="XTNodes/prompt",
            inputs=[*_prompt_options(), io.AnyType.Input("prompt", optional=True)],
            outputs=[io.String.Output("result", display_name="result")],
        )

    @classmethod
    def execute(cls, **kwargs):
        # The original method, with the inputs exactly as provided (an unconnected prompt raises its TypeError).
        return _node_output(_xt.CleanPrompt()._clean_prompt(**kwargs))


class PromptConcatenate(io.ComfyNode):
    # Pure value node: inputs arrive as plain values, and it uses no host capability.
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        # prompt_concatenate.py:131-149
        return io.Schema(
            node_id="XTNodesPromptConcatenate",
            display_name="Prompt Concatenate(XTNodes)",
            category="XTNodes/prompt",
            inputs=[
                *_prompt_options(),
                *(io.AnyType.Input(f"prompt_{x}", optional=True) for x in "ABCDE"),
            ],
            outputs=[io.String.Output("result", display_name="result")],
        )

    @classmethod
    def execute(cls, **kwargs):
        return _node_output(_xt.PromptConcatenate()._concatenate_prompt(**kwargs))


NODE_CLASS_MAPPINGS = {
    "XTNodesCleanPrompt": CleanPrompt,
    "XTNodesPromptConcatenate": PromptConcatenate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "XTNodesCleanPrompt": "Clean Prompt(XTNodes)",
    "XTNodesPromptConcatenate": "Prompt Concatenate(XTNodes)",
}
