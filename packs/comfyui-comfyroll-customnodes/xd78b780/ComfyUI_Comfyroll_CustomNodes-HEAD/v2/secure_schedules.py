"""Bounded workflow-owned schedules/text lists; native pinned parsing math stays pack-side."""
import math
from comfy_api.latest import io

def _guard(values):
    totals={'items':0,'bytes':0}
    def visit(value,depth=0):
        if depth>8:raise ValueError('Schedule data nesting exceeds bound')
        totals['items']+=1
        if totals['items']>16384:raise ValueError('Schedule item workload exceeds bound')
        if isinstance(value,str):
            totals['bytes']+=len(value.encode('utf-8'))
            if totals['bytes']>262144 or value.count('\n')>4096:raise ValueError('Schedule text workload exceeds bound')
        elif type(value) is int and value.bit_length()>4096:raise ValueError('Schedule integer exceeds bound')
        elif isinstance(value,float) and not math.isfinite(value):raise ValueError('Schedule scalar must be finite')
        elif isinstance(value,(list,tuple)):
            for child in value:visit(child,depth+1)
    for value in values.values():visit(value)

def _output(value):
    if isinstance(value,tuple):
        _guard(dict(enumerate(value)))
        if not value:return ()
        return io.NodeOutput(*value)
    return value

def keyframe_scheduler(schedule, schedule_alias, current_frame):
    schedule_lines = list()
    previous_params = ''
    for item in schedule:
        alias = item[0]
        if alias == schedule_alias:
            schedule_lines.extend([item])
    for i, item in enumerate(schedule_lines):
        alias, line = item
        if not line.strip():
            print(f'[Warning] Skipped blank line at line {i}')
            continue
        frame_str, params = line.split(',', 1)
        frame = int(frame_str)
        params = params.lstrip()
        if frame < current_frame:
            previous_params = params
            continue
        if frame == current_frame:
            previous_params = params
        else:
            params = previous_params
        return params
    return previous_params

def prompt_scheduler(schedule, schedule_alias, current_frame):
    schedule_lines = list()
    previous_prompt = ''
    previous_keyframe = 0
    for item in schedule:
        alias = item[0]
        if alias == schedule_alias:
            schedule_lines.extend([item])
    for i, item in enumerate(schedule_lines):
        alias, line = item
        frame_str, prompt = line.split(',', 1)
        frame_str = frame_str.strip('"')
        frame = int(frame_str)
        prompt = prompt.lstrip()
        prompt = prompt.replace('"', '')
        if frame < current_frame:
            previous_prompt = prompt
            previous_keyframe = frame
            continue
        if frame == current_frame:
            next_prompt = prompt
            next_keyframe = frame
            previous_prompt = prompt
            previous_keyframe = frame
        else:
            next_prompt = prompt
            next_keyframe = frame
            prompt = previous_prompt
        return (prompt, next_prompt, previous_keyframe, next_keyframe)
    return (previous_prompt, previous_prompt, previous_keyframe, previous_keyframe)

class CR_SimpleSchedule(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Schedule', display_name='📋 CR Simple Schedule', category='🧩 Comfyroll Studio/🎥 Animation/📋 Schedule', is_output_node=False, is_input_list=False, inputs=[io.String.Input('schedule', multiline=True, default='frame_number, item_alias, [attr_value1, attr_value2]'), io.Combo.Input('schedule_type', options=['Value', 'Text', 'Prompt', 'Prompt Weight', 'Model', 'LoRA', 'ControlNet', 'Style', 'Upscale', 'Camera', 'Job']), io.String.Input('schedule_alias', default='', multiline=False), io.Combo.Input('schedule_format', options=['CR', 'Deforum'])], outputs=[io.Custom('SCHEDULE').Output(display_name='SCHEDULE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, schedule, schedule_type, schedule_alias, schedule_format):
        _guard({'schedule': schedule, 'schedule_type': schedule_type, 'schedule_alias': schedule_alias, 'schedule_format': schedule_format})
        schedule_lines = list()
        if schedule != '' and schedule_alias != '':
            lines = schedule.split('\n')
            for line in lines:
                if not line.strip():
                    print(f'[Warning] CR Simple Schedule. Skipped blank line: {line}')
                    continue
                schedule_lines.extend([(schedule_alias, line)])
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Schedule-Nodes#cr-simple-schedule'
        return _output((schedule_lines, show_help))


class CR_CombineSchedules(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Combine Schedules', display_name='📋 CR Combine Schedules', category='🧩 Comfyroll Studio/🎥 Animation/📋 Schedule', is_output_node=False, is_input_list=False, inputs=[io.Custom('SCHEDULE').Input('schedule_1', optional=True), io.Custom('SCHEDULE').Input('schedule_2', optional=True), io.Custom('SCHEDULE').Input('schedule_3', optional=True), io.Custom('SCHEDULE').Input('schedule_4', optional=True)], outputs=[io.Custom('SCHEDULE').Output(display_name='SCHEDULE'), io.String.Output(display_name='show_text')])

    @classmethod
    def execute(cls, schedule_1=None, schedule_2=None, schedule_3=None, schedule_4=None):
        _guard({'schedule_1': schedule_1, 'schedule_2': schedule_2, 'schedule_3': schedule_3, 'schedule_4': schedule_4})
        schedules = list()
        schedule_text = list()
        if schedule_1 is not None:
            (schedules.extend([l for l in schedule_1]),)
            (schedule_text.extend(schedule_1),)
        if schedule_2 is not None:
            (schedules.extend([l for l in schedule_2]),)
            (schedule_text.extend(schedule_2),)
        if schedule_3 is not None:
            (schedules.extend([l for l in schedule_3]),)
            (schedule_text.extend(schedule_3),)
        if schedule_4 is not None:
            (schedules.extend([l for l in schedule_4]),)
            (schedule_text.extend(schedule_4),)
        print(f'[Debug] CR Combine Schedules: {schedules}')
        show_text = ''.join(str(schedule_text))
        return _output((schedules, show_text))


class CR_CentralSchedule(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Central Schedule', display_name='📋 CR Central Schedule', category='🧩 Comfyroll Studio/🎥 Animation/📋 Schedule', is_output_node=False, is_input_list=False, inputs=[io.String.Input('schedule_1', multiline=True, default='schedule'), io.Combo.Input('schedule_type1', options=['Value', 'Text', 'Prompt', 'Prompt Weight', 'Model', 'LoRA', 'ControlNet', 'Style', 'Upscale', 'Camera', 'Job']), io.String.Input('schedule_alias1', multiline=False, default=''), io.String.Input('schedule_2', multiline=True, default='schedule'), io.Combo.Input('schedule_type2', options=['Value', 'Text', 'Prompt', 'Prompt Weight', 'Model', 'LoRA', 'ControlNet', 'Style', 'Upscale', 'Camera', 'Job']), io.String.Input('schedule_alias2', multiline=False, default=''), io.String.Input('schedule_3', multiline=True, default='schedule'), io.Combo.Input('schedule_type3', options=['Value', 'Text', 'Prompt', 'Prompt Weight', 'Model', 'LoRA', 'ControlNet', 'Style', 'Upscale', 'Camera', 'Job']), io.String.Input('schedule_alias3', multiline=False, default=''), io.Combo.Input('schedule_format', options=['CR', 'Deforum']), io.Custom('SCHEDULE').Input('schedule', optional=True)], outputs=[io.Custom('SCHEDULE').Output(display_name='SCHEDULE'), io.String.Output(display_name='show_text')])

    @classmethod
    def execute(cls, schedule_1, schedule_type1, schedule_alias1, schedule_2, schedule_type2, schedule_alias2, schedule_3, schedule_type3, schedule_alias3, schedule_format, schedule=None):
        _guard({'schedule_1': schedule_1, 'schedule_type1': schedule_type1, 'schedule_alias1': schedule_alias1, 'schedule_2': schedule_2, 'schedule_type2': schedule_type2, 'schedule_alias2': schedule_alias2, 'schedule_3': schedule_3, 'schedule_type3': schedule_type3, 'schedule_alias3': schedule_alias3, 'schedule_format': schedule_format, 'schedule': schedule})
        schedules = list()
        schedule_text = list()
        if schedule is not None:
            schedules.extend([l for l in schedule])
            (schedule_text.extend([l for l in schedule]),)
        if schedule_1 != '' and schedule_alias1 != '':
            lines = schedule_1.split('\n')
            for line in lines:
                (schedules.extend([(schedule_alias1, line)]),)
            (schedule_text.extend([schedule_alias1 + ',' + schedule_1 + '\n']),)
        if schedule_2 != '' and schedule_alias2 != '':
            lines = schedule_2.split('\n')
            for line in lines:
                (schedules.extend([(schedule_alias2, line)]),)
            (schedule_text.extend([schedule_alias2 + ',' + schedule_2 + '\n']),)
        if schedule_3 != '' and schedule_alias3 != '':
            lines = schedule_3.split('\n')
            for line in lines:
                (schedules.extend([(schedule_alias3, line)]),)
            (schedule_text.extend([schedule_alias3 + ',' + schedule_3 + '\n']),)
        show_text = ''.join(schedule_text)
        return _output((schedules, show_text))


class Comfyroll_ScheduleInputSwitch(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Schedule Input Switch', display_name='📋 CR Schedule Input Switch', category='🧩 Comfyroll Studio/🎥 Animation/📋 Schedule', is_output_node=True, is_input_list=False, inputs=[io.Int.Input('Input', default=1, min=1, max=2), io.Custom('SCHEDULE').Input('schedule1'), io.Custom('SCHEDULE').Input('schedule2')], outputs=[io.Custom('SCHEDULE').Output(display_name='SCHEDULE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, Input, schedule1, schedule2):
        _guard({'Input': Input, 'schedule1': schedule1, 'schedule2': schedule2})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Schedule-Nodes#cr-schedule-input-switch'
        if Input == 1:
            return _output((schedule1, show_help))
        else:
            return _output((schedule2, show_help))


class CR_ValueScheduler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Value Scheduler', display_name='📑 CR Value Scheduler', category='🧩 Comfyroll Studio/🎥 Animation/📑 Schedulers', is_output_node=False, is_input_list=False, inputs=[io.Combo.Input('mode', options=['Default Value', 'Schedule']), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.String.Input('schedule_alias', default='', multiline=False), io.Float.Input('default_value', default=1.0, min=-9999.0, max=9999.0, step=0.01), io.Combo.Input('schedule_format', options=['CR', 'Deforum']), io.Custom('SCHEDULE').Input('schedule', optional=True)], outputs=[io.Int.Output(display_name='INT'), io.Float.Output(display_name='FLOAT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, current_frame, schedule_alias, default_value, schedule_format, schedule=None):
        _guard({'mode': mode, 'current_frame': current_frame, 'schedule_alias': schedule_alias, 'default_value': default_value, 'schedule_format': schedule_format, 'schedule': schedule})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Scheduler-Nodes#cr-value-scheduler'
        if mode == 'Default Value':
            print(f'[Info] CR Value Scheduler: Scheduler {schedule_alias} is disabled')
            int_out, float_out = (int(default_value), float(default_value))
            return _output((int_out, float_out, show_help))
        params = keyframe_scheduler(schedule, schedule_alias, current_frame)
        if params == '':
            if current_frame == 0:
                print(f'[Warning] CR Value Scheduler. No frame 0 found in schedule. Starting with default value at frame 0')
            int_out, float_out = (int(default_value), float(default_value))
        else:
            try:
                value = float(params)
                int_out, float_out = (int(value), float(value))
            except ValueError:
                print(f'[Warning] CR Value Scheduler. Invalid params: {params}')
                return _output(())
        return _output((int_out, float_out, show_help))


class CR_TextScheduler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text Scheduler', display_name='📑 CR Text Scheduler', category='🧩 Comfyroll Studio/🎥 Animation/📑 Schedulers', is_output_node=False, is_input_list=False, inputs=[io.Combo.Input('mode', options=['Default Text', 'Schedule']), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.String.Input('schedule_alias', default='', multiline=False), io.String.Input('default_text', multiline=False, default='default text'), io.Combo.Input('schedule_format', options=['CR', 'Deforum']), io.Custom('SCHEDULE').Input('schedule', optional=True)], outputs=[io.String.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, current_frame, schedule_alias, default_text, schedule_format, schedule=None):
        _guard({'mode': mode, 'current_frame': current_frame, 'schedule_alias': schedule_alias, 'default_text': default_text, 'schedule_format': schedule_format, 'schedule': schedule})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Scheduler-Nodes#cr-text-scheduler'
        if mode == 'Default Text':
            print(f'[Info] CR Text Scheduler: Scheduler {schedule_alias} is disabled')
            text_out = default_text
            return _output((text_out, show_help))
        params = keyframe_scheduler(schedule, schedule_alias, current_frame)
        if params == '':
            if current_frame == 0:
                print(f'[Warning] CR Text Scheduler. No frame 0 found in schedule. Starting with default value at frame 0')
            text_out = (default_value,)
        else:
            try:
                text_out = params
            except ValueError:
                print(f'[Warning] CR Text Scheduler. Invalid params: {params}')
                return _output(())
        return _output((text_out, show_help))


class CR_PromptScheduler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Prompt Scheduler', display_name='📑 CR Prompt Scheduler', category='🧩 Comfyroll Studio/🎥 Animation/📑 Schedulers', is_output_node=False, is_input_list=False, inputs=[io.Combo.Input('mode', options=['Default Prompt', 'Keyframe List', 'Schedule']), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.String.Input('default_prompt', multiline=False, default='default prompt'), io.Combo.Input('schedule_format', options=['CR', 'Deforum']), io.Combo.Input('interpolate_prompt', options=['Yes', 'No']), io.Custom('SCHEDULE').Input('schedule', optional=True), io.String.Input('schedule_alias', multiline=False, optional=True, extra_dict={'default prompt': ''}), io.String.Input('keyframe_list', multiline=True, default='keyframe list', optional=True), io.String.Input('prepend_text', multiline=True, default='prepend text', optional=True), io.String.Input('append_text', multiline=True, default='append text', optional=True)], outputs=[io.String.Output(display_name='current_prompt'), io.String.Output(display_name='next_prompt'), io.Float.Output(display_name='weight'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, mode, prepend_text, append_text, current_frame, schedule_alias, default_prompt, schedule_format, interpolate_prompt, keyframe_list='', schedule=None):
        _guard({'mode': mode, 'prepend_text': prepend_text, 'append_text': append_text, 'current_frame': current_frame, 'schedule_alias': schedule_alias, 'default_prompt': default_prompt, 'schedule_format': schedule_format, 'interpolate_prompt': interpolate_prompt, 'keyframe_list': keyframe_list, 'schedule': schedule})
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Scheduler-Nodes#cr-prompt-scheduler'
        schedule_lines = list()
        if mode == 'Default Prompt':
            print(f'[Info] CR Prompt Scheduler: Scheduler {schedule_alias} is disabled')
            return _output((default_prompt, default_prompt, 1.0, show_help))
        if mode == 'Keyframe List':
            if keyframe_list == '':
                print(f'[Error] CR Prompt Scheduler: No keyframe list found.')
                return _output(())
            else:
                lines = keyframe_list.split('\n')
                for line in lines:
                    if schedule_format == 'Deforum':
                        line = line.replace(':', ',')
                        line = line.rstrip(',')
                        line = line.lstrip()
                    if not line.strip():
                        print(f'[Warning] CR Simple Prompt Scheduler. Skipped blank line at line {i}')
                        continue
                    schedule_lines.extend([(schedule_alias, line)])
                schedule = schedule_lines
        if mode == 'Schedule':
            if schedule is None:
                print(f'[Error] CR Prompt Scheduler: No schedule found.')
                return _output(())
            if schedule_format == 'Deforum':
                for item in schedule:
                    alias, line = item
                    line = line.replace(':', ',')
                    line = line.rstrip(',')
                    schedule_lines.extend([(schedule_alias, line)])
                schedule = schedule_lines
        current_prompt, next_prompt, current_keyframe, next_keyframe = prompt_scheduler(schedule, schedule_alias, current_frame)
        if current_prompt == '':
            print(f'[Warning] CR Simple Prompt Scheduler. No prompt found for frame. Schedules should start at frame 0.')
        else:
            try:
                current_prompt_out = prepend_text + ', ' + str(current_prompt) + ', ' + append_text
                next_prompt_out = prepend_text + ', ' + str(next_prompt) + ', ' + append_text
                from_index = int(current_keyframe)
                to_index = int(next_keyframe)
            except ValueError:
                print(f'[Warning] CR Simple Text Scheduler. Invalid keyframe at frame {current_frame}')
        if from_index == to_index or interpolate_prompt == 'No':
            weight_out = 1.0
        else:
            weight_out = (to_index - current_frame) / (to_index - from_index)
        return _output((current_prompt_out, next_prompt_out, weight_out, show_help))


class CR_SimplePromptScheduler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Prompt Scheduler', display_name='📑 CR Simple Prompt Scheduler', category='🧩 Comfyroll Studio/🎥 Animation/📑 Schedulers', is_output_node=False, is_input_list=False, inputs=[io.String.Input('keyframe_list', multiline=True, default='frame_number, text'), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0), io.Combo.Input('keyframe_format', options=['CR', 'Deforum'])], outputs=[io.String.Output(display_name='current_prompt'), io.String.Output(display_name='next_prompt'), io.Float.Output(display_name='weight'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, keyframe_list, keyframe_format, current_frame):
        _guard({'keyframe_list': keyframe_list, 'keyframe_format': keyframe_format, 'current_frame': current_frame})
        keyframes = list()
        if keyframe_list == '':
            print(f'[Error] CR Simple Prompt Scheduler. No lines in keyframe list')
            return _output(())
        lines = keyframe_list.split('\n')
        for line in lines:
            if keyframe_format == 'Deforum':
                line = line.replace(':', ',')
                line = line.rstrip(',')
            if not line.strip():
                print(f'[Warning] CR Simple Prompt Scheduler. Skipped blank line at line {i}')
                continue
            keyframes.extend([('SIMPLE', line)])
        current_prompt, next_prompt, current_keyframe, next_keyframe = prompt_scheduler(keyframes, 'SIMPLE', current_frame)
        if current_prompt == '':
            print(f'[Warning] CR Simple Prompt Scheduler. No prompt found for frame. Simple schedules must start at frame 0.')
        else:
            try:
                current_prompt_out = str(current_prompt)
                next_prompt_out = str(next_prompt)
                from_index = int(current_keyframe)
                to_index = int(next_keyframe)
            except ValueError:
                print(f'[Warning] CR Simple Text Scheduler. Invalid keyframe at frame {current_frame}')
            if from_index == to_index:
                weight_out = 1.0
            else:
                weight_out = (to_index - current_frame) / (to_index - from_index)
            show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Scheduler-Nodes#cr-simple-prompt-scheduler'
            return _output((current_prompt_out, next_prompt_out, weight_out, show_help))


class CR_SimpleValueScheduler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Value Scheduler', display_name='📑 CR Simple Value Scheduler', category='🧩 Comfyroll Studio/🎥 Animation/📑 Schedulers', is_output_node=False, is_input_list=False, inputs=[io.String.Input('schedule', multiline=True, default='frame_number, value'), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0)], outputs=[io.Int.Output(display_name='INT'), io.Float.Output(display_name='FLOAT'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, schedule, current_frame):
        _guard({'schedule': schedule, 'current_frame': current_frame})
        schedule_lines = list()
        if schedule == '':
            print(f'[Warning] CR Simple Value Scheduler. No lines in schedule')
            return _output(())
        lines = schedule.split('\n')
        for line in lines:
            schedule_lines.extend([('SIMPLE', line)])
        params = keyframe_scheduler(schedule_lines, 'SIMPLE', current_frame)
        if params == '':
            print(f'[Warning] CR Simple Value Scheduler. No schedule found for frame. Simple schedules must start at frame 0.')
        else:
            try:
                int_out = int(params.split('.')[0])
                float_out = float(params)
            except ValueError:
                print(f'[Warning] CR Simple Value Scheduler. Invalid params {params} at frame {current_frame}')
            show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Scheduler-Nodes#cr-simple-value-scheduler'
            return _output((int_out, float_out, show_help))


class CR_SimpleTextScheduler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Simple Text Scheduler', display_name='📑 CR Simple Text Scheduler', category='🧩 Comfyroll Studio/🎥 Animation/📑 Schedulers', is_output_node=False, is_input_list=False, inputs=[io.String.Input('schedule', multiline=True, default='frame_number, text'), io.Int.Input('current_frame', default=0.0, min=0.0, max=9999.0, step=1.0)], outputs=[io.String.Output(display_name='STRING'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, schedule, current_frame):
        _guard({'schedule': schedule, 'current_frame': current_frame})
        schedule_lines = list()
        if schedule == '':
            print(f'[Warning] CR Simple Text Scheduler. No lines in schedule')
            return _output(())
        lines = schedule.split('\n')
        for line in lines:
            schedule_lines.extend([('SIMPLE', line)])
        params = keyframe_scheduler(schedule_lines, 'SIMPLE', current_frame)
        if params == '':
            print(f'[Warning] CR Simple Text Scheduler. No schedule found for frame. Simple schedules must start at frame 0.')
        else:
            try:
                text_out = str(params)
            except ValueError:
                print(f'[Warning] CR Simple Text Scheduler. Invalid params {params} at frame {current_frame}')
            show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/Scheduler-Nodes#cr-simple-text-scheduler'
            return _output((text_out, show_help))


class CR_TextListSimple(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Text List Simple', display_name='CR Text List Simple (Legacy)', category='🧩 Comfyroll Studio/🎥 Animation/💀 Legacy', is_output_node=False, is_input_list=False, inputs=[io.String.Input('text_1', multiline=False, default='', optional=True), io.String.Input('text_2', multiline=False, default='', optional=True), io.String.Input('text_3', multiline=False, default='', optional=True), io.String.Input('text_4', multiline=False, default='', optional=True), io.String.Input('text_5', multiline=False, default='', optional=True), io.Custom('TEXT_LIST_SIMPLE').Input('text_list_simple', optional=True)], outputs=[io.Custom('TEXT_LIST_SIMPLE').Output(display_name='TEXT_LIST_SIMPLE'), io.String.Output(display_name='show_help')])

    @classmethod
    def execute(cls, text_1, text_2, text_3, text_4, text_5, text_list_simple=None):
        _guard({'text_1': text_1, 'text_2': text_2, 'text_3': text_3, 'text_4': text_4, 'text_5': text_5, 'text_list_simple': text_list_simple})
        texts = list()
        if text_list_simple is not None:
            texts.extend((l for l in text_list_simple))
        if text_1 != '' and text_1 != None:
            (texts.append(text_1),)
        if text_2 != '' and text_2 != None:
            texts.append(text_2)
        if text_3 != '' and text_3 != None:
            texts.append(text_3)
        if text_4 != '' and text_4 != None:
            (texts.append(text_4),)
        if text_5 != '' and text_5 != None:
            (texts.append(text_5),)
        show_help = 'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-text-list-simple'
        return _output((texts, show_help))


NODE_CLASS_MAPPINGS = {
    'CR Simple Schedule': CR_SimpleSchedule,
    'CR Combine Schedules': CR_CombineSchedules,
    'CR Central Schedule': CR_CentralSchedule,
    'CR Schedule Input Switch': Comfyroll_ScheduleInputSwitch,
    'CR Value Scheduler': CR_ValueScheduler,
    'CR Text Scheduler': CR_TextScheduler,
    'CR Prompt Scheduler': CR_PromptScheduler,
    'CR Simple Prompt Scheduler': CR_SimplePromptScheduler,
    'CR Simple Value Scheduler': CR_SimpleValueScheduler,
    'CR Simple Text Scheduler': CR_SimpleTextScheduler,
    'CR Text List Simple': CR_TextListSimple,
}
NODE_DISPLAY_NAME_MAPPINGS = {'CR Simple Schedule': '📋 CR Simple Schedule', 'CR Combine Schedules': '📋 CR Combine Schedules', 'CR Central Schedule': '📋 CR Central Schedule', 'CR Schedule Input Switch': '📋 CR Schedule Input Switch', 'CR Value Scheduler': '📑 CR Value Scheduler', 'CR Text Scheduler': '📑 CR Text Scheduler', 'CR Prompt Scheduler': '📑 CR Prompt Scheduler', 'CR Simple Prompt Scheduler': '📑 CR Simple Prompt Scheduler', 'CR Simple Value Scheduler': '📑 CR Simple Value Scheduler', 'CR Simple Text Scheduler': '📑 CR Simple Text Scheduler', 'CR Text List Simple': 'CR Text List Simple (Legacy)'}
