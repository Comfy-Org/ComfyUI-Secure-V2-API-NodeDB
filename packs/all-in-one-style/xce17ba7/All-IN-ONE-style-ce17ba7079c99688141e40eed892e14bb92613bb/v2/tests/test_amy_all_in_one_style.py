"""Complete bundled source/catalogue/options/composition/workload controls."""
import asyncio, hashlib, importlib.util, json, os, shutil, sys
from pathlib import Path
import pytest
sys.dont_write_bytecode = True
V2 = Path(__file__).resolve().parents[1]
PACK = V2.parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path/'__init__.py', submodule_search_locations=[str(path)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

OLD = load('amy_all_in_one_style_pristine', PACK)
NEW = load('amy_all_in_one_style_v2', V2)
SOURCE = sys.modules[NEW.__name__+'.prompt_styler']
ORIGINAL = sys.modules[OLD.__name__+'.prompt_styler']
LIMITS = sys.modules[NEW.__name__+'._limits']
RESOURCES = sys.modules[NEW.__name__+'._resources']
NATIVE = OLD.NODE_CLASS_MAPPINGS['ComfyUIStyler']
CONVERTED = NEW.NODE_CLASS_MAPPINGS['ComfyUIStyler']
MENUS = list(NATIVE.menus)

def defaults():
    fields = {}
    for k,row in NATIVE.INPUT_TYPES()['required'].items():
        fields[k] = row[0][0] if isinstance(row[0],list) else row[1]['default']
    fields['log_prompt'] = False
    return fields

def native(fields):
    return NATIVE().prompt_styler(**fields)

def compare(fields):
    try:
        expected = native(fields)
    except Exception as error:
        with pytest.raises(type(error)) as got:
            CONVERTED.execute(**fields)
        assert str(got.value) == str(error)
    else:
        assert CONVERTED.execute(**fields).result == expected

def test_full_census_schema_options_and_exact_algorithms_resources():
    assert list(OLD.NODE_CLASS_MAPPINGS)==list(NEW.NODE_CLASS_MAPPINGS)==['ComfyUIStyler']
    assert asyncio.run(NEW.AllInOneStyleExtension().get_node_list()) == [CONVERTED]
    assert len(MENUS) == 21
    assert not hasattr(OLD,'WEB_DIRECTORY') and not hasattr(NEW,'WEB_DIRECTORY')
    assert not list(PACK.rglob('*.js'))
    schema = CONVERTED.GET_SCHEMA(); schema.validate()
    projected = CONVERTED.INPUT_TYPES()['required']
    expected = NATIVE.INPUT_TYPES()['required']
    assert list(projected) == list(expected)
    for k,row in expected.items():
        if isinstance(row[0],list):
            assert projected[k][0]=='COMBO'
            assert projected[k][1]=={'options':row[0],'multiselect':False}
        else:
            assert projected[k] == row
    assert tuple(CONVERTED.RETURN_TYPES)==NATIVE.RETURN_TYPES
    assert tuple(CONVERTED.RETURN_NAMES)==NATIVE.RETURN_NAMES
    assert schema.category==NATIVE.CATEGORY
    assert CONVERTED.SDK_PERMISSIONS == () and not CONVERTED.SDK_REFS
    assert NEW.NODE_DISPLAY_NAME_MAPPINGS==OLD.NODE_DISPLAY_NAME_MAPPINGS
    for name in ['prompt_styler.py','LICENSE']+[p.relative_to(PACK).as_posix() for p in (PACK/'data').rglob('*.json')]:
        assert (V2/name).read_bytes()==(PACK/name).read_bytes()
    assert not list(PACK.rglob('__pycache__')) and not list(PACK.rglob('*.pyc'))

@pytest.mark.parametrize('positive,negative', [('', ''), ('hello','avoid'), ('😀\n{prompt}\x00','ä, 文'),
    ('leading\nline','\n'), (' a ',' b ')])
def test_all21_native_defaults_and_plain_text(positive,negative):
    compare(defaults() | {'text_positive':positive,'text_negative':negative})

@pytest.mark.parametrize('menu', MENUS)
def test_every_bundled_style_exact_native_template(menu):
    # One selected menu per case isolates each of all10,277 source rows.
    for choice in ORIGINAL.styler_data[menu]:
        compare({'text_positive':'AMY 😀 {prompt}','text_negative':'avoid, blue','log_prompt':False,menu:choice})

def test_full_catalogue_row_unique_duplicate_and_filesystem_order():
    data_files=list((PACK/'data').glob('*/*.json'))
    assert len(data_files)==21
    count=0
    for path in data_files:
        data=json.loads(path.read_bytes());count += len(data)
        names=list(dict.fromkeys(row['name'] for row in data))
        assert list(ORIGINAL.styler_data[path.parent.name])==names
        assert list(SOURCE.styler_data[path.parent.name])==names
        last_values={row['name']:row for row in data}
        for row in data:
            # Later same-name entries overwrite values without reordering.
            last=last_values[row['name']]
            template=SOURCE.styler_data[path.parent.name][row['name']]
            assert (template.prompt,template.negative_prompt)==(last['prompt'],last['negative_prompt'])
    assert count==10277

def test_multi_menu_and_reversed_supplied_order_exact():
    for order in (MENUS,list(reversed(MENUS)),MENUS[::2]+MENUS[1::2]):
        values={'text_positive':'seed','text_negative':'avoid','log_prompt':False}
        for menu in order:
            values[menu]=list(ORIGINAL.styler_data[menu])[min(1,len(ORIGINAL.styler_data[menu])-1)]
        compare(values)

def test_logging_exact_native_and_unknown_selection_error(capsys):
    values=defaults() | {'text_positive':'quoted\n😀','text_negative':'bad','log_prompt':True}
    expected=native(values);a=capsys.readouterr().out
    assert CONVERTED.execute(**values).result==expected
    assert capsys.readouterr().out==a
    compare({'text_positive':'x','text_negative':'','log_prompt':False,'Aesthetic':'__unknown_source_selection__'})

def test_loader_duplicate_insertion_partial_failure_and_malformed_json(tmp_path,capsys):
    root=tmp_path/'data';group=root/'Aesthetic';group.mkdir(parents=True)
    entries=[{'name':'a','prompt':'A {prompt}','negative_prompt':''},
             {'name':'b','prompt':'B {prompt}','negative_prompt':'b'},
             {'name':'a','prompt':'last {prompt}','negative_prompt':'last'}, {'prompt':'valid','negative_prompt':''}]
    (group/'a.json').write_text(json.dumps(entries))
    old=ORIGINAL.StylerData(root);new=SOURCE.StylerData(root)
    assert list(old['Aesthetic'])==list(new['Aesthetic'])==['a','b']
    assert new['Aesthetic']['a'].prompt==old['Aesthetic']['a'].prompt=='last {prompt}'
    assert 'Malformed data' in capsys.readouterr().out
    (group/'a.json').write_text(json.dumps([{'malformed':'missing'}]))
    for module in (ORIGINAL,SOURCE):
        with pytest.raises(TypeError,match='missing 2 required positional arguments'):
            module.StylerData(root)
    (group/'a.json').write_text('{')
    with pytest.raises(json.JSONDecodeError): ORIGINAL.StylerData(root)
    with pytest.raises(json.JSONDecodeError): SOURCE.StylerData(root)
    # Native loader oracle only, NOT profile admission of authored edits.

def test_pre_operation_oversize_plain_type_selection_and_expansion_sentinels(monkeypatch,capsys):
    called=[]
    def forbidden(*a,**k): called.append(True);raise AssertionError('native formatting invoked')
    monkeypatch.setattr(SOURCE.NODE_CLASS_MAPPINGS['ComfyUIStyler'],'prompt_styler',forbidden)
    base={'text_positive':'a','text_negative':'','log_prompt':False}
    for values in [base | {'text_positive':'x'*65537},base|{'text_positive':object()},
            base|{'log_prompt':1},base|{'Aesthetic':'x'*257},base|{'unknown_menu':'None'}]:
        with pytest.raises(LIMITS.ProfileError): CONVERTED.execute(**values)
    # Synthetic owned template exercises projected repeated replacement,
    # without changing source files or extending bundled profile.
    template=SOURCE.styler_data['Aesthetic']['None']
    monkeypatch.setattr(template,'prompt','{prompt}{prompt}')
    with pytest.raises(LIMITS.ProfileError,match='projected'):
        CONVERTED.execute(**(base|{'text_positive':'😀'*9000,'Aesthetic':'None'}))
    assert called==[] and capsys.readouterr().out==''

def test_exact_text_budget_inclusive_ceiling():
    for length in (65535,65536):
        compare({'text_positive':'x'*length,'text_negative':'','log_prompt':False})
    with pytest.raises(LIMITS.ProfileError,match='input text'):
        CONVERTED.execute(text_positive='x'*65536,text_negative='x',log_prompt=False)

def test_cumulative_log_work_sentinel_before_native_print(monkeypatch,capsys):
    called=[]
    monkeypatch.setattr(SOURCE.NODE_CLASS_MAPPINGS['ComfyUIStyler'],'prompt_styler',lambda **k:called.append(True))
    monkeypatch.setattr(LIMITS,'MAX_WORK_BYTES',64)
    with pytest.raises(LIMITS.ProfileError,match='print work'):
        CONVERTED.execute(text_positive='x',text_negative='',log_prompt=True)
    assert called==[] and capsys.readouterr().out==''

@pytest.mark.parametrize('change',['changed','extra','symlink','group_symlink','profile_large'])
def test_immutable_resource_inventory_refusal_before_loader(tmp_path,change):
    fresh=tmp_path/'v2';shutil.copytree(V2,fresh)
    target=fresh/'data/Aesthetic/Aesthetic.json'
    if change=='changed':target.write_text('[]')
    elif change=='extra':(target.parent/'other.json').write_text('[]')
    elif change=='symlink':
        outside=tmp_path/'outside.json';outside.write_text('[]');target.unlink();target.symlink_to(outside)
    elif change=='group_symlink':
        group=target.parent;group.rename(tmp_path/'moved');group.symlink_to(tmp_path/'moved',target_is_directory=True)
    else:(fresh/'_resource_profile.json').write_bytes(b' '*16385)
    with pytest.raises(ValueError,match='bundled resource'): RESOURCES.verify(fresh)
    assert RESOURCES.verify()['format']=='amy-bundled-json-profile/1'
