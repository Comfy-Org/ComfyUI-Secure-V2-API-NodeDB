"""Prepared original cache-hit branch; deliberately absent from staged mapping.

The original cache-miss download cannot yet be expressed by the released public
admission catalogue. This module keeps the exact schema and working public
cache-hit loader, without inventing a URL method or claiming the node complete.
"""
from comfy_api.latest import io,sdk
from .secure_nlf_nodes import load_nlf_resource
from .secure_nlf_download_contract import (
    URLS,LEGACY_CACHE_NAME,CACHE_KEY,validate_nlf_download_url,
    decode_nlf_cache_record,choose_nlf_cached_asset,
)


async def load_existing_original_nlf_cache(url,warmup=True):
    validate_nlf_download_url(url)
    context=sdk.current_context()
    legacy_exists=await context.assets.exists('nlf',LEGACY_CACHE_NAME)
    record=None
    record_exists=False
    if not legacy_exists:
        record=decode_nlf_cache_record(await context.storage.get(CACHE_KEY))
        if record is not None:
            record_exists=await context.assets.exists('nlf',record['model_name'])
    selected=choose_nlf_cached_asset(url,legacy_exists,record,record_exists)
    if selected is None:
        raise RuntimeError(
            'Original NLF cache miss requires admitted original TorchScript assets and '
            'a verified managed acquisition mapping for both original URLs. This node is '
            'not registered until that public admission contract is implemented.')
    return await load_nlf_resource(selected['model_name'],warmup,
        expected_sha256=selected['sha256'])


class DownloadAndLoadNLFModel(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('assets','raw','models.download','storage')

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='DownloadAndLoadNLFModel',display_name='(Download)Load NLF Model',
            category='WanVideoWrapper',inputs=[io.Combo.Input('url',options=list(URLS),default=URLS[0]),
                io.Boolean.Input('warmup',default=True,optional=True,tooltip='Whether to warmup the model after loading')],
            outputs=[io.Custom('NLFMODEL').Output(display_name='nlf_model')])

    @classmethod
    async def execute(cls,url,warmup=True):
        _,recipe=await load_existing_original_nlf_cache(url,warmup)
        return io.NodeOutput(recipe)


# No NODE_CLASS_MAPPINGS: original cache-miss behavior is still unimplemented.
