"""Published schema plus direct delegation to untouched native implementation."""
from comfy_api.latest import ComfyExtension, io

class PlaceholderReplacerByID(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Placeholder Replacer By ID",
            display_name="Placeholder Replacer By ID",
            category="Utils",
            inputs=[
                io.Custom("INT_LIST").Input("id_sequences", extra_dict={"forceInput": True}),
                io.String.Input("prompt_list", force_input=True),
                io.String.Input("term_mappings", force_input=True),
                io.Boolean.Input("mirror_first_prompt", default=False, extra_dict={"label": "Mirror First Prompt Across All"}),
                io.Boolean.Input("auto_step_ids", default=False, extra_dict={"label": "Auto-Step IDs"}),
                io.Boolean.Input("manual_ids", default=False, extra_dict={"label": "Use Manual IDs"}),
                io.Boolean.Input("mirror_first_id", default=False, extra_dict={"label": "Mirror First ID Across All"}),
                io.String.Input("manual_ids_list", force_input=True),
                io.Int.Input("increment_base", force_input=True),
                io.String.Input("placeholder_token", default="[a1]", extra_dict={"label": "Literal Placeholder Token"}),
                io.String.Input("prompt_delimiter", default=";;;;;", extra_dict={"label": "Prompt Delimiter"}),
            ],
            outputs=[io.String.Output("resolved_prompts"), io.String.Output("debug_info"), io.String.Output("primary_ids")],
        )

    @classmethod
    def execute(cls, id_sequences, prompt_list, term_mappings,
                mirror_first_prompt, auto_step_ids, manual_ids, mirror_first_id,
                manual_ids_list, increment_base, placeholder_token, prompt_delimiter):
        from ._native_call import process_native
        result = process_native(id_sequences, prompt_list, term_mappings,
                                mirror_first_prompt, auto_step_ids, manual_ids, mirror_first_id,
                                manual_ids_list, increment_base, placeholder_token, prompt_delimiter)
        return io.NodeOutput(*result)

NODE_CLASS_MAPPINGS = {"Placeholder Replacer By ID": PlaceholderReplacerByID}

class Extension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())
