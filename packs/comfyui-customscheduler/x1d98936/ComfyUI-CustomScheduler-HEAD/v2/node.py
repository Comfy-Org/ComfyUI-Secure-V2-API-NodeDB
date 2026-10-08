"""Pinned float32 sequence construction via the public SIGMAS constructor."""
from comfy_api.latest import io, sdk

class CustomScheduler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    FUNCTION = 'execute'

    @classmethod
    def define_schema(cls):
        defaults = [4.12, 1.62, 0.7, 0.04]
        return io.Schema(
            node_id='CustomScheduler', display_name='CustomScheduler',
            category='sampling/custom_sampling/schedulers',
            inputs=[io.Int.Input('steps', default=4, min=1, max=25)] + [
                io.Float.Input(f'sigma_{index}', optional=True,
                    default=defaults[index] if index < len(defaults) else 0.0,
                    min=0.0, max=100.0, step=0.01, round=0.0001)
                for index in range(26)
            ],
            outputs=[io.Sigmas.Output()],
        )

    @classmethod
    async def execute(cls, steps, **kwargs):
        if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 25:
            raise ValueError('steps must be a nonboolean integer in 1..25')
        # Deliberately retain the source's KeyError for omitted active sigmas.
        values = [kwargs[f'sigma_{index}'] for index in range(steps + 1)]
        return io.NodeOutput(await sdk.SigmasRef.from_values(values))
