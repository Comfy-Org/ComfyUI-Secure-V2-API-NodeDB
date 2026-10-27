"""Explicit unrun GIRISS callback for an existing observed component executor.

The existing owner/executor creates and retires its one Guest. This hook only
joins that object and d304 observation to the six-purpose finite consumer.
"""
import hashlib
import inspect
import os
from pathlib import Path

from focused_consumer import compare_six_purposes


async def compare_in_existing_owner(actual_config, observed_session, creation_observer):
    assert actual_config['execution_selected'] is True
    assert actual_config['authorization_message']
    assert actual_config['actual_accepted_owner']
    assert os.environ.get('COMFY_SECURE_SANDBOX_MODE') == 'required'
    assert os.environ.get('COMFY_SECURE_SANDBOX_BACKEND') == 'seatbelt'
    observer_source = Path(inspect.getfile(type(creation_observer))).resolve()
    assert hashlib.sha256(observer_source.read_bytes()).hexdigest() == (
        'd304ef30e21d2c70886177f0635b7dde64b20ab9da0a1ce7e9fe881974fd4488')
    pack = Path(actual_config['pack_root']).resolve()
    assert pack.name == 'ComfyUI-Image-Saver-HEAD'
    assert pack.parent.name == 'x65e6903' and pack.parent.parent.name == 'comfy-image-saver'
    assert Path(observed_session.guest_runtime_root).resolve() == pack/'v2'
    assert Path(observed_session.work_root).resolve() == Path(actual_config['owned_guest_work_root']).resolve()
    assert observed_session.pack_runtime is None
    tenant = actual_config['tenant_id']
    assert type(tenant) is str and tenant and observed_session.tenant_epoch == tenant
    assert observed_session.tenant in ('', tenant)
    startup = creation_observer.verify_session(observed_session)
    assert startup['pid'] == observed_session.pid
    assert startup['sandbox_kind'] == observed_session.sandbox_kind == 'seatbelt'
    assert startup['actual_profile_matches_genuine_supported_source_recipe'] is True
    forbidden = {Path('/'),Path('<private-path:df4a3fcc00a1a54a>'),Path('<private-path:7287631717aac754>'),Path('<private-path:11fe14a563f7aed6>')}
    assert not any(Path(p).resolve() in forbidden for p in startup['ordered_read_roots_source_bound'])
    result = await compare_six_purposes(actual_config, observed_session)
    assert result['status'] == 'PASS_FOCUSED_GIRISS_SIX_COMPONENT_ONLY'
    assert len(result['rows']) == result['Guest_dispatches'] == 87
    assert result['route_calls'] == {'original':87,'default':87,'Guest':87}
    assert result['first_case_gate']['passed'] is True and result['strict_comparisons'] == 174
    assert len(result['controls']) == 16 and all(c['detected'] and c['additional_dispatches'] == 0 for c in result['controls'])
    assert observed_session.tenant == tenant
    return dict(consumer=result, verified_actual_startup=startup,
        lifecycle_owner=actual_config['actual_accepted_owner'],
        retirement_credit_from_this_hook=False, whole_pack_accepted=False)
