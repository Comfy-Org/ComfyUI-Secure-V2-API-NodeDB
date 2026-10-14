"""Only call-boundary adapter; original class/helpers/process stay unchanged."""
from .PlaceholderReplacerByID import PlaceholderReplacerByID as _Original

def process_native(id_sequences, prompt_list, term_mappings,
                   mirror_first_prompt, auto_step_ids, manual_ids, mirror_first_id,
                   manual_ids_list, increment_base, placeholder_token, prompt_delimiter):
    return _Original().process(id_sequences, prompt_list, term_mappings,
                               mirror_first_prompt, auto_step_ids, manual_ids, mirror_first_id,
                               manual_ids_list, increment_base, placeholder_token, prompt_delimiter)
