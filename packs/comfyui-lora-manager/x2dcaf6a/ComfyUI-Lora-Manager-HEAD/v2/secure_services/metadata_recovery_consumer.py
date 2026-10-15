"""Real managed sampling-name consumer; canonical image/mask still pending."""
from __future__ import annotations

from comfy_api.latest import sdk

from .image_metadata_source import read_image_source
from .metadata_catalogue import read_metadata_catalogue
from ..secure_algorithms.metadata_recovery import prepare_settings, finish_settings


async def recover_managed_settings(name, *, sampler_node_id='', missing_settings='use_defaults',
                                   overrides_json='{}', prefer_saved_image_metadata=True):
    source = await read_image_source(name, interpret=False)
    names = await sdk.ctx().models.sampling_names()
    if type(names) is not dict or set(names) != {'samplers', 'schedulers'}:
        raise ValueError('Sampling catalogue response identity is invalid')
    diagnostics = 'Managed input: ' + source['name'] + '; SHA256: ' + source['sha256']
    prepared = prepare_settings(source['fields'], image_width=source['width'], image_height=source['height'],
        samplers=names['samplers'], schedulers=names['schedulers'], diagnostics=diagnostics,
        sampler_node_id=sampler_node_id, missing_settings=missing_settings, overrides_json=overrides_json,
        prefer_saved_image_metadata=prefer_saved_image_metadata)
    try:
        catalogue = await read_metadata_catalogue()
    except PermissionError:
        raise
    except (ValueError, TypeError, KeyError, OSError) as error:
        # Original library errors produce a diagnostic + unresolved names.
        # Capability failures are not covered here and remain execution errors.
        return finish_settings(prepared, [], source['name'], library_error=str(error))
    return finish_settings(prepared, catalogue, source['name'])
