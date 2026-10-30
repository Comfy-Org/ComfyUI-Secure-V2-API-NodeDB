"""Allocation checks tied to the runtime's per-store-dispatch byte policy.

An IMAGE store limit is not a global process-memory limit. Concurrent inputs,
output lists, concatenation and per-frame scratch are accounted separately;
the execution owner must fit that peak inside its real memory envelope.
Estimates are emitted on this module's INFO logger; they are not admissions.
"""
import math
import logging
import os
import struct
import sys

def limit():
    value=int(os.environ.get('COMFY_SECURE_MAX_STORE_BYTES',str(2*1024**3)))
    if value<=0:raise ValueError('Runtime store byte limit must be positive')
    return value

def check_bytes(size,label='allocation'):
    if size>limit():
        raise ValueError(f'Comfyroll {label} exceeds runtime store byte limit')
    return size

def asset_bytes(size):
    # Asset reads use a different, explicit transport policy from refs.store.
    maximum=int(os.environ.get('COMFY_SECURE_ASSET_READ_MAX',str(64*1024**2)))
    if maximum<0:raise ValueError('Runtime asset-read byte limit must be nonnegative')
    if size>maximum:raise ValueError('Comfyroll encoded asset exceeds runtime asset-read byte limit')
    return size

def tensor(value):
    return check_bytes(value.numel()*value.element_size(),'input tensor')

def canvas(batch,height,width,channels=3,itemsize=4,label='output tensor',kind='IMAGE'):
    # Negative geometry must still reach the original method's own error.
    size=math.prod(max(0,int(v)) for v in (batch,height,width,channels))*itemsize
    # These are exact target SDK IMAGE constraints, not a guessed PIL axis cap.
    # Intermediate canvases and MASKs have separate semantics.
    if kind=='IMAGE' and label=='output tensor' and all(v>0 for v in (batch,height,width,channels)):
        if batch>4096 or height*width>67_108_864 or channels not in (1,2,3,4):
            raise ValueError('Comfyroll output exceeds runtime IMAGE batch/pixel/channel policy')
    return check_bytes(size,label)

def projection(input_bytes,outputs,frame_temporary_bytes=0,output_copies=2):
    for size in outputs:check_bytes(size,'projected output tensor')
    # This concurrent sum is only an estimate, never one store admission.
    # Native scratch is reported without applying a guest-ref byte ceiling.
    report=dict(input_bytes=input_bytes,output_bytes=sum(outputs),
                frame_temporary_bytes=frame_temporary_bytes,
                estimated_live_bytes=input_bytes+sum(outputs)*output_copies+frame_temporary_bytes,
                per_reference_limit=limit(),native_workspace_measured=False)
    logging.getLogger(__name__).info('Comfyroll allocation estimate: %s',report)
    return report

def items(count,bytes_per_item=None,label='sequence'):
    # CPython pointer-array size is measured on the running interpreter.
    pointer=struct.calcsize('P') if bytes_per_item is None else bytes_per_item
    return check_bytes(sys.getsizeof([])+max(0,count)*pointer,label)

def text(value,label='text'):
    return check_bytes(sys.getsizeof(value),label)

def glyphs(value,font_size,font_path,stroke=0):
    """Check actual font metrics before Pillow rasterizes a text run."""
    from PIL import ImageFont
    text(value)
    font=ImageFont.truetype(str(font_path),size=font_size)
    largest=0
    for line in value.split('\n'):
        left,top,right,bottom=font.getbbox(line,stroke_width=stroke)
        largest=max(largest,max(0,right-left)*max(0,bottom-top))
    projection(0,[],largest)
    return largest # Native rasterizer scratch, not a guest-created ref.

def data(value):
    """Meter ordinary Python containers without traversing opaque SDK handles."""
    active=set()
    def visit(item):
        if isinstance(item,(str,bytes,bytearray,int,float,bool,type(None))):
            return check_bytes(sys.getsizeof(item),'scalar data')
        if isinstance(item,(list,tuple,dict)):
            ident=id(item)
            if ident in active:raise ValueError('Comfyroll container data must be acyclic')
            active.add(ident)
            total=sys.getsizeof(item)
            values=item.items() if isinstance(item,dict) else item
            for child in values:
                total+=visit(child)
                check_bytes(total,'container data')
            active.remove(ident)
            return total
        return 0
    return visit(value)
