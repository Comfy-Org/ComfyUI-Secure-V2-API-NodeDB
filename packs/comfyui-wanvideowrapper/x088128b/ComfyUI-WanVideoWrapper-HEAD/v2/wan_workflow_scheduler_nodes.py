"""Staged original scheduler sockets backed by reconstructable solver recipes.

Legacy plotting UI is not qualified; numerical and transport paths are tested
separately before these schemas can enter the canonical registry.
"""
from comfy_api.latest import io
from .wan_workflow_scheduler_runtime import produce_scheduler, scheduler_list


def _inputs():
    return [io.Combo.Input('scheduler', options=scheduler_list, default='unipc'),
            io.Int.Input('steps', default=30, min=1, tooltip='Number of steps for the scheduler'),
            io.Float.Input('shift', default=5.0, min=0.0, max=1000.0, step=0.01),
            io.Int.Input('start_step', default=0, min=0, tooltip='Starting step for the scheduler'),
            io.Int.Input('end_step', default=-1, min=-1, tooltip='Ending step for the scheduler'),
            io.Custom('SIGMAS').Input('sigmas', optional=True),
            io.Boolean.Input('enhance_hf', optional=True, default=False, tooltip='Enhanced high-frequency denoising schedule')]


class WanVideoScheduler(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoScheduler', display_name='WanVideo Scheduler', category='WanVideoWrapper',
            is_experimental=True, inputs=_inputs(),
            outputs=[io.Custom('SIGMAS').Output(display_name='sigmas'),
                     io.Int.Output(display_name='steps'), io.Float.Output(display_name='shift'),
                     io.Combo.Output(display_name='scheduler', options=scheduler_list),
                     io.Int.Output(display_name='start_step'), io.Int.Output(display_name='end_step')])

    @classmethod
    def execute(cls, scheduler, steps, start_step, end_step, shift, sigmas=None, enhance_hf=False):
        legacy, _ = produce_scheduler(scheduler, steps, start_step, end_step, shift, sigmas, enhance_hf)
        return io.NodeOutput(*legacy)


class WanVideoSchedulerv2(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='WanVideoSchedulerv2', display_name='WanVideo Scheduler v2', category='WanVideoWrapper',
            is_experimental=True, inputs=_inputs(),
            outputs=[io.Custom('WANVIDEOSCHEDULER').Output(display_name='scheduler')])

    @classmethod
    def execute(cls, scheduler, steps, start_step, end_step, shift, sigmas=None, enhance_hf=False):
        legacy, _ = produce_scheduler(scheduler, steps, start_step, end_step, shift, sigmas, enhance_hf)
        return io.NodeOutput(legacy[3])


NODE_CLASS_MAPPINGS = {'WanVideoScheduler': WanVideoScheduler,
                       'WanVideoSchedulerv2': WanVideoSchedulerv2}
