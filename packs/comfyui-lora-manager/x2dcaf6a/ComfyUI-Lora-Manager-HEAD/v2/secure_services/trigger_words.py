"""Native trigger processing; existing service enforces wire/resource limits."""
from ..secure_algorithms.trigger_word_toggle import TriggerWordToggleLM

def process_trigger_words(group_mode, default_active, allow_strength_adjustment=False, *, id=None, **kwargs):
    return TriggerWordToggleLM().process_trigger_words(id, group_mode, default_active, allow_strength_adjustment, **kwargs)
