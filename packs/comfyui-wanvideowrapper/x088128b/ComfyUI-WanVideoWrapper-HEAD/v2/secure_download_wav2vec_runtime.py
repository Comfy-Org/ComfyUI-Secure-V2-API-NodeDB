"""Exact original Facebook/Tencent branches from pinned local bundle bytes.

Public catalogue assets are streamed into a private temporary bundle. Original
from_pretrained implementations then consume those original bytes. Scratch
capacity, full model loading and learned execution still need qualification.
"""
import hashlib
import json
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from comfy_api.latest import sdk

FORMAT = 'wan-download-wav2vec-model-v1'
KEYS = {'format', 'model_type', 'bundle_id', 'base_precision', 'load_device'}
DATA = Path(__file__).parent/'wav2vec_bundle_data'
BUNDLES = json.loads((DATA/'bundles.json').read_text())
CHUNK_BYTES = 8*1024**2


def validate_recipe(recipe):
    if type(recipe) is not dict or set(recipe) != KEYS or recipe['format'] != FORMAT:
        raise ValueError('Invalid owned downloaded Wav2Vec recipe')
    if recipe['model_type'] not in BUNDLES:
        raise ValueError('Unknown original downloaded Wav2Vec model')
    bundle = BUNDLES[recipe['model_type']]
    if recipe['bundle_id'] != bundle['bundle_id']:
        raise ValueError('Downloaded Wav2Vec source bundle changed')
    if recipe['base_precision'] not in ('fp32', 'bf16', 'fp16'):
        raise ValueError('Invalid downloaded Wav2Vec precision')
    if recipe['load_device'] not in ('main_device', 'offload_device'):
        raise ValueError('Invalid downloaded Wav2Vec initial device')
    return recipe


def required_weights():
    return tuple(sdk.HuggingFaceWeight(**bundle['required_weight'], on_demand=True)
                 for bundle in BUNDLES.values())


@asynccontextmanager
async def private_bundle(model, *, allow_download):
    bundle = BUNDLES[model]
    context = sdk.current_context()
    weight = bundle['required_weight']
    logical = 'huggingface/'+weight['repo_id']+'/'+weight['revision']+'/'+weight['filename']
    if allow_download:
        admitted_name = await context.models.download_huggingface_weights(**weight)
        if admitted_name != logical:
            raise ValueError('Public Wav2Vec weight catalogue identity changed')
    ref = await context.assets.resolve(weight['folder'], logical)
    if (await context.assets.size(ref) != bundle['weight_bytes']
            or await context.assets.digest(ref) != weight['sha256']):
        raise ValueError('Wav2Vec checkpoint differs from the pinned original bundle')
    with TemporaryDirectory(prefix='wan-original-wav2vec-') as directory:
        target = Path(directory)
        for row in bundle['data_files']:
            source = DATA/bundle['data_subdirectory']/row['filename']
            raw = source.read_bytes()
            if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('Packaged original Wav2Vec data changed')
            (target/row['filename']).write_bytes(raw)
        digest = hashlib.sha256()
        with (target/weight['filename']).open('xb') as stream:
            for offset in range(0, bundle['weight_bytes'], CHUNK_BYTES):
                length = min(CHUNK_BYTES, bundle['weight_bytes']-offset)
                data = await context.assets.read_range(ref, offset=offset, length=length)
                if type(data) is not bytes or len(data) != length:
                    raise ValueError('Pinned Wav2Vec checkpoint range was truncated')
                digest.update(data)
                stream.write(data)
                del data
        if (digest.hexdigest() != weight['sha256']
                or await context.assets.digest(ref) != weight['sha256']
                or await context.assets.size(ref) != bundle['weight_bytes']):
            raise ValueError('Complete original Wav2Vec checkpoint changed')
        yield str(target)


async def load_downloaded_wav2vec(model, base_precision, load_device, *, expected=None,
                                preserve_rng=False, allow_download=True):
    import torch
    from transformers import Wav2Vec2Model, Wav2Vec2Processor, Wav2Vec2FeatureExtractor
    from .multitalk.wav2vec2 import Wav2Vec2Model as MultiTalkWav2Vec2Model

    recipe = validate_recipe({'format': FORMAT, 'model_type': model,
        'bundle_id': BUNDLES[model]['bundle_id'], 'base_precision': base_precision, 'load_device': load_device})
    if expected is not None and recipe != expected:
        raise ValueError('Downloaded Wav2Vec recipe changed since loader execution')
    base_dtype = {'fp8_e4m3fn': torch.float8_e4m3fn, 'fp8_e4m3fn_fast': torch.float8_e4m3fn,
        'bf16': torch.bfloat16, 'fp16': torch.float16, 'fp16_fast': torch.float16, 'fp32': torch.float32}[base_precision]
    device = torch.device('cpu')
    offload_device = torch.device('cpu')
    if load_device == 'offload_device':
        transfomer_load_device = offload_device
    else:
        transfomer_load_device = device
    async with private_bundle(model, allow_download=allow_download) as model_path:
        with torch.random.fork_rng(devices=[], enabled=preserve_rng):
            if model == 'facebook/wav2vec2-base-960h':
                wav2vec_processor = Wav2Vec2Processor.from_pretrained(model_path)
                wav2vec = Wav2Vec2Model.from_pretrained(model_path).to(base_dtype).to(transfomer_load_device).eval()
            elif model == 'TencentGameMate/chinese-wav2vec2-base':
                wav2vec = MultiTalkWav2Vec2Model.from_pretrained(model_path).to(base_dtype).to(transfomer_load_device).eval()
                wav2vec_feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_path, local_files_only=True)
    wav2vec_processor_model = {
        'processor': wav2vec_processor if model == 'facebook/wav2vec2-base-960h' else None,
        'feature_extractor': wav2vec_feature_extractor if model == 'TencentGameMate/chinese-wav2vec2-base' else None,
        'model': wav2vec, 'dtype': base_dtype, 'model_type': model,
    }
    return wav2vec_processor_model, recipe


async def rebuild_downloaded_wav2vec(recipe):
    validate_recipe(recipe)
    value, _ = await load_downloaded_wav2vec(recipe['model_type'], recipe['base_precision'],
        recipe['load_device'], expected=recipe, preserve_rng=True, allow_download=False)
    return value


async def rebuild_fantasy_wav2vec(recipe):
    if type(recipe) is dict and recipe.get('format') == 'wan-tencent-wav2vec-model-v1':
        from .secure_wav2vec_runtime import rebuild_wav2vec
        # That original loader lacks processor; the original Fantasy caller's
        # subsequent ['processor'] access must retain its native KeyError.
        return await rebuild_wav2vec(recipe)
    return await rebuild_downloaded_wav2vec(recipe)
