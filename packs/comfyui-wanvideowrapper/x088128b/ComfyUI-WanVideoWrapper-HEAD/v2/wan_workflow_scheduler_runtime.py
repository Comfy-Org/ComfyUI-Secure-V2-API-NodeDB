"""Explicit scheduler recipe boundary; consumers receive real solver instances.

This is private staging, not a registered node or a Core SchedulerRef facade.
The complete original solver package is retained alongside this module.
"""
import math
import torch
from .wan_workflow_schedulers import get_scheduler,scheduler_list

FORMAT='wan-video-scheduler-recipe-v1'
SOURCE_ID='d652f59ffb8ac621aa1682e763732b416be5f495f6357443ee89bbd8008d4c84'
PARAMETERS={'scheduler','steps','start_step','end_step','shift','enhance_hf'}


def _parameters(scheduler,steps,start_step,end_step,shift,enhance_hf):
    if scheduler not in scheduler_list:
        raise ValueError('Unknown original Wan scheduler selection')
    if type(steps) is not int or not 1<=steps<=4096:
        raise ValueError('Wan scheduler steps exceed the bounded 4096-step domain')
    for value in (start_step,end_step):
        if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>4096:
            raise ValueError('Wan scheduler slice exceeds the bounded step domain')
    if type(shift) not in (int,float) or not math.isfinite(shift) or not 0<=shift<=1000:
        raise ValueError('Wan scheduler shift is outside its original public domain')
    if type(enhance_hf) is not bool:raise ValueError('enhance_hf must be boolean')
    return dict(scheduler=scheduler,steps=steps,start_step=start_step,end_step=end_step,
                shift=shift,enhance_hf=enhance_hf)


def _sigmas(sigmas):
    if sigmas is not None:
        if not isinstance(sigmas,torch.Tensor) or sigmas.layout!=torch.strided or sigmas.device.type!='cpu':
            raise ValueError('Wan custom sigmas require a dense CPU tensor')
        if sigmas.ndim!=1 or not 2<=sigmas.numel()<=4097:
            raise ValueError('Wan custom sigmas exceed the bounded schedule domain')
    return sigmas


def produce_scheduler(scheduler,steps,start_step,end_step,shift,sigmas=None,enhance_hf=False):
    """Preserve legacy tuple scalars, including its original SIGMAS passthrough.

    The legacy original returns its input ``sigmas`` (possibly None), and the
    original input step/slice values. Those are deliberately not rewritten to
    the generated tensor length or the factory's calculated slice indices.
    """
    parameters=_parameters(scheduler,steps,start_step,end_step,shift,enhance_hf)
    sigmas=_sigmas(sigmas)
    solver,timesteps,_,_=get_scheduler(scheduler,steps,start_step,end_step,shift,
        torch.device('cpu'),sigmas=sigmas,log_timesteps=True,enhance_hf=enhance_hf)
    recipe={'format':FORMAT,'source_identity':SOURCE_ID,'parameters':parameters,'sigmas':sigmas}
    actual={'sample_scheduler':solver,'timesteps':timesteps}
    return (sigmas,steps,shift,recipe,start_step,end_step),actual


def restore_scheduler(recipe):
    """Reconstruct the actual original solver, not a dictionary posing as one."""
    if not isinstance(recipe,dict) or set(recipe)!={'format','source_identity','parameters','sigmas'}:
        raise ValueError('Invalid owned Wan scheduler recipe')
    if recipe['format']!=FORMAT or recipe['source_identity']!=SOURCE_ID:
        raise ValueError('Wan scheduler source identity changed')
    values=recipe['parameters']
    if not isinstance(values,dict) or set(values)!=PARAMETERS:
        raise ValueError('Invalid Wan scheduler parameters')
    parameters=_parameters(**values)
    solver,timesteps,_,_=get_scheduler(**parameters,device=torch.device('cpu'),
        sigmas=_sigmas(recipe['sigmas']),log_timesteps=True)
    return {'sample_scheduler':solver,'timesteps':timesteps}
