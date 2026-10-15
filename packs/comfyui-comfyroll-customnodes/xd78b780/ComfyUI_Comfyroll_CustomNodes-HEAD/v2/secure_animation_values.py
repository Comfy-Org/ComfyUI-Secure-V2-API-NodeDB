"""Pinned bounded animation values/opaque image routing, no model or filesystem authority."""
from comfy_api.latest import io
from .secure_schedules import _guard, _output

def _preflight(node_id,values):
    _guard(values)
    strings=0;items=0
    def visit(value):
        nonlocal strings,items
        if isinstance(value,str):strings+=len(value.encode('utf-8'))
        elif isinstance(value,(list,tuple)):
            items+=len(value)
            if items>16384:raise ValueError('Animation item workload exceeds bound')
            for child in value:visit(child)
    for value in values.values():visit(value)
    loops=values.get('loops',1)
    if isinstance(loops,int):
        if abs(loops)>1000:raise ValueError('Animation loops exceed bound')
        if max(0,loops)*max(1,items+5)>16384:
            raise ValueError('Animation projected item workload exceeds bound')
    if node_id in ('CR Simple Prompt List Keyframes','CR Prompt List Keyframes'):
        if not isinstance(loops,int):return
        intervals=[values.get('keyframe_interval',0)]
        if node_id=='CR Prompt List Keyframes':
            rows=values['prompt_list']
            intervals.extend(row[4] for row in rows if isinstance(row,(list,tuple)) and len(row)>=5)
        digits=max((len(str(v))+len(str(max(1,items)*max(1,loops)))+2 for v in intervals if isinstance(v,(int,float))),default=1)
        projected=max(0,loops)*(strings+max(1,items)*(digits+16))
        if projected>262144:raise ValueError('Animation projected keyframe text exceeds bound')

class CR_SimplePromptList(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Prompt List',display_name='CR Simple Prompt List (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',is_output_node=False,inputs=[io.String.Input('prompt_1', multiline=True, default='prompt'), io.String.Input('prompt_2', multiline=True, default='prompt'), io.String.Input('prompt_3', multiline=True, default='prompt'), io.String.Input('prompt_4', multiline=True, default='prompt'), io.String.Input('prompt_5', multiline=True, default='prompt'), io.Custom('SIMPLE_PROMPT_LIST').Input('simple_prompt_list', optional=True)],outputs=[io.Custom('SIMPLE_PROMPT_LIST').Output(display_name='SIMPLE_PROMPT_LIST'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, prompt_1, prompt_2, prompt_3, prompt_4, prompt_5, simple_prompt_list=None):
        _preflight('CR Simple Prompt List', {'prompt_1': prompt_1, 'prompt_2': prompt_2, 'prompt_3': prompt_3, 'prompt_4': prompt_4, 'prompt_5': prompt_5, 'simple_prompt_list': simple_prompt_list})
        prompts = list()
        if simple_prompt_list is not None:
            prompts.extend([l for l in simple_prompt_list])
        if prompt_1 != '':
            (prompts.extend([prompt_1]),)
        if prompt_2 != '':
            (prompts.extend([prompt_2]),)
        if prompt_3 != '':
            (prompts.extend([prompt_3]),)
        if prompt_4 != '':
            (prompts.extend([prompt_4]),)
        if prompt_5 != '':
            (prompts.extend([prompt_5]),)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Prompt-Nodes#cr-simple-prompt-list'
        return _output((prompts, show_help))


class CR_SimplePromptListKeyframes(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Prompt List Keyframes',display_name='CR Simple Prompt List Keyframes (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',is_output_node=False,inputs=[io.Custom('SIMPLE_PROMPT_LIST').Input('simple_prompt_list'), io.Int.Input('keyframe_interval', default=30, min=0, max=999, step=1), io.Int.Input('loops', default=1, min=1, max=1000), io.Combo.Input('transition_type', options=['Default']), io.Combo.Input('transition_speed', options=['Default']), io.Combo.Input('transition_profile', options=['Default']), io.Combo.Input('keyframe_format', options=['Deforum'])],outputs=[io.String.Output(display_name='keyframe_list'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, simple_prompt_list, keyframe_interval, loops, transition_type, transition_speed, transition_profile, keyframe_format):
        _preflight('CR Simple Prompt List Keyframes', {'simple_prompt_list': simple_prompt_list, 'keyframe_interval': keyframe_interval, 'loops': loops, 'transition_type': transition_type, 'transition_speed': transition_speed, 'transition_profile': transition_profile, 'keyframe_format': keyframe_format})
        keyframe_format = 'Deforum'
        keyframe_list = list()
        i = 0
        for j in range(1, loops + 1):
            for index, prompt in enumerate(simple_prompt_list):
                if i == 0:
                    keyframe_list.extend(['"0": "' + prompt + '",\n'])
                    i += keyframe_interval
                    continue
                new_keyframe = '"' + str(i) + '": "' + prompt + '",\n'
                keyframe_list.extend([new_keyframe])
                i += keyframe_interval
        keyframes_out = ' '.join(keyframe_list)[:-2]
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Prompt-Nodes#cr-simple-prompt-list-keyframes'
        return _output((keyframes_out, show_help))


class CR_PromptListKeyframes(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Prompt List Keyframes',display_name='CR Prompt List Keyframes (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',is_output_node=False,inputs=[io.Custom('PROMPT_LIST').Input('prompt_list'), io.Combo.Input('keyframe_format', options=['Deforum'])],outputs=[io.String.Output(display_name='keyframe_list'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, prompt_list, keyframe_format):
        _preflight('CR Prompt List Keyframes', {'prompt_list': prompt_list, 'keyframe_format': keyframe_format})
        keyframe_format = 'Deforum'
        keyframe_list = list()
        i = 0
        for index, prompt_tuple in enumerate(prompt_list):
            prompt, transition_type, transition_speed, transition_profile, keyframe_interval, loops = prompt_tuple
            if i == 0:
                keyframe_list.extend(['"0": "' + prompt + '",\n'])
                i += keyframe_interval
                continue
            new_keyframe = '"' + str(i) + '": "' + prompt + '",\n'
            keyframe_list.extend([new_keyframe])
            i += keyframe_interval
        keyframes_out = ''.join(keyframe_list)[:-2]
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Prompt-Nodes#cr-prompt-list-keyframes'
        return _output((keyframes_out, show_help))


class CR_KeyframeList(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Keyframe List',display_name='📝 CR Keyframe List',category='🧩 Comfyroll Studio/🎥 Animation/📝 Prompt',is_output_node=False,inputs=[io.String.Input('keyframe_list', multiline=True, default='keyframes'), io.Combo.Input('keyframe_format', options=['Deforum', 'CR'])],outputs=[io.String.Output(display_name='keyframe_list'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, keyframe_list, keyframe_format):
        _preflight('CR Keyframe List', {'keyframe_list': keyframe_list, 'keyframe_format': keyframe_format})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Prompt-Nodes#cr-keyframe-list'
        return _output((keyframe_list, show_help))


class CR_CycleText(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Cycle Text',display_name='CR Cycle Text (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',is_output_node=False,inputs=[io.Combo.Input('mode', options=['Sequential']), io.Custom('TEXT_LIST').Input('text_list'), io.Int.Input('frame_interval', default=30, min=0, max=999, step=1), io.Int.Input('loops', default=1, min=1, max=1000), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0)],outputs=[io.String.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, text_list, frame_interval, loops, current_frame):
        _preflight('CR Cycle Text', {'mode': mode, 'text_list': text_list, 'frame_interval': frame_interval, 'loops': loops, 'current_frame': current_frame})
        text_params = list()
        if text_list:
            for _ in range(loops):
                text_params.extend(text_list)
        if mode == 'Sequential':
            current_text_index = current_frame // frame_interval % len(text_params)
            current_text_params = text_params[current_text_index]
            print(f'[Debug] CR Cycle Text:{current_text_params}')
            text_alias, current_text_item = current_text_params
            show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Cycler-Nodes#cr-cycle-text'
            return _output((current_text_item, show_help))


class CR_CycleTextSimple(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Cycle Text Simple',display_name='CR Cycle Text Simple (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',is_output_node=False,inputs=[io.Combo.Input('mode', options=['Sequential']), io.Int.Input('frame_interval', default=30, min=0, max=999, step=1), io.Int.Input('loops', default=1, min=1, max=1000), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.String.Input('text_1', multiline=False, default='', optional=True), io.String.Input('text_2', multiline=False, default='', optional=True), io.String.Input('text_3', multiline=False, default='', optional=True), io.String.Input('text_4', multiline=False, default='', optional=True), io.String.Input('text_5', multiline=False, default='', optional=True), io.Custom('TEXT_LIST_SIMPLE').Input('text_list_simple', optional=True)],outputs=[io.String.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, frame_interval, loops, current_frame, text_1, text_2, text_3, text_4, text_5, text_list_simple=None):
        _preflight('CR Cycle Text Simple', {'mode': mode, 'frame_interval': frame_interval, 'loops': loops, 'current_frame': current_frame, 'text_1': text_1, 'text_2': text_2, 'text_3': text_3, 'text_4': text_4, 'text_5': text_5, 'text_list_simple': text_list_simple})
        text_params = list()
        text_list = list()
        if text_1 != '':
            text_list.append(text_1)
        if text_2 != '':
            text_list.append(text_2)
        if text_3 != '':
            text_list.append(text_3)
        if text_4 != '':
            text_list.append(text_4)
        if text_5 != '':
            text_list.append(text_5)
        for _ in range(loops):
            if text_list_simple:
                text_params.extend(text_list_simple)
            text_params.extend(text_list)
        if mode == 'Sequential':
            current_text_index = current_frame // frame_interval % len(text_params)
            current_text_item = text_params[current_text_index]
            show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Cycler-Nodes#cr-cycle-text-simple'
            return _output((current_text_item, show_help))


class CR_CycleImages(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Cycle Images',display_name='CR Cycle Images (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',is_output_node=False,inputs=[io.Combo.Input('mode', options=['Sequential']), io.Custom('IMAGE_LIST').Input('image_list'), io.Int.Input('frame_interval', default=30, min=0, max=999, step=1), io.Int.Input('loops', default=1, min=1, max=1000), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, image_list, frame_interval, loops, current_frame):
        _preflight('CR Cycle Images', {'mode': mode, 'image_list': image_list, 'frame_interval': frame_interval, 'loops': loops, 'current_frame': current_frame})
        image_params = list()
        if image_list:
            for _ in range(loops):
                image_params.extend(image_list)
        if mode == 'Sequential':
            current_image_index = current_frame // frame_interval % len(image_params)
            print(f'[Debug] CR Cycle Image:{current_image_index}')
            current_image_params = image_params[current_image_index]
            image_alias, current_image_item = current_image_params
            show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Cycler-Nodes#cr-cycle-images'
            return _output((current_image_item, show_help))


class CR_CycleImagesSimple(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Cycle Images Simple',display_name='CR Cycle Images Simple (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',is_output_node=False,inputs=[io.Combo.Input('mode', options=['Sequential']), io.Int.Input('frame_interval', default=30, min=0, max=999, step=1), io.Int.Input('loops', default=1, min=1, max=1000), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.Image.Input('image_1', optional=True), io.Image.Input('image_2', optional=True), io.Image.Input('image_3', optional=True), io.Image.Input('image_4', optional=True), io.Image.Input('image_5', optional=True), io.Custom('IMAGE_LIST_SIMPLE').Input('image_list_simple', optional=True)],outputs=[io.Image.Output(display_name='IMAGE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, frame_interval, loops, current_frame, image_1=None, image_2=None, image_3=None, image_4=None, image_5=None, image_list_simple=None):
        _preflight('CR Cycle Images Simple', {'mode': mode, 'frame_interval': frame_interval, 'loops': loops, 'current_frame': current_frame, 'image_1': image_1, 'image_2': image_2, 'image_3': image_3, 'image_4': image_4, 'image_5': image_5, 'image_list_simple': image_list_simple})
        image_params = list()
        image_list = list()
        if image_1 != None:
            (image_list.append(image_1),)
        if image_2 != None:
            (image_list.append(image_2),)
        if image_3 != None:
            (image_list.append(image_3),)
        if image_4 != None:
            (image_list.append(image_4),)
        if image_5 != None:
            (image_list.append(image_5),)
        for _ in range(loops):
            if image_list_simple:
                image_params.extend(image_list_simple)
            image_params.extend(image_list)
        if mode == 'Sequential':
            current_image_index = current_frame // frame_interval % len(image_params)
            print(f'[Debug] CR Cycle Text:{current_image_index}')
            current_image_item = image_params[current_image_index]
            show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Cycler-Nodes#cr-cycle-images-simple'
            return _output((current_image_item, show_help))


class CR_ImageList(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image List',display_name='CR Image List (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',is_output_node=False,inputs=[io.Image.Input('image_1', optional=True), io.String.Input('alias1', multiline=False, default='', optional=True), io.Image.Input('image_2', optional=True), io.String.Input('alias2', multiline=False, default='', optional=True), io.Image.Input('image_3', optional=True), io.String.Input('alias3', multiline=False, default='', optional=True), io.Image.Input('image_4', optional=True), io.String.Input('alias4', multiline=False, default='', optional=True), io.Image.Input('image_5', optional=True), io.String.Input('alias5', multiline=False, default='', optional=True), io.Custom('image_LIST').Input('image_list', optional=True)],outputs=[io.Custom('IMAGE_LIST').Output(display_name='IMAGE_LIST'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image_1=None, alias1=None, image_2=None, alias2=None, image_3=None, alias3=None, image_4=None, alias4=None, image_5=None, alias5=None, image_list=None):
        _preflight('CR Image List', {'image_1': image_1, 'alias1': alias1, 'image_2': image_2, 'alias2': alias2, 'image_3': image_3, 'alias3': alias3, 'image_4': image_4, 'alias4': alias4, 'image_5': image_5, 'alias5': alias5, 'image_list': image_list})
        images = list()
        if image_list is not None:
            image_tup = [(alias1, image_1)]
            images.extend([l for l in image_list])
        if image_1 != None:
            (images.extend([(alias1, image_1)]),)
        if image_2 != None:
            (images.extend([(alias2, image_2)]),)
        if image_3 != None:
            (images.extend([(alias3, image_3)]),)
        if image_4 != None:
            (images.extend([(alias4, image_4)]),)
        if image_5 != None:
            (images.extend([(alias5, image_5)]),)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-image-list'
        return _output((images, show_help))


class CR_ImageListSimple(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Image List Simple',display_name='CR Image List Simple (Legacy)',category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy',is_output_node=False,inputs=[io.Image.Input('image_1', optional=True), io.Image.Input('image_2', optional=True), io.Image.Input('image_3', optional=True), io.Image.Input('image_4', optional=True), io.Image.Input('image_5', optional=True), io.Custom('IMAGE_LIST_SIMPLE').Input('image_list_simple', optional=True)],outputs=[io.Custom('IMAGE_LIST_SIMPLE').Output(display_name='IMAGE_LIST_SIMPLE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, image_1=None, image_2=None, image_3=None, image_4=None, image_5=None, image_list_simple=None):
        _preflight('CR Image List Simple', {'image_1': image_1, 'image_2': image_2, 'image_3': image_3, 'image_4': image_4, 'image_5': image_5, 'image_list_simple': image_list_simple})
        images = list()
        if image_list_simple is not None:
            images.extend(image_list_simple)
        if image_1 != None:
            (images.append(image_1),)
        if image_2 != None:
            images.append(image_2)
        if image_3 != None:
            images.append(image_3)
        if image_4 != None:
            (images.append(image_4),)
        if image_5 != None:
            (images.append(image_5),)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-image-list-simple'
        return _output((images, show_help))


NODE_CLASS_MAPPINGS={
    'CR Simple Prompt List':CR_SimplePromptList,
    'CR Simple Prompt List Keyframes':CR_SimplePromptListKeyframes,
    'CR Prompt List Keyframes':CR_PromptListKeyframes,
    'CR Keyframe List':CR_KeyframeList,
    'CR Cycle Text':CR_CycleText,
    'CR Cycle Text Simple':CR_CycleTextSimple,
    'CR Cycle Images':CR_CycleImages,
    'CR Cycle Images Simple':CR_CycleImagesSimple,
    'CR Image List':CR_ImageList,
    'CR Image List Simple':CR_ImageListSimple,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Simple Prompt List': 'CR Simple Prompt List (Legacy)', 'CR Simple Prompt List Keyframes': 'CR Simple Prompt List Keyframes (Legacy)', 'CR Prompt List Keyframes': 'CR Prompt List Keyframes (Legacy)', 'CR Keyframe List': '📝 CR Keyframe List', 'CR Cycle Text': 'CR Cycle Text (Legacy)', 'CR Cycle Text Simple': 'CR Cycle Text Simple (Legacy)', 'CR Cycle Images': 'CR Cycle Images (Legacy)', 'CR Cycle Images Simple': 'CR Cycle Images Simple (Legacy)', 'CR Image List': 'CR Image List (Legacy)', 'CR Image List Simple': 'CR Image List Simple (Legacy)'}

