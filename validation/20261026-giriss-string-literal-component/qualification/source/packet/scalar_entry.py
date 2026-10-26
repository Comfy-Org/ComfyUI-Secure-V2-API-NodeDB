"""One unrun scalar entry for the inherited finite Mac owner payload slot.

Reuses d304 observation and the retained GIRISS Guest start/finally recipe.
Only the unchanged explicit hook/13 cases/2 controls run in this payload.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def checked(row):
    path = Path(row['path']).resolve(strict=True)
    assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    return path


def module_at(name, path):
    assert name not in sys.modules
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def scalar_entry(config, output, report):
    from comfy_secure_nodes.transport.host import GuestSession
    from comfy_api.latest import _sdk
    host_pin = config['support_source_pins']['host']
    assert Path(inspect.getfile(GuestSession)).resolve() == checked(host_pin)
    hook = module_at('_giriss_explicit_hook', HERE/'consumer/owner_session_hook.py')
    observer = module_at('_giriss_d304_observer', HERE/'guest_startup_observer.py')
    prior_backend = _sdk.providers.execution_backend
    session = creation_observer = None
    guest_pgid = sockdir = None
    try:
        # Same existing observed ordinary-Guest construction/start pattern;
        # no managed runtime, model, encoder or all9 fixture initialization.
        creation_observer = observer.GuestStartupObserver(output, config['observer_binding']['subprocess_source'])
        session = GuestSession('giriss-string-literal', runtime=None,
            tenant=config['tenant_id'], work_root=Path(config['owned_guest_work_root']),
            guest_runtime_root=Path(config['pack_root'])/'v2')
        creation_observer.begin_creation()
        try:
            await session.start()
        finally:
            creation_observer.end_creation()
            report['creation_observation'] = creation_observer.snapshot()
        report['actual_startup'] = creation_observer.verify_session(session)
        guest_pgid, sockdir = session._pgid, Path(session._sockdir)
        report['Guest_instances'] = 1
        # The concrete owner -> driver -> live observed session -> consumer join.
        focused = await hook.compare_in_existing_owner(config, session, creation_observer)
        report['consumer'] = focused['consumer']
        report['actual_startup'] = focused['verified_actual_startup']
        report['lifecycle_owner'] = focused['lifecycle_owner']
        report['scope_complete'] = True
    finally:
        cleanup_errors = []
        try:
            _sdk.providers.register_execution_backend(prior_backend)
        except BaseException as error:
            cleanup_errors.append('restore provider: '+repr(error))
        if session is not None:
            # Save actual PGID/socket before kill clears the session fields.
            selected_pgid = guest_pgid or session._pgid
            selected_sockdir = sockdir or (Path(session._sockdir) if session._sockdir else None)
            try:
                await asyncio.wait_for(session.kill(), 3)
                if selected_pgid is not None:
                    try:
                        os.killpg(selected_pgid, 0)
                    except ProcessLookupError:
                        report['normal_path_guest_group_absent'] = True
                    else:
                        raise AssertionError('Guest group remains')
                if selected_sockdir is not None:
                    assert not selected_sockdir.exists(), 'Guest socket directory remains'
                    report['normal_path_guest_socket_absent'] = True
            except BaseException as error:
                cleanup_errors.append('Guest kill/absence: '+repr(error))
        if creation_observer is not None:
            report['creation_observation'] = creation_observer.snapshot()
            try:
                assert not creation_observer.errors, 'Actual creation observer reported errors'
                creation_observer.close()
            except BaseException as error:
                cleanup_errors.append('creation observer close: '+repr(error))
        report['cleanup_errors'] = cleanup_errors
        if cleanup_errors:
            raise RuntimeError('Existing scalar Guest cleanup failed: '+repr(cleanup_errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--authorization-message', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    assert hashlib.sha256(args.config.read_bytes()).hexdigest() == args.config_sha256
    config = json.loads(args.config.read_bytes())
    assert config['execution_selected'] is True
    assert config['authorization_message'] == args.authorization_message
    assert args.authorization_message.startswith('m_') and args.authorization_message not in (
        'm_d2bcc1db10','m_1053376416','m_914ef8db07','m_09f9070f28','m_5fee0f86ca')
    assert sys.platform == 'darwin' and sys.flags.isolated and not sys.flags.no_site and sys.dont_write_bytecode
    assert not os.environ.get('COMFY_UNSANDBOXED_NODES')
    checked(config['actual_interpreter_profile'])
    checked(config['actual_accepted_owner'])
    for row in config['actual_source_pins'].values():
        checked(row)
    for row in config['support_source_pins'].values():
        checked(row)
    checked(config['observer_binding']['subprocess_source'])
    assert hashlib.sha256((HERE/'INPUTS.json').read_bytes()).hexdigest() == config['input_manifest_sha256']
    pins = json.loads((HERE/'INPUTS.json').read_bytes())
    for relative, row in pins.items():
        path = (HERE/relative).resolve(strict=True)
        assert path.is_relative_to(HERE.resolve()) and not path.is_symlink()
        assert path.stat().st_size == row['bytes']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    output = args.output
    assert output.is_absolute() and not output.exists() and not output.is_symlink()
    assert not output.resolve().is_relative_to(HERE.resolve())
    assert Path(config['owned_guest_work_root']).resolve() == output.resolve()/'work'
    output.mkdir(mode=0o700)
    (output/'work').mkdir(mode=0o700)
    sys.path[:0] = [str(HERE/'consumer'), *config['host_import_roots']]
    sys.argv = [sys.argv[0], '--cpu']
    report = dict(status='FAILED_GIRISS_STRING_LITERAL_COMPONENT',
        authorization_message=args.authorization_message, consumer={}, Guest_instances=0,
        actual_startup={}, cleanup_errors=[], normal_generator_runs=0, replay_runs=0,
        whole_pack_accepted=False, retirement_requires_independent_owner_evidence=True)
    try:
        asyncio.run(scalar_entry(config, output, report))
        assert report['normal_path_guest_group_absent'] and report['normal_path_guest_socket_absent']
        assert report['scope_complete'] and report['cleanup_errors'] == []
        report['status'] = 'PASS_GIRISS_STRING_LITERAL_ORIGINAL_DEFAULT_GUEST_ONLY'
    except BaseException as error:
        report['error'] = dict(type=type(error).__name__, message=str(error)[:4096])
        raise
    finally:
        (output/'RESULT.json').write_text(json.dumps(report,indent=2,ensure_ascii=True)+'\n')


if __name__ == '__main__':
    main()
