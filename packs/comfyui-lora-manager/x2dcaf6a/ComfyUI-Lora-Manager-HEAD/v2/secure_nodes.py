"""Public ref-mode adapters preserve native workflow-owned value behavior. Resource limits are enforced by the existing service, not new pack-level caps."""
from comfy_api.latest import io
from .secure_algorithms.lora_pool import LoraPoolLM
from .secure_algorithms.lora_stack_combiner import LoraStackCombinerLM
from .secure_algorithms.trigger_word_toggle import TriggerWordToggleLM
from .secure_services.trigger_words import process_trigger_words

class LoraPool(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Lora Pool (LoraManager)', display_name='Lora Pool (LoraManager)', category='Lora Manager/randomizer', inputs=[io.Custom('LORA_POOL_CONFIG').Input('pool_config')], outputs=[io.Custom('POOL_CONFIG').Output(display_name='POOL_CONFIG')], hidden=[io.Hidden.unique_id])

    @classmethod
    def execute(cls, pool_config, unique_id=None):
        return io.NodeOutput(*LoraPoolLM().process(pool_config, unique_id))

class LoraStackCombiner(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        tooltip = 'A LoRA stack to combine. Connect to add more inputs.'
        return io.Schema(node_id='Lora Stack Combiner (LoraManager)', display_name='Lora Stack Combiner (LoraManager)', category='Lora Manager/stackers', description='Combines multiple LoRA stacks into a single stack. Supports dynamic inputs: connect a stack to add more inputs.', inputs=[io.Custom('LORA_STACK').Input('lora_stack1', optional=True, tooltip=tooltip), io.Custom('LORA_STACK').Input('lora_stack2', optional=True, tooltip=tooltip)], outputs=[io.Custom('LORA_STACK').Output(display_name='LORA_STACK')], accept_all_inputs=True)

    @classmethod
    def execute(cls, lora_stack1=None, lora_stack2=None, **kwargs):
        return io.NodeOutput(*LoraStackCombinerLM().combine_stacks(lora_stack1, lora_stack2, **kwargs))

class TriggerWordToggle(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='TriggerWord Toggle (LoraManager)', display_name='TriggerWord Toggle (LoraManager)', category='Lora Manager/utils', description='Toggle trigger words on/off', inputs=[io.Boolean.Input('group_mode', default=True, tooltip='When enabled, treats each group of trigger words as a single toggleable unit.'), io.Boolean.Input('default_active', default=True, tooltip='Sets the default initial state (active or inactive) when trigger words are added.'), io.Boolean.Input('allow_strength_adjustment', default=False, tooltip="Enable mouse wheel adjustment of each trigger word's strength.")], outputs=[io.String.Output(display_name='filtered_trigger_words')], hidden=[io.Hidden.unique_id], accept_all_inputs=True)

    @classmethod
    def execute(cls, group_mode, default_active, allow_strength_adjustment=False, **kwargs):
        return io.NodeOutput(*process_trigger_words(group_mode, default_active, allow_strength_adjustment, **kwargs))
