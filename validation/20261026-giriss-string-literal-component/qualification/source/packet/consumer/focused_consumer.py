"""UNRUN focused consumer. Accepted owner supplies its actual observed Guest.

No owner, lifecycle, manifest, API, provider or production implementation is
defined here. The small dispatch adapter forwards real Core plans to the
actual Guest and cannot invoke local proxy bodies.
"""
import hashlib
import importlib.util
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


async def compare_string_literal(config, session):
    require(config['execution_selected'] is True and config['authorization_message'],
        'Source-only consumer requires separately selected accepted owner')
    import execution
    from comfy_api.latest import io, _sdk
    from comfy_secure_nodes import packdb
    from comfy_secure_nodes.transport.host import GuestSession

    here = Path(__file__).resolve().parent
    source = json.loads((here/'PACK_SOURCE.json').read_bytes())
    pack = Path(config['pack_root']).resolve()
    require(pack.is_dir() and pack.is_absolute(), 'Actual private frozen pack required')
    for name, row in source['files'].items():
        path = pack/name
        require(path.is_file() and not path.is_symlink() and digest(path) == row['sha256'],
            'Frozen original/candidate bytes differ: '+name)
    require(type(session) is GuestSession and session.pid != os.getpid()
        and session._pgid == session.pid and session.sandbox_kind == 'seatbelt'
        and session.pack_runtime is None, 'Accepted actual ordinary required-Guest session required')
    require(type(_sdk.providers.execution_backend) is _sdk.InProcessExecutionBackend
        and type(_sdk.providers.ctx_provider) is _sdk.InProcessCtxProvider
        and type(_sdk.providers.ops_provider) is _sdk.InProcessOps
        and _sdk.providers.ref_resolver_factory is _sdk.InProcessRefResolver,
        'Actual stock default SDK providers required')
    for module, name in [(execution,'execution'),(io,'io'),(_sdk,'sdk'),(packdb,'packdb')]:
        pin = config['actual_source_pins'][name]
        require(Path(module.__file__).resolve() == Path(pin['path']).resolve()
            and digest(module.__file__) == pin['sha256'], 'Actual selected source binding differs: '+name)
    providers = {name:getattr(_sdk.providers,name) for name in
        ('execution_backend','ctx_provider','ops_provider','ref_resolver_factory')}
    suffix = uuid.uuid4().hex
    original = source_module('_giriss_string_original_'+suffix, pack/'nodes.py')
    candidate = source_module('_giriss_string_candidate_'+suffix, pack/'v2/__init__.py', package=True)
    node_id = 'String_Literal_5bb4d668d27398985246d1d5'
    cls = candidate.NODE_CLASS_MAPPINGS[node_id]
    native_cls = original.StringLiteral
    loaded = packdb.load_pack(pack.parent, mount_name='custom_nodes.giriss_string_'+suffix)
    proxy = loaded.node_mappings[node_id]
    require(cls.__name__ == proxy.__name__ == native_cls.__name__ == 'StringLiteral'
        and cls.SDK_REFS is proxy.SDK_REFS is True
        and tuple(cls.SDK_PERMISSIONS) == tuple(proxy.SDK_PERMISSIONS) == (),
        'Exact existing String Literal identity and zero capabilities')
    schema = cls.GET_SCHEMA()
    schema.validate()
    require(schema.node_id == node_id and [v.id for v in schema.inputs] == ['string'],
        'Existing scalar input schema differs')
    native_schema = native_cls.INPUT_TYPES()
    require(native_schema['required']['string'] == ('STRING',{'default':'','multiline':True}),
        'Genuine original default/multiline contract differs')

    report = dict(status='FAILED_FOCUSED_STRING_SOURCE_CONSUMER',node_id=node_id,
        authorization_message=config['authorization_message'],rows=[],controls=[],
        actual_Guest_pid=session.pid,Guest_dispatches=0,normalgen_runs=0,
        encoder_calls=0,new_API_or_generated_contract_edits=0,whole_pack_accepted=False)

    class ForwardToActualGuest:
        async def dispatch(self, plan, local_call, runtime=None):
            require(type(plan) is _sdk.ExecutionPlan and runtime is not None
                and plan.node_module == proxy.__module__ and plan.node_type == 'StringLiteral'
                and plan.method == 'execute' and plan.input_mode == 'refs'
                and tuple(plan.permissions or ()) == (), 'Only real zero-capability scalar Core plan')
            module = sys.modules[plan.node_module]
            require(Path(module.__file__).resolve() == (pack/'v2/nodes.py').resolve(),
                'Proxy module must be actual frozen production source')
            report['Guest_dispatches'] += 1
            result = await session.execute(plan, runtime, capabilities=frozenset(), tenant=config['tenant_id'])
            require(session.last_guest_pid == session.pid, 'Reply did not come from owned Guest')
            return result

    adapter = ForwardToActualGuest()

    async def invoke(value, guest):
        before = _sdk.providers.execution_backend
        try:
            if guest:
                _sdk.providers.register_execution_backend(adapter)
            result = await execution._async_map_node_over_list('giriss-string-source',str(report['Guest_dispatches']),
                proxy if guest else cls,dict(string=[value]),'execute')
            settled = await execution.resolve_map_node_over_list_results(result)
            require(len(settled) == 1 and isinstance(settled[0],io.NodeOutput), 'Actual Core typed scalar output')
            return settled[0].result
        finally:
            if guest:
                _sdk.providers.register_execution_backend(before)

    def equal(actual, expected):
        require(type(actual) is type(expected) is tuple and len(actual) == len(expected) == 1
            and type(actual[0]) is type(expected[0]) is str and actual[0] == expected[0],
            'Exact tuple/string identity, no coercion or normalization')

    try:
        cases = json.loads((here/'CASES.json').read_bytes())['cases']
        for row in cases:
            value = row['value']
            require(type(value) is str, 'Only actual valid string inputs selected')
            expected = native_cls().get_string(value)
            default = await invoke(value,False)
            guest = await invoke(value,True)
            equal(default,expected)
            equal(guest,expected)
            encoded = value.encode('utf-8')
            report['rows'].append(dict(case=row['id'],type='str',tuple_items=1,
                utf8_bytes=len(encoded),sha256=hashlib.sha256(encoded).hexdigest(),
                original_default_Guest_exact=True,Guest_pid=session.pid))
        for label,wrong in [('changed-string',('different\x00'+cases[0]['value'],)),('wrong-container',[cases[0]['value']])]:
            try:
                equal(wrong,(cases[0]['value'],))
            except AssertionError:
                report['controls'].append(label)
            else:
                raise AssertionError('Scalar comparator missed a wrong result')
        require(len(report['rows']) == report['Guest_dispatches'] == len(cases) == 13,
            'Complete focused source case census')
        report['status'] = 'PASS_FOCUSED_GIRISS_STRING_LITERAL_COMPONENT_ONLY'
        return report
    finally:
        require(all(getattr(_sdk.providers,k) is v for k,v in providers.items()),
            'Existing SDK providers must be restored')
        for name,row in source['files'].items():
            require(digest(pack/name) == row['sha256'], 'Frozen pack changed during focused consumer')
        # Lifecycle belongs to the accepted observing outer owner; this source
        # does not create, kill, replace or infer retirement of its Guest.
