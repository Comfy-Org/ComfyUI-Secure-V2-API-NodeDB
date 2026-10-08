"""Exact pinned socket options with closed managed catalogue adaptations."""
import json
from pathlib import Path
from comfy_api.latest import io

SCHEMAS=json.loads((Path(__file__).parent/'source-schema.json').read_text())
BUNDLED=tuple(SCHEMAS['Wildcards']['inputs']['required']['textfile'][0])
FONTS=tuple(SCHEMAS['ImageAddText']['inputs']['required']['font'][0])
TYPES={'STRING':io.String,'INT':io.Int,'FLOAT':io.Float,'CLIP':io.Clip,
       'MODEL':io.Model,'VAE':io.Vae,'LATENT':io.Latent,'IMAGE':io.Image,
       'MASK':io.Mask,'CONDITIONING':io.Conditioning}
ROUTE='/secure-nodes/text-files/input?prefix=chibi-wildcards/&suffix=.txt'

def schema(name):
    source=SCHEMAS[name]
    inputs=[]
    for section in ('required','optional'):
        for key,value in source['inputs'].get(section,{}).items():
            kind=value[0];options=dict(value[1]) if len(value)>1 else {}
            optional=section=='optional'
            options.pop('forceInput',None)
            if isinstance(kind,list):
                remote=None
                if name=='Wildcards' and key=='textfile':
                    remote=io.RemoteOptions(ROUTE,True,static_options=list(BUNDLED))
                elif name=='Loader':
                    folder='checkpoints' if key=='Checkpoint' else 'vae'
                    remote=io.RemoteOptions('/secure-nodes/models/'+folder,True,
                        static_options=['Included'] if key=='Vae' else [])
                    kind=[] if key=='Checkpoint' else ['Included']
                elif name=='LoadEmbedding' and key=='embedding':
                    remote=io.RemoteOptions('/secure-nodes/models/embeddings',True)
                    kind=[]
                elif name=='LoadImageExtended':
                    remote=io.RemoteOptions('/secure-nodes/assets/input?kind=image',True)
                    kind=[]
                inputs.append(io.Combo.Input(key,options=kind,optional=optional,
                    remote=remote,extra_dict=options))
            else:
                # Preserve unusual legacy widget options verbatim; the normal
                # forceInput marker remains authoritative in the V1 schema.
                options=dict(value[1]) if len(value)>1 else {}
                constructor={}
                for option in ('default','min','max','step','multiline'):
                    if option in options:constructor[option]=options.pop(option)
                if 'forceInput' in options:constructor['force_input']=options.pop('forceInput')
                inputs.append(TYPES[kind].Input(key,optional=optional,extra_dict=options,**constructor))
    names=source['names'] or source['outputs']
    outputs=[TYPES[kind].Output(display_name=label)
             for kind,label in zip(source['outputs'],names)]
    return io.Schema(node_id=name,category=source['category'],inputs=inputs,
        outputs=outputs,is_output_node=source['output_node'])
