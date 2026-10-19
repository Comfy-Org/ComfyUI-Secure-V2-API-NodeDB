"""Frozen, host-safe V2 schemas and ref-boundary conversion."""
from __future__ import annotations
import copy
import inspect
import json
from pathlib import Path, PurePosixPath
from comfy_api.latest import io, sdk
from . import _packload
SCHEMAS=json.loads(Path(__file__).with_name('_schemas.json').read_text())
CANONICAL={row['id']:key for key,row in SCHEMAS.items()}
_TYPES={'INT':io.Int,'FLOAT':io.Float,'BOOLEAN':io.Boolean,'STRING':io.String,'IMAGE':io.Image,'MASK':io.Mask,'LATENT':io.Latent,'CONDITIONING':io.Conditioning,'MODEL':io.Model,'VAE':io.Vae,'CLIP':io.Clip}
def iotype(name):return _TYPES.get(name) or io.Custom(name)

def schema_for(original):
    row=SCHEMAS[original];inputs=[]
    for section in ['required','optional']:
        for name,spec in row['inputs'].get(section,{}).items():
            wire=spec[0];opts=copy.deepcopy(spec[1] if len(spec)>1 else {})
            opts['optional']=section=='optional'
            rename={'forceInput':'force_input','dynamicPrompts':'dynamic_prompts'}
            opts={rename.get(k,k):v for k,v in opts.items()}
            if isinstance(wire,list):
                catalogs=[s[9:] for s in wire if isinstance(s,str) and s.startswith('@catalog:')]
                choices=[s for s in wire if not isinstance(s,str) or not s.startswith('@catalog:')]
                if catalogs:opts['remote']=io.RemoteOptions(route='/models/'+catalogs[0],refresh_button=True)
                factory=io.Combo.Input;opts['options']=choices
            else:factory=iotype(wire).Input
            accepted=set(inspect.signature(factory).parameters)
            extra={k:v for k,v in opts.items() if k not in accepted}
            opts={k:v for k,v in opts.items() if k in accepted}
            if extra:opts['extra_dict']={**opts.get('extra_dict',{}),**extra}
            inputs.append(factory(name,**opts))
    hidden=[]
    for name,source in row['inputs'].get('hidden',{}).items():
        key={'PROMPT':'prompt','EXTRA_PNGINFO':'extra_pnginfo','UNIQUE_ID':'unique_id'}.get(source) if isinstance(source,str) else None
        if key:hidden.append(getattr(io.Hidden,key))
    outputs=[iotype(t).Output(display_name=n) for t,n in zip(row['returns'],row['names'])]
    return io.Schema(node_id=row['id'],display_name=row['display_name'],category=row['category'],inputs=inputs,outputs=outputs,hidden=hidden,is_output_node=row['output_node'],enable_expand=original=='ttN advPlot images',accept_all_inputs=False)

def validate(original,values):
    # Host-safe: pure validation, no imports of the admitted implementation.
    for section in ['required','optional']:
        for name,spec in SCHEMAS[original]['inputs'].get(section,{}).items():
            if name not in values:continue
            value=values[name];wire=spec[0]
            if isinstance(wire,list) and any(isinstance(w,str) and w.startswith('@catalog:') for w in wire):
                if not isinstance(value,str) or not value or '\x00' in value:return f'{name} requires a logical asset name'
                p=PurePosixPath(value.replace('\\','/'))
                if p.is_absolute() or '..' in p.parts or ':' in value:return f'{name} requires a catalogue-relative name'
    return True

async def wrap(value,wire):
    if value is None or isinstance(value,(sdk.Ref,int,float,str,bool)):return value
    if wire=='IMAGE':return await sdk.ImageRef.from_value(value)
    if wire=='MASK':return await sdk.MaskRef.from_value(value)
    if wire=='LATENT':return await sdk.LatentRef.from_value(value)
    if wire=='CONDITIONING':return await sdk.CondRef.from_value(value)
    if wire in ['PIPE_LINE','PIPE_LINE_SDXL']:
        mapping={'positive':'CONDITIONING','negative':'CONDITIONING','refiner_positive':'CONDITIONING','refiner_negative':'CONDITIONING','samples':'LATENT','images':'IMAGE'}
        # SDK classifies any mapping with a top-level `samples` key as LATENT.
        # A pipe also contains live models: keep its latent in a distinct field
        # on the wire so the SDK wraps each leaf with its own narrow handle.
        return {('__ttn_latent__' if k=='samples' else k):await wrap(v,mapping[k]) if k in mapping else await wrap_settings(v) for k,v in value.items()}
    if wire in ['BASIC_PIPE','DETAILER_PIPE']:
        types=['MODEL','CLIP','VAE','CONDITIONING','CONDITIONING']
        return tuple([await wrap(v,types[i]) if i<len(types) else v for i,v in enumerate(value)])
    return value
async def wrap_settings(v):
    if isinstance(v,dict):return {k:await wrap(x,'LATENT') if k=='empty_samples' and x is not None else await wrap_settings(x) for k,x in v.items()}
    return v

def unpack_pipe(value):
    if isinstance(value,dict) and '__ttn_latent__' in value:
        return {('samples' if k=='__ttn_latent__' else k):v for k,v in value.items()}
    return value

async def output(original,result):
    if isinstance(result,io.NodeOutput):return result
    ui=None
    if isinstance(result,dict) and ('result' in result or 'ui' in result):ui=result.get('ui');values=result.get('result',result.get('return',()))
    else:values=result
    if values is None:values=()
    if not isinstance(values,(list,tuple)):values=(values,)
    row=SCHEMAS[original]
    # Source pipeEncodeConcat returns a UI dictionary as a fifth pseudo-output.
    if original=='ttN pipeEncodeConcat' and len(values)==5 and isinstance(values[-1],dict):ui=values[-1].get('ui');values=values[:4]
    if len(values)!=len(row['returns']):raise RuntimeError(f"{original}: returned {len(values)} outputs, expected {len(row['returns'])}")
    return io.NodeOutput(*[await wrap(v,t) for v,t in zip(values,row['returns'])],ui=ui)

_RAW_NODES={k for k in SCHEMAS if any(p in k for p in ['Loader','Sampler','conditioning','EncodeConcat','hiresfix','REMBG','advPlot images'])}
async def execute_node(cls,original,kwargs):
    from . import _ops
    row=SCHEMAS[original];kwargs=dict(kwargs);hidden=getattr(cls,'hidden',None)
    for section in ['required','optional']:
        for name,spec in row['inputs'].get(section,{}).items():
            if spec[0] in ['PIPE_LINE','PIPE_LINE_SDXL'] and name in kwargs:
                kwargs[name]=unpack_pipe(kwargs[name])
    for name,source in row['inputs'].get('hidden',{}).items():
        key={'PROMPT':'prompt','EXTRA_PNGINFO':'extra_pnginfo','UNIQUE_ID':'unique_id'}.get(source) if isinstance(source,str) else None
        if key:kwargs[name]=getattr(hidden,key,None)
    if 'my_unique_id' in kwargs and kwargs['my_unique_id'] is None:kwargs['my_unique_id']='0'
    token=_ops.begin(row['module']=='legacy')
    try:
        if original in _RAW_NODES:kwargs={k:await _ops.materialize(v) for k,v in kwargs.items()}
        handlers=_packload.load('_handlers')
        if original in handlers.HANDLERS:
            result=await handlers.HANDLERS[original](**kwargs)
        else:
            module=_packload.load('_impl_'+row['module']);obj=getattr(module,row['class'])()
            method=getattr(obj,row['function'])
            # Missing optional widgets receive the defaults in the original FUNCTION.
            sig=inspect.signature(method)
            if not any(p.kind==inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):kwargs={k:v for k,v in kwargs.items() if k in sig.parameters}
            if row['module']=='legacy' and kwargs.get('xyPlot'):
                _ops._services.get()['font']=await _ops.font_bytes()
            result=method(**kwargs)
            if inspect.isawaitable(result):result=await result
        return await output(original,result)
    finally:_ops.end(token)
