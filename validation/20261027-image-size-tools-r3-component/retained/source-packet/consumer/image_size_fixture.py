"""UNRUN pack-specific body for the existing owned values/ref acceptance runner.

No CLI, profile selection, SDK import at module scope, Guest constructor,
Popen/sandbox replacement or new lifecycle. The already-reviewed owner must bind
the genuine modules, stage pinned roots, start exactly one observed real Guest,
call this body once, then retain its existing cleanup/retirement checks. This
body does not establish those external actual bindings or authorize execution.
"""
import contextlib
import copy
import hashlib
import inspect
import io as stdio
import json
from pathlib import Path
import sys
import warnings

HERE = Path(__file__).resolve().parent
NODE_IDS = ['SD15ResolutionNode', 'SDXLResolutionNode', 'FluxResolutionNode',
            'ImageSizeDetectorNode', 'WAN21ResolutionNode', 'WAN21AdvancedResolutionNode']
REPORT_BYTES = 512 * 1024


def typed(value):
    if value is None or type(value) in (bool, int, str):
        return {'type': type(value).__name__, 'value': value}
    if type(value) is float:
        return {'type': 'float', 'hex': value.hex()}
    if type(value) in (tuple, list):
        return {'type': type(value).__name__, 'items': [typed(item) for item in value]}
    if type(value) is dict:
        return {'type': 'dict', 'items': [[typed(key), typed(item)] for key, item in value.items()]}
    raise TypeError('Unselected result type: ' + type(value).__name__)


def compare(actual, expected):
    assert actual == expected, 'Strict typed outcome differs'


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=True, indent=2) + '\n').encode()
    assert len(raw) <= REPORT_BYTES, 'Finite report exceeds byte bound'
    path.write_bytes(raw)


def fingerprint(image):
    return {'shape': list(image.shape), 'stride': list(image.stride()), 'dtype': str(image.dtype),
            'device': str(image.device), 'version': image._version, 'data_ptr': image.data_ptr(),
            'sha256': hashlib.sha256(image.detach().contiguous().numpy().tobytes()).hexdigest()}


def inputs_for(case, torch):
    values = copy.deepcopy(case['parameters'])
    if 'image' not in case:
        return values
    data = case['image']
    assert data['dtype'] == 'float32'
    shape = data['shape']
    if data['layout'] == 'transpose-spatial':
        image = torch.full((shape[0], shape[2], shape[1], shape[3]), data['fill'], dtype=torch.float32).transpose(1, 2)
        assert not image.is_contiguous()
    else:
        assert data['layout'] == 'contiguous'
        image = torch.full(tuple(shape), data['fill'], dtype=torch.float32)
    assert list(image.shape) == shape and image.device.type == 'cpu'
    values['image'] = image
    return values


def original_call(cls, inputs):
    stdout, stderr = stdio.StringIO(), stdio.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try:
            result = getattr(cls(), cls.FUNCTION)(**inputs)
            assert type(result) is tuple
            outcome = {'kind': 'return', 'result': typed(result), 'ui': typed(None), 'expand': typed(None), 'block_execution': typed(None)}
        except Exception as error:
            outcome = {'kind': 'error', 'type': type(error).__name__, 'message': str(error)}
    outcome.update(stdout=stdout.getvalue(), stderr=stderr.getvalue(), warnings=[{'type': item.category.__name__, 'message': str(item.message)} for item in caught])
    return outcome


async def sdk_call(cls, inputs, case_id, io, sdk, wire, *, remote, counts, raw_denial_capture=None):
    assert sdk.__name__ == 'comfy_api.latest._sdk', 'Trusted driver needs the genuine internal f1 module'
    providers = sdk.providers
    assert not providers.overlay_active
    if not remote:
        assert not providers.engaged and type(providers.execution_backend) is sdk.InProcessExecutionBackend
    refs = providers.ref_resolver_factory()
    assert type(refs) is sdk.InProcessRefResolver
    permissions = ('raw',) if cls.__name__ == 'ImageSizeDetectorNode' else ()
    assert cls.SDK_REFS is True and tuple(getattr(cls, 'SDK_PERMISSIONS', ()) or ()) == permissions
    plan = sdk.ExecutionPlan(prompt_id='image-size-tools-finite', node_id=case_id, node_type=cls.__name__,
        node_module=cls.__module__, tier='sandbox' if remote else 'default', inputs={}, input_mode='refs', permissions=permissions, method='execute')
    scope = sdk.bind_runtime(refs, providers.ctx_provider.build(plan), providers.ops_provider)
    owned = []
    stdout, stderr = stdio.StringIO(), stdio.StringIO()

    def capture_raw_denial(**fields):
        # This pack-specific optional sink is used only by control/missing-raw.
        # Record a real remote envelope before the existing phase/frame guards.
        if raw_denial_capture is not None:
            path, evidence = raw_denial_capture
            evidence.update(fields)
            save(path, evidence)
    try:
        with scope:
            plan.inputs = dict(inputs)
            if 'image' in inputs:
                ref = await sdk.ImageRef.from_tensor(inputs['image'])
                owned.append(ref)
                assert type(ref) is sdk.ImageRef and await refs.resolve(ref) is inputs['image']
                plan.inputs['image'] = ref

            async def local_call():
                assert not remote, 'Required Guest route cannot call the local candidate'
                counts['actual_default_local_calls'] += 1
                value = cls.execute(**plan.inputs)
                return await value if inspect.isawaitable(value) else value

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                try:
                    value = await providers.execution_backend.dispatch(plan, local_call, scope.runtime)
                    value = await sdk.unwrap_outputs(refs, value)
                    assert type(value) is io.NodeOutput
                    result = () if value.result is None else value.result
                    assert type(result) is tuple
                    outcome = {'kind': 'return', 'result': typed(result), 'ui': typed(value.ui),
                               'expand': typed(value.expand), 'block_execution': typed(value.block_execution)}
                except wire.WireError as error:
                    outcome = {'kind': 'error', 'type': error.remote_type, 'message': error.remote_message}
                    capture_raw_denial(wire_error={'wrapper_class': type(error).__module__ + '.' + type(error).__qualname__,
                        'remote_type': error.remote_type, 'remote_message': error.remote_message,
                        'remote_phase': error.remote_phase, 'remote_frames': error.remote_frames},
                        normalized_outcome=dict(outcome), observed_wire_error=True)
                    assert remote and error.remote_phase == 'execute', 'Birth/import/transport failure is not a compute diagnostic'
                    source_root = Path(sys.modules[cls.__module__].__file__).resolve().parent
                    assert any(Path(str(frame.get('file', ''))).resolve().is_relative_to(source_root) for frame in error.remote_frames), 'No actual candidate execution frame'
                    capture_raw_denial(execute_phase_and_candidate_frame_guards_passed=True)
                except Exception as error:
                    capture_raw_denial(local_Host_error={'type': type(error).__module__ + '.' + type(error).__qualname__, 'message': str(error)})
                    assert not remote, 'A local Host error cannot stand in for a Guest outcome'
                    outcome = {'kind': 'error', 'type': type(error).__name__, 'message': str(error)}
            outcome.update(stdout=stdout.getvalue(), stderr=stderr.getvalue(), warnings=[{'type': item.category.__name__, 'message': str(item.message)} for item in caught])
            if remote:
                assert not outcome['stdout'] and not outcome['stderr'] and not outcome['warnings']
                session = providers.execution_backend.session
                outcome.update(stdout=session.last_stdout, stderr=session.last_stderr)
            capture_raw_denial(normalized_outcome=outcome)
            return outcome
    finally:
        for ref in reversed(owned):
            await refs.release(ref)
            try:
                await refs.resolve(ref)
            except KeyError:
                pass
            else:
                raise AssertionError('Released genuine input ref still resolves')
        assert refs.clear() == 0, 'Untracked input refs survived explicit release'
        capture_raw_denial(explicit_input_ref_release_and_clear_zero=True)


def schema_checks(original, candidate):
    expected = json.loads((HERE / 'SCHEMAS.json').read_bytes())
    assert list(original.NODE_CLASS_MAPPINGS) == list(candidate.NODE_CLASS_MAPPINGS) == NODE_IDS
    assert original.NODE_DISPLAY_NAME_MAPPINGS == candidate.NODE_DISPLAY_NAME_MAPPINGS
    rows = []
    for row in expected:
        old, new = original.NODE_CLASS_MAPPINGS[row['id']], candidate.NODE_CLASS_MAPPINGS[row['id']]
        schema = new.GET_SCHEMA()
        schema.validate()
        assert old.__name__ == new.__name__ == row['id'] == schema.node_id
        assert schema.display_name == row['display_name'] == original.NODE_DISPLAY_NAME_MAPPINGS[row['id']]
        assert schema.category == old.CATEGORY == row['category']
        assert not schema.hidden and schema.is_input_list is False and schema.is_output_node is False
        assert [item.id for item in schema.inputs] == list(old.INPUT_TYPES()['required']) == [item['id'] for item in row['inputs']]
        assert [item.io_type for item in schema.inputs] == [item['type'] for item in row['inputs']]
        assert all(not item.optional for item in schema.inputs)
        assert [item.io_type for item in schema.outputs] == list(old.RETURN_TYPES) == row['output_types']
        assert [item.display_name for item in schema.outputs] == list(old.RETURN_NAMES) == row['output_names']
        assert all(not item.is_output_list for item in schema.outputs)
        converted_v1 = new.INPUT_TYPES()['required']
        for item in row['inputs']:
            actual = converted_v1[item['id']]
            if item['type'] == 'COMBO':
                options = actual[0] if isinstance(actual[0], (list, tuple)) else actual[1]['options']
                assert list(options) == item['options'] == list(old.INPUT_TYPES()['required'][item['id']][0])
            if 'default' in item:
                assert actual[1]['default'] == item['default'] == old.INPUT_TYPES()['required'][item['id']][1]['default']
        assert tuple(getattr(new, 'SDK_PERMISSIONS', ()) or ()) == tuple(row['permissions'])
        rows.append({'id': row['id'], 'inputs': len(row['inputs']), 'outputs': len(row['output_types']), 'exact': True})
    return rows


async def run_owned_component(*, original, candidate, io, sdk, host, wire, session, torch, output):
    """Called only by the existing owner after actual source/profile/birth checks.

    The wrapper remains responsible for constructor identity, complete source
    maps, normal-site startup, confinement, finite watchdog and retirement.
    Passing a fake session is refused. No runtime selection is implied here.
    """
    output = Path(output)
    assert output.is_absolute() and output.is_dir() and not output.is_symlink()
    assert type(session) is host.GuestSession and session.pid is not None
    assert session.sandbox_kind == 'seatbelt', 'Same qualified development Guest required; another sandbox needs its own actual-binding review'
    assert sdk.__name__ == 'comfy_api.latest._sdk'
    prior_backend = sdk.providers.execution_backend
    assert type(prior_backend) is sdk.InProcessExecutionBackend
    assert not sdk.providers.engaged and not sdk.providers.overlay_active
    cases = json.loads((HERE / 'CASES.json').read_bytes())
    ordinary, diagnostics = cases['ordinary'], cases['diagnostics']
    assert len(ordinary) == cases['ordinary_count'] == 76 and len(diagnostics) == cases['diagnostic_count'] == 6
    assert ordinary[0]['id'] == cases['smoke_case_id']
    guest_pid = session.pid
    counts = dict(original=0, default=0, Guest=0, diagnostics_original=0, diagnostics_default=0, diagnostics_Guest=0,
                  actual_default_local_calls=0, actual_Guest_dispatches=0)
    result = {'status': 'FAILED', 'counts': counts, 'rows': [], 'diagnostics': [], 'controls': [],
              'schemas': schema_checks(original, candidate), 'required_real_guest_pid': guest_pid,
              'Guest_creations_by_body': 0, 'expected_outer_observed_Guest_creations': 1,
              'runtime_or_whole_pack_or_service_accepted': False}

    raw_denial_evidence = None

    class ForwardToActualGuest:
        def __init__(self):
            self.session = session
            self.deny_raw_once = False

        async def dispatch(self, plan, local_call, runtime=None):
            assert type(plan) is sdk.ExecutionPlan and runtime is not None
            assert plan.node_type in NODE_IDS and plan.node_module == candidate.NODE_CLASS_MAPPINGS[plan.node_type].__module__
            assert plan.input_mode == 'refs' and plan.method == 'execute'
            requested = ('raw',) if plan.node_type == 'ImageSizeDetectorNode' else ()
            assert tuple(plan.permissions) == requested
            granted = () if self.deny_raw_once else requested
            self.deny_raw_once = False
            counts['actual_Guest_dispatches'] += 1
            if plan.node_id == 'control/missing-raw':
                raw_denial_evidence.update(requested_permissions=list(requested), granted_permissions=list(granted),
                    dispatch_count=counts['actual_Guest_dispatches'])
                save(output / 'RAW_PERMISSION_DENIAL.json', raw_denial_evidence)
            return await session.execute(plan, runtime, capabilities=granted, tenant='image-size-tools-owned-component')

    forward = ForwardToActualGuest()

    async def triplet(case, diagnostic=False):
        inputs = inputs_for(case, torch)
        before = fingerprint(inputs['image']) if 'image' in inputs else copy.deepcopy(inputs)
        node_id = case['node_id']
        sdk.providers.register_execution_backend(prior_backend)
        original_value = original_call(original.NODE_CLASS_MAPPINGS[node_id], inputs)
        if diagnostic:
            assert original_value['kind'] == 'error'
            assert {key: original_value[key] for key in ('type', 'message')} == case['error']
        else:
            assert original_value['kind'] == 'return' and original_value['result'] == typed(tuple(case['expected']))
            assert original_value['ui'] == typed(None)
        counts['diagnostics_original' if diagnostic else 'original'] += 1
        default_value = await sdk_call(candidate.NODE_CLASS_MAPPINGS[node_id], inputs, case['id'], io, sdk, wire, remote=False, counts=counts)
        compare(default_value, original_value)
        counts['diagnostics_default' if diagnostic else 'default'] += 1
        sdk.providers.register_execution_backend(forward)
        dispatches = counts['actual_Guest_dispatches']
        guest_value = await sdk_call(candidate.NODE_CLASS_MAPPINGS[node_id], inputs, case['id'], io, sdk, wire, remote=True, counts=counts)
        compare(guest_value, original_value)
        assert counts['actual_Guest_dispatches'] == dispatches + 1 and session.last_guest_pid == session.pid == guest_pid
        counts['diagnostics_Guest' if diagnostic else 'Guest'] += 1
        after = fingerprint(inputs['image']) if 'image' in inputs else inputs
        assert before == after, 'Input mutated across actual routes'
        row = {'id': case['id'], 'original': original_value, 'default': default_value, 'Guest': guest_value, 'inputs_unchanged': True}
        if 'pixel_pair' in case:
            row['pixel_pair'] = case['pixel_pair']
        result['diagnostics' if diagnostic else 'rows'].append(row)
        save(output / 'PARTIAL.json', result)

    try:
        await triplet(ordinary[0])
        assert [counts[key] for key in ('original', 'default', 'Guest')] == [1, 1, 1]
        assert counts['actual_default_local_calls'] == counts['actual_Guest_dispatches'] == 1
        assert all(counts[key] == 0 for key in ('diagnostics_original', 'diagnostics_default', 'diagnostics_Guest'))
        save(output / 'SMOKE.json', {'status': 'PASS_STRICT_FIRST_ORIGINAL_DEFAULT_REQUIRED_GUEST_1_1_1',
            'case': ordinary[0]['id'], 'counts': dict(counts), 'guest_pid': guest_pid, 'strict_outcomes_equal': True})
        # No remaining ordinary row or diagnostic may execute before SMOKE.json.
        for case in ordinary[1:]:
            await triplet(case)
        for case in diagnostics:
            await triplet(case, True)
        assert [counts[key] for key in ('original', 'default', 'Guest')] == [76, 76, 76]
        assert [counts[key] for key in ('diagnostics_original', 'diagnostics_default', 'diagnostics_Guest')] == [6, 6, 6]
        assert counts['actual_default_local_calls'] == counts['actual_Guest_dispatches'] == 82
        pairs = {}
        for row in result['rows']:
            if 'pixel_pair' in row:
                pairs.setdefault(row['pixel_pair'], []).append(row)
        assert len(pairs) == 6 and all(len(pair) == 2 for pair in pairs.values())
        for pair in pairs.values():
            compare(pair[0]['Guest'], pair[1]['Guest'])
        result['pixel_invariance_pairs'] = 6
        observed = result['rows'][0]['Guest']
        assert observed['result'] == typed((1024, 576, '16:9', 512, 288))
        for name in ('wrong-width', 'float-for-int', 'wrong-output-arity', 'wrong-ratio', 'wrong-halved-output', 'spurious-ui'):
            poisoned = copy.deepcopy(observed)
            values = poisoned['result']['items']
            if name == 'wrong-width':
                values[0]['value'] += 1
            elif name == 'float-for-int':
                values[0] = typed(1024.0)  # numerically equal: strict type must reject.
            elif name == 'wrong-output-arity':
                values.pop()
            elif name == 'wrong-ratio':
                values[2] = typed('9:16')
            elif name == 'wrong-halved-output':
                values[3]['value'] += 1
            else:
                poisoned['ui'] = typed({'text': ['invented']})
            try:
                compare(poisoned, observed)
            except AssertionError:
                result['controls'].append({'id': name, 'detected': True})
            else:
                raise AssertionError('Poisoned comparison accepted: ' + name)
        # Capability refusal is a separate control, never an ordinary parity pass.
        image_case = next(row for row in ordinary if row['node_id'] == 'ImageSizeDetectorNode')
        denial_inputs = inputs_for(image_case, torch)
        raw_denial_evidence = {'id': 'missing-raw', 'state': 'STARTED_NO_OUTCOME',
            'expected_contract_basis': 'Pinned Guest0f5468 source inference; R2 actual denied envelope was not retained',
            'expected_remote_type': 'PermissionError',
            'expected_remote_message': "raw buffer access requires the 'raw' capability (not granted: operate on the asset via its ops instead)",
            'inputs_before': fingerprint(denial_inputs['image']), 'counts_before': dict(counts),
            'observed_wire_error': False, 'execute_phase_and_candidate_frame_guards_passed': False,
            'session_pid': guest_pid, 'fresh_error_reply_PID_claim': False,
            'raw_RPC_observation': 'Not instrumented; pinned Guest _require_raw rejects before refs.materialize'}
        result['raw_denial_control'] = raw_denial_evidence
        save(output / 'RAW_PERMISSION_DENIAL.json', raw_denial_evidence)
        save(output / 'PARTIAL.json', result)
        forward.deny_raw_once = True
        sdk.providers.register_execution_backend(forward)
        try:
            denied = await sdk_call(candidate.NODE_CLASS_MAPPINGS['ImageSizeDetectorNode'], denial_inputs,
                'control/missing-raw', io, sdk, wire, remote=True, counts=counts,
                raw_denial_capture=(output / 'RAW_PERMISSION_DENIAL.json', raw_denial_evidence))
            raw_denial_evidence.update(state='OUTCOME_RECORDED_BEFORE_CONTRACT_ASSERTIONS', normalized_outcome=denied)
        finally:
            raw_denial_evidence.update(counts_after=dict(counts), inputs_after=fingerprint(denial_inputs['image']),
                cached_last_guest_pid=session.last_guest_pid,
                error_PID_limit='last_guest_pid may be cached; continuity only, no fresh error-reply PID receipt')
            save(output / 'RAW_PERMISSION_DENIAL.json', raw_denial_evidence)
            save(output / 'PARTIAL.json', result)
        assert raw_denial_evidence['observed_wire_error'] is True
        assert raw_denial_evidence['execute_phase_and_candidate_frame_guards_passed'] is True
        assert denied['kind'] == 'error' and denied['type'] == 'PermissionError'
        assert denied['message'] == "raw buffer access requires the 'raw' capability (not granted: operate on the asset via its ops instead)"
        assert raw_denial_evidence['requested_permissions'] == ['raw'] and raw_denial_evidence['granted_permissions'] == []
        assert raw_denial_evidence['inputs_before'] == raw_denial_evidence['inputs_after']
        assert raw_denial_evidence['explicit_input_ref_release_and_clear_zero'] is True
        assert session.last_guest_pid == guest_pid and counts['actual_Guest_dispatches'] == 83
        raw_denial_evidence.update(state='PASS_EXACT_GUEST_RAW_DENIAL_CONTROL_ONLY', input_unchanged=True,
            granted_raw_permission=False, raw_denial_before_materialize_source_bound=True)
        save(output / 'RAW_PERMISSION_DENIAL.json', raw_denial_evidence)
        result['controls'].append({'id': 'missing-raw', 'detected': True, 'Guest_outcome': denied})
        result.update(status='PASS_FINITE_COMPONENT_ONLY', ordinary=76, separate_diagnostics=6,
            comparator_controls=6, permission_controls=1, normal_generation_pair_and_replays='pending owner next stage')
        return result
    finally:
        sdk.providers.register_execution_backend(prior_backend)
        assert sdk.providers.execution_backend is prior_backend
        save(output / 'COMPONENT_RESULT.json', result)
        # The unchanged existing owner still must kill/probe this actual Guest,
        # retain live policy verification and independently prove retirement.
