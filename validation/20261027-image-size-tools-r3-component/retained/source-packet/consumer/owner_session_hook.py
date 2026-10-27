"""Focused unrun join; the existing owner creates and retires its one Guest."""
import hashlib
import inspect
import os
from pathlib import Path

from focused_consumer import compare_image_size_tools


async def compare_in_existing_owner(actual_config, observed_session, creation_observer):
    assert actual_config['execution_selected'] is True
    assert actual_config['authorization_message'] and actual_config['actual_accepted_owner']
    assert os.environ.get('COMFY_SECURE_SANDBOX_MODE') == 'required'
    assert os.environ.get('COMFY_SECURE_SANDBOX_BACKEND') == 'seatbelt'
    observer_source = Path(inspect.getfile(type(creation_observer))).resolve()
    assert hashlib.sha256(observer_source.read_bytes()).hexdigest() == (
        'd304ef30e21d2c70886177f0635b7dde64b20ab9da0a1ce7e9fe881974fd4488')
    pack = Path(actual_config['pack_root']).resolve(strict=True)
    assert pack.name == 'ComfyUI-Image-Size-Tools-HEAD'
    assert pack.parent.name == 'x1cb252c' and pack.parent.parent.name == 'image-size-tools'
    assert Path(observed_session.guest_runtime_root).resolve() == pack/'v2'
    assert Path(observed_session.work_root).resolve() == Path(actual_config['owned_guest_work_root']).resolve()
    assert observed_session.pack_runtime is None
    tenant = actual_config['tenant_id']
    assert tenant == 'image-size-tools-owned-component' == observed_session.tenant_epoch
    assert observed_session.tenant in ('', tenant)
    startup = creation_observer.verify_session(observed_session)
    assert startup['pid'] == observed_session.pid
    assert startup['sandbox_kind'] == observed_session.sandbox_kind == 'seatbelt'
    assert startup['actual_profile_matches_genuine_supported_source_recipe'] is True
    forbidden = {Path('/'), Path('<private-path:df4a3fcc00a1a54a>'), Path('<private-path:7287631717aac754>'), Path('<private-path:11fe14a563f7aed6>')}
    assert not any(Path(path).resolve() in forbidden for path in startup['ordered_read_roots_source_bound'])
    result = await compare_image_size_tools(actual_config, observed_session,
        Path(actual_config['owned_guest_work_root']).parent)
    assert result['status'] == 'PASS_FINITE_COMPONENT_ONLY'
    assert result['ordinary'] == len(result['rows']) == 76
    assert result['separate_diagnostics'] == len(result['diagnostics']) == 6
    assert result['counts']['actual_Guest_dispatches'] == 83
    assert observed_session.tenant == tenant
    return dict(consumer=result, verified_actual_startup=startup,
        lifecycle_owner=actual_config['actual_accepted_owner'],
        retirement_credit_from_this_hook=False, whole_pack_accepted=False)

