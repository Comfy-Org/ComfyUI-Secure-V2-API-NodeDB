import asyncio
import copy
import json

import pytest
from test_ned_comfyroll_random_lora import NEW, V2, weight_args, stack_args
from comfy_api.latest import _sdk
from comfy_secure_nodes import storage
from comfy_secure_nodes.transport.host import GuestSession
import execution
import nodes


class Server:
    client_id = None
    last_node_id = None

    def send_sync(self, *args):
        pass


@pytest.mark.parametrize('node_id,args,iterations,expected', [
    ('CR Random Weight LoRA', weight_args(weight_min=.25, weight_max=.25, stride=3), 2, [('a.safetensors', .25, 1.0)]),
    ('CR Random LoRA Stack', stack_args(stride=3, force_randomize_after_stride='Off',
        lora_name_1='a', switch_1='On', chance_1=1., switch_2='Off', switch_3='Off'), 3, [('a', 1., -1.)]),
])
def test_real_prompt_executor_fingerprints_tick_while_cached_output_is_reused(node_id, args, iterations, expected, tmp_path, monkeypatch):
    store = storage.PackStorage(tmp_path / 'backing')
    monkeypatch.setattr(storage, '_STORAGE', store)
    monkeypatch.setenv('COMFY_SECURE_SANDBOX_MODE', 'required')
    cls = NEW.NODE_CLASS_MAPPINGS[node_id]
    monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS, node_id, cls)
    graph = {'random': {'class_type': node_id, 'inputs': args}}

    async def run():
        events = []
        session = await GuestSession('comfyroll-real-cache', tenant='cache-user', guest_runtime_root=V2).start()
        class Backend:
            async def dispatch(self, plan, local_call, runtime):
                result = await session.execute(plan, runtime, capabilities=('storage',), tenant='cache-user')
                events.append((plan.prompt_id, plan.method))
                return result
        monkeypatch.setattr(_sdk.providers, 'execution_backend', Backend())
        executor = execution.PromptExecutor(Server(), cache_type=execution.CacheType.CLASSIC,
            cache_args={'ram': 0, 'ram_inactive': 0})
        try:
            assert session.sandbox_kind == 'seatbelt'
            outputs = []
            for index in range(iterations):
                await executor.execute_async(copy.deepcopy(graph), 'random-cache-' + str(index), {}, ['random'])
                assert executor.success, executor.status_messages
                cached = next(data['nodes'] for event, data in executor.status_messages if event == 'execution_cached')
                assert ('random' in cached) == (index > 0)
                entry = await executor.caches.outputs.get('random')
                outputs.append(entry.outputs)
            assert outputs[0] == outputs[-1]
            assert outputs[0] == [[expected]]
            assert sum(method == 'execute' for _, method in events) == 1
            assert sum(method == 'fingerprint_inputs' for _, method in events) == iterations
            keys = store.list('cache-user', 'development/comfyroll-real-cache')
            assert len(keys) == 1
            state = json.loads(store.get('cache-user', 'development/comfyroll-real-cache', keys[0]))
            assert state['counter'] == iterations - 1
        finally:
            await session.kill()
    asyncio.run(run())
