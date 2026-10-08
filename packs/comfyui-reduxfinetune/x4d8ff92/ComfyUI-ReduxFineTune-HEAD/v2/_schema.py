import json
from pathlib import Path
from comfy_api.latest import io

SOURCE=json.loads((Path(__file__).parent/'source-schema.json').read_text())
DISPLAY={'ReduxFineTune':'Flux Redux Style Fine Tune (Simple)',
         'ReduxFineTuneAdvanced':'Flux Redux Style Fine Tune (Advanced)',
         'ClipVisionStyleLoader':'CLIP Vision + Style Loader'}
TYPES={'CONDITIONING':io.Conditioning,'STYLE_MODEL':io.StyleModel,
       'CLIP_VISION_OUTPUT':io.ClipVisionOutput,'CLIP_VISION':io.ClipVision,
       'IMAGE':io.Image,'MASK':io.Mask,'FLOAT':io.Float,'INT':io.Int,'BOOLEAN':io.Boolean}

def schema(name):
    source=SOURCE[name];inputs=[]
    for section in ('required','optional'):
        for key,value in source['inputs'].get(section,{}).items():
            kind=value[0];opts=dict(value[1]) if len(value)>1 else {}
            optional=section=='optional'
            if isinstance(kind,list):
                remote=None
                if name=='ClipVisionStyleLoader' and key in ('clip_vision','style_model'):
                    folder='clip_vision' if key=='clip_vision' else 'style_models'
                    remote=io.RemoteOptions('/secure-nodes/models/'+folder,True)
                inputs.append(io.Combo.Input(key,options=kind,optional=optional,remote=remote,extra_dict=opts))
            else:
                constructor={}
                for option in ('default','min','max','step','tooltip'):
                    if option in opts:constructor[option]=opts.pop(option)
                inputs.append(TYPES[kind].Input(key,optional=optional,extra_dict=opts,**constructor))
    outputs=[]
    for index,kind in enumerate(source['outputs']):
        options={}
        if source['names']:options['display_name']=source['names'][index]
        if source['output_is_list']:options['is_output_list']=source['output_is_list'][index]
        outputs.append(TYPES[kind].Output(**options))
    return io.Schema(node_id=name,display_name=DISPLAY[name],category=source['category'],inputs=inputs,outputs=outputs)
