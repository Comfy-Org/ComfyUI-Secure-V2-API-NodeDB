"""Public-ref pipe routing and bounded pack-side interpolation. No durable state."""
from comfy_api.latest import io
from .secure_schedules import _guard, _output

class CR_DataBusIn(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Data Bus In',display_name='🚌 CR Data Bus In',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe/🚌 Bus',is_output_node=False,inputs=[io.AnyType.Input('pipe', optional=True), io.AnyType.Input('any1', optional=True), io.AnyType.Input('any2', optional=True), io.AnyType.Input('any3', optional=True), io.AnyType.Input('any4', optional=True)],outputs=[io.Custom('PIPE_LINE').Output(display_name='pipe'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, any1=None, any2=None, any3=None, any4=None, pipe=None):
        _guard({'any1': any1, 'any2': any2, 'any3': any3, 'any4': any4, 'pipe': pipe})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-data-bus-in'
        new_any1, new_any2, new_any3, new_any4 = (None, None, None, None)
        if pipe is not None:
            new_any1, new_any2, new_any3, new_any4 = pipe
        new_any1 = any1 if any1 is not None else new_any1
        new_any2 = any2 if any2 is not None else new_any2
        new_any3 = any3 if any3 is not None else new_any3
        new_any4 = any4 if any4 is not None else new_any4
        new_pipe = (new_any1, new_any2, new_any3, new_any4)
        return _output((new_pipe, show_help))


class CR_DataBusOut(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Data Bus Out',display_name='🚌 CR Data Bus Out',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe/🚌 Bus',is_output_node=False,inputs=[io.Custom('PIPE_LINE').Input('pipe')],outputs=[io.Custom('PIPE_LINE').Output(display_name='pipe'), io.AnyType.Output(display_name='any1'), io.AnyType.Output(display_name='any2'), io.AnyType.Output(display_name='any3'), io.AnyType.Output(display_name='any4'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, any1=None, any2=None, any3=None, any4=None, pipe=None):
        _guard({'any1': any1, 'any2': any2, 'any3': any3, 'any4': any4, 'pipe': pipe})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-data-bus-out'
        new_any1, new_any2, new_any3, new_any4 = pipe
        return _output((pipe, new_any1, new_any2, new_any3, new_any4, show_help))


class CR_8ChannelIn(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR 8 Channel In',display_name='🚌 CR 8 Channel In',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe/🚌 Bus',is_output_node=False,inputs=[io.AnyType.Input('pipe', optional=True), io.AnyType.Input('ch1', optional=True), io.AnyType.Input('ch2', optional=True), io.AnyType.Input('ch3', optional=True), io.AnyType.Input('ch4', optional=True), io.AnyType.Input('ch5', optional=True), io.AnyType.Input('ch6', optional=True), io.AnyType.Input('ch7', optional=True), io.AnyType.Input('ch8', optional=True)],outputs=[io.Custom('PIPE_LINE').Output(display_name='pipe'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, ch1=None, ch2=None, ch3=None, ch4=None, ch5=None, ch6=None, ch7=None, ch8=None, pipe=None):
        _guard({'ch1': ch1, 'ch2': ch2, 'ch3': ch3, 'ch4': ch4, 'ch5': ch5, 'ch6': ch6, 'ch7': ch7, 'ch8': ch8, 'pipe': pipe})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-8-channel-in'
        new_ch1, new_ch2, new_ch3, new_ch4, new_ch5, new_ch6, new_ch7, new_ch8 = (None, None, None, None, None, None, None, None)
        if pipe is not None:
            new_ch1, new_ch2, new_ch3, new_ch4, new_ch5, new_ch6, new_ch7, new_ch8 = pipe
        new_ch1 = ch1 if ch1 is not None else new_ch1
        new_ch2 = ch2 if ch2 is not None else new_ch2
        new_ch3 = ch3 if ch3 is not None else new_ch3
        new_ch4 = ch4 if ch4 is not None else new_ch4
        new_ch5 = ch5 if ch5 is not None else new_ch5
        new_ch6 = ch6 if ch6 is not None else new_ch6
        new_ch7 = ch7 if ch7 is not None else new_ch7
        new_ch8 = ch8 if ch8 is not None else new_ch8
        new_pipe = (new_ch1, new_ch2, new_ch3, new_ch4, new_ch5, new_ch6, new_ch7, new_ch8)
        return _output((new_pipe, show_help))


class CR_8ChannelOut(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR 8 Channel Out',display_name='🚌 CR 8 Channel Out',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe/🚌 Bus',is_output_node=False,inputs=[io.Custom('PIPE_LINE').Input('pipe')],outputs=[io.Custom('PIPE_LINE').Output(display_name='pipe'), io.AnyType.Output(display_name='ch1'), io.AnyType.Output(display_name='ch2'), io.AnyType.Output(display_name='ch3'), io.AnyType.Output(display_name='ch4'), io.AnyType.Output(display_name='ch5'), io.AnyType.Output(display_name='ch6'), io.AnyType.Output(display_name='ch7'), io.AnyType.Output(display_name='ch8'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, ch1=None, ch2=None, ch3=None, ch4=None, ch5=None, ch6=None, ch7=None, ch8=None, pipe=None):
        _guard({'ch1': ch1, 'ch2': ch2, 'ch3': ch3, 'ch4': ch4, 'ch5': ch5, 'ch6': ch6, 'ch7': ch7, 'ch8': ch8, 'pipe': pipe})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-8-channel-out'
        new_ch1, new_ch2, new_ch3, new_ch4, new_ch5, new_ch6, new_ch7, new_ch8 = pipe
        return _output((pipe, new_ch1, new_ch2, new_ch3, new_ch4, new_ch5, new_ch6, new_ch7, new_ch8, show_help))


class CR_ModulePipeLoader(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Module Pipe Loader',display_name='✈️ CR Module Pipe Loader',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe/✈️ Module',is_output_node=False,inputs=[io.Model.Input('model', optional=True), io.Conditioning.Input('pos', optional=True), io.Conditioning.Input('neg', optional=True), io.Latent.Input('latent', optional=True), io.Vae.Input('vae', optional=True), io.Clip.Input('clip', optional=True), io.Custom('CONTROL_NET').Input('controlnet', optional=True), io.Image.Input('image', optional=True), io.Int.Input('seed', default=0, min=0, max=18446744073709551615, optional=True)],outputs=[io.Custom('PIPE_LINE').Output(display_name='pipe'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, model=0, pos=0, neg=0, latent=0, vae=0, clip=0, controlnet=0, image=0, seed=0):
        _guard({'model': model, 'pos': pos, 'neg': neg, 'latent': latent, 'vae': vae, 'clip': clip, 'controlnet': controlnet, 'image': image, 'seed': seed})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-module-pipe-loader'
        pipe_line = (model, pos, neg, latent, vae, clip, controlnet, image, seed)
        return _output((pipe_line, show_help))


class CR_ModuleInput(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Module Input',display_name='✈️ CR Module Input',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe/✈️ Module',is_output_node=False,inputs=[io.Custom('PIPE_LINE').Input('pipe')],outputs=[io.Custom('PIPE_LINE').Output(display_name='pipe'), io.Model.Output(display_name='model'), io.Conditioning.Output(display_name='pos'), io.Conditioning.Output(display_name='neg'), io.Latent.Output(display_name='latent'), io.Vae.Output(display_name='vae'), io.Clip.Output(display_name='clip'), io.Custom('CONTROL_NET').Output(display_name='controlnet'), io.Image.Output(display_name='image'), io.Int.Output(display_name='seed'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, pipe):
        _guard({'pipe': pipe})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-module-input'
        model, pos, neg, latent, vae, clip, controlnet, image, seed = pipe
        return _output((pipe, model, pos, neg, latent, vae, clip, controlnet, image, seed, show_help))


class CR_ModuleOutput(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Module Output',display_name='✈️ CR Module Output',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe/✈️ Module',is_output_node=False,inputs=[io.Custom('PIPE_LINE').Input('pipe'), io.Model.Input('model', optional=True), io.Conditioning.Input('pos', optional=True), io.Conditioning.Input('neg', optional=True), io.Latent.Input('latent', optional=True), io.Vae.Input('vae', optional=True), io.Clip.Input('clip', optional=True), io.Custom('CONTROL_NET').Input('controlnet', optional=True), io.Image.Input('image', optional=True), io.Int.Input('seed', default=0, min=0, max=18446744073709551615, optional=True)],outputs=[io.Custom('PIPE_LINE').Output(display_name='pipe'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, pipe, model=None, pos=None, neg=None, latent=None, vae=None, clip=None, controlnet=None, image=None, seed=None):
        _guard({'pipe': pipe, 'model': model, 'pos': pos, 'neg': neg, 'latent': latent, 'vae': vae, 'clip': clip, 'controlnet': controlnet, 'image': image, 'seed': seed})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-module-output'
        new_model, new_pos, new_neg, new_latent, new_vae, new_clip, new_controlnet, new_image, new_seed = pipe
        if model is not None:
            new_model = model
        if pos is not None:
            new_pos = pos
        if neg is not None:
            new_neg = neg
        if latent is not None:
            new_latent = latent
        if vae is not None:
            new_vae = vae
        if clip is not None:
            new_clip = clip
        if controlnet is not None:
            new_controlnet = controlnet
        if image is not None:
            new_image = image
        if seed is not None:
            new_seed = seed
        pipe = (new_model, new_pos, new_neg, new_latent, new_vae, new_clip, new_controlnet, new_image, new_seed)
        return _output((pipe, show_help))


class CR_ImagePipeIn(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image Pipe In',display_name='🛩 CR Image Pipe In',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe/🛩️ Image',is_output_node=False,inputs=[io.Image.Input('image', optional=True), io.Int.Input('width', default=512, min=64, max=2048, optional=True), io.Int.Input('height', default=512, min=64, max=2048, optional=True), io.Float.Input('upscale_factor', default=1, min=1, max=2000, optional=True)],outputs=[io.Custom('PIPE_LINE').Output(display_name='pipe'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image=0, width=0, height=0, upscale_factor=0):
        _guard({'image': image, 'width': width, 'height': height, 'upscale_factor': upscale_factor})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-image-pipe-in'
        pipe_line = (image, width, height, upscale_factor)
        return _output((pipe_line, show_help))


class CR_ImagePipeEdit(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image Pipe Edit',display_name='🛩️ CR Image Pipe Edit',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe/🛩️ Image',is_output_node=False,inputs=[io.Custom('PIPE_LINE').Input('pipe'), io.Image.Input('image', optional=True), io.Int.Input('width', default=512, min=64, max=2048, force_input=True, optional=True), io.Int.Input('height', default=512, min=64, max=2048, force_input=True, optional=True), io.Float.Input('upscale_factor', default=1, min=1, max=2000, force_input=True, optional=True)],outputs=[io.Custom('PIPE_LINE').Output(display_name='pipe'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, pipe, image=None, width=None, height=None, upscale_factor=None):
        _guard({'pipe': pipe, 'image': image, 'width': width, 'height': height, 'upscale_factor': upscale_factor})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-image-pipe-edit'
        new_image, new_width, new_height, new_upscale_factor = pipe
        if image is not None:
            new_image = image
        if width is not None:
            new_width = width
        if height is not None:
            new_height = height
        if upscale_factor is not None:
            new_upscale_factor = upscale_factor
        pipe = (new_image, new_width, new_height, new_upscale_factor)
        return _output((pipe, show_help))


class CR_ImagePipeOut(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image Pipe Out',display_name='🛩️ CR Image Pipe Out',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe/🛩️ Image',is_output_node=False,inputs=[io.Custom('PIPE_LINE').Input('pipe')],outputs=[io.Custom('PIPE_LINE').Output(display_name='pipe'), io.Image.Output(display_name='image'), io.Int.Output(display_name='width'), io.Int.Output(display_name='height'), io.Float.Output(display_name='upscale_factor'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, pipe):
        _guard({'pipe': pipe})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-image-pipe-out'
        image, width, height, upscale_factor = pipe
        return _output((pipe, image, width, height, upscale_factor, show_help))


class CR_InputSwitchPipe(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Pipe Switch',display_name='🔀️ CR Pipe Switch',category='🧩 Comfyroll Studio/✨ Essential/🎷 Pipe',is_output_node=True,inputs=[io.Int.Input('Input', default=1, min=1, max=2), io.Custom('PIPE_LINE').Input('pipe1'), io.Custom('PIPE_LINE').Input('pipe2')],outputs=[io.Custom('PIPE_LINE').Output(display_name='PIPE_LINE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, pipe1, pipe2):
        _guard({'Input': Input, 'pipe1': pipe1, 'pipe2': pipe2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Pipe-Nodes#cr-pipe-switch'
        if Input == 1:
            return _output((pipe1, show_help))
        else:
            return _output((pipe2, show_help))


class CR_GradientInteger(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Gradient Integer',display_name='🔢 CR Gradient Integer',category='🧩 Comfyroll Studio/🎥 Animation/🔢 Interpolate',is_output_node=False,inputs=[io.Int.Input('start_value', default=1.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('end_value', default=1.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('start_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('frame_duration', default=1.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.Combo.Input('gradient_profile', options=['Lerp'])],outputs=[io.Int.Output(display_name='INT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, start_value, end_value, start_frame, frame_duration, current_frame, gradient_profile):
        _guard({'start_value': start_value, 'end_value': end_value, 'start_frame': start_frame, 'frame_duration': frame_duration, 'current_frame': current_frame, 'gradient_profile': gradient_profile})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Interpolation-Nodes#cr-gradient-integer'
        if current_frame < start_frame:
            return _output((start_value, show_help))
        if current_frame > start_frame + frame_duration:
            return _output((end_value, show_help))
        step = (end_value - start_value) / frame_duration
        current_step = current_frame - start_frame
        int_out = start_value + int(current_step * step)
        return _output((int_out, show_help))


class CR_GradientFloat(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Gradient Float',display_name='🔢 CR Gradient Float',category='🧩 Comfyroll Studio/🎥 Animation/🔢 Interpolate',is_output_node=False,inputs=[io.Float.Input('start_value', default=1.0, min=0.0, max=9999.0, step=0.01), io.Float.Input('end_value', default=1.0, min=0.0, max=9999.0, step=0.01), io.Int.Input('start_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('frame_duration', default=1.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.Combo.Input('gradient_profile', options=['Lerp'])],outputs=[io.Float.Output(display_name='FLOAT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, start_value, end_value, start_frame, frame_duration, current_frame, gradient_profile):
        _guard({'start_value': start_value, 'end_value': end_value, 'start_frame': start_frame, 'frame_duration': frame_duration, 'current_frame': current_frame, 'gradient_profile': gradient_profile})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Interpolation-Nodes#cr-gradient-float'
        if current_frame < start_frame:
            return _output((start_value, show_help))
        if current_frame > start_frame + frame_duration:
            return _output((end_value, show_help))
        step = (end_value - start_value) / frame_duration
        current_step = current_frame - start_frame
        float_out = start_value + current_step * step
        return _output((float_out, show_help))


class CR_IncrementFloat(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Increment Float',display_name='🔢 CR Increment Float',category='🧩 Comfyroll Studio/🎥 Animation/🔢 Interpolate',is_output_node=True,inputs=[io.Float.Input('start_value', default=1.0, min=0.0, max=9999.0, step=0.001), io.Float.Input('step', default=0.1, min=-9999.0, max=9999.0, step=0.001), io.Int.Input('start_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('frame_duration', default=1.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0)],outputs=[io.Float.Output(display_name='FLOAT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, start_value, step, start_frame, frame_duration, current_frame):
        _guard({'start_value': start_value, 'step': step, 'start_frame': start_frame, 'frame_duration': frame_duration, 'current_frame': current_frame})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Interpolation-Nodes#cr-increment-float'
        if current_frame < start_frame:
            return _output((start_value, show_help))
        current_value = start_value + (current_frame - start_frame) * step
        if current_frame <= start_frame + frame_duration:
            current_value += step
            return _output((current_value, show_help))
        return _output((current_value, show_help))


class CR_IncrementInteger(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Increment Integer',display_name='🔢 CR Increment Integer',category='🧩 Comfyroll Studio/🎥 Animation/🔢 Interpolate',is_output_node=True,inputs=[io.Int.Input('start_value', default=1.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('step', default=1.0, min=-9999.0, max=9999.0, step=1.0), io.Int.Input('start_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('frame_duration', default=1.0, min=0.0, max=9999.0, step=1.0), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0)],outputs=[io.Int.Output(display_name='INT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, start_value, step, start_frame, frame_duration, current_frame):
        _guard({'start_value': start_value, 'step': step, 'start_frame': start_frame, 'frame_duration': frame_duration, 'current_frame': current_frame})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Interpolation-Nodes#cr-increment-integer'
        if current_frame < start_frame:
            return _output((start_value, show_help))
        current_value = start_value + (current_frame - start_frame) * step
        if current_frame <= start_frame + frame_duration:
            current_value += step
            return _output((current_value, show_help))
        return _output((current_value, show_help))


NODE_CLASS_MAPPINGS={
    'CR Data Bus In':CR_DataBusIn,
    'CR Data Bus Out':CR_DataBusOut,
    'CR 8 Channel In':CR_8ChannelIn,
    'CR 8 Channel Out':CR_8ChannelOut,
    'CR Module Pipe Loader':CR_ModulePipeLoader,
    'CR Module Input':CR_ModuleInput,
    'CR Module Output':CR_ModuleOutput,
    'CR Image Pipe In':CR_ImagePipeIn,
    'CR Image Pipe Edit':CR_ImagePipeEdit,
    'CR Image Pipe Out':CR_ImagePipeOut,
    'CR Pipe Switch':CR_InputSwitchPipe,
    'CR Gradient Integer':CR_GradientInteger,
    'CR Gradient Float':CR_GradientFloat,
    'CR Increment Float':CR_IncrementFloat,
    'CR Increment Integer':CR_IncrementInteger,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Data Bus In': '🚌 CR Data Bus In', 'CR Data Bus Out': '🚌 CR Data Bus Out', 'CR 8 Channel In': '🚌 CR 8 Channel In', 'CR 8 Channel Out': '🚌 CR 8 Channel Out', 'CR Module Pipe Loader': '✈️ CR Module Pipe Loader', 'CR Module Input': '✈️ CR Module Input', 'CR Module Output': '✈️ CR Module Output', 'CR Image Pipe In': '🛩 CR Image Pipe In', 'CR Image Pipe Edit': '🛩️ CR Image Pipe Edit', 'CR Image Pipe Out': '🛩️ CR Image Pipe Out', 'CR Pipe Switch': '🔀️ CR Pipe Switch', 'CR Gradient Integer': '🔢 CR Gradient Integer', 'CR Gradient Float': '🔢 CR Gradient Float', 'CR Increment Float': '🔢 CR Increment Float', 'CR Increment Integer': '🔢 CR Increment Integer'}
