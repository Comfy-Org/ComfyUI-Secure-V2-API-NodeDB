"""Real SDK declarations/Core catalogue files; Host/UI sentinel merge is unrun."""
import pytest
import folder_paths
from _current_sdk_test_support import module,io
NEW=module('__init__')
ROWS=[(node_id,item.id) for node_id,cls in NEW.NODE_CLASS_MAPPINGS.items()
      for item in cls.GET_SCHEMA().inputs
      if isinstance(item,io.Combo.Input) and item.remote is not None and '/models/' in item.remote.route]
def field(node_id,input_id):
    return next(i for i in NEW.NODE_CLASS_MAPPINGS[node_id].GET_SCHEMA().inputs if i.id==input_id)
def test_exact_33_model_fields_keep_public_routes_and_frozen_options():
    assert len(ROWS)==33 and len({node for node,_ in ROWS})==13
    sentinels=0
    for node,input_id in ROWS:
        item=field(node,input_id)
        assert item.remote.route.startswith('/secure-nodes/models/')
        assert not hasattr(item.remote,'static_options')
        assert item.options in ([],['None'])
        if item.options==['None']:sentinels+=1
    assert sentinels==30
@pytest.mark.parametrize('node_id,input_id',ROWS)
def test_actual_core_catalogue_population_removal_and_empty_refresh(node_id,input_id,tmp_path,monkeypatch):
    item=field(node_id,input_id);folder=item.remote.route.rsplit('/',1)[-1]
    root=tmp_path/folder;root.mkdir()
    monkeypatch.setitem(folder_paths.folder_names_and_paths,folder,([str(root)],{'.safetensors'}))
    monkeypatch.delitem(folder_paths.filename_list_cache,folder,raising=False)
    original=list(item.options)
    assert folder_paths.get_filename_list(folder)==[]
    for name in ['a.safetensors','z.safetensors']:(root/name).write_bytes(b'inert catalogue data; never model weights')
    monkeypatch.delitem(folder_paths.filename_list_cache,folder,raising=False)
    assert folder_paths.get_filename_list(folder)==['a.safetensors','z.safetensors']
    (root/'a.safetensors').unlink();monkeypatch.delitem(folder_paths.filename_list_cache,folder,raising=False)
    assert folder_paths.get_filename_list(folder)==['z.safetensors']
    (root/'z.safetensors').unlink();monkeypatch.delitem(folder_paths.filename_list_cache,folder,raising=False)
    assert folder_paths.get_filename_list(folder)==[]
    assert item.options==original
    # This test does not execute Host proxy validation or browser getValue.
    # None's UI loss on remote refresh remains an explicit partial purpose.
