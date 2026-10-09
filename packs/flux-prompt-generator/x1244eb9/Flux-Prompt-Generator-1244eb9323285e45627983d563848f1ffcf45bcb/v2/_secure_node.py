"""Public typed scalar workflow interface; original prompt algorithms remain pack-owned."""
import hashlib,json,math
from pathlib import Path
from comfy_api.latest import io
ROOT=Path(__file__).resolve().parent
PROFILE=json.loads((ROOT/'bundled-data-profile.json').read_bytes())
for relative,row in PROFILE['files'].items():
    p=ROOT/relative
    if not p.is_file() or p.is_symlink() or p.stat().st_size!=row['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
        raise ValueError('Flux Prompt Generator bundled catalogue drift')
from .flux_prompt_generator import FluxPromptGenerator as Native
MAX_INPUT=4096
MAX_STAGE=8192
MAX_OUTPUT=65536
def preflight(values):
    seed=values.get('seed',0)
    if type(seed) is not int or seed.bit_length()>64:raise ValueError('Flux prompt seed outside64-bit plain integer profile')
    text=0
    for key,value in values.items():
        if key=='seed':continue
        if type(value) is not str:raise TypeError('Flux prompt fields require plain strings')
        text+=len(value.encode('utf8'))
        if text>MAX_INPUT:raise ValueError('Flux prompt cumulative UTF8 input budget exceeded')
    # Fixed source literals and all possible source random choices, including
    # up to four lighting choices and gender-specific additions. This bounds
    # every intermediate native regex subject before running the algorithm.
    choices=sum(row['max_utf8']*(4 if Path(relative).stem=='lighting' else 1)
                for relative,row in PROFILE['files'].items()
                if values.get(Path(relative).stem,'random').lower()=='random')
    if text+choices+512>MAX_STAGE:raise ValueError('Flux prompt projected text/regex workload exceeded')
class FluxPromptGeneratorSecure(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        specs=Native.INPUT_TYPES()['required'];inputs=[]
        for name,spec in specs.items():
            options=dict(spec[1]) if len(spec)>1 else {}
            if name=='seed':options['default']=PROFILE['seed_default']
            if isinstance(spec[0],list):inputs.append(io.Combo.Input(name,options=spec[0],**options))
            elif spec[0]=='INT':inputs.append(io.Int.Input(name,**options))
            else:inputs.append(io.String.Input(name,**options))
        return io.Schema(node_id='FluxPromptGenerator',display_name='Flux Prompt Generator',category=Native.CATEGORY,
                         inputs=inputs,outputs=[io.String.Output(display_name='prompt')])
    @classmethod
    def execute(cls,**values):
        preflight(values)
        result=Native().execute(**values)
        if type(result) is not tuple or len(result)!=5 or type(result[1]) is not int or any(type(result[i]) is not str for i in (0,2,3,4)):
            raise TypeError('Flux prompt native result contract changed')
        if sum(len(result[i].encode('utf8')) for i in (0,2,3,4))>MAX_OUTPUT:raise ValueError('Flux prompt output budget exceeded')
        # Preserve five raw native values. V3 merges the single declared prompt
        # socket; legacy also caches four surplus, undeclared internal columns.
        return io.NodeOutput(*result)
    @classmethod
    def fingerprint_inputs(cls,**values):return Native.IS_CHANGED(**values)
NODE_CLASS_MAPPINGS={'FluxPromptGenerator':FluxPromptGeneratorSecure}
