"""Bounded pack-side tensor algorithms under raw/value-mode; no host object access."""
import math
import torch
from comfy_api.latest import io
from .secure_schedules import _guard, _output

def _bytes(t):
    return t.numel()*t.element_size()

def _preflight(node_id, values):
    tensors=[];items=0;text_bytes=0
    def walk(value,depth=0):
        nonlocal items,text_bytes
        items+=1
        if depth>8 or items>4096:raise ValueError('Tensor container workload exceeds bound')
        if isinstance(value,torch.Tensor):
            if value.layout!=torch.strided or value.ndim>8 or any(d>8192 for d in value.shape):
                raise ValueError('Tensor layout/dimensions exceed bound')
            tensors.append(value)
        elif isinstance(value,(list,tuple)):
            for child in value:walk(child,depth+1)
        elif isinstance(value,dict):
            for key,child in value.items():
                walk(key,depth+1);walk(child,depth+1)
        else:
            if isinstance(value,str):
                text_bytes+=len(value.encode('utf-8'))
                if text_bytes>262144:raise ValueError('Tensor metadata text exceeds bound')
            _guard({'value':value})
    walk(values)
    input_bytes=sum(_bytes(t) for t in tensors)
    if input_bytes>64*1024*1024:raise ValueError('Tensor inputs exceed 64MiB')
    projected=input_bytes
    if node_id=='CR Latent Batch Size':
        count=values['batch_size']
        if type(count) is int:
            if abs(count)>64:raise ValueError('Latent batch multiplier exceeds bound')
            latent=values['latent']
            if isinstance(latent,dict) and isinstance(latent.get('samples'),torch.Tensor):
                projected=max(1,count)*_bytes(latent['samples'])
    elif node_id=='CR Debatch Frames':
        frames=values['frames']
        if isinstance(frames,torch.Tensor) and frames.ndim and frames.shape[0]>64:
            raise ValueError('Frame batch exceeds bound')
    elif node_id=='CR Conditioning Mixer':
        first=values['conditioning_1'];second=values['conditioning_2']
        if isinstance(first,(list,tuple)) and isinstance(second,(list,tuple)) and first:
            if len(first)>64 or len(second)>64:raise ValueError('Conditioning rows exceed bound')
            if values['mix_method'] in ('Average','Concatenate'):
                source=first[0][0]
                if isinstance(source,torch.Tensor) and source.ndim==3:
                    projected=0
                    for row in second:
                        target=row[0]
                        if isinstance(target,torch.Tensor) and target.ndim==3:
                            sequence=target.shape[1]+source.shape[1] if values['mix_method']=='Concatenate' else target.shape[1]
                            projected+=max(source.shape[0],target.shape[0])*sequence*max(source.shape[2],target.shape[2])*max(4,source.element_size(),target.element_size())
                            if values['mix_method']=='Average' and isinstance(first[0][1],dict) and isinstance(row[1],dict):
                                pooled_from=first[0][1].get('pooled_output')
                                pooled_to=row[1].get('pooled_output',pooled_from)
                                if isinstance(pooled_from,torch.Tensor):
                                    if isinstance(pooled_to,torch.Tensor):
                                        try:pooled_shape=torch.broadcast_shapes(pooled_from.shape,pooled_to.shape)
                                        except RuntimeError:pooled_shape=pooled_from.shape
                                        projected+=math.prod(pooled_shape)*max(4,pooled_from.element_size(),pooled_to.element_size())
                                    else:projected+=_bytes(pooled_from)
    elif node_id=='CR Interpolate Latents':
        weight=values['weight']
        if isinstance(weight,(int,float)) and abs(weight)>100:raise ValueError('Latent interpolation weight exceeds bound')
        first=values['latent1'];second=values['latent2']
        if isinstance(first,dict) and isinstance(second,dict) and isinstance(first.get('samples'),torch.Tensor) and isinstance(second.get('samples'),torch.Tensor):
            a=first['samples'];b=second['samples']
            try:shape=torch.broadcast_shapes(a.shape,b.shape)
            except RuntimeError:shape=a.shape
            projected=math.prod(shape)*max(4,a.element_size(),b.element_size())
            projected+=sum(_bytes(value) for key,value in first.items() if key!='samples' and isinstance(value,torch.Tensor))
    if projected>64*1024*1024 or input_bytes+6*projected>256*1024*1024:
        raise ValueError('Tensor projected output/temporary workload exceeds bound')

class CR_LatentBatchSize(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Latent Batch Size',display_name='⚙️ CR Latent Batch Size',category='🧩 Comfyroll Studio/✨ Essential/📦 Core',is_output_node=False,inputs=[io.Latent.Input('latent'), io.Int.Input('batch_size', default=2, min=1, max=999, step=1)],outputs=[io.Latent.Output(display_name='LATENT',is_output_list=False)])

    @classmethod
    def execute(cls, latent, batch_size):
        _preflight('CR Latent Batch Size', {'latent': latent, 'batch_size': batch_size})
        samples = latent['samples']
        shape = samples.shape
        sample_list = [samples] + [torch.clone(samples) for _ in range(batch_size - 1)]
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Core-Nodes#cr-latent-batch-size'
        return _output(({'samples': torch.cat(sample_list)},))


class CR_ConditioningMixer(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Conditioning Mixer',display_name='⚙️ CR Conditioning Mixer',category='🧩 Comfyroll Studio/✨ Essential/📦 Core',is_output_node=False,inputs=[io.Conditioning.Input('conditioning_1'), io.Conditioning.Input('conditioning_2'), io.Combo.Input('mix_method', options=['Combine', 'Average', 'Concatenate']), io.Float.Input('average_strength', default=0.5, min=0.0, max=1.0, step=0.01)],outputs=[io.Conditioning.Output(display_name='CONDITIONING',is_output_list=False), io.String.Output(display_name='show_help',is_output_list=False)])

    @classmethod
    def execute(cls, mix_method, conditioning_1, conditioning_2, average_strength):
        _preflight('CR Conditioning Mixer', {'mix_method': mix_method, 'conditioning_1': conditioning_1, 'conditioning_2': conditioning_2, 'average_strength': average_strength})
        conditioning_from = conditioning_1
        conditioning_to = conditioning_2
        conditioning_to_strength = average_strength
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Core-Nodes#cr-conditioning-mixer'
        if mix_method == 'Combine':
            return _output((conditioning_1 + conditioning_2, show_help))
        if mix_method == 'Average':
            out = []
            if len(conditioning_from) > 1:
                print('Warning: ConditioningAverage conditioning_from contains more than 1 cond, only the first one will actually be applied to conditioning_to.')
            cond_from = conditioning_from[0][0]
            pooled_output_from = conditioning_from[0][1].get('pooled_output', None)
            for i in range(len(conditioning_to)):
                t1 = conditioning_to[i][0]
                pooled_output_to = conditioning_to[i][1].get('pooled_output', pooled_output_from)
                t0 = cond_from[:, :t1.shape[1]]
                if t0.shape[1] < t1.shape[1]:
                    t0 = torch.cat([t0] + [torch.zeros((1, t1.shape[1] - t0.shape[1], t1.shape[2]))], dim=1)
                tw = torch.mul(t1, conditioning_to_strength) + torch.mul(t0, 1.0 - conditioning_to_strength)
                t_to = conditioning_to[i][1].copy()
                if pooled_output_from is not None and pooled_output_to is not None:
                    t_to['pooled_output'] = torch.mul(pooled_output_to, conditioning_to_strength) + torch.mul(pooled_output_from, 1.0 - conditioning_to_strength)
                elif pooled_output_from is not None:
                    t_to['pooled_output'] = pooled_output_from
                n = [tw, t_to]
                out.append(n)
            return _output((out, show_help))
        if mix_method == 'Concatenate':
            out = []
            if len(conditioning_from) > 1:
                print('Warning: ConditioningConcat conditioning_from contains more than 1 cond, only the first one will actually be applied to conditioning_to.')
            cond_from = conditioning_from[0][0]
            for i in range(len(conditioning_to)):
                t1 = conditioning_to[i][0]
                tw = torch.cat((t1, cond_from), 1)
                n = [tw, conditioning_to[i][1].copy()]
                out.append(n)
            return _output((out, show_help))


class CR_DebatchFrames(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Debatch Frames',display_name='🛠️ CR Debatch Frames',category='🧩 Comfyroll Studio/🎥 Animation/🛠️ Utils',is_output_node=False,inputs=[io.Image.Input('frames')],outputs=[io.Image.Output(display_name='debatched_frames',is_output_list=True)])

    @classmethod
    def execute(cls, frames):
        _preflight('CR Debatch Frames', {'frames': frames})
        images = [frames[i:i + 1, ...] for i in range(frames.shape[0])]
        return _output((images,))


class CR_InterpolateLatents(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=('raw',)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Interpolate Latents',display_name='🔢 CR Interpolate Latents',category='🧩 Comfyroll Studio/🎥 Animation/🔢 Interpolate',is_output_node=False,inputs=[io.Latent.Input('latent1'), io.Latent.Input('latent2'), io.Float.Input('weight', default=0.5, min=0.0, max=1.0, step=0.01), io.Combo.Input('method', options=['lerp'])],outputs=[io.Latent.Output(display_name='LATENT',is_output_list=False), io.String.Output(display_name='show_help',is_output_list=False)])

    @classmethod
    def execute(cls, latent1, latent2, weight, method):
        _preflight('CR Interpolate Latents', {'latent1': latent1, 'latent2': latent2, 'weight': weight, 'method': method})
        a = latent1.copy()
        b = latent2.copy()
        c = {}
        if method == 'lerp':
            torch.lerp(a['samples'], b['samples'], weight, out=a['samples'])
        elif method == 'slerp':
            dot_products = torch.sum(latent1['samples'] * latent2['samples'], dim=(2, 3))
            dot_products = torch.clamp(dot_products, -1, 1)
            angles = torch.acos(dot_products)
            sin_angles = torch.sin(angles)
            weight1 = torch.sin((1 - weight) * angles) / sin_angles
            weight2 = torch.sin(weight * angles) / sin_angles
            weight1 = weight1.unsqueeze(-1).unsqueeze(-1)
            weight2 = weight2.unsqueeze(-1).unsqueeze(-1)
            interpolated_samples = weight1 * latent1['samples'] + weight2 * latent2['samples']
            a['samples'] = interpolated_samples
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Interpolation-Nodes#cr-interpolate-latents'
        return _output((a, show_help))


NODE_CLASS_MAPPINGS={
    'CR Latent Batch Size':CR_LatentBatchSize,
    'CR Conditioning Mixer':CR_ConditioningMixer,
    'CR Debatch Frames':CR_DebatchFrames,
    'CR Interpolate Latents':CR_InterpolateLatents,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Latent Batch Size': '⚙️ CR Latent Batch Size', 'CR Conditioning Mixer': '⚙️ CR Conditioning Mixer', 'CR Debatch Frames': '🛠️ CR Debatch Frames', 'CR Interpolate Latents': '🔢 CR Interpolate Latents'}
