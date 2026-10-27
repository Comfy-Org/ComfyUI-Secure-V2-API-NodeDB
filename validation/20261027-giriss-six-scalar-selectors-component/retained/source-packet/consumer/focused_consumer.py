"""UNRUN finite six-purpose consumer; an accepted owner supplies one real Guest.

No lifecycle, catalogue provider, production shim or public API is defined here.
"""
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import sys
import uuid


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_module(name, path, package=False):
    require(name not in sys.modules, 'Fresh private source module required')
    spec = importlib.util.spec_from_file_location(name, path,
        submodule_search_locations=[str(path.parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def capture(actual, kind):
    require(type(actual) is tuple and len(actual) == 1, 'Exact builtin one-item tuple required')
    value = actual[0]
    expected = {'int': int, 'float': float, 'str': str}[kind]
    require(type(value) is expected, 'Exact builtin scalar required; no bool/coercion/subclass')
    encoded = str(value) if kind == 'int' else value.hex() if kind == 'float' else value
    return dict(container='tuple', items=1, type=kind, value=encoded)


def equal(actual, expected, kind):
    require(capture(actual, kind) == capture(expected, kind), 'Strict typed scalar mismatch')


def materialize(row, maximum):
    kind = row['type']
    if kind == 'int':
        value = maximum if row.get('bound') == 'MAX_RESOLUTION' else maximum-1 if row.get('bound') == 'MAX_RESOLUTION_MINUS_ONE' else int(row['value'], 10)
    elif kind == 'float':
        value = float.fromhex(row['value'])
    else:
        require(kind == 'str' and type(row['value']) is str, 'Authored string case required')
        value = row['value']
    return value


async def compare_six_purposes(config, session):
    require(config['execution_selected'] is True and config['authorization_message'],
        'Separately selected accepted owner required')
    import execution
    import comfy.samplers
    from comfy_api.latest import io, _sdk
    from comfy_secure_nodes import packdb, packmanifest
    from comfy_secure_nodes.transport.host import GuestSession

    here = Path(__file__).resolve().parent
    cases = json.loads((here/'CASES.json').read_bytes())
    nodes = json.loads((here/'SCHEMA_CASES.json').read_bytes())['nodes']
    fixture = json.loads((here/'ENUM_FIXTURE.json').read_bytes())
    source = json.loads((here/'PACK_SOURCE.json').read_bytes())
    pack = Path(config['pack_root']).resolve()
    require(pack.is_dir() and pack.is_absolute(), 'Actual private frozen pack required')
    for name, row in source['files'].items():
        path = pack/name
        require(path.is_file() and not path.is_symlink() and digest(path) == row['sha256'],
            'Frozen original/candidate bytes differ: '+name)
    require(type(session) is GuestSession and session.pid != os.getpid()
        and session._pgid == session.pid and session.sandbox_kind == 'seatbelt'
        and session.pack_runtime is None, 'Actual ordinary required-Guest session required')
    require(type(_sdk.providers.execution_backend) is _sdk.InProcessExecutionBackend
        and type(_sdk.providers.ctx_provider) is _sdk.InProcessCtxProvider
        and type(_sdk.providers.ops_provider) is _sdk.InProcessOps
        and _sdk.providers.ref_resolver_factory is _sdk.InProcessRefResolver,
        'Actual stock default SDK providers required')
    for module, name in [(execution,'execution'), (io,'io'), (_sdk,'sdk'),
                         (packdb,'packdb'), (packmanifest,'packmanifest')]:
        pin = config['actual_source_pins'][name]
        require(Path(module.__file__).resolve() == Path(pin['path']).resolve()
            and digest(module.__file__) == pin['sha256'], 'Actual selected binding differs: '+name)
    sampler_source = Path(inspect.getfile(comfy.samplers.KSampler)).resolve()
    sampler_pin = config['actual_source_pins']['samplers']
    require(sampler_source == Path(sampler_pin['path']).resolve() and digest(sampler_source) == sampler_pin['sha256'],
        'Genuine KSampler implementation source binding differs')
    providers = {name:getattr(_sdk.providers,name) for name in
        ('execution_backend','ctx_provider','ops_provider','ref_resolver_factory')}
    suffix = uuid.uuid4().hex
    original = source_module('_giriss_six_original_'+suffix, pack/'nodes.py')
    candidate = source_module('_giriss_six_candidate_'+suffix, pack/'v2/__init__.py', package=True)
    loaded = packdb.load_pack(pack.parent, mount_name='custom_nodes.giriss_six_'+suffix)
    manifest = json.loads((pack/'v2/secure-nodes.json').read_bytes())
    maximum = original.MAX_RESOLUTION
    require(type(maximum) is int and maximum == io.MAX_RESOLUTION == config['expected_MAX_RESOLUTION'] and maximum >= 512,
        'Equal genuine original/SDK MAX_RESOLUTION required')
    genuine = {'SAMPLERS':list(comfy.samplers.KSampler.SAMPLERS),
               'SCHEDULERS':list(comfy.samplers.KSampler.SCHEDULERS)}
    require(genuine == fixture['ordered_catalogues'], 'Complete genuine ordered enums differ; no filtering or substitution')
    classes = {}
    schema_rows = []
    for desc in nodes:
        node_id, name = desc['node_id'], desc['class']
        cls, native, proxy = candidate.NODE_CLASS_MAPPINGS[node_id], getattr(original,name), loaded.node_mappings[node_id]
        require(cls.__name__ == native.__name__ == proxy.__name__ == name
            and cls.SDK_REFS is proxy.SDK_REFS is True
            and tuple(cls.SDK_PERMISSIONS) == tuple(proxy.SDK_PERMISSIONS) == (), 'Exact zero-capability class identity')
        schema = cls.GET_SCHEMA()
        schema.validate()
        require(schema.node_id == node_id and schema.category == native.CATEGORY
            and not schema.is_output_node and len(schema.inputs) == len(schema.outputs) == 1, 'Exact scalar schema structure')
        old = native.INPUT_TYPES()
        require(list(old) == ['required'] and list(old['required']) == [desc['input']], 'Exact native required input')
        spec = old['required'][desc['input']]
        item, output = schema.inputs[0], schema.outputs[0]
        require(item.id == desc['input'] and not item.optional, 'Exact candidate input')
        expected_type = 'COMBO' if desc['enum'] else desc['io_type']
        require(item.io_type == output.io_type == expected_type, 'Exact scalar input/output IO type')
        if desc['enum']:
            choices = fixture['ordered_catalogues'][desc['enum']]
            require(list(spec[0]) == list(native.RETURN_TYPES[0]) == list(item.options) == list(output.options) == choices,
                'Ordered genuine native/candidate input/output options differ')
            require([output.display_name] == list(native.RETURN_NAMES), 'Selector output name differs')
        else:
            require(spec[0] == native.RETURN_TYPES[0] == desc['io_type'], 'Native literal IO type differs')
            expected_attrs = {key:(maximum if value == '@MAX_RESOLUTION' else value) for key,value in desc['input_attrs'].items()}
            require(spec[1] == expected_attrs, 'Original literal schema differs from authored oracle')
            for key,value in expected_attrs.items():
                require(item.as_dict()[key] == value, 'Candidate literal attribute differs: '+key)
        encoded = packmanifest.encode_schema(schema)
        require(encoded == manifest['nodes'][node_id]['schema']
            and manifest['nodes'][node_id]['permissions'] == [], 'Generated schema contract differs')
        schema_rows.append(dict(node_id=node_id, schema=encoded, native_required=old['required'], passed=True))
        classes[node_id] = (cls, native, proxy, desc)
    require(len(cases['cases']) == 87 and len(classes) == 6, 'Exact six-purpose census')
    report = dict(status='FAILED_FOCUSED_GIRISS_SIX_COMPONENT', authorization_message=config['authorization_message'],
        actual_Guest_pid=session.pid, rows=[], controls=[], schema_checks=schema_rows,
        route_calls={'original':0,'default':0,'Guest':0}, Guest_dispatches=0, strict_comparisons=0,
        enum_observation=dict(genuine_ordered_catalogues=genuine, candidate_fixture_sha256=digest(here/'ENUM_FIXTURE.json'),
            candidate_implementation_sha256=digest(pack/'v2/_catalogues.py'), genuine_KSampler_source=dict(path=str(sampler_source),sha256=digest(sampler_source)),
            before_dispatch=True, exact_ordered_equality=True),
        MAX_RESOLUTION=maximum, normalgen_runs=0, encoder_calls=0, new_API_or_generated_contract_edits=0,
        whole_pack_accepted=False, RNG_semantics='Seed is unchanged passthrough; no seeding, RNG calls, state substitution or extra entropy behavior added.')

    class ForwardToActualGuest:
        async def dispatch(self, plan, local_call, runtime=None):
            match = next(((proxy,desc) for _,_,proxy,desc in classes.values()
                if plan.node_module == proxy.__module__ and plan.node_type == desc['class']), None)
            require(type(plan) is _sdk.ExecutionPlan and runtime is not None and match is not None
                and plan.method == 'execute' and plan.input_mode == 'refs' and tuple(plan.permissions or ()) == (),
                'Only exact real six-purpose zero-capability plans')
            proxy, desc = match
            require(Path(sys.modules[plan.node_module].__file__).resolve() == pack/'v2/nodes.py', 'Actual frozen proxy source required')
            report['Guest_dispatches'] += 1
            result = await session.execute(plan, runtime, capabilities=frozenset(), tenant=config['tenant_id'])
            require(session.last_guest_pid == session.pid, 'Reply must come from the same owned Guest')
            return result

    adapter = ForwardToActualGuest()

    async def invoke(row, value, guest):
        cls,native,proxy,desc = classes[row['node_id']]
        before = _sdk.providers.execution_backend
        try:
            if guest:
                _sdk.providers.register_execution_backend(adapter)
            settled = await execution.resolve_map_node_over_list_results(
                await execution._async_map_node_over_list('giriss-six-source', row['id'], proxy if guest else cls,
                    {desc['input']:[value]}, 'execute'))
            require(len(settled) == 1 and isinstance(settled[0],io.NodeOutput), 'Actual Core typed output required')
            return settled[0].result
        finally:
            if guest:
                _sdk.providers.register_execution_backend(before)

    try:
        for index,row in enumerate(cases['cases']):
            if index == 1:
                require(report['first_case_gate']['route_calls'] == {'original':1,'default':1,'Guest':1}, 'First1/1/1 gate required before matrix')
            cls,native,proxy,desc = classes[row['node_id']]
            value = materialize(row, maximum)
            # Bounded independent identity oracle comes from the frozen original
            # one-return method and authored value, never from candidate output.
            oracle = (value,)
            actual_row = dict(id=row['id'], node_id=row['node_id'], input=capture(oracle,row['type']),
                oracle=capture(oracle,row['type']), Guest_pid=session.pid, exact=False)
            report['rows'].append(actual_row)
            original_result = getattr(native(),desc['method'])(value)
            report['route_calls']['original'] += 1
            actual_row['original'] = capture(original_result,row['type'])
            equal(original_result,oracle,row['type'])
            default_result = await invoke(row,value,False)
            report['route_calls']['default'] += 1
            actual_row['default'] = capture(default_result,row['type'])
            equal(default_result,original_result,row['type'])
            guest_result = await invoke(row,value,True)
            report['route_calls']['Guest'] += 1
            actual_row['Guest'] = capture(guest_result,row['type'])
            equal(guest_result,original_result,row['type'])
            report['strict_comparisons'] += 2
            actual_row['exact'] = True
            if index == 0:
                require(report['route_calls'] == {'original':1,'default':1,'Guest':1} and report['Guest_dispatches'] == 1, 'First existing case exact1/1/1')
                report['first_case_gate'] = dict(id=row['id'], node_id=row['node_id'], route_calls=dict(report['route_calls']), passed=True)

        def control(label, actual, expected, kind):
            try:
                equal(actual,expected,kind)
            except AssertionError:
                report['controls'].append(dict(id=label, detected=True, additional_dispatches=0))
            else:
                raise AssertionError('Comparator missed wrong result: '+label)

        for desc in nodes:
            row = next(row for row in cases['cases'] if row['node_id'] == desc['node_id'])
            value = materialize(row,maximum)
            wrong = value+1 if row['type'] == 'int' else value+1.0 if row['type'] == 'float' else value+'!wrong'
            control(desc['class']+':wrong-value',(wrong,),(value,),row['type'])
            control(desc['class']+':wrong-container',[value],(value,),row['type'])
        control('SeedGenerator:uint64-rounded',(2**64,),(2**64-1,),'int')
        control('CfgLiteral:signed-zero',(0.0,),(-0.0,),'float')
        for key in ('SAMPLERS','SCHEDULERS'):
            wrong = list(genuine[key]); wrong[0],wrong[1] = wrong[1],wrong[0]
            require(wrong != fixture['ordered_catalogues'][key], 'Order mutant must be detected')
            report['controls'].append(dict(id=key+':reordered-enum',detected=True,additional_dispatches=0))
        require(report['route_calls'] == {'original':87,'default':87,'Guest':87}
            and report['Guest_dispatches'] == len(report['rows']) == 87 and report['strict_comparisons'] == 174
            and len(report['controls']) == 16, 'Exact finite case/route/control census')
        report['status'] = 'PASS_FOCUSED_GIRISS_SIX_COMPONENT_ONLY'
        return report
    except BaseException as error:
        report['error'] = dict(type=type(error).__name__, message=str(error)[:4096])
        raise
    finally:
        (Path(config['owned_guest_work_root']).parent/'FINITE_PROGRESS.json').write_text(
            json.dumps(report,indent=2,ensure_ascii=True)+'\n')
        require(all(getattr(_sdk.providers,k) is v for k,v in providers.items()), 'Actual providers must be restored')
        for name,row in source['files'].items():
            require(digest(pack/name) == row['sha256'], 'Frozen pack changed during finite consumer')
