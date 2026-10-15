import asyncio
import copy
from pathlib import Path
import sys

import pytest
from test_ned_comfyroll_cycle_models import NEW, V2
import folder_paths
from comfy_api.latest import io
from comfy_secure_nodes import packdb
from comfy_secure_nodes.packmanifest import encode_schema

sys.path.insert(0, '/Users/ben/comfy/ComfyUI_secure_nodes/backend/tests')
from test_remote_catalogue_admission import _validator


ROWS = [(node_id, item.id) for node_id, cls in NEW.NODE_CLASS_MAPPINGS.items()
        for item in cls.define_schema().inputs
        if isinstance(item, io.Combo.Input) and item.remote is not None and '/models/' in item.remote.route]


def test_exact_33_model_fields_have_closed_catalogue_owners():
    assert len(ROWS) == 33 and len({node_id for node_id, _ in ROWS}) == 13
    for node_id, input_id in ROWS:
        item = next(x for x in NEW.NODE_CLASS_MAPPINGS[node_id].define_schema().inputs if x.id == input_id)
        assert item.remote.route.startswith('/secure-nodes/models/'), (node_id, input_id, item.remote.route)
        assert packdb.remote_catalogue_options(item.remote.route) is not None
        if item.options == ['None']:
            assert item.remote.static_options == ['None']


@pytest.mark.parametrize('node_id,input_id', ROWS)
def test_actual_model_files_refresh_stale_removal_and_canonical_field_admission(node_id, input_id, tmp_path, monkeypatch):
    cls = NEW.NODE_CLASS_MAPPINGS[node_id]
    item = next(x for x in cls.define_schema().inputs if x.id == input_id)
    folder = item.remote.route.rsplit('/', 1)[-1]
    root = tmp_path / folder
    root.mkdir()
    monkeypatch.setitem(folder_paths.folder_names_and_paths, folder, ([str(root)], {'.safetensors'}))
    monkeypatch.delitem(folder_paths.filename_list_cache, folder, raising=False)
    for name in ['a.safetensors', 'z.safetensors']:
        (root / name).write_bytes(b'inert catalogue fixture; not weights')
    declared = copy.deepcopy(encode_schema(io.Schema(node_id='ModelField', inputs=[item], outputs=[io.String.Output()])))
    definition = {'class': 'ModelField', 'schema': declared}
    before = copy.deepcopy(definition)
    proxy = packdb._proxy_class('custom_nodes.comfyroll_model_field', V2 / '__init__.py', definition)
    validate = _validator({'ModelField': proxy})
    static = ['None'] if item.options == ['None'] else []
    assert proxy.define_schema().inputs[0].options == static + ['a.safetensors', 'z.safetensors']
    for name in static + ['a.safetensors', 'z.safetensors']:
        assert asyncio.run(validate('ModelField', {input_id: name}))[0]
    for invalid in ['../a.safetensors', str(root / 'a.safetensors'), 'missing.safetensors']:
        assert not asyncio.run(validate('ModelField', {input_id: invalid}))[0]
    (root / 'a.safetensors').unlink()
    monkeypatch.delitem(folder_paths.filename_list_cache, folder, raising=False)
    assert proxy.define_schema().inputs[0].options == static + ['z.safetensors']
    assert not asyncio.run(validate('ModelField', {input_id: 'a.safetensors'}))[0]
    (root / 'z.safetensors').unlink()
    monkeypatch.delitem(folder_paths.filename_list_cache, folder, raising=False)
    assert proxy.define_schema().inputs[0].options == static
    if static:
        assert asyncio.run(validate('ModelField', {input_id: 'None'}))[0]
    else:
        assert not asyncio.run(validate('ModelField', {input_id: 'None'}))[0]
    assert definition == before
