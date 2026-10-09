"""Native full census/schema/options/errors and pre-operation workload controls."""
import ast, asyncio, copy, importlib.util, math, os, sys
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

OLD = load('amy_basic_math_pristine', PACK)
NEW = load('amy_basic_math_converted', V2)
LIMITS = sys.modules[NEW.__name__ + '._limits']
IDS = list(OLD.NODE_CLASS_MAPPINGS)

def values(node_id):
    fields = {}
    for group, rows in OLD.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES().items():
        for key, row in rows.items():
            kind = row[0]
            options = row[1] if len(row) > 1 else {}
            fields[key] = options.get('default', kind[0] if type(kind) is list else
                {'INT': 2, 'FLOAT': 2.5, 'INT,FLOAT': 2.5, 'BOOLEAN': True, 'STRING': 'AMY', '*': '3.5'}[str(kind)])
    return fields

def equivalent(a, b):
    assert type(a) is type(b), (a,b)
    if type(a) in (tuple, list):
        assert len(a) == len(b)
        for x,y in zip(a,b): equivalent(x,y)
    elif type(a) is float:
        if math.isnan(a): assert math.isnan(b)
        else: assert a.hex() == b.hex()
    else: assert a == b

def compare(node_id, fields):
    source = OLD.NODE_CLASS_MAPPINGS[node_id]
    try: expected = getattr(source(), source.FUNCTION)(**fields)
    except Exception as error:
        with pytest.raises(type(error)) as got: NEW.NODE_CLASS_MAPPINGS[node_id].execute(**fields)
        assert str(got.value) == str(error)
    else:
        result = NEW.NODE_CLASS_MAPPINGS[node_id].execute(**fields)
        equivalent(None if result is None else result.result, expected)

@pytest.mark.parametrize('node_id', IDS)
def test_all23_native_defaults(node_id): compare(node_id, values(node_id))

def test_full_census_byte_identical_source_algorithms_and_exact_schema_contracts():
    assert len(IDS) == 23 and list(NEW.NODE_CLASS_MAPPINGS) == IDS
    assert asyncio.run(NEW.BasicMathExtension().get_node_list()) == list(NEW.NODE_CLASS_MAPPINGS.values())
    assert NEW.NODE_DISPLAY_NAME_MAPPINGS == OLD.NODE_DISPLAY_NAME_MAPPINGS
    for name in ('math_nodes.py', 'tools.py', 'base_node.py', 'LICENSE'):
        assert (PACK/name).read_bytes() == (V2/name).read_bytes()
    for node_id in IDS:
        source = OLD.NODE_CLASS_MAPPINGS[node_id]
        converted = NEW.NODE_CLASS_MAPPINGS[node_id]
        schema = converted.GET_SCHEMA(); schema.validate()
        classic = converted.INPUT_TYPES()
        # Framework-managed hidden context is not a guest argument or source input.
        for group, rows in source.INPUT_TYPES().items():
            assert list(classic[group]) == list(rows)
            for key, row in rows.items():
                got = classic[group][key]
                if type(row[0]) is list:
                    assert got[0] == 'COMBO'
                    assert got[1]['options'] == row[0]
                    assert got[1]['multiselect'] is False
                    assert {k:v for k,v in got[1].items() if k not in ('options','multiselect')} == (row[1] if len(row)>1 else {})
                    continue
                assert got[0] == row[0]
                # V3's classic projection always spells the implied empty
                # options as {}; all actual source options remain exact.
                assert got[1] == (row[1] if len(row) > 1 else {})
        assert tuple(map(str,converted.RETURN_TYPES)) == tuple(map(str,source.RETURN_TYPES))
        assert tuple(converted.RETURN_NAMES) == tuple(source.RETURN_NAMES)
        assert schema.category == source.CATEGORY and converted.SDK_PERMISSIONS == () and not converted.SDK_REFS
        for types in ({'a':'INT','b':'FLOAT'}, [{'any':'MODEL'}], {'value':'STRING'}, {'unused':'ANY'}):
            assert converted.validate_inputs(types) == source.VALIDATE_INPUTS(types)
    assert not hasattr(OLD, 'WEB_DIRECTORY') and not hasattr(NEW, 'WEB_DIRECTORY')
    assert not list(PACK.rglob('*.js'))

@pytest.mark.parametrize('node_id',['BasicMath','IntMath','UnaryMath','NumberComparison','IntegerComparison','FloatComparison','BooleanLogic','BooleanUnary','MathConstants'])
def test_every_native_operation_option_and_unknown_return(node_id):
    source = OLD.NODE_CLASS_MAPPINGS[node_id]
    f = values(node_id)
    field = 'constant' if node_id == 'MathConstants' else 'operation'
    for op in source.INPUT_TYPES()['required'][field][0] + ['source-invalid-option']:
        g = f | {field: op}
        compare(node_id, g)

@pytest.mark.parametrize('node_id',['BasicMath','IntMath'])
@pytest.mark.parametrize('a,b',[(8,0),(0,0),(-8,0),(-8,3),(2,-3),(0,-2),(True,False),(2**64-1,3),(7,2)])
def test_all_arithmetic_zero_negative_unsigned_boolean_and_native_bare_catches(node_id,a,b):
    for op in OLD.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES()['required']['operation'][0]:
        compare(node_id, dict(a=a,b=b,operation=op))

@pytest.mark.parametrize('node_id',['BasicMath','UnaryMath','NumberClamp','NumberLerp','NumberInRange','FloatComparison'])
@pytest.mark.parametrize('number',[float('nan'),float('inf'),float('-inf'),-0.,0.,-2.5])
def test_native_nonfinite_and_signed_zero_not_normalized(node_id,number):
    f=values(node_id)
    key='value' if 'value' in f else 'a'
    f[key]=number
    if 'operation' in f:
        for op in OLD.NODE_CLASS_MAPPINGS[node_id].INPUT_TYPES()['required']['operation'][0]: compare(node_id,f|{'operation':op})
    else: compare(node_id,f)

@pytest.mark.parametrize('node_id',['ToInt','ToFloat','ToString','ToBool'])
@pytest.mark.parametrize('value',[None,False,True,0,-1,1.25,-0.,float('nan'),float('inf'),'3.5','garbage','NaN','Infinity','1_000',[],[1,'😀'],{'a':[2,None]},(1,'x')])
def test_any_closed_plain_values_native_cast_repr_truth_and_fallback(node_id,value):
    f=values(node_id)|{'any':value}
    if node_id=='ToInt':
        for method in ('round','floor','ceil','trunc','unknown'): compare(node_id,f|{'round_method':method})
    elif node_id=='ToBool':
        compare(node_id,f); compare(node_id,f|{'invert':True})
    else: compare(node_id,f)

@pytest.mark.parametrize('pattern',['','a','^a$','[a-z]+','a*','a+?','a{1,3}','[^b]*','.*','a\\w+','a\\d{0,3}','$','(a)b','(?i)a+','[','(','a{3,1}','\\','a{99999999999999999999999}'])
@pytest.mark.parametrize('subject',['','a','aaa','ab','ABC','a123','😀','á','a\nb','\ud800'])
@pytest.mark.parametrize('sensitive',[True,False])
def test_original_re_match_exact_admitted_and_malformed_patterns(pattern,subject,sensitive):
    compare('StringComparison',dict(a=subject,b=pattern,operation='a MATCH REGEX(b)',case_sensitive=sensitive))

@pytest.mark.parametrize('op',['a == b','a != b','a IN b','a BEGINSWITH b','a ENDSWITH b','unknown'])
@pytest.mark.parametrize('a,b',[('Ab','aB'),('',''),('İ','i\u0307'),('😀x','😀'),('a\nb','\nb')])
def test_string_options_unicode_lower_order(op,a,b):
    for sensitive in (True,False):compare('StringComparison',dict(a=a,b=b,operation=op,case_sensitive=sensitive))

@pytest.mark.parametrize('pattern',['(a+)+','(a|aa)+','(ab)+','a*b*','a|ab','(?=a)','(a)\\1','(?:a?)*','(?<=a)b'])
def test_unadmitted_valid_regex_is_visible_profile_error_before_engine(pattern,monkeypatch):
    source=sys.modules[NEW.__name__+'.math_nodes']
    monkeypatch.setattr(source.re,'match',lambda *a,**k: (_ for _ in ()).throw(AssertionError('native engine must not run')))
    with pytest.raises(LIMITS.ProfileError,match='regex'):
        NEW.NODE_CLASS_MAPPINGS['StringComparison'].execute(a='a'*100,b=pattern,operation='a MATCH REGEX(b)',case_sensitive=True)

@pytest.mark.parametrize('node_id,fields',[
 ('IntMath',dict(a=2,b=4096,operation='**')),
 ('BasicMath',dict(a=2,b=4096,operation='**')),
 ('IntMath',dict(a=1,b=10**100,operation='<<')),
 ('IntegerInput',dict(value=2**2048)),
 ('ToString',dict(any=['\x00'*2000]*8)),
 ('ToString',dict(any=[0]*4096)),
 ('NumberRound',dict(value=4,decimals=-1001)),
 ('StringComparison',dict(a='a'*8193,b='a*',operation='a MATCH REGEX(b)',case_sensitive=True)),
 ('StringComparison',dict(a='a',b='a'*1025,operation='a MATCH REGEX(b)',case_sensitive=True))])
def test_guard_before_native_operation_or_formatting(node_id,fields,monkeypatch):
    source=NEW._secure_nodes.SOURCES[node_id]
    monkeypatch.setattr(source,source.FUNCTION,lambda *a,**k: (_ for _ in ()).throw(AssertionError('native must not run')))
    with pytest.raises(LIMITS.ProfileError): NEW.NODE_CLASS_MAPPINGS[node_id].execute(**fields)

def test_cycle_nonplain_objects_and_subclasses_never_call_repr_truth_or_cast():
    class Dangerous:
        def __str__(self):raise AssertionError('str')
        def __repr__(self):raise AssertionError('repr')
        def __bool__(self):raise AssertionError('bool')
    class SubInt(int):pass
    cycle=[];cycle.append(cycle)
    for value in (Dangerous(),SubInt(1),cycle):
        for node in ('ToInt','ToFloat','ToString','ToBool'):
            with pytest.raises(LIMITS.ProfileError):NEW.NODE_CLASS_MAPPINGS[node].execute(any=value)

def test_input_output_integer_ceilings_and_admitted_small_work():
    compare('IntegerInput',dict(value=(1<<2048)-1))
    compare('IntMath',dict(a=2,b=2047,operation='**'))
    compare('IntMath',dict(a=2,b=2048,operation='**')) # upper-bound estimate4096, result2049bits
    compare('IntMath',dict(a=1,b=4095,operation='<<'))
    with pytest.raises(LIMITS.ProfileError):LIMITS.after((1<<4096,))
    for decimals in (0,2,10,-1,-1000,1000):compare('NumberRound',dict(value=125,decimals=decimals))

@pytest.mark.parametrize('node_id',IDS)
def test_missing_argument_keeps_native_typeerror(node_id): compare(node_id,{})
