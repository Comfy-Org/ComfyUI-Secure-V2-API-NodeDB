"""Pinned pack LoRA normalization/filtering; no host model mutation.

The exact original state transforms are independent of model ownership.
Unmerged patch creation and consumption remain a shared lifecycle gate.
"""
import logging
import torch

log = logging.getLogger(__name__)

def filter_state_dict_by_blocks(state_dict, blocks_mapping, layer_filter=[]):
    filtered_dict = {}

    if isinstance(layer_filter, str):
        layer_filters = [layer_filter] if layer_filter else []
    else:
        # Filter out empty strings
        layer_filters = [f for f in layer_filter if f] if layer_filter else []

    #print("layer_filter: ", layer_filters)

    for key in state_dict:
        if not any(filter_str in key for filter_str in layer_filters):
            if 'blocks.' in key:

                block_pattern = key.split('diffusion_model.')[1].split('.', 2)[0:2]
                block_key = f'{block_pattern[0]}.{block_pattern[1]}.'

                if block_key in blocks_mapping:
                    filtered_dict[key] = state_dict[key]
            else:
                filtered_dict[key] = state_dict[key]

    for key in filtered_dict:
        print(key)

    #from safetensors.torch import save_file
    #save_file(filtered_dict, "filtered_state_dict_2.safetensors")

    return filtered_dict

def standardize_lora_key_format(lora_sd):
    new_sd = {}
    for k, v in lora_sd.items():
        # aitoolkit/lycoris format
        if k.startswith("lycoris_blocks_"):
            k = k.replace("lycoris_blocks_", "blocks.")
            k = k.replace("_cross_attn_", ".cross_attn.")
            k = k.replace("_self_attn_", ".self_attn.")
            k = k.replace("_ffn_net_0_proj", ".ffn.0")
            k = k.replace("_ffn_net_2", ".ffn.2")
            k = k.replace("to_out_0", "o")
        # Diffusers format
        if k.startswith('transformer.'):
            k = k.replace('transformer.', 'diffusion_model.')
        if k.startswith('pipe.dit.'): #unianimate-dit/diffsynth
            k = k.replace('pipe.dit.', 'diffusion_model.')
        if k.startswith('blocks.'):
            k = k.replace('blocks.', 'diffusion_model.blocks.')
        if k.startswith('vace_blocks.'):
            k = k.replace('vace_blocks.', 'diffusion_model.vace_blocks.')
        k = k.replace('.default.', '.')
        k = k.replace('.diff_m', '.modulation.diff')
        k = k.replace('base_model.model.', 'diffusion_model.')

        # Fun LoRA format
        if k.startswith('lora_unet__'):
            # Split into main path and weight type parts
            parts = k.split('.')
            main_part = parts[0]  # e.g. lora_unet__blocks_0_cross_attn_k
            weight_type = '.'.join(parts[1:]) if len(parts) > 1 else None  # e.g. lora_down.weight

            # Process the main part - convert from underscore to dot format
            if 'blocks_' in main_part:
                # Extract components
                components = main_part[len('lora_unet__'):].split('_')

                # Start with diffusion_model
                new_key = "diffusion_model"

                # Add blocks.N
                if components[0] == 'blocks':
                    new_key += f".blocks.{components[1]}"

                    # Handle different module types
                    idx = 2
                    if idx < len(components):
                        if components[idx] == 'self' and idx+1 < len(components) and components[idx+1] == 'attn':
                            new_key += ".self_attn"
                            idx += 2
                        elif components[idx] == 'cross' and idx+1 < len(components) and components[idx+1] == 'attn':
                            new_key += ".cross_attn"
                            idx += 2
                        elif components[idx] == 'ffn':
                            new_key += ".ffn"
                            idx += 1

                    # Add the component (k, q, v, o) and handle img suffix
                    if idx < len(components):
                        component = components[idx]
                        idx += 1

                        # Check for img suffix
                        if idx < len(components) and components[idx] == 'img':
                            component += '_img'
                            idx += 1

                        new_key += f".{component}"

                # Handle weight type
                if weight_type:
                    if weight_type == 'alpha':
                        new_key += '.alpha'
                    elif weight_type == 'lora_down.weight' or weight_type == 'lora_down':
                        new_key += '.lora_A.weight'
                    elif weight_type == 'lora_up.weight' or weight_type == 'lora_up':
                        new_key += '.lora_B.weight'
                    else:
                        # Keep original weight type if not matching our patterns
                        new_key += f'.{weight_type}'
                        # Add .weight suffix if missing
                        if not new_key.endswith('.weight'):
                            new_key += '.weight'

                k = new_key
            else:
                # For other lora_unet__ formats (head, embeddings, etc.)
                new_key = main_part.replace('lora_unet__', 'diffusion_model.')

                # Fix specific component naming patterns
                new_key = new_key.replace('_self_attn', '.self_attn')
                new_key = new_key.replace('_cross_attn', '.cross_attn')
                new_key = new_key.replace('_ffn', '.ffn')
                new_key = new_key.replace('blocks_', 'blocks.')
                new_key = new_key.replace('head_head', 'head.head')
                new_key = new_key.replace('img_emb', 'img_emb')
                new_key = new_key.replace('text_embedding', 'text.embedding')
                new_key = new_key.replace('time_embedding', 'time.embedding')
                new_key = new_key.replace('time_projection', 'time.projection')

                # Replace remaining underscores with dots
                parts = new_key.split('.')
                final_parts = []
                for part in parts:
                    if part in ['img_emb', 'self_attn', 'cross_attn']:
                        final_parts.append(part)
                    else:
                        final_parts.append(part.replace('_', '.'))
                new_key = '.'.join(final_parts)

                # Handle weight type
                if weight_type:
                    if weight_type == 'alpha':
                        new_key += '.alpha'
                    elif weight_type == 'lora_down.weight' or weight_type == 'lora_down':
                        new_key += '.lora_A.weight'
                    elif weight_type == 'lora_up.weight' or weight_type == 'lora_up':
                        new_key += '.lora_B.weight'
                    else:
                        new_key += f'.{weight_type}'
                        if not new_key.endswith('.weight'):
                            new_key += '.weight'

                k = new_key

            # Handle special embedded components
            special_components = {
                'time.projection': 'time_projection',
                'img.emb': 'img_emb',
                'text.emb': 'text_emb',
                'time.emb': 'time_emb',
            }
            for old, new in special_components.items():
                if old in k:
                    k = k.replace(old, new)

        # Fix diffusion.model -> diffusion_model
        if k.startswith('diffusion.model.'):
            k = k.replace('diffusion.model.', 'diffusion_model.')

        # Finetrainer format
        if '.attn1.' in k:
            k = k.replace('.attn1.', '.cross_attn.')
            k = k.replace('.to_k.', '.k.')
            k = k.replace('.to_q.', '.q.')
            k = k.replace('.to_v.', '.v.')
            k = k.replace('.to_out.0.', '.o.')
        elif '.attn2.' in k:
            k = k.replace('.attn2.', '.cross_attn.')
            k = k.replace('.to_k.', '.k.')
            k = k.replace('.to_q.', '.q.')
            k = k.replace('.to_v.', '.v.')
            k = k.replace('.to_out.0.', '.o.')

        if "img_attn.proj" in k:
            k = k.replace("img_attn.proj", "img_attn_proj")
        if "img_attn.qkv" in k:
            k = k.replace("img_attn.qkv", "img_attn_qkv")
        if "txt_attn.proj" in k:
            k = k.replace("txt_attn.proj", "txt_attn_proj")
        if "txt_attn.qkv" in k:
            k = k.replace("txt_attn.qkv", "txt_attn_qkv")
        new_sd[k] = v
    return new_sd

def compensate_rs_lora_format(lora_sd):
    rank = lora_sd["base_model.model.blocks.0.cross_attn.k.lora_A.weight"].shape[0]
    alpha = torch.tensor(rank * rank // rank ** 0.5)
    log.info(f"Detected rank stabilized peft lora format with rank {rank}, setting alpha to {alpha} to compensate.")
    new_sd = {}
    for k, v in lora_sd.items():
        if k.endswith(".lora_A.weight"):
            new_sd[k] = v
            new_k = k.replace(".lora_A.weight", ".alpha")
            new_sd[new_k] = alpha
        else:
            new_sd[k] = v
    return new_sd


def prepare_set_lora_state(lora_sd, descriptor, model_state_keys):
    """Native SetLoRAs preprocessing in its original guard/order.

    The caller owns the actual safe state and must derive model_state_keys
    from its real transformer. No model or patcher is fabricated here.
    """
    if "dwpose_embedding.0.weight" in lora_sd:
        raise NotImplementedError("Unianimate LoRA patching is not implemented in this node.")
    if "base_model.model.blocks.0.cross_attn.k.lora_A.weight" in lora_sd:
        lora_sd = compensate_rs_lora_format(lora_sd)
    lora_sd = standardize_lora_key_format(lora_sd)
    if descriptor["blocks"]:
        lora_sd = filter_state_dict_by_blocks(lora_sd, descriptor["blocks"], descriptor.get("layer_filter", []))
    if not any('img' in key for key in model_state_keys):
        lora_sd = {key:value for key,value in lora_sd.items() if 'img' not in key}
    if "diffusion_model.patch_embedding.lora_A.weight" in lora_sd:
        raise NotImplementedError("Control LoRA patching is not implemented in this node.")
    return lora_sd
