"""Unchanged original pure classes; gallery host I/O is excluded."""
from itertools import product
import re
import random

id_pattern = re.compile(r'^[a-zA-Z0-9 ]+$')

class PromptCombinator:
    """
    ComfyUI-Prompt-Combinator
    https://github.com/lquesada/ComfyUI-Prompt-Combinator

    Node that generates all possible combinations of prompts from several lists of strings.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "id_separator": ("STRING", {"default": '@'}),
                "comment_prefix": ("STRING", {"default": '#'}),
                "join_prompt_using": (["comma and space", "space", "enter"], {"default": "comma and space"}),
                "input_list_1": ("STRING", {"default": '', "multiline": True}),
            },
            "optional": {
                "input_list_2": ("STRING", {"default": '', "multiline": True}),
                "input_list_3": ("STRING", {"default": '', "multiline": True}),
                "input_list_4": ("STRING", {"default": '', "multiline": True}),
                "input_list_5": ("STRING", {"default": '', "multiline": True}),
                "input_list_6": ("STRING", {"default": '', "multiline": True}),
                "input_list_7": ("STRING", {"default": '', "multiline": True}),
                "input_list_8": ("STRING", {"default": '', "multiline": True}),
            }
        }

    RETURN_TYPES = ("STRING", "PROMPTCOMBINATORIDS", "STRING")
    RETURN_NAMES = ("prompts", "combination_ids", "filenames")
    OUTPUT_IS_LIST = (True, True, True)

    FUNCTION = "execute"

    CATEGORY = "prompt_combinator"

    def parse_input(self, input_list, id_separator, comment_prefix):
        entries = input_list.strip().split('\n') if input_list.strip() else ['']
        ids = []
        descriptions = []
        no_id_counter = 1

        for entry in entries:
            if entry.strip() == '' or entry.strip().startswith(comment_prefix):
                continue
            parts = entry.split(id_separator, 1)
            if len(parts) == 1:
                ids.append(None)
                descriptions.append(parts[0].strip())
            else:
                id_candidate = parts[0].strip()
                assert id_pattern.match(id_candidate), f'IDs can only contain alphanumeric characters (a-z, A-Z, 0-9). Offending id is {id_candidate}'
                ids.append(id_candidate)
                descriptions.append(parts[1].strip())

        if ids == []:
            ids.append('')
        if not descriptions:
            descriptions.append('')

        return ids, descriptions

    def combine_descriptions_and_ids(self, *inputs, id_separator, comment_prefix, join_prompt_using):
        list_of_ids = []
        list_of_descriptions = []
        no_id_counters = [1] * len(inputs)

        for input_idx, input_list in enumerate(inputs):
            ids, descriptions = self.parse_input(input_list, id_separator, comment_prefix)
            for i in range(len(ids)):
                if ids[i] is None:
                    ids[i] = f'input_{input_idx+1}_no_id_{no_id_counters[input_idx]}'
                    no_id_counters[input_idx] += 1
            list_of_ids.append(ids)
            list_of_descriptions.append(descriptions)

        all_description_combinations = list(product(*list_of_descriptions))
        all_id_combinations = list(product(*list_of_ids))

        if join_prompt_using == "comma and space":
            use = ', '
        elif join_prompt_using == "space":
            use = ' '
        else: #"enter"
            use = '\n'

        outputs = [use.join(filter(None, comb)).strip() for comb in all_description_combinations]
        ids_lists = [list(comb) for comb in all_id_combinations]

        return outputs, ids_lists

    def execute(self, id_separator, comment_prefix, join_prompt_using, input_list_1, input_list_2="", input_list_3="", input_list_4="", input_list_5="", input_list_6="", input_list_7="", input_list_8=""):
        prompts, ids = self.combine_descriptions_and_ids(
            input_list_1, input_list_2, input_list_3, input_list_4, input_list_5, input_list_6, input_list_7, input_list_8,
            id_separator=id_separator, comment_prefix=comment_prefix, join_prompt_using=join_prompt_using
        )

        filenames = []
        for id_list in ids:
            filename_parts = [id_part for id_part in id_list]
            filenames.append('-'.join(filename_parts))

        return prompts, ids, filenames

class PromptCombinatorMerger:
    """
    ComfyUI-Prompt-Combinator
    https://github.com/lquesada/ComfyUI-Prompt-Combinator

    Node that merges the prompts and IDs out of two PromptCombinators.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompts_1": ("STRING", {"forceInput": True}),
                "combination_ids_1": ("PROMPTCOMBINATORIDS",),
                "prompts_2": ("STRING", {"forceInput": True}),
                "combination_ids_2": ("PROMPTCOMBINATORIDS",),
            },
        }

    INPUT_IS_LIST = True

    RETURN_TYPES = ("STRING", "PROMPTCOMBINATORIDS", "STRING")
    RETURN_NAMES = ("prompts", "combination_ids", "filenames")
    OUTPUT_IS_LIST = (True, True, True)

    FUNCTION = "execute"

    CATEGORY = "prompt_combinator"

    def merge_lists(self, list1, list2):
        if not list1:
            list1 = []
        if not list2:
            list2 = []
        return list1 + list2

    def execute(self, prompts_1, combination_ids_1, prompts_2, combination_ids_2):
        combined_prompts = self.merge_lists(prompts_1, prompts_2)
        combined_ids = self.merge_lists(combination_ids_1, combination_ids_2)

        filenames = []
        for id_list in combination_ids_1:
            filename_parts = []
            for i, id_part in enumerate(id_list):
                if id_part.startswith('input_'):
                    filename_parts.append(f'input_merge_1_{id_part}')
                else:
                    filename_parts.append(id_part)
            filenames.append('-'.join(filename_parts))
        for id_list in combination_ids_2:
            filename_parts = []
            for i, id_part in enumerate(id_list):
                if id_part.startswith('input_'):
                    filename_parts.append(f'input_merge_2_{id_part}')
                else:
                    filename_parts.append(id_part)
            filenames.append('-'.join(filename_parts))

        return combined_prompts, combined_ids, filenames

class PromptCombinatorRandomPrompt:
    """
    ComfyUI-Prompt-Combinator
    https://github.com/lquesada/ComfyUI-Prompt-Combinator

    Node that picks a random prompt from a prompt combinator output.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompts": ("STRING", {"default": '', "multiline": True, "forceInput": True}),
                "combination_ids": ("PROMPTCOMBINATORIDS",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
        }
    INPUT_IS_LIST = True

    RETURN_TYPES = ("STRING", "PROMPTCOMBINATORIDS", "STRING")
    RETURN_NAMES = ("prompt", "combination_id", "filename")
    FUNCTION = "pick_random"

    OUTPUT_NODE = True

    CATEGORY = "prompt_combinator"

    def pick_random(self, prompts, combination_ids, seed):
        assert len(combination_ids) == len(prompts), "Amount of combination ids must be the same as amount of prompts"
    
        index = random.randint(0, len(prompts) - 1)
        prompt = prompts[index]
        combination_id = combination_ids[index]

        filename = '-'.join(combination_id)

        return (prompt, combination_id, filename)

