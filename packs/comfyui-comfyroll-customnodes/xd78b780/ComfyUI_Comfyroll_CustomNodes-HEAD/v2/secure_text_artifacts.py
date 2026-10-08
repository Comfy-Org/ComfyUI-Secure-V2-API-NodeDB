"""Authored text in host tenant+pack KV. Logical labels, never OS paths.

Local authoritative KV plus bounded managed INPUT import and OUTPUT export.
KV-first publication is deliberately nontransactional; cloud identity is unproved.
"""
import csv
import hashlib
from io import StringIO
import json
import unicodedata
from comfy_api.latest import io, sdk
from .secure_schedules import _guard

MAX_RECORD_BYTES=65536
MAX_COLLISIONS=256
MAX_CONFLICTS=32

def _identity(label,name,extension):
    for value,limit in ((label,1024),(name,512)):
        if not isinstance(value,str) or len(value.encode('utf-8'))>limit or '\x00' in value:
            raise ValueError('Text artifact logical label/name exceeds bound')
    if extension not in ('txt','csv'):raise ValueError('Text artifact extension must be txt or csv')
    return (label,name,extension)

def _key(identity):
    return 'text-artifact.v1.'+hashlib.sha256(json.dumps(identity,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()

def _decode(value,identity):
    if value is None:return None
    if not isinstance(value,str) or len(value.encode('utf-8'))>MAX_RECORD_BYTES:raise ValueError('Corrupt text artifact record')
    def unique(pairs):
        out={}
        for key,val in pairs:
            if key in out:raise ValueError('Corrupt duplicate text artifact field')
            out[key]=val
        return out
    try:record=json.loads(value,object_pairs_hook=unique)
    except (ValueError,RecursionError) as exc:raise ValueError('Corrupt text artifact JSON') from exc
    if not isinstance(record,dict) or set(record)!={'v','label','name','extension','payload'} or type(record['v']) is not int or record['v']!=1 or (record['label'],record['name'],record['extension'])!=identity or not isinstance(record['payload'],str):
        raise ValueError('Corrupt text artifact identity/schema')
    return record

def _encode(identity,payload):
    if not isinstance(payload,str):raise ValueError('Text artifact requires UTF8 text')
    label,name,extension=identity
    encoded=json.dumps({'v':1,'label':label,'name':name,'extension':extension,'payload':payload},ensure_ascii=False,separators=(',',':'),allow_nan=False)
    if len(encoded.encode('utf-8'))>MAX_RECORD_BYTES:raise ValueError('Text artifact whole record exceeds 64KiB bound')
    return encoded

def _managed_name(label,name,extension):
    """Portable logical names only; old opaque KV labels never reach this IO."""
    _identity(label,name,extension)
    if (not label or not name or '\\' in label or ':' in label
            or '\\' in name or ':' in name or '/' in name
            or any(part in ('','.','..') for part in label.split('/'))
            or name in ('.','..')
            or any(unicodedata.category(char)=='Cc' for char in label+name)):
        raise ValueError('Text artifact requires a portable relative logical label/basename')
    relative=label+'/'+name+'.'+extension
    if len(relative.encode('utf-8'))>1024:
        raise ValueError('Text artifact logical filename exceeds 1024 UTF8 bytes')
    return relative

def _universal_newlines(payload):
    # Match pinned text-mode IO; Unicode NEL/line separators are NOT splitlines.
    return payload.replace('\r\n','\n').replace('\r','\n')

async def _save(label,name,extension,payload,kind):
    _managed_name(label,name,extension);conflicts=0
    for index in range(MAX_COLLISIONS):
        chosen=name if index==0 else name+'_'+str(index) if kind=='text' else name+str(index+1)
        identity=_identity(label,chosen,extension);key=_key(identity);encoded=_encode(identity,payload)
        filename=_managed_name(label,chosen,extension)
        while True:
            old=await sdk.ctx().storage.read(key)
            if old['value'] is not None:
                _decode(old['value'],identity);break
            if await sdk.ctx().assets.exists('output',filename):break
            saved=await sdk.ctx().storage.compare_and_set(key,old['revision'],encoded)
            if saved['updated']:
                # Authoring is authoritative BEFORE publication. Do not roll back,
                # silently skip a race, or retry after a possibly partial write.
                try:
                    await sdk.ctx().output.write_text(payload,filename=filename,
                        folder='output',mode='new_only',insert_newline=False)
                except Exception as exc:
                    raise RuntimeError('Text artifact KV committed; output publication failed for '+
                        filename+' (logical identity '+key+'); authored record preserved') from exc
                return chosen
            conflicts+=1
            if conflicts>=MAX_CONFLICTS:raise RuntimeError('Text artifact exceeded 32 CAS conflicts')
            if saved['value'] is not None:
                _decode(saved['value'],identity);break
    raise RuntimeError('Text artifact exceeded 256 collision candidates; no reset')

async def _read(label,name,extension):
    identity=_identity(label,name,extension)
    if not label.startswith('input:'):
        record=_decode((await sdk.ctx().storage.read(_key(identity)))['value'],identity)
        if record is not None:return _universal_newlines(record['payload'])
        # Only a true miss reaches managed INPUT; corruption/service failure raises.
        imported_label=label
    else:
        imported_label=label[len('input:'):]
    filename=_managed_name(imported_label,name,extension)
    ref=await sdk.ctx().assets.resolve('input',filename)
    size=await sdk.ctx().assets.size(ref)
    if type(size) is not int or not 0<=size<=MAX_RECORD_BYTES:
        raise ValueError('Managed text artifact input size exceeds 64KiB bound')
    data=await sdk.ctx().assets.read_range(ref,offset=0,length=size+1)
    if not isinstance(data,bytes) or len(data)!=size or await sdk.ctx().assets.size(ref)!=size:
        raise ValueError('Managed text artifact changed size or complete read failed')
    payload=data.decode('utf-8')
    _encode(identity,payload)  # Same whole-record workload bound, but NO import CAS/cache.
    return _universal_newlines(payload)

def _text_payload(text,extension):
    if not isinstance(text,str):raise ValueError('Text artifact requires string')
    _guard({'text':text})
    if extension=='csv':
        out=StringIO(newline='');writer=csv.writer(out)
        for line in text.split('\n'):writer.writerow([line.strip()])
        return out.getvalue()
    return text

def _schedule_payload(schedule,extension):
    _guard({'schedule':schedule})
    if not isinstance(schedule,(list,tuple)):raise ValueError('Schedule must be bounded list/tuple rows')
    for row in schedule:
        if not isinstance(row,(list,tuple,str)) or any(type(v) not in (str,int,float,bool,type(None)) for v in row):
            raise ValueError('Schedule rows require scalar text-safe fields')
    if extension=='csv':
        out=StringIO(newline='');csv.writer(out).writerows(schedule);return out.getvalue()
    return ''.join(f'{row[0]},"{row[1]}"\n' for row in schedule)
class CR_SaveTextToFile(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('storage','assets','output')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Save Text To File',display_name='🔤 CR Save Text To File',category='🧩 Comfyroll Studio/🛠️ Utils/🔤 Text',is_output_node=True,inputs=[io.String.Input('multiline_text', multiline=True, default=''), io.String.Input('output_file_path', multiline=False, default=''), io.String.Input('file_name', multiline=False, default=''), io.Combo.Input('file_extension', options=['txt', 'csv'])],outputs=[io.String.Output(display_name='show_help',is_output_list=False)])

    @classmethod
    async def execute(cls,multiline_text,output_file_path,file_name,file_extension):
        _identity(output_file_path,file_name,file_extension)
        if output_file_path=='' or file_name=='':return ()
        await _save(output_file_path,file_name,file_extension,_text_payload(multiline_text,file_extension),'text')
        return io.NodeOutput('https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-save-text-to-file')


class CR_OutputScheduleToFile(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('storage','assets','output')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Output Schedule To File',display_name='📋 CR Output Schedule To File',category='🧩 Comfyroll Studio/🎥 Animation/📋 Schedule',is_output_node=True,inputs=[io.String.Input('output_file_path', multiline=False, default=''), io.String.Input('file_name', multiline=False, default=''), io.Combo.Input('file_extension', options=['txt', 'csv']), io.Custom('SCHEDULE').Input('schedule')],outputs=[])

    @classmethod
    async def execute(cls,output_file_path,file_name,schedule,file_extension):
        _identity(output_file_path,file_name,file_extension)
        if output_file_path=='' or file_name=='':return ()
        await _save(output_file_path,file_name,file_extension,_schedule_payload(schedule,file_extension),'schedule')
        return ()


class CR_LoadScheduleFromFile(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('storage','assets')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Load Schedule From File',display_name='📋 CR Load Schedule From File',category='🧩 Comfyroll Studio/🎥 Animation/📋 Schedule',is_output_node=False,inputs=[io.String.Input('input_file_path', multiline=False, default=''), io.String.Input('file_name', multiline=False, default=''), io.Combo.Input('file_extension', options=['txt', 'csv'])],outputs=[io.Custom('SCHEDULE').Output(display_name='SCHEDULE',is_output_list=False), io.String.Output(display_name='show_text',is_output_list=False)])

    @classmethod
    async def execute(cls,input_file_path,file_name,file_extension):
        text=await _read(input_file_path,file_name,file_extension)
        rows=[]
        if file_extension=='csv':
            rows=list(csv.reader(StringIO(text)))
        else:
            for row in StringIO(text):
                parts=row.strip().split(',',1)
                if len(parts)>=2:rows.append([parts[0],parts[1].strip('"')])
        _guard({'rows':rows})
        return io.NodeOutput(rows,str(rows))


class CR_LoadTextList(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=('storage','assets')
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CR Load Text List',display_name='📜 CR Load Text List',category='🧩 Comfyroll Studio/✨ Essential/📜 List',is_output_node=False,inputs=[io.String.Input('input_file_path', multiline=False, default=''), io.String.Input('file_name', multiline=False, default=''), io.Combo.Input('file_extension', options=['txt', 'csv'])],outputs=[io.String.Output(display_name='STRING',is_output_list=True), io.String.Output(display_name='show_help',is_output_list=False)])

    @classmethod
    async def execute(cls,input_file_path,file_name,file_extension):
        text=await _read(input_file_path,file_name,file_extension)
        rows=list(StringIO(text));_guard({'rows':rows})
        return io.NodeOutput(rows,'https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes/wiki/List-Nodes#cr-load-value-list')


NODE_CLASS_MAPPINGS={
    'CR Save Text To File':CR_SaveTextToFile,
    'CR Output Schedule To File':CR_OutputScheduleToFile,
    'CR Load Schedule From File':CR_LoadScheduleFromFile,
    'CR Load Text List':CR_LoadTextList,
}
NODE_DISPLAY_NAME_MAPPINGS={'CR Save Text To File': '🔤 CR Save Text To File', 'CR Output Schedule To File': '📋 CR Output Schedule To File', 'CR Load Schedule From File': '📋 CR Load Schedule From File', 'CR Load Text List': '📜 CR Load Text List'}
