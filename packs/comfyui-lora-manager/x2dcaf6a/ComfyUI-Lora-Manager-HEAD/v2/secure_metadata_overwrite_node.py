"""Manual metadata overwrite parity; Model/Sampler identity bridge pending."""
from comfy_api.latest import io,sdk
from .secure_services.metadata_overwrite import collect_overwrites
class MetadataOverwrite(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='Metadata Overwrite (LoraManager)',category='Lora Manager/utils',
            description='Manually specify generation parameters to override automatically collected metadata. Only filled/connected inputs will take effect — empty defaults are ignored.',
            inputs=[io.String.Input('prompt',optional=True,default='',multiline=True,tooltip='Positive prompt. Only overwrites when non-empty.'),
                    io.String.Input('negative_prompt',optional=True,default='',multiline=True,tooltip='Negative prompt. Only overwrites when non-empty.'),
                    io.Int.Input('seed',optional=True,default=0,min=0,max=18446744073709551615,control_after_generate=False,tooltip='Seed value. Only overwrites when > 0.'),
                    io.Int.Input('steps',optional=True,default=0,min=0,max=10000,tooltip='Number of steps. Only overwrites when > 0.'),
                    io.Float.Input('cfg_scale',optional=True,default=0.0,min=0.0,max=100.0,tooltip='CFG scale. Only overwrites when > 0.'),
                    io.MultiType.Input('sampler',types=[io.String,io.Custom('SAMPLER')],optional=True,tooltip='Sampler name. Fill in the name manually or connect a SAMPLER output (e.g. KSamplerSelect) — the sampler name is then extracted automatically. Note: ddim is recorded as euler (ComfyUI internal representation). Only overwrites when non-empty.',extra_dict={'default': '', 'widgetType': 'STRING'}),
                    io.String.Input('scheduler',optional=True,default='',tooltip='Scheduler name. Only overwrites when non-empty.'),
                    io.MultiType.Input('model',types=[io.String,io.Model],optional=True,tooltip='The checkpoint or diffusion model (UNet) used for generation. Fill in the name manually or connect a MODEL output — the model name is then extracted automatically. Only overwrites when non-empty.',extra_dict={'default': '', 'widgetType': 'STRING'}),
                    io.String.Input('loras',optional=True,default='',multiline=True,tooltip='LoRA syntax, e.g. <lora:name:strength> or <lora:name:model_strength:clip_strength>, separated by spaces. Only overwrites when non-empty.'),
                    io.String.Input('size',optional=True,default='',tooltip='Image size in WIDTHxHEIGHT format (e.g. 512x768). Only overwrites when non-empty.'),
                    io.Int.Input('clip_skip',optional=True,default=-25,min=-25,max=24,tooltip='Clip skip (ComfyUI: -24..-1, A1111: 1+). Default -25 means not set — any other value overwrites.'),
                    io.String.Input('additional_data',optional=True,default='',multiline=True,tooltip='Additional data to embed in the image metadata. Inserted between Clip skip and Model hash in the A1111-compatible parameters string. Example: "Copyright": "Some license info"')],outputs=[io.Custom('METADATA').Output(display_name='metadata')],is_output_node=True)
    @classmethod
    def execute(cls,**kwargs):
        # Never inspect a patcher or sampler function behind its public handle.
        # The native wired branch needs a sanctioned source-name projection.
        for key in ('model','sampler'):
            if isinstance(kwargs.get(key),sdk.Ref):
                raise NotImplementedError('Public wired '+key+' identity projection is unavailable for Metadata Overwrite')
        return io.NodeOutput(collect_overwrites(kwargs))
