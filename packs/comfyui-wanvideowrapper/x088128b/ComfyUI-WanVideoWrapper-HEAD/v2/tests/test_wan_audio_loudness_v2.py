"""Actual native/vendor/SDK/guest comparisons for an externally qualified run.

The executor supplies qualified_wan_audio_runtime AFTER real installed-origin,
vendor ABI, current admission, finite issue and independent cleanup checks.
Missing fixtures fail collection/execution; these tests never self-admit a
runtime, inject SDK/vendor mocks, install packages or load source by FileSpec.
"""
import asyncio

import pytest


@pytest.fixture
def selected(request):
    return request.getfixturevalue("qualified_wan_audio_runtime")


def audio_case(q, *, sample_rate=16000, channels=1, seconds=0.75,
               dtype_name="float32", amplitude=0.1, batched=True,
               noncontiguous=False):
    torch = q.torch
    count = int(sample_rate * seconds)
    # Deterministic varying content exercises the actual loudness filters.
    times = torch.arange(count * (2 if noncontiguous else 1), dtype=torch.float64) / sample_rate
    wave = amplitude * (torch.sin(times * (2 * torch.pi * 440))
                        + 0.31 * torch.sin(times * (2 * torch.pi * 173)))
    waveform = torch.stack([wave * (1 - 0.17 * channel) for channel in range(channels)])
    if noncontiguous:
        waveform = waveform[:, ::2]
    waveform = waveform.to(getattr(torch, dtype_name))
    if batched:
        waveform = waveform.unsqueeze(0)
    return {"waveform": waveform, "sample_rate": sample_rate}


def equal_audio(q, expected, actual):
    assert set(expected) == set(actual) == {"waveform", "sample_rate"}
    assert actual["sample_rate"] == expected["sample_rate"]
    assert actual["waveform"].shape == expected["waveform"].shape
    assert actual["waveform"].dtype == expected["waveform"].dtype == q.torch.float32
    assert actual["waveform"].device == expected["waveform"].device
    q.torch.testing.assert_close(actual["waveform"], expected["waveform"], rtol=0, atol=0, equal_nan=True)


async def resolve_audio(q, refs, output):
    result = await refs.resolve(output.result[0])
    waveform = result["waveform"]
    if isinstance(waveform, q.sdk.Ref):
        waveform = await refs.resolve(waveform)
    return {"waveform": waveform, "sample_rate": result["sample_rate"]}


async def direct(q, audio, lufs):
    # q.make_plan uses the actual owner-selected namespace and finite case
    # admission; no arbitrary prompt identity or grant is manufactured here.
    plan = q.make_plan(audio, lufs, input_mode="refs")
    refs = q.sdk.InProcessRefResolver()
    context = q.sdk.InProcessCtxProvider().build(plan)
    with q.sdk.bind_runtime(refs, context, q.sdk.InProcessOps()):
        wrapped = await q.sdk.wrap_inputs(refs, {"audio": audio}, {"audio": "AUDIO"})
        output = await q.candidate_class.execute(wrapped["audio"], lufs)
        return await resolve_audio(q, refs, output)


def test_exact_native_schema_workflow_identity_and_permissions(selected):
    q = selected
    old = q.native_class
    cls = q.candidate_class
    schema = cls.GET_SCHEMA()
    assert schema.node_id == "NormalizeAudioLoudness"
    assert schema.display_name == "Normalize Audio Loudness"
    assert schema.category == old.CATEGORY
    assert [(item.id, item.io_type, item.optional) for item in schema.inputs] == [
        ("audio", "AUDIO", False), ("lufs", "FLOAT", False)]
    legacy = old.INPUT_TYPES()["required"]["lufs"][1]
    lufs = schema.inputs[1]
    for field in ("default", "min", "max", "step"):
        assert getattr(lufs, field) == legacy[field]
    assert lufs.extra_dict == {"tool": legacy["tool"]}
    assert schema.outputs[0].io_type == old.RETURN_TYPES[0]
    assert schema.outputs[0].display_name == old.RETURN_NAMES[0]
    assert len(schema.outputs) == 1
    assert cls.SDK_REFS is True and cls.SDK_PERMISSIONS == ("raw",)


def test_native_differential_dtype_rank_stereo_rate_and_noncontiguous(selected):
    q = selected
    rng = q.torch.random.get_rng_state().clone()
    async def run():
        for sample_rate in (8000, 16000, 48000):
            for channels, batched, dtype, sliced in (
                (1, True, "float32", False), (2, True, "float64", False),
                (1, False, "float64", True), (2, False, "float32", True)):
                audio = audio_case(q, sample_rate=sample_rate, channels=channels,
                                   batched=batched, dtype_name=dtype, noncontiguous=sliced)
                before = audio["waveform"].clone()
                for target in (-32.0, -23.0, -12.0):
                    expected = q.native_class().normalize(audio, target)[0]
                    actual = await direct(q, audio, target)
                    equal_audio(q, expected, actual)
                    assert not q.torch.equal(actual["waveform"].reshape(-1), before.float().reshape(-1))
                    q.torch.testing.assert_close(audio["waveform"], before, rtol=0, atol=0)
    asyncio.run(run())
    assert q.torch.equal(q.torch.random.get_rng_state(), rng)


def test_real_meter_targets_and_silence_native_branch(selected):
    q = selected
    async def run():
        audio = audio_case(q, channels=2)
        for target in (-32.0, -23.0, -12.0):
            actual = await direct(q, audio, target)
            wave = actual["waveform"].squeeze(0).transpose(0, 1).numpy()
            loudness = q.pyloudnorm.Meter(audio["sample_rate"]).integrated_loudness(wave)
            assert loudness == pytest.approx(target, abs=1e-5)
        for dtype in ("float32", "float64"):
            silent = audio_case(q, amplitude=0.0, dtype_name=dtype)
            equal_audio(q, q.native_class().normalize(silent, -23.0)[0], await direct(q, silent, -23.0))
    asyncio.run(run())


def test_native_short_audio_and_malformed_numeric_errors(selected):
    q = selected
    async def run():
        cases = [audio_case(q, seconds=0.1), audio_case(q, channels=6)]
        bad_batch = audio_case(q)
        bad_batch["waveform"] = bad_batch["waveform"].repeat(2, 1, 1)
        cases.append(bad_batch)
        bad_rate = audio_case(q)
        bad_rate["sample_rate"] = 0
        cases.append(bad_rate)
        for audio in cases:
            try:
                q.native_class().normalize(audio, -23.0)
            except Exception as native_error:
                with pytest.raises(type(native_error)) as converted_error:
                    await direct(q, audio, -23.0)
                assert str(converted_error.value) == str(native_error)
            else:
                pytest.fail("Malformed fixture did not exercise a native failure")
    asyncio.run(run())


def test_actual_required_guest_fresh_roots_raw_denial_and_recovery(selected):
    q = selected
    async def run():
        assert len(q.guest_roots) == 2 and q.guest_roots[0] != q.guest_roots[1]
        assert q.required_sandbox_kind and q.required_sandbox_kind != "none"
        pids = []
        for root in q.guest_roots:
            session = await q.GuestSession(q.pack_scope, guest_runtime_root=root).start()
            assert session.sandbox_kind == q.required_sandbox_kind
            try:
                for index, (channels, dtype, amplitude) in enumerate(
                    ((1, "float32", 0.1), (2, "float64", 0.2), (1, "float32", 0.0))):
                    audio = audio_case(q, channels=channels, dtype_name=dtype, amplitude=amplitude)
                    target = -23.0 + index
                    plan = q.make_plan(audio, target, input_mode="refs", guest_root=root)
                    refs = q.sdk.InProcessRefResolver()
                    runtime = q.sdk.Runtime(refs=refs, ctx=q.sdk.InProcessCtxProvider().build(plan),
                                            ops=q.sdk.InProcessOps())
                    plan.inputs = await q.sdk.wrap_inputs(refs, plan.inputs, plan.input_types)
                    output = await session.execute(plan, runtime, capabilities=("raw",), tenant=q.tenant)
                    equal_audio(q, q.native_class().normalize(audio, target)[0],
                                await resolve_audio(q, refs, output))
                    with pytest.raises(Exception, match="raw"):
                        await session.execute(plan, runtime, capabilities=(), tenant=q.tenant)
                    recovered = await session.execute(plan, runtime, capabilities=("raw",), tenant=q.tenant)
                    equal_audio(q, q.native_class().normalize(audio, target)[0],
                                await resolve_audio(q, refs, recovered))
                pids.append(session.last_guest_pid)
            finally:
                await session.kill()
        assert all(pid is not None for pid in pids) and pids[0] != pids[1]
    asyncio.run(run())


def test_actual_guest_native_short_audio_failure_then_recovery(selected):
    q = selected
    async def run():
        session = await q.GuestSession(q.pack_scope, guest_runtime_root=q.guest_roots[0]).start()
        assert session.sandbox_kind == q.required_sandbox_kind and session.sandbox_kind != "none"
        try:
            for duration in (0.1, 0.75):
                audio = audio_case(q, seconds=duration)
                plan = q.make_plan(audio, -23.0, input_mode="refs", guest_root=q.guest_roots[0])
                refs = q.sdk.InProcessRefResolver()
                runtime = q.sdk.Runtime(refs=refs, ctx=q.sdk.InProcessCtxProvider().build(plan),
                                        ops=q.sdk.InProcessOps())
                plan.inputs = await q.sdk.wrap_inputs(refs, plan.inputs, plan.input_types)
                if duration < 0.4:
                    with pytest.raises(Exception) as native_error:
                        q.native_class().normalize(audio, -23.0)
                    with pytest.raises(Exception) as guest_error:
                        await session.execute(plan, runtime, capabilities=("raw",), tenant=q.tenant)
                    assert str(native_error.value) in str(guest_error.value)
                else:
                    output = await session.execute(plan, runtime, capabilities=("raw",), tenant=q.tenant)
                    equal_audio(q, q.native_class().normalize(audio, -23.0)[0],
                                await resolve_audio(q, refs, output))
        finally:
            await session.kill()
    asyncio.run(run())


def test_real_vendor_absence_preserves_native_import_error(request):
    # This is a separate real dependency profile, not sys.modules injection.
    q = request.getfixturevalue("qualified_wan_audio_without_vendor_runtime")
    audio = audio_case(q)
    with pytest.raises(ImportError, match="pyloudnorm package is not installed"):
        q.native_class().normalize(audio, -23.0)
    with pytest.raises(ImportError, match="pyloudnorm package is not installed"):
        asyncio.run(direct(q, audio, -23.0))
