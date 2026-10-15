"""Exact exported converter behavior with synthetic states, real broker/guest."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import sys

import numpy as np
import pytest
import torch
from safetensors.torch import load_file, save_file
from safetensors import safe_open

V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent
sys.dont_write_bytecode = True


def load(name, path, package=False):
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def gguf_string(value):
    value = value.encode()
    return struct.pack('<Q', len(value)) + value


def synthetic_gguf():
    metadata = gguf_string('general.architecture') + struct.pack('<I', 8) + gguf_string('pig')
    tensor = gguf_string('vector') + struct.pack('<IQQIQ', 2, 3, 2, 0, 0)
    header = b'GGUF' + struct.pack('<IQQ', 3, 1, 1) + metadata + tensor
    header += b'\0' * ((-len(header)) % 32)
    return header + np.array([.25, -.3, 1.25, 70000., -1000., 0.], dtype=np.float32).tobytes()


@pytest.mark.parametrize('node_name', ['TENSORBoost', 'GGUFUndo'])
def test_exported_node_actual_guest_outer_fresh_render(node_name, tmp_path, monkeypatch):
    from comfy.cli_args import args
    monkeypatch.setattr(args, 'cpu', True)
    from comfy_api.latest import _sdk
    from comfy_secure_nodes.transport.host import GuestSession
    from comfy_secure_nodes.transport.wire import WireError
    import folder_paths

    catalogue = tmp_path / 'synthetic-operator-catalogue'
    catalogue.mkdir()
    state = {'vector': torch.arange(6, dtype=torch.float16).reshape(2, 3), 'scalar': torch.tensor(3, dtype=torch.int64), 'boolean': torch.tensor([True, False])}
    save_file(state, str(catalogue / 'synthetic.safetensors'))
    (catalogue / 'synthetic.gguf').write_bytes(synthetic_gguf())
    monkeypatch.setitem(folder_paths.folder_names_and_paths, 'diffusion_models', ([str(catalogue)], {'.safetensors', '.gguf'}))
    output_dir = tmp_path / 'managed-output'
    output_dir.mkdir()
    monkeypatch.setattr(folder_paths, 'output_directory', str(output_dir))
    if node_name == 'TENSORBoost':
        arguments = {'select_safetensors': 'synthetic.safetensors'}
        expected = {k: v.to(torch.float32) for k, v in state.items()}
        expected_metadata = None
    else:
        arguments = {'select_gguf': 'synthetic.gguf'}
        root = importlib.util.module_from_spec(importlib.machinery.ModuleSpec('moe_pinned_undo', None, is_package=True))
        root.__path__ = [str(PACK / 'gguf_connector')]
        sys.modules[root.__name__] = root
        reader_module = importlib.import_module(root.__name__ + '.reader')
        reader = reader_module.GGUFReader(catalogue / 'synthetic.gguf')
        expected = {'vector': torch.from_numpy(reader.tensors[0].data.copy()).to(torch.float16)}
        expected_metadata = {key: str(field) for key, field in reader.fields.items()}

    def verify_file(path):
        actual = load_file(str(path))
        assert list(sorted(actual)) == list(sorted(expected))
        assert all(torch.equal(actual[k], expected[k]) and actual[k].dtype == expected[k].dtype for k in expected)
        with safe_open(str(path), framework='pt') as file:
            assert file.metadata() == expected_metadata

    async def run():
        pids, artifacts = [], []
        for render in range(2):
            current = tmp_path / ('fresh-' + node_name + str(render))
            shutil.copytree(V2, current)
            prefix = 'moe_exported_gguf_' + node_name + str(render)
            pack = load(prefix, current / '__init__.py', True)
            node = pack.NODE_CLASS_MAPPINGS[node_name]
            session = await GuestSession(prefix, guest_runtime_root=current).start()
            try:
                refs = _sdk.InProcessRefResolver()
                plan = _sdk.ExecutionPlan(prompt_id='gguf-synthetic', node_id='1', node_type=node_name, node_module=node.__module__, tier='raw', input_mode='values', permissions=node.SDK_PERMISSIONS, inputs=arguments, method='execute')
                runtime = _sdk.Runtime(refs=refs, ctx=_sdk.InProcessCtxProvider().build(plan), ops=_sdk.InProcessOps())
                output = await session.execute(plan, runtime, capabilities=plan.permissions)
                assert not output.result
                files = sorted(output_dir.rglob('*.safetensors'))
                assert len(files) == render + 1
                verify_file(files[-1])
                artifacts.append(str(files[-1].relative_to(output_dir)))
                for missing in plan.permissions:
                    with pytest.raises(WireError):
                        await session.execute(plan, runtime, capabilities=tuple(permission for permission in plan.permissions if permission != missing))
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert len(set(pids)) == 2 and all(pid not in (None, os.getpid()) for pid in pids)

        # Actual outer-executor empty-output contract; no hidden tensor return.
        import execution
        previous = _sdk.providers.execution_backend
        class Backend:
            session = None
            async def dispatch(self, plan, local_call, runtime):
                self.session = await GuestSession('moe-gguf-converter-outer-' + node_name, guest_runtime_root=current).start()
                plan.inputs = await _sdk.wrap_inputs(runtime.refs, plan.inputs)
                return await self.session.execute(plan, runtime, capabilities=plan.permissions)
        backend = Backend()
        _sdk.providers.register_execution_backend(backend)
        try:
            result = await execution._async_map_node_over_list(prompt_id='gguf-outer', unique_id='1', obj=node, input_data_all={k: [v] for k, v in arguments.items()}, func=node.FUNCTION, v3_data=None)
            assert tuple(node.RETURN_TYPES) == () and not result[0].result
            files = sorted(output_dir.rglob('*.safetensors'))
            assert len(files) == 3
            for path in files:
                verify_file(path)
        finally:
            _sdk.providers.register_execution_backend(previous)
            if backend.session:
                await backend.session.kill()
        print('GGUF_EXPORT_OBSERVED ' + json.dumps({'node': node_name, 'synthetic_only': True, 'guest_pids': pids, 'artifacts': artifacts, 'outer_empty_contract': True, 'denials': ['raw', 'assets', 'output'], 'metadata_exact': True}))
    asyncio.run(run())
