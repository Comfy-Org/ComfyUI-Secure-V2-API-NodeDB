"""Private source-staged consumer for the child audio projection recipes.

Only recipes cross the graph. Rebuilt modules, tensors, AssetRefs and temporary
GGUF readers stay inside the owning materialization call. Trained parity and
main-model GGUF execution remain unqualified.
"""
from contextlib import asynccontextmanager
import hashlib
import logging
from pathlib import Path
import tempfile

from .wan_workflow_context import clone_options
from .secure_audio_projection_runtime import (
    rebuild_fantasytalking, rebuild_multitalk,
    validate_fantasytalking_recipe, validate_multitalk_recipe,
)

log = logging.getLogger(__name__)
RECIPE_KEYS = {'fantasytalking', 'multitalk'}


def projection_recipes(fantasytalking=None, multitalk=None):
    if fantasytalking is not None:
        validate_fantasytalking_recipe(fantasytalking)
    if multitalk is not None:
        validate_multitalk_recipe(multitalk)
    if fantasytalking is None and multitalk is None:
        return None
    return clone_options({'fantasytalking': fantasytalking, 'multitalk': multitalk})


def validate_projection_recipes(recipes):
    if recipes is None:
        return None
    if type(recipes) is not dict or set(recipes) != RECIPE_KEYS:
        raise ValueError('Invalid private audio projection recipe collection')
    return projection_recipes(recipes['fantasytalking'], recipes['multitalk'])


async def rebuild_projection_inputs(recipes):
    recipes = validate_projection_recipes(recipes)
    if recipes is None:
        return None, None
    fantasy = (await rebuild_fantasytalking(recipes['fantasytalking'])
               if recipes['fantasytalking'] is not None else None)
    multi = (await rebuild_multitalk(recipes['multitalk'])
             if recipes['multitalk'] is not None else None)
    return fantasy, multi


@asynccontextmanager
async def _verified_gguf_file(assets, asset, recipe):
    # Future GGUF branch only. Never substitute a fabricated host path or
    # deserialize a GGUF resource as SafeTensors. Keep its reader/file alive
    # through the caller's materialization scope using AsyncExitStack.
    if await assets.size(asset) != recipe['bytes'] or await assets.digest(asset) != recipe['sha256']:
        raise ValueError('MultiTalk GGUF asset changed before private materialization')
    with tempfile.TemporaryDirectory(prefix='wan-multitalk-gguf-') as directory:
        path = Path(directory) / 'weights.gguf'
        digest = hashlib.sha256()
        with path.open('xb') as stream:
            for offset in range(0, recipe['bytes'], 8 * 1024**2):
                length = min(8 * 1024**2, recipe['bytes'] - offset)
                data = await assets.read_range(asset, offset=offset, length=length)
                if type(data) is not bytes or len(data) != length:
                    raise ValueError('MultiTalk GGUF range is truncated or not bytes')
                stream.write(data)
                digest.update(data)
                del data
        if digest.hexdigest() != recipe['sha256'] or await assets.digest(asset) != recipe['sha256']:
            raise ValueError('MultiTalk GGUF asset digest changed')
        yield path


async def apply_audio_projection_state(context, transformer, sd, recipes, *, dim,
        num_heads, attention_mode, transformer_load_device, gguf=False,
        gguf_reader=None, lifetime):
    recipes = validate_projection_recipes(recipes)
    if recipes is None:
        return sd
    multi_recipe = recipes['multitalk']
    fantasy, multi = await rebuild_projection_inputs(recipes)
    apply_fantasytalking_native(transformer, sd, fantasy, dim)
    if multi is None:
        return sd
    if not external_multitalk_branch_selected(sd):
        raise NotImplementedError('Native embedded LongCat/Skyreels audio branch precedes the external MultiTalk branch; complete embedded consumer remains gated')
    assets = context.assets

    async def load_gguf(asset):
        if not gguf or type(gguf_reader) is not list:
            raise NotImplementedError('Main-model GGUF residency must be implemented before its audio reader can execute')
        from .wan_workflow_math.gguf.gguf import load_gguf as native_load_gguf
        path = await lifetime.enter_async_context(_verified_gguf_file(assets, asset, multi_recipe))
        return native_load_gguf(str(path))

    async def load_torch_file(asset, *, device, safe_load):
        if safe_load is not True:
            raise ValueError('The original safe-load policy is required')
        if not multi_recipe['name'].lower().endswith(('.safetensors', '.sft')):
            raise NotImplementedError('Non-SafeTensors safe checkpoints need their own original consumer proof')
        from .secure_audio_safetensors import VerifiedAudioSafeTensors
        reader = await VerifiedAudioSafeTensors.open(assets, asset,
            multi_recipe['bytes'], multi_recipe['sha256'])
        state = {name: (await reader.tensor(name)).to(device) for name in sorted(reader.tensors)}
        await reader.verify_unchanged()
        return state

    await apply_multitalk_native(transformer, sd, multi, dim, num_heads,
        attention_mode, transformer_load_device, gguf, gguf_reader,
        load_gguf=load_gguf, load_torch_file=load_torch_file)
    return sd


# The three functions below are generated from exact original loader AST;
# the successor builder records every boundary substitution explicitly.


def apply_fantasytalking_native(transformer, sd, fantasytalking_model, dim):
    import torch.nn as nn
    if fantasytalking_model is not None:
        log.info('FantasyTalking model detected, patching model...')
        context_dim = fantasytalking_model['sd']['proj_model.proj.weight'].shape[0]
        for block in transformer.blocks:
            block.cross_attn.k_proj = nn.Linear(context_dim, dim, bias=False)
            block.cross_attn.v_proj = nn.Linear(context_dim, dim, bias=False)
        sd.update(fantasytalking_model['sd'])


def external_multitalk_branch_selected(sd):
    proj1_key = 'multitalk_audio_proj.proj1.weight' if 'multitalk_audio_proj.proj1.weight' in sd else 'multitalk_audio_proj.proj1.weight_int8' if 'multitalk_audio_proj.proj1.weight_int8' in sd else None
    return not (proj1_key is not None and ('blocks.0.audio_cross_attn.q_norm.weight' in sd or 'blocks.0.audio_cross_attn.q_norm.weight_int8' in sd) or ('blocks.1.audio_cross_attn.kv_linear.weight' in sd and 'audio_proj.proj1.weight' in sd))


async def apply_multitalk_native(transformer, sd, multitalk_model, dim, num_heads, attention_mode, transformer_load_device, gguf, gguf_reader, *, load_gguf, load_torch_file):
    from accelerate import init_empty_weights
    if multitalk_model is not None:
        multitalk_model_type = multitalk_model.get('model_type', 'MultiTalk')
        log.info(f'{multitalk_model_type} detected, patching model...')
        multitalk_model_path = multitalk_model['model_name']
        if multitalk_model_path.endswith('.gguf') and (not gguf):
            raise ValueError('Multitalk/InfiniteTalk model is a GGUF model, main model also has to be a GGUF model.')
        if 'scaled' in multitalk_model and gguf:
            raise ValueError("fp8 scaled Multitalk/InfiniteTalk model can't be used with GGUF main model")
        from .wan_workflow_math.multitalk.multitalk import SingleStreamMultiAttention
        from .wan_workflow_math.wanvideo.modules.model import WanLayerNorm
        for block in transformer.blocks:
            with init_empty_weights():
                block.norm_x = WanLayerNorm(dim, transformer.eps, elementwise_affine=True)
                block.audio_cross_attn = SingleStreamMultiAttention(dim=dim, num_heads=num_heads, attention_mode=attention_mode)
        transformer.multitalk_audio_proj = multitalk_model['proj_model']
        transformer.multitalk_model_type = multitalk_model_type
        extra_model_path = multitalk_model['asset']
        extra_sd = {}
        if multitalk_model_path.endswith('.gguf'):
            extra_sd_temp, extra_reader = await load_gguf(extra_model_path)
            gguf_reader.append(extra_reader)
            del extra_reader
        else:
            extra_sd_temp = await load_torch_file(extra_model_path, device=transformer_load_device, safe_load=True)
        for k, v in extra_sd_temp.items():
            extra_sd[k.replace('audio_proj.', 'multitalk_audio_proj.')] = v
        sd.update(extra_sd)
        del extra_sd
