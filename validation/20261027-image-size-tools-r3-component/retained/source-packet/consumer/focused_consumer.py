"""Unrun Image Size Tools join to the accepted owner's already started Guest.

The immutable R1 body owns only the finite comparisons and restores the stock
backend. Creation, live policy evidence, deadlines and retirement stay with the
existing observed owner. Scientific and SDK imports occur only in a separately
selected future invocation of compare_image_size_tools.
"""
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import stat
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    root = Path(root).resolve(strict=True)
    rows = {}
    for path in sorted(root.rglob('*')):
        assert not path.is_symlink(), 'No source symlinks'
        if path.is_file():
            rows[path.relative_to(root).as_posix()] = dict(
                bytes=path.stat().st_size, sha256=digest(path),
                mode=stat.S_IMODE(path.stat().st_mode))
    return rows


def source_module(name, path, package=False):
    assert name not in sys.modules, 'Load each frozen source module exactly once'
    spec = importlib.util.spec_from_file_location(name, path,
        submodule_search_locations=[str(path.parent)] if package else None)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def compare_image_size_tools(config, session, output):
    assert config['execution_selected'] is True and config['authorization_message']
    assert sys.version_info[:2] == (3, 13), 'Use qualified Python 3.13 explicitly'
    import comfy_api.latest as latest
    from comfy_api.latest import io, _sdk
    from comfy_secure_nodes.transport import host, wire
    import torch

    here = Path(__file__).resolve().parent
    source = json.loads((here/'PACK_SOURCE.json').read_bytes())
    pack = Path(config['pack_root']).resolve(strict=True)
    assert pack == (here.parent/source['packet_pack_relative']).resolve(strict=True)
    assert inventory(pack) == source['files'], 'Frozen 15-original/20-candidate bytes and modes differ'
    assert len(source['files']) == 35
    assert type(session) is host.GuestSession and session.pid != os.getpid()
    assert session._pgid == session.pid and session.sandbox_kind == 'seatbelt'
    assert session.pack_runtime is None
    assert type(_sdk.providers.execution_backend) is _sdk.InProcessExecutionBackend
    assert type(_sdk.providers.ctx_provider) is _sdk.InProcessCtxProvider
    assert type(_sdk.providers.ops_provider) is _sdk.InProcessOps
    assert _sdk.providers.ref_resolver_factory is _sdk.InProcessRefResolver
    assert not _sdk.providers.engaged and not _sdk.providers.overlay_active
    actual_paths = dict(io=Path(io.__file__), sdk=Path(_sdk.__file__),
        latest_init=Path(latest.__file__), io_impl=Path(inspect.getfile(io.NodeOutput)))
    for name, path in actual_paths.items():
        row = config['actual_source_pins'][name]
        assert path.resolve() == Path(row['path']).resolve(strict=True)
        assert digest(path) == row['sha256'], 'Selected public facade/implementation differs: '+name
    assert digest(host.__file__) == config['support_source_pins']['host']['sha256']
    assert Path(host.__file__).resolve() == Path(config['support_source_pins']['host']['path']).resolve(strict=True)
    providers = {name:getattr(_sdk.providers, name) for name in
        ('execution_backend', 'ctx_provider', 'ops_provider', 'ref_resolver_factory')}
    original = source_module('_image_size_tools_genuine_original', pack/'__init__.py', package=True)
    candidate = source_module('_image_size_tools_frozen_candidate', pack/'v2/__init__.py', package=True)
    fixture = source_module('_image_size_tools_r1_fixture', here/'image_size_fixture.py')
    assert Path(fixture.HERE).resolve() == here
    assert digest(fixture.__file__) == source['fixture_sha256']
    for name in ('CASES.json', 'SCHEMAS.json'):
        assert digest(fixture.HERE/name) == source['fixture_inputs'][name]['sha256']
    for node_id in source['node_ids']:
        assert Path(inspect.getfile(original.NODE_CLASS_MAPPINGS[node_id])).resolve() == pack/'image_size_nodes.py'
        assert Path(inspect.getfile(candidate.NODE_CLASS_MAPPINGS[node_id])).resolve() == pack/'v2/image_size_nodes.py'
    try:
        result = await fixture.run_owned_component(original=original, candidate=candidate,
            io=io, sdk=_sdk, host=host, wire=wire, session=session, torch=torch, output=output)
        assert result['status'] == 'PASS_FINITE_COMPONENT_ONLY'
        assert result['counts'] == dict(original=76, default=76, Guest=76,
            diagnostics_original=6, diagnostics_default=6, diagnostics_Guest=6,
            actual_default_local_calls=82, actual_Guest_dispatches=83)
        assert len(result['rows']) == 76 and len(result['diagnostics']) == 6
        assert len(result['controls']) == 7 and all(row['detected'] is True for row in result['controls'])
        assert result['Guest_creations_by_body'] == 0 and result['expected_outer_observed_Guest_creations'] == 1
        assert result['required_real_guest_pid'] == session.pid
        smoke = json.loads((Path(output)/'SMOKE.json').read_bytes())
        assert smoke['status'] == 'PASS_STRICT_FIRST_ORIGINAL_DEFAULT_REQUIRED_GUEST_1_1_1'
        assert smoke['case'] == source['smoke_case_id']
        assert smoke['counts'] == dict(original=1, default=1, Guest=1,
            diagnostics_original=0, diagnostics_default=0, diagnostics_Guest=0,
            actual_default_local_calls=1, actual_Guest_dispatches=1)
        assert smoke['strict_outcomes_equal'] is True and smoke['guest_pid'] == session.pid
        result.update(authorization_message=config['authorization_message'],
            actual_Guest_pid=session.pid, smoke=smoke,
            source_bindings={name:dict(path=str(path.resolve()), sha256=digest(path))
                for name, path in actual_paths.items()},
            loaded_original_candidate_fixture_once=True,
            error_pid_evidence='last_guest_pid may be cached on error; diagnostic/refusal attribution is limited to this observed owned session, execute phase and candidate frames',
            whole_pack_accepted=False)
        return result
    finally:
        assert all(getattr(_sdk.providers, name) is value for name, value in providers.items())
        assert inventory(pack) == source['files'], 'Frozen source changed during finite comparisons'

