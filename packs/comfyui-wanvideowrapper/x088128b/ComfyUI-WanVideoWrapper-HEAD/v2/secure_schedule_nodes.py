"""Pack-owned scalar schedules and execution-scoped, best-effort plain text."""
import math
from comfy_api.latest import io, sdk


def _schedule(steps, start, end, default, interpolation, start_percent, end_percent):
    # Bound allocation and loop work before creating the list. Preserve the
    # pinned negative/zero/reversed-range arithmetic within this bounded scope.
    if isinstance(steps, int) and abs(steps) > 1000:
        raise ValueError('Wan schedule exceeds 1000 steps')
    for value in (start, end, default, start_percent, end_percent):
        if not isinstance(value, (int, float)):
            raise TypeError('Wan schedule values must be scalar numbers')
        if not math.isfinite(value) or abs(value) > 1000000:
            raise ValueError('Wan schedule requires finite bounded values')
    if isinstance(interpolation, str) and len(interpolation.encode('utf-8', errors='surrogatepass')) > 65536:
        raise ValueError('Wan schedule interpolation exceeds 64 KiB')
    cfg_list = [default] * steps
    start_idx = min(int(steps * start_percent), steps - 1)
    end_idx = min(int(steps * end_percent), steps - 1)
    if end_idx - start_idx > 10000:
        raise ValueError('Wan schedule exceeds 10001 loop iterations')
    for i in range(start_idx, end_idx + 1):
        if i >= steps:
            break
        if end_idx == start_idx:
            t = 0
        else:
            t = (i - start_idx) / (end_idx - start_idx)
        if interpolation == 'linear':
            factor = t
        elif interpolation == 'ease_in':
            factor = t * t
        elif interpolation == 'ease_out':
            factor = t * (2 - t)
        cfg_list[i] = round(start + factor * (end - start), 2)
    if start_percent > 0:
        cfg_list[0] = default
    return cfg_list


async def _publish(values):
    # The broker captures the executing node and client, never caller IDs.
    # Match upstream's best-effort status update: failure cannot lose the list.
    try:
        await sdk.ctx().progress.text(str(values))
    except Exception:
        pass


def _tail():
    return [
        io.Combo.Input('interpolation', options=['linear', 'ease_in', 'ease_out'], default='linear', tooltip='Interpolation method to use for the cfg scale'),
        io.Float.Input('start_percent', default=0.0, min=0.0, max=1.0, step=0.01, round=0.01, tooltip='Start percent of the steps to apply cfg'),
        io.Float.Input('end_percent', default=1.0, min=0.0, max=1.0, step=0.01, round=0.01, tooltip='End percent of the steps to apply cfg'),
    ]


class CreateCFGScheduleFloatList(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CreateCFGScheduleFloatList', display_name='Create CFG Schedule Float List',
            category='WanVideoWrapper',
            description='Helper node to generate a list of floats that can be used to schedule cfg scale for the steps, outside the set range cfg is set to 1.0',
            inputs=[
                io.Int.Input('steps', default=30, min=2, max=1000, step=1, tooltip='Number of steps to schedule cfg for'),
                io.Float.Input('cfg_scale_start', default=5.0, min=0.0, max=30.0, step=0.01, round=0.01, tooltip='CFG scale to use for the steps'),
                io.Float.Input('cfg_scale_end', default=5.0, min=0.0, max=30.0, step=0.01, round=0.01, tooltip='CFG scale to use for the steps'),
                *_tail(),
            ], outputs=[io.Float.Output(display_name='float_list')], hidden=[io.Hidden.unique_id])

    @classmethod
    async def execute(cls, steps, cfg_scale_start, cfg_scale_end, interpolation, start_percent, end_percent):
        values = _schedule(steps, cfg_scale_start, cfg_scale_end, 1.0, interpolation, start_percent, end_percent)
        await _publish(values)
        return io.NodeOutput(values)


class CreateScheduleFloatList(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CreateScheduleFloatList', display_name='Create Schedule Float List',
            category='WanVideoWrapper',
            description='Helper node to generate a list of floats that can be used to schedule things like cfg and lora scale per step',
            inputs=[
                io.Int.Input('steps', default=30, min=2, max=1000, step=1, tooltip='Number of steps to schedule cfg for'),
                io.Float.Input('start_value', default=5.0, min=0.0, max=100.0, step=0.01, round=0.01, tooltip='CFG scale to use for the steps'),
                io.Float.Input('end_value', default=5.0, min=0.0, max=100.0, step=0.01, round=0.01, tooltip='CFG scale to use for the steps'),
                io.Float.Input('default_value', default=0.0, min=0.0, max=1000.0, step=0.01, round=0.01, tooltip='Default value to use for the steps'),
                *_tail(),
            ], outputs=[io.Float.Output(display_name='float_list')], hidden=[io.Hidden.unique_id])

    @classmethod
    async def execute(cls, steps, start_value, end_value, default_value, interpolation, start_percent, end_percent):
        values = _schedule(steps, start_value, end_value, default_value, interpolation, start_percent, end_percent)
        await _publish(values)
        return io.NodeOutput(values)


NODE_CLASS_MAPPINGS = {
    'CreateCFGScheduleFloatList': CreateCFGScheduleFloatList,
    'CreateScheduleFloatList': CreateScheduleFloatList,
}
