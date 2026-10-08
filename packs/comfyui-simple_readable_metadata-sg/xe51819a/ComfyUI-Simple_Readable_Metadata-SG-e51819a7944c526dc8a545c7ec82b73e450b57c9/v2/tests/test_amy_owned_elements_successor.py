"""Narrow successor delta proof; behavior lives in actual browser probes."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import pytest

V2=Path(os.environ.get('AMY_METADATA_SUCCESSOR_V2',str(Path(__file__).resolve().parents[1]))).resolve()
PROFILE=json.loads((Path(__file__).parent/'owned_elements_inputs.json').read_bytes())

def _root(variable):
    value=os.environ.get(variable)
    if not value:
        raise RuntimeError(variable+' is required: no ambient default or fallback')
    root=Path(value).resolve()
    if not root.is_dir():
        raise RuntimeError(variable+' is not an existing directory')
    return root

def _row(path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Regular immutable input required: '+str(path))
    data=path.read_bytes()
    return {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'mode':path.stat().st_mode&0o777}

def _predecessor():
    root=_root('AMY_METADATA_PREDECESSOR_V2')
    actual={}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('Predecessor symlink refused: '+str(path))
        if path.is_file():
            actual[path.relative_to(root).as_posix()]=_row(path)
    if actual!=PROFILE['predecessor']:
        raise RuntimeError('Predecessor complete file/byte/mode inventory drift')
    return root

def _canonical():
    root=_root('AMY_METADATA_CANONICAL_FRONTEND_ROOT')
    for relative,expected in PROFILE['frontend'].items():
        if _row(root/relative)!=expected:
            raise RuntimeError('Canonical published source/declaration drift: '+relative)
    return root

@pytest.fixture
def OLD():
    return _predecessor()

def test_runtime_delta_is_exactly_owner_scopes_only(OLD):
    before=(OLD/'web/Simple_Readable_Metadata_Text_Viewer_SG.js').read_text()
    expected=before.replace('comfy.element(state.elementName)',"comfy.element(state.elementName, {nodeId: state.ownerNodeId, widget: 'textDisplay'})")
    expected=expected.replace('const state = initialState(node.getProperties()); state.elementName', 'const state = initialState(node.getProperties()); state.ownerNodeId = node.id; state.elementName')
    actual=(V2/'web/Simple_Readable_Metadata_Text_Viewer_SG.js').read_text()
    assert expected==actual and actual.count('comfy.element(')==3
    before=(OLD/'web/Simple_Readable_Metadata_MAX_SG.js').read_text()
    actual=(V2/'web/Simple_Readable_Metadata_MAX_SG.js').read_text()
    assert actual==before.replace('comfy.element(name)',"comfy.element(name, {nodeId: node.id, widget: 'metadata_preview'})")
    assert actual.count('comfy.element(')==1
    assert 'srm-shared-viewer' not in (V2/'web/Simple_Readable_Metadata_Text_Viewer_SG.js').read_text()

def test_no_python_schema_permission_or_resource_drift(OLD):
    for path in V2.glob('*.py'):assert path.read_bytes()==(OLD/path.name).read_bytes()
    assert (V2/'comfy-api.pyi').read_bytes()==(OLD/'comfy-api.pyi').read_bytes()
    assert json.loads((V2/'secure-nodes.json').read_bytes())==json.loads((OLD/'secure-nodes.json').read_bytes())
    for path in (V2/'web').iterdir():
        if path.name in ('Simple_Readable_Metadata_Text_Viewer_SG.js','Simple_Readable_Metadata_MAX_SG.js'):continue
        assert path.read_bytes()==(OLD/'web'/path.name).read_bytes()

def test_provider_scope_declaration_exact_and_unrelated_composite_retained(OLD):
    canonical=(_canonical()/'docs/node-api/comfy-api.d.ts').read_text()
    actual=(V2/'comfy-api.d.ts').read_text()
    assert 'element(name: string, scope?: OwnedElementScope): OwnedElementHandle' in canonical
    assert 'element(name: string, scope?: OwnedElementScope): OwnedElementHandle' in actual
    for fragment in ['readonly nodeId: string','readonly widget: string',"get(property: 'value'): Promise<string>",'listen(']:
        assert fragment in canonical and fragment in actual
    assert 'permanently refuses' in actual
    # Existing model catalogue and typed producer families survive additive change.
    for token in ["'ipadapter'","'vae_approx'",'export interface Comfy','export interface OwnedElementHandle']:
        assert token in (OLD/'comfy-api.d.ts').read_text() and token in actual

@pytest.mark.parametrize('variable,validate',[
    ('AMY_METADATA_PREDECESSOR_V2',_predecessor),
    ('AMY_METADATA_CANONICAL_FRONTEND_ROOT',_canonical)])
def test_missing_root_refuses_without_default(monkeypatch,variable,validate):
    monkeypatch.delenv(variable,raising=False)
    with pytest.raises(RuntimeError,match='required'):validate()

@pytest.mark.parametrize('variable,validate',[
    ('AMY_METADATA_PREDECESSOR_V2',_predecessor),
    ('AMY_METADATA_CANONICAL_FRONTEND_ROOT',_canonical)])
def test_nonexistent_root_refuses(monkeypatch,tmp_path,variable,validate):
    monkeypatch.setenv(variable,str(tmp_path/'absent'))
    with pytest.raises(RuntimeError,match='existing directory'):validate()

def test_drifted_predecessor_refuses_before_delta(OLD,monkeypatch,tmp_path):
    destination=tmp_path/'caller-owned predecessor with spaces'
    shutil.copytree(OLD,destination)
    (destination/'README.md').write_bytes(b'drift')
    monkeypatch.setenv('AMY_METADATA_PREDECESSOR_V2',str(destination))
    with pytest.raises(RuntimeError,match='inventory drift'):_predecessor()

def test_extra_predecessor_file_refuses(OLD,monkeypatch,tmp_path):
    destination=tmp_path/'extra-file'
    shutil.copytree(OLD,destination)
    (destination/'unexpected.txt').write_text('not pinned')
    monkeypatch.setenv('AMY_METADATA_PREDECESSOR_V2',str(destination))
    with pytest.raises(RuntimeError,match='inventory drift'):_predecessor()

def test_drifted_canonical_declaration_refuses(monkeypatch,tmp_path):
    source=_canonical();destination=tmp_path/'canonical with spaces'
    for relative in PROFILE['frontend']:
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source/relative,target)
    (destination/'docs/node-api/comfy-api.d.ts').write_bytes(b'wrong published declaration')
    monkeypatch.setenv('AMY_METADATA_CANONICAL_FRONTEND_ROOT',str(destination))
    with pytest.raises(RuntimeError,match='published source/declaration drift'):_canonical()
