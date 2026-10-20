"""Unrun public V2 ports; gallery remains explicitly unregistered pending output API."""
from comfy_api.latest import io
from . import _algorithms

CombinationIds = io.Custom("PROMPTCOMBINATORIDS")


class PromptCombinator(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='PromptCombinator', display_name='🔢 Prompt Combinator', category='prompt_combinator',
            inputs=[io.String.Input('id_separator', default='@'),
                    io.String.Input('comment_prefix', default='#'),
                    io.Combo.Input('join_prompt_using', options=['comma and space', 'space', 'enter'], default='comma and space'),
                    io.String.Input('input_list_1', default='', multiline=True),
                    io.String.Input('input_list_2', default='', multiline=True, optional=True),
                    io.String.Input('input_list_3', default='', multiline=True, optional=True),
                    io.String.Input('input_list_4', default='', multiline=True, optional=True),
                    io.String.Input('input_list_5', default='', multiline=True, optional=True),
                    io.String.Input('input_list_6', default='', multiline=True, optional=True),
                    io.String.Input('input_list_7', default='', multiline=True, optional=True),
                    io.String.Input('input_list_8', default='', multiline=True, optional=True)],
            outputs=[io.String.Output(display_name='prompts', is_output_list=True), CombinationIds.Output(display_name='combination_ids', is_output_list=True), io.String.Output(display_name='filenames', is_output_list=True)],
            is_input_list=False, is_output_node=False)

    @classmethod
    def execute(cls, id_separator, comment_prefix, join_prompt_using, input_list_1, input_list_2='', input_list_3='', input_list_4='', input_list_5='', input_list_6='', input_list_7='', input_list_8=''):
        return io.NodeOutput(*_algorithms.PromptCombinator().execute(id_separator=id_separator, comment_prefix=comment_prefix, join_prompt_using=join_prompt_using, input_list_1=input_list_1, input_list_2=input_list_2, input_list_3=input_list_3, input_list_4=input_list_4, input_list_5=input_list_5, input_list_6=input_list_6, input_list_7=input_list_7, input_list_8=input_list_8))


class PromptCombinatorMerger(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='PromptCombinatorMerger', display_name='🔢 Prompt Combinator Merger', category='prompt_combinator',
            inputs=[io.String.Input('prompts_1', force_input=True),
                    CombinationIds.Input('combination_ids_1'),
                    io.String.Input('prompts_2', force_input=True),
                    CombinationIds.Input('combination_ids_2')],
            outputs=[io.String.Output(display_name='prompts', is_output_list=True), CombinationIds.Output(display_name='combination_ids', is_output_list=True), io.String.Output(display_name='filenames', is_output_list=True)],
            is_input_list=True, is_output_node=False)

    @classmethod
    def execute(cls, prompts_1, combination_ids_1, prompts_2, combination_ids_2):
        return io.NodeOutput(*_algorithms.PromptCombinatorMerger().execute(prompts_1=prompts_1, combination_ids_1=combination_ids_1, prompts_2=prompts_2, combination_ids_2=combination_ids_2))


class PromptCombinatorRandomPrompt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='PromptCombinatorRandomPrompt', display_name='🔢 Pick Random Prompt from Prompt Combinator', category='prompt_combinator',
            inputs=[io.String.Input('prompts', default='', multiline=True, force_input=True),
                    CombinationIds.Input('combination_ids'),
                    io.Int.Input('seed', default=0, min=0, max=18446744073709551615)],
            outputs=[io.String.Output(display_name='prompt', is_output_list=False), CombinationIds.Output(display_name='combination_id', is_output_list=False), io.String.Output(display_name='filename', is_output_list=False)],
            is_input_list=True, is_output_node=True)

    @classmethod
    def execute(cls, prompts, combination_ids, seed):
        return io.NodeOutput(*_algorithms.PromptCombinatorRandomPrompt().pick_random(prompts=prompts, combination_ids=combination_ids, seed=seed))

NODE_CLASS_MAPPINGS = {
    'PromptCombinator': PromptCombinator,
    'PromptCombinatorMerger': PromptCombinatorMerger,
    'PromptCombinatorRandomPrompt': PromptCombinatorRandomPrompt,
}
NODE_DISPLAY_NAME_MAPPINGS = {'PromptCombinator': '🔢 Prompt Combinator', 'PromptCombinatorMerger': '🔢 Prompt Combinator Merger', 'PromptCombinatorRandomPrompt': '🔢 Pick Random Prompt from Prompt Combinator'}
