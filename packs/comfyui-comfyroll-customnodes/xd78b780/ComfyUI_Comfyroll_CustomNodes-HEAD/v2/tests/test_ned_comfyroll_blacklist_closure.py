"""CR-BLACKLIST-EXPANDED-WORK-01 successor, not whole-pack release proof."""
import asyncio
import os
import sys

import pytest

from test_ned_comfyroll_pure import NEW, V2, _sdk, GuestSession, old, new
from comfy_secure_nodes.transport import wire

ID = 'CR Text Blacklist'
LIMIT = 16777216

def growth(replacement_size=32768):
    return dict(text='a', blacklist_words='a\n' + 'b\n' * 599,
                replacement_text='a' * replacement_size)

@pytest.mark.parametrize('args', [
    dict(text='', blacklist_words='', replacement_text=''),
    dict(text='a b a', blacklist_words='a\n b ', replacement_text='x'),
    dict(text='αβ', blacklist_words='β', replacement_text='🙂'),
    dict(text='a', blacklist_words='\n\n', replacement_text='x'),
    dict(text='ab', blacklist_words='a\nb', replacement_text='b'),
    dict(text='a', blacklist_words='#a\na', replacement_text=''),
    dict(text='a', blacklist_words='a\n' + 'b\n' * 40, replacement_text='a' * 64),
    growth(16384),
])
def test_native_exact_admitted_replacement_results(args):
    assert new(ID, args) == old(ID, args)

def test_actual_expanded_work_refused_at_unchanged_limit_before_next_replacement(monkeypatch):
    args = growth()
    assert (args['blacklist_words'].count('\n') + 1) * len(args['text']) == 601
    # The native result succeeds: this is a bounded-work adaptation, not a
    # claim that the pristine implementation raises the same exception.
    assert old(ID, args)[0] == 'a' * 32768
    assert 1 + 599 * 32768 == 19628033
    module = sys.modules[NEW.NODE_CLASS_MAPPINGS[ID].__module__]
    original = module._bounded_replace
    calls = []
    def observed(value, *rest, **kwargs):
        calls.append(len(value))
        return original(value, *rest, **kwargs)
    monkeypatch.setattr(module, '_bounded_replace', observed)
    with pytest.raises(ValueError, match='bounded replacement workload'):
        new(ID, args)
    assert len(calls) == 512 and sum(calls) == 16744449
    assert sum(calls) <= LIMIT < sum(calls) + 32768

def test_blank_lines_do_not_spend_replacement_work(monkeypatch):
    module = sys.modules[NEW.NODE_CLASS_MAPPINGS[ID].__module__]
    original = module._bounded_replace
    calls = []
    def observed(value, *rest, **kwargs):
        calls.append(len(value))
        return original(value, *rest, **kwargs)
    monkeypatch.setattr(module, '_bounded_replace', observed)
    args = dict(text='alpha', blacklist_words='\n  \nalpha\n\t\n', replacement_text='β')
    assert new(ID, args) == old(ID, args)
    assert calls == [5]

def test_two_fresh_zero_capability_guests_and_real_outer_success_refusal():
    import execution
    async def run():
        previous = _sdk.providers.execution_backend
        pids = []
        cls = NEW.NODE_CLASS_MAPPINGS[ID]
        cls.GET_SCHEMA()
        try:
            for render in range(2):
                session = await GuestSession('ned-blacklist-closure-' + str(render), guest_runtime_root=V2).start()
                class Backend:
                    async def dispatch(self, plan, local_call, runtime):
                        assert plan.permissions == ()
                        return await session.execute(plan, runtime, capabilities=())
                _sdk.providers.register_execution_backend(Backend())
                async def execute(args):
                    result = await execution._async_map_node_over_list(
                        prompt_id='ned-blacklist-closure', unique_id='1', obj=cls,
                        input_data_all={k: [v] for k, v in args.items()},
                        func=cls.FUNCTION, v3_data=None)
                    return result[0].result
                try:
                    args = growth(16384)
                    actual = await execute(args)
                    assert tuple(actual) == old(ID, args)
                    assert type(actual[0]) is str and type(actual[1]) is str
                    with pytest.raises(wire.WireError, match='bounded replacement workload'):
                        await execute(growth())
                    # A refused workload must not corrupt a later admitted call.
                    args = dict(text='αβ', blacklist_words='β', replacement_text='🙂')
                    assert tuple(await execute(args)) == old(ID, args)
                    assert session.alive()
                    pids.append(session.last_guest_pid)
                finally:
                    await session.kill()
        finally:
            _sdk.providers.register_execution_backend(previous)
        assert len(set(pids)) == 2 and all(pid not in (None, os.getpid()) for pid in pids)
    asyncio.run(run())
