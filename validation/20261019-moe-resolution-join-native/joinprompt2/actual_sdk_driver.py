"""Prepared genuine Core/original/SDK test; no synthetic server or SDK."""
import argparse
import asyncio
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys

def mount(root, name):
    spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
    assert spec is not None and spec.loader is not None and name not in sys.modules
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def compare(actual, expected):
    assert actual == expected, 'Genuine original value/error differs'

def record_outcome(cls, values, io):
    try:
        value = cls.execute(**values)
    except Exception as error:
        return ('error', type(error).__name__, str(error))
    assert isinstance(value, io.NodeOutput) and type(value.result) is tuple and len(value.result) == 1
    assert type(value.result[0]) is str
    return ('value', value.result)

def main():
    parser = argparse.ArgumentParser()
    for name in ('backend', 'site', 'core', 'original', 'candidate', 'vectors', 'scratch', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    sys.path[:0] = [str(args.backend), str(args.site), str(args.core)]
    root = args.scratch.resolve(strict=True)
    assert root == args.scratch and root.is_absolute()
    owned = {}
    for name in ('base', 'user', 'models', 'frontend', 'input', 'output', 'temporary'):
        owned[name] = root / name
        owned[name].mkdir(exist_ok=False)
    sys.argv = ['joinprompt-real-sdk', '--cpu', '--offline', '--disable-assets', '--disable-all-custom-nodes',
                '--base-directory', str(owned['base']), '--user-directory', str(owned['user']),
                '--models-directory', str(owned['models']), '--front-end-root', str(owned['frontend']),
                '--database-url', 'sqlite:///:memory:']
    import comfy.options
    comfy.options.enable_args_parsing()
    import comfy.cli_args
    import folder_paths
    assert Path(comfy.cli_args.__file__).resolve().is_relative_to(args.core.resolve())
    assert comfy.cli_args.args.cpu and comfy.cli_args.args.disable_assets and comfy.cli_args.args.offline
    folder_paths.set_user_directory(str(owned['user']))
    folder_paths.set_input_directory(str(owned['input']))
    folder_paths.set_output_directory(str(owned['output']))
    folder_paths.set_temp_directory(str(owned['temporary']))
    for getter in (folder_paths.get_user_directory, folder_paths.get_input_directory,
                   folder_paths.get_output_directory, folder_paths.get_temp_directory):
        assert Path(getter()).resolve().is_relative_to(root)
    from comfy_api.latest import io, ComfyExtension
    from comfy_secure_nodes import packmanifest
    assert Path(io.__file__).resolve().is_relative_to(args.site.resolve())
    assert Path(packmanifest.__file__).resolve().is_relative_to(args.backend.resolve())
    vectors = json.loads(args.vectors.read_bytes())
    assert vectors['planned_differential_count'] == 704 and len(vectors['direct_cases']) == 699

    async def exercise():
        # All dependencies below are genuine installed/Core implementations.
        import server
        from app.assets.manager import default_asset_manager, NoAssets
        assert Path(server.__file__).resolve() == (args.core / 'server.py').resolve()
        assert hashlib.sha256(Path(server.__file__).read_bytes()).hexdigest() == '50be822484b0f77d17b76306c7b7a5cc6f276992eed5ce4a2db4b459f24c47e9'
        assets = default_asset_manager()
        assert isinstance(assets, NoAssets) and assets.enabled is False
        instance = None
        prior_instance = getattr(server.PromptServer, 'instance', None)
        cleanup = {'client_session_closed': False, 'app_cleaned': False, 'asset_manager_shutdown': False, 'owned_paths_checked': False}
        try:
            instance = server.PromptServer(asyncio.get_running_loop(), assets)
            assert type(instance) is server.PromptServer and server.PromptServer.instance is instance
            assert instance.asset_manager is assets
            assert instance.client_session is None, 'setup was not called; unexpected session requires review'
            before_routes = Counter((route.method, route.path) for route in instance.routes)
            original = mount(args.original, '_join_full_original_actual')
            extension = await original.comfy_entrypoint()
            assert isinstance(extension, ComfyExtension)
            native_classes = await extension.get_node_list()
            ids = ['jupo.JoinPrompt.JoinStrings', 'jupo.JoinPrompt.JoinPrompt']
            assert [cls.GET_SCHEMA().node_id for cls in native_classes] == ids
            native = dict(zip(ids, native_classes, strict=True))
            assert Counter((route.method, route.path) for route in instance.routes) == before_routes
            assert sys.modules['_join_full_original_actual.py.utils'].Endpoint.routes is instance.routes
            converted = mount(args.candidate, '_join_candidate_actual')
            assert list(converted.NODE_CLASS_MAPPINGS) == ids
            candidate_extension = await converted.comfy_entrypoint()
            assert isinstance(candidate_extension, ComfyExtension)
            assert await candidate_extension.get_node_list() == list(converted.NODE_CLASS_MAPPINGS.values())
            helper_spec = importlib.util.spec_from_file_location('_join_component_loader', Path(__file__).resolve().parent / 'original_components.py')
            assert helper_spec is not None and helper_spec.loader is not None
            helper = importlib.util.module_from_spec(helper_spec)
            helper_spec.loader.exec_module(helper)
            components, component_scope = helper.mount_components(args.original)
            schemas = {}
            for node_id in ids:
                cls = converted.NODE_CLASS_MAPPINGS[node_id]
                assert issubclass(cls, io.ComfyNode) and cls.SDK_REFS is False and cls.SDK_PERMISSIONS == ()
                expected = packmanifest.encode_schema(native[node_id].GET_SCHEMA())
                actual = packmanifest.encode_schema(cls.GET_SCHEMA())
                assert actual == expected == packmanifest.encode_schema(components[node_id].GET_SCHEMA())
                assert [row['io_type'] for row in actual['outputs']] == ['STRING']
                schemas[node_id] = actual
            assert Path(original.WEB_DIRECTORY) == Path(converted.WEB_DIRECTORY) == Path('web')
            assert len(schemas) == 2
            rng_before = random.getstate()
            cases = list(vectors['direct_cases'])
            for recipe in vectors['boundary_recipes']:
                text = recipe['char'] * recipe['repeat']
                values = {'texts': {f'text_{i}': text for i in range(recipe['rows'])}, 'delimiter': '', 'cleanup': recipe['cleanup']}
                cases.append({'id': recipe['id'], 'node': ids[0], 'inputs': values})
            summaries = []
            for case in cases:
                expected = record_outcome(native[case['node']], case['inputs'], io)
                compare(record_outcome(converted.NODE_CLASS_MAPPINGS[case['node']], case['inputs'], io), expected)
                compare(record_outcome(components[case['node']], case['inputs'], io), expected)
                if expected[0] == 'value':
                    text = expected[1][0]
                    observed = {'kind': 'value', 'characters': len(text), 'sha256_utf8_surrogatepass': hashlib.sha256(text.encode('utf-8', errors='surrogatepass')).hexdigest()}
                else:
                    observed = {'kind': 'error', 'type': expected[1], 'message': expected[2]}
                summaries.append(dict(observed, case_id=case['id'], node_id=case['node']))
            assert len(summaries) == 704
            guards = []
            for recipe in vectors['guard_denial_recipes']:
                node_id = recipe.get('node', ids[0])
                values = {'texts': {}, 'delimiter': '', 'cleanup': False} if node_id == ids[0] else {'text': 'a', 'prev': '', 'options': ''}
                text = recipe['char'] * recipe['repeat']
                values[recipe['field']] = {f'text_{i}': text for i in range(recipe['rows'])} if recipe['field'] == 'texts' else text
                if 'cleanup' in recipe:
                    values['cleanup'] = recipe['cleanup']
                outcome = record_outcome(converted.NODE_CLASS_MAPPINGS[node_id], values, io)
                assert outcome[0] == 'error' and outcome[1] == 'ValueError'
                guards.append({'id': recipe['id'], 'type': outcome[1], 'message': outcome[2]})
            assert len(guards) == 7
            control_cases = [
                (ids[0], {'texts': {'text_2': 'second', 'text_0': 'zero', 'text_1': 'first'}, 'delimiter': '|'}, ('value', ('zero|first|second',))),
                (ids[0], {'texts': {'text_0': 'a', 'text_1': 'b'}, 'delimiter': r'\n'}, ('value', (r'a\nb',))),
                (ids[0], {'texts': {'text_0': ' a ,,b ', 'text_1': 'c'}, 'delimiter': '\n', 'cleanup': True}, ('value', ('a, b\nc',))),
                (ids[1], {'text': 'new', 'prev': 'old', 'options': '{"delimiter":"|"}'}, ('value', ('new',))),
                (ids[1], {'text': 'a', 'prev': 'b', 'options': '{broken'}, ('error', 'ValueError', 'bad json')),
                (ids[1], {'text': 'a', 'options': '[]'}, ('value', ('a',))),
            ]
            controls = []
            for label, (node_id, values, corrupted) in zip(vectors['wrong_controls'], control_cases, strict=True):
                expected = record_outcome(native[node_id], values, io)
                compare(record_outcome(converted.NODE_CLASS_MAPPINGS[node_id], values, io), expected)
                try:
                    compare(corrupted, expected)
                except AssertionError:
                    controls.append({'control': label, 'detected': True})
                else:
                    raise AssertionError('Wrong-output control escaped actual comparator: ' + label)
            assert len(controls) == 6 and random.getstate() == rng_before
            return {'status': 'PASS_GENUINE_FULL_ORIGINAL_AND_REAL_SELECTED_SDK_COMPONENTS_ONLY',
                    'node_ids': ids, 'schemas': schemas, 'execution_comparisons': 704,
                    'component_crosschecks': 704, 'outcome_summaries': summaries,
                    'guard_denials': guards, 'negative_controls': controls,
                    'full_original_entrypoint_imported': True, 'synthetic_server_or_sdk': False,
                    'real_server_constructor': True, 'server_setup_or_listeners_started': False,
                    'route_registration_count_before_and_after': sum(before_routes.values()),
                    'original_added_routes': 0, 'component_oracle_scope': component_scope,
                    'sdk_io_origin': str(Path(io.__file__).resolve()), 'server_origin': str(Path(server.__file__).resolve()),
                    'encoder_origin': str(Path(packmanifest.__file__).resolve()),
                    'frontend_or_guest_or_service_or_general_adoption': False,
                    'cleanup': cleanup}
        finally:
            for getter in (folder_paths.get_user_directory, folder_paths.get_input_directory,
                           folder_paths.get_output_directory, folder_paths.get_temp_directory):
                assert Path(getter()).resolve().is_relative_to(root)
            cleanup['owned_paths_checked'] = True
            if instance is not None and instance.client_session is not None:
                await instance.client_session.close()
            cleanup['client_session_closed'] = instance is None or instance.client_session is None or instance.client_session.closed
            if instance is not None:
                await instance.app.cleanup()
            cleanup['app_cleaned'] = True
            assets.shutdown()
            cleanup['asset_manager_shutdown'] = True
            server.PromptServer.instance = prior_instance
    report = asyncio.run(exercise())
    assert all(report['cleanup'].values())
    with args.output.open('x') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: report[key] for key in ('status', 'node_ids', 'execution_comparisons', 'component_crosschecks')}))

if __name__ == '__main__':
    main()
