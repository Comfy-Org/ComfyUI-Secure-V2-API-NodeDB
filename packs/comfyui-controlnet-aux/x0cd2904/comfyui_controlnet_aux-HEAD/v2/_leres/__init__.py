from .._annotator import common_annotator_call
from .detector import LeresDetector
from .selection import selected_checkpoint

async def execute( image, rm_nearest=0, rm_background=0, resolution=512, boost="disable", **kwargs):

    item = selected_checkpoint()
    model = (await LeresDetector.from_managed(item)).to(item['depth_device'])
    out = common_annotator_call(model, image, resolution=resolution, thr_a=rm_nearest, thr_b=rm_background, boost=boost == "enable")
    del model
    return (out, )
