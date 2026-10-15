"""Wan option mutations for the digest-bound model recipe.

These functions only transform pack-owned option containers. They do not
resolve an opaque model, load a weight, select a device, or expose host state.
The recursive clone matches the ModelPatcher list/dict clone semantics:
dict/list aliases are retained inside a clone; tuples and leaves retain their
identities. Newly supplied node inputs are assigned without cloning, exactly
as in the pinned original nodes.
"""


def clone_model_options(value, memo=None):
    if memo is None:
        memo = {}
    identity = id(value)
    if identity in memo:
        return memo[identity]
    if isinstance(value, dict):
        result = {clone_model_options(key, memo): clone_model_options(item, memo)
                  for key, item in value.items()}
    elif isinstance(value, list):
        result = [clone_model_options(item, memo) for item in value]
    else:
        result = value
    memo[identity] = result
    return result


def block_swap_options(model_options, block_swap_args=None):
    if block_swap_args is None:
        return model_options
    options = clone_model_options(model_options)
    if 'transformer_options' not in options:
        options['transformer_options'] = {}
    options['transformer_options']['block_swap_args'] = block_swap_args
    return options


def attention_override_options(model_options, attention_mode, start_step,
                               end_step, verbose, blocks=None):
    options = clone_model_options(model_options)
    override = {'mode': attention_mode, 'start_step': start_step,
                'end_step': end_step, 'verbose': verbose}
    if blocks is not None:
        override['blocks'] = blocks
    options['transformer_options']['attention_mode_override'] = override
    return options


def ultravico_options(model_options, alpha):
    options = clone_model_options(model_options)
    options['transformer_options']['ultravico_alpha'] = alpha
    return options


def radial_options(model_options, original_attention_mode, dense_attention_mode,
                   dense_blocks, dense_vace_blocks, dense_timesteps,
                   decay_factor, block_size):
    if 'radial' not in original_attention_mode:
        raise Exception('Enable radial attention first in the model loader.')
    options = clone_model_options(model_options)
    if 'transformer_options' not in options:
        options['transformer_options'] = {}
    options['transformer_options']['dense_attention_mode'] = dense_attention_mode
    options['transformer_options']['dense_blocks'] = dense_blocks
    options['transformer_options']['dense_vace_blocks'] = dense_vace_blocks
    options['transformer_options']['dense_timesteps'] = dense_timesteps
    options['transformer_options']['decay_factor'] = decay_factor
    options['transformer_options']['block_size'] = block_size
    return options
