"""Pack-side RandomLoRA math with deliberately scoped, atomic local persistence.

Not a claim of legacy global-process/restart or deployed cloud-storage parity.
"""
import hashlib
import json
from random import random, uniform
from comfy_api.latest import io, sdk
from .secure_lora import _name, _weight, _stack

MAX_CONFLICTS=32
MAX_DRAW_CYCLES=256

def _digest(names):
    return hashlib.sha256(json.dumps(sorted(set(names)),ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()

def _common(args):
    stride=args['stride']
    if type(stride) is not int or not 1<=stride<=1000:
        raise ValueError('RandomLoRA stride must be an integer in [1,1000]')
    if args['force_randomize_after_stride'] not in ('Off','On'):
        raise ValueError('Invalid RandomLoRA force option')
    _stack(args.get('lora_stack'))

def _weight_args(args):
    _common(args);_name(args['lora_name'])
    if args['switch'] not in ('Off','On'):raise ValueError('Invalid RandomLoRA switch')
    for key in ('weight_min','weight_max','clip_weight'):_weight(args[key])

def _stack_args(args):
    _common(args)
    if args['exclusive_mode'] not in ('Off','On'):raise ValueError('Invalid exclusive mode')
    for i in range(1,4):
        _name(args[f'lora_name_{i}'])
        for key in ('model_weight','clip_weight'):_weight(args[f'{key}_{i}'])
        chance=args[f'chance_{i}']
        if type(chance) not in (int,float) or not 0<=chance<=1:raise ValueError('Invalid LoRA chance')
        if args[f'switch_{i}'] not in ('Off','On'):raise ValueError('Invalid LoRA switch')

def _decode(value,kind,identity,names=()):
    if value is None:return None
    if not isinstance(value,str) or len(value.encode('utf-8'))>8192:
        raise ValueError('Corrupt RandomLoRA state')
    def unique(pairs):
        out={}
        for key,val in pairs:
            if key in out:raise ValueError('Duplicate RandomLoRA state field')
            out[key]=val
        return out
    try:record=json.loads(value,object_pairs_hook=unique)
    except (ValueError,RecursionError) as exc:raise ValueError('Corrupt RandomLoRA state') from exc
    fields={'v','counter','last_fingerprint','last_weight' if kind=='weight' else 'used_names'}
    if not isinstance(record,dict) or set(record)!=fields or type(record['v']) is not int or record['v']!=1 or type(record['counter']) is not int or not 0<=record['counter']<1000:
        raise ValueError('Corrupt RandomLoRA state schema')
    if kind=='weight':
        try:_weight(record['last_weight'])
        except ValueError as exc:raise ValueError('Corrupt RandomLoRA weight') from exc
        expected=f"{identity}_{record['last_weight']:.3f}"
    else:
        used=record['used_names']
        if not isinstance(used,list) or len(used)>3 or any(not isinstance(n,str) or n not in names for n in used) or len(set(used))!=len(used):
            raise ValueError('Corrupt RandomLoRA names')
        expected=_digest(used)
    if record['last_fingerprint']!=expected:raise ValueError('Corrupt RandomLoRA fingerprint')
    return record

async def _atomic(key,kind,identity,names,choose):
    service=sdk.ctx().storage
    for _ in range(MAX_CONFLICTS):
        old=await service.read(key)
        record=_decode(old['value'],kind,identity,names)
        next_record=choose(record)
        encoded=json.dumps(next_record,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        if len(encoded.encode('utf-8'))>8192:raise ValueError('RandomLoRA record exceeds bound')
        updated=await service.compare_and_set(key,old['revision'],encoded)
        if updated['updated']:return next_record['last_fingerprint']
    raise RuntimeError('RandomLoRA exceeded 32 storage conflicts; no local choice committed')

def _choose_weight(args,identity,old):
    counter=(old['counter'] if old else 0)+1
    if args['stride']>1 and counter<args['stride'] and old:
        return dict(old,counter=counter)
    last=old['last_weight'] if old else None
    for _ in range(MAX_DRAW_CYCLES):
        value=uniform(args['weight_min'],args['weight_max'])
        if last is None or value!=last:
            return {'v':1,'counter':0,'last_weight':value,'last_fingerprint':f'{identity}_{value:.3f}'}
    raise RuntimeError('RandomLoRA exceeded 256 draw cycles; no state committed')

def _choose_stack(args,names,old):
    counter=(old['counter'] if old else 0)+1
    if args['stride']>1 and counter<args['stride'] and old:return dict(old,counter=counter)
    total_on=sum(name!='None' and args[f'switch_{i}']=='On' and args[f'chance_{i}']>0 for i,name in enumerate(names,1))
    previous=set(old['used_names']) if old else set()
    for _ in range(MAX_DRAW_CYCLES):
        draws=[random(),random(),random()]
        selected=[i for i in range(3) if draws[i]<=args[f'chance_{i+1}'] and args[f'switch_{i+1}']=='On']
        if args['exclusive_mode']=='On' and len(selected)>1:selected=[min(selected,key=lambda i:draws[i])]
        chosen={names[i] for i in selected if names[i]!='None'}
        if not(args['force_randomize_after_stride']=='On' and previous and total_on>1 and chosen==previous):
            return {'v':1,'counter':0,'used_names':sorted(chosen),'last_fingerprint':_digest(chosen)}
    raise RuntimeError('RandomLoRA exceeded 256 draw cycles; no state committed')

def weight_id(lora_name: str, force_randomize_after_stride, stride, weight_min, weight_max, clip_weight) -> int:
    fl_str = f'{lora_name}_{force_randomize_after_stride}_{stride}_{weight_min:.2f}_{weight_max:.2f}_{clip_weight:.2f}'
    return hashlib.sha256(fl_str.encode('utf-8')).hexdigest()

def deduplicateLoraNames(lora_name_1: str, lora_name_2: str, lora_name_3: str):
    is_same_1 = False
    is_same_2 = False
    is_same_3 = False
    if lora_name_1 == lora_name_2:
        is_same_1 = True
        is_same_2 = True
    if lora_name_1 == lora_name_3:
        is_same_1 = True
        is_same_3 = True
    if lora_name_2 == lora_name_3:
        is_same_2 = True
        is_same_3 = True
    if is_same_1:
        lora_name_1 = lora_name_1 + 'CR_RandomLoRAStack_1'
    if is_same_2:
        lora_name_2 = lora_name_2 + 'CR_RandomLoRAStack_2'
    if is_same_3:
        lora_name_3 = lora_name_3 + 'CR_RandomLoRAStack_3'
    return (lora_name_1, lora_name_2, lora_name_3)

def cleanLoraName(lora_name) -> str:
    if 'CR_RandomLoRAStack_1' in lora_name:
        lora_name = lora_name.replace('CR_RandomLoRAStack_1', '')
    elif 'CR_RandomLoRAStack_2' in lora_name:
        lora_name = lora_name.replace('CR_RandomLoRAStack_2', '')
    elif 'CR_RandomLoRAStack_3' in lora_name:
        lora_name = lora_name.replace('CR_RandomLoRAStack_3', '')
    return lora_name

class CR_RandomWeightLoRA(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('storage',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Random Weight LoRA',display_name='💊 CR Random Weight LoRA',category='🧩 Comfyroll Studio/✨ Essential/💊 LoRA',inputs=[io.Int.Input('stride', default=1, min=1, max=1000), io.Combo.Input('force_randomize_after_stride', options=['Off', 'On']), io.Combo.Input('lora_name', options=['None'], default='None', remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.Combo.Input('switch', options=['Off', 'On']), io.Float.Input('weight_min', default=0.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('weight_max', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('clip_weight', default=1.0, min=-10.0, max=10.0, step=0.01), io.Custom('LORA_STACK').Input('lora_stack', optional=True)],outputs=[io.Custom('LORA_STACK').Output(display_name='LORA_STACK')])

    @classmethod
    async def fingerprint_inputs(cls, **args):
        _weight_args(args)
        identity=weight_id(args['lora_name'],args['force_randomize_after_stride'],args['stride'],args['weight_min'],args['weight_max'],args['clip_weight'])
        if args['switch']=='Off':return identity+'_Off'
        if args['lora_name']=='None':return identity
        return await _atomic('random-weight.v1.'+identity,'weight',identity,(),lambda old:_choose_weight(args,identity,old))

    @classmethod
    async def execute(cls, **args):
        _weight_args(args)
        identity=weight_id(args['lora_name'],args['force_randomize_after_stride'],args['stride'],args['weight_min'],args['weight_max'],args['clip_weight'])
        old=_decode((await sdk.ctx().storage.read('random-weight.v1.'+identity))['value'],'weight',identity)
        result=[row for row in _stack(args.get('lora_stack')) if row[0]!='None']
        if args['lora_name']!='None' and args['switch']=='On':
            result.append((args['lora_name'],old['last_weight'] if old else 0.0,args['clip_weight']))
        return io.NodeOutput(result)

class CR_RandomLoRAStack(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('storage',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Random LoRA Stack',display_name='💊 CR Random LoRA Stack',category='🧩 Comfyroll Studio/✨ Essential/💊 LoRA',inputs=[io.Combo.Input('exclusive_mode', options=['Off', 'On']), io.Int.Input('stride', default=1, min=1, max=1000), io.Combo.Input('force_randomize_after_stride', options=['Off', 'On']), io.Combo.Input('lora_name_1', options=['None'], default='None', remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.Combo.Input('switch_1', options=['Off', 'On']), io.Float.Input('chance_1', default=1.0, min=0.0, max=1.0, step=0.01), io.Float.Input('model_weight_1', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('clip_weight_1', default=1.0, min=-10.0, max=10.0, step=0.01), io.Combo.Input('lora_name_2', options=['None'], default='None', remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.Combo.Input('switch_2', options=['Off', 'On']), io.Float.Input('chance_2', default=1.0, min=0.0, max=1.0, step=0.01), io.Float.Input('model_weight_2', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('clip_weight_2', default=1.0, min=-10.0, max=10.0, step=0.01), io.Combo.Input('lora_name_3', options=['None'], default='None', remote=io.RemoteOptions(route='/secure-nodes/models/loras', refresh_button=True, static_options=['None'])), io.Combo.Input('switch_3', options=['Off', 'On']), io.Float.Input('chance_3', default=1.0, min=0.0, max=1.0, step=0.01), io.Float.Input('model_weight_3', default=1.0, min=-10.0, max=10.0, step=0.01), io.Float.Input('clip_weight_3', default=1.0, min=-10.0, max=10.0, step=0.01), io.Custom('LORA_STACK').Input('lora_stack', optional=True)],outputs=[io.Custom('LORA_STACK').Output(display_name='LORA_STACK')])

    @classmethod
    async def fingerprint_inputs(cls, **args):
        _stack_args(args)
        names=deduplicateLoraNames(*(args[f'lora_name_{i}'] for i in range(1,4)))
        identity=_digest(names)
        return await _atomic('random-stack.v1.'+identity,'stack',identity,names,lambda old:_choose_stack(args,names,old))

    @classmethod
    async def execute(cls, **args):
        _stack_args(args)
        names=deduplicateLoraNames(*(args[f'lora_name_{i}'] for i in range(1,4)))
        identity=_digest(names)
        old=_decode((await sdk.ctx().storage.read('random-stack.v1.'+identity))['value'],'stack',identity,names)
        chosen=set(old['used_names']) if old else set()
        result=[row for row in _stack(args.get('lora_stack')) if row[0]!='None']
        for i,name in enumerate(names,1):
            if name!='None' and args[f'switch_{i}']=='On' and name in chosen:
                result.append((cleanLoraName(name),args[f'model_weight_{i}'],args[f'clip_weight_{i}']))
        return io.NodeOutput(result)

NODE_CLASS_MAPPINGS={'CR Random Weight LoRA':CR_RandomWeightLoRA,'CR Random LoRA Stack':CR_RandomLoRAStack}
NODE_DISPLAY_NAME_MAPPINGS={node_id:cls.define_schema().display_name for node_id,cls in NODE_CLASS_MAPPINGS.items()}
