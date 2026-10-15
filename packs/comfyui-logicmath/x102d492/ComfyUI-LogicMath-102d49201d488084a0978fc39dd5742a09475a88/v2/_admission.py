"""Proposed source-sized admission; operations themselves stay literal source."""
import math
import numpy as np

INPUT_BITS=2048
OUTPUT_BITS=4096
MAX_ITEMS=4096
MAX_DEPTH=32
MAX_TEXT=65536
MAX_ELEMENTS=4194304
MAX_OUTPUT=64*1024*1024
MAX_OWNERSHIP=128*1024*1024
MAX_WORK=128000000
NUMPY_NUMERIC=frozenset(np.dtype(n).type for n in ('bool','int8','int16','int32','int64','uint8','uint16','uint32','uint64','float16','float32','float64','longdouble','complex64','complex128','clongdouble'))

def numeric(value,output=False):
    t=type(value)
    if t not in (bool,int,float,complex) and t not in NUMPY_NUMERIC:
        raise TypeError('LogicMath admits closed numeric scalar leaves only')
    if t is int or (t in NUMPY_NUMERIC and value.dtype.kind in 'iu'):
        if int(value).bit_length()>(OUTPUT_BITS if output else INPUT_BITS):
            raise ValueError('LogicMath integer bit budget exceeded')
    return value

def project_numeric(a,b,operation):
    numeric(a,True);numeric(b,True)
    if type(a) in (bool,int) and type(b) in (bool,int):
        bits_a=abs(a).bit_length();bits_b=abs(b).bit_length()
        if operation in ('Add','Subtract'):upper=max(bits_a,bits_b)+1
        elif operation=='Multiply':upper=bits_a+bits_b
        elif operation=='Power':
            # Exact zero/±one and negative exponent branches have no growing
            # integer result. Native ZeroDivision/float domain errors still run.
            upper=1 if abs(a)<=1 or b<=0 else bits_a*b
        else:upper=0
        if upper>OUTPUT_BITS:raise ValueError('LogicMath projected integer growth budget exceeded')

def project_integer_conversion(value):
    numeric(value)
    # Preserve native bool/int/complex and nonfinite exceptions. For finite
    # real floats, frexp exponent safely bounds floor/ceil/int output growth.
    if type(value) is float and math.isfinite(value):
        if math.frexp(value)[1]>OUTPUT_BITS:
            raise ValueError('LogicMath projected integer conversion budget exceeded')
    elif type(value) in NUMPY_NUMERIC and value.dtype.kind=='f' and np.isfinite(value):
        if int(np.frexp(value)[1])>OUTPUT_BITS:
            raise ValueError('LogicMath projected integer conversion budget exceeded')

def tree_stats(values,output=False):
    stack=[(value,0) for value in values];items=0;text=0
    while stack:
        value,depth=stack.pop();items+=1
        if items>MAX_ITEMS or depth>MAX_DEPTH:
            raise ValueError('LogicMath sequence item/depth budget exceeded')
        t=type(value)
        if t in (list,tuple):
            if len(value)>MAX_ITEMS:raise ValueError('LogicMath sequence item budget exceeded')
            stack.extend((child,depth+1) for child in value)
        elif t in (str,bytes):
            if len(value)>MAX_TEXT:raise ValueError('LogicMath text/bytes budget exceeded')
            text+=len(value.encode('utf-8')) if t is str else len(value)
            if text>MAX_TEXT:raise ValueError('LogicMath cumulative text/bytes budget exceeded')
        else:numeric(value,output)
    return {'items':items,'text_bytes':text}

def project_tree(a,b,operation):
    tree_stats((a,b))
    ta=type(a);tb=type(b)
    sequences=(str,bytes,list,tuple)
    if operation=='Add' and ta==tb and ta in sequences:
        sa=tree_stats((a,));sb=tree_stats((b,))
        items=1 if ta in (str,bytes) else sa['items']+sb['items']-1
        if items>MAX_ITEMS or sa['text_bytes']+sb['text_bytes']>MAX_TEXT:
            raise ValueError('LogicMath projected concatenation budget exceeded')
    if operation=='Multiply':
        sequence=None;repeat=None
        # Pinned NumPy2.4.6 integer/list multiplication uses sequence index
        # repetition on BOTH sides. Addition may instead produce an ndarray.
        if ta in sequences and (tb in (bool,int) or (tb in NUMPY_NUMERIC and b.dtype.kind in 'iu')):
            sequence=a;repeat=int(b)
        elif tb in sequences and (ta in (bool,int) or (ta in NUMPY_NUMERIC and a.dtype.kind in 'iu')):
            sequence=b;repeat=int(a)
        if sequence is not None:
            stats=tree_stats((sequence,));positive=max(repeat,0)
            items=1 if type(sequence) in (str,bytes) else 1+(stats['items']-1)*positive
            if items>MAX_ITEMS or stats['text_bytes']*positive>MAX_TEXT:
                raise ValueError('LogicMath projected repetition budget exceeded')
    if ta not in sequences and tb not in sequences:project_numeric(a,b,operation)
    integer_repeat=(operation=='Multiply' and (
        ta in NUMPY_NUMERIC and a.dtype.kind in 'iu' and tb in (str,bytes,list,tuple) or
        tb in NUMPY_NUMERIC and b.dtype.kind in 'iu' and ta in (str,bytes,list,tuple)))
    if operation in ('Add','Subtract','Multiply','Divide') and not integer_repeat and (
        ta in NUMPY_NUMERIC and tb in (list,tuple) or
        tb in NUMPY_NUMERIC and ta in (list,tuple)):
        # NumPy may first rectangularize an inert sequence. A long lone text
        # item can pad every entry even when the eventual ufunc raises. Meter
        # that prospective backing before calling the original operator.
        sequence=b if ta in NUMPY_NUMERIC else a
        projected=sequence_projection(sequence)['conversion_bytes']
        if projected>MAX_OUTPUT or 4*projected>MAX_OWNERSHIP:
            raise ValueError('LogicMath projected NumPy sequence conversion ownership budget exceeded')

def sequence_projection(value):
    """No NumPy construction: rectangular shape and padded backing upper bound.

    Ragged input is flagged rather than padded/coerced. The native numeric
    ndarray conversion (or Torch/list operator) still raises on admitted small
    ragged data after bounded input ownership, without a result allocation.
    """
    tree_stats((value,))
    leaves=[]
    def shape(item):
        if type(item) not in (list,tuple):leaves.append(item);return ()
        children=[shape(child) for child in item]
        if not children:return (0,)
        if children[0] is None or any(child!=children[0] for child in children):return None
        return (len(item),)+children[0]
    dims=shape(value)
    has_text=any(type(item) in (str,bytes) for item in leaves)
    width=16
    if has_text:
        chars=0
        for item in leaves:
            if type(item) in (str,bytes):chars=max(chars,len(item))
            elif type(item) in (int,bool):chars=max(chars,(int(item).bit_length()*302+999)//1000+4)
            else:chars=max(chars,96)
        width=max(width,4*chars)
    else:
        if type(value) in (list,tuple) and dims is not None and any(type(item) is int and not -(2**63)<=item<=2**64-1 for item in leaves):
            # Numeric sequence inference would select object storage. Its
            # Python-number results do not fit the closed worst16B buffer
            # profile; refuse before rectangularization/raw import, not after.
            raise TypeError('LogicMath NumPy object sequence conversion is outside the dense profile')
        for item in leaves:
            if type(item) in NUMPY_NUMERIC:width=max(width,item.dtype.itemsize)
    count=len(leaves) if dims is None else math.prod(dims)
    backing=count*width
    if backing>MAX_OUTPUT or 4*backing>MAX_OWNERSHIP:
        raise ValueError('LogicMath projected rectangular sequence conversion ownership budget exceeded')
    return {'shape':None if dims is None else list(dims),'elements':count,'conversion_bytes':backing,
            'extra_bytes':max(0,backing-count*16),'native_conversion_error':dims is None}

def string_parse(text):
    if type(text) is not str:raise TypeError('LogicMath STRING input required')
    tree_stats((text,))
    if '.' not in text:
        candidate=text.strip().lstrip('+-').replace('_','')
        if candidate.isdecimal():
            digits=len(candidate.lstrip('0'))
            if (digits*3322+999)//1000>OUTPUT_BITS:
                raise ValueError('LogicMath projected parsed integer budget exceeded')

def ordered(values):
    if type(values) is not dict:raise TypeError('LogicMath ordered autogrow map required')
    if len(values)>10:raise ValueError('LogicMath autogrow operand budget exceeded')
    if any(type(key) is not str for key in values):raise TypeError('LogicMath autogrow string keys required')
    for value in values.values():numeric(value)
    return values

def node_inputs(name,fields):
    if name=='StringToNumber':
        string_parse(fields['string']);numeric(fields['default_value']);return
    for key,value in fields.items():
        if key in ('cls','unit','comparison','operation'):continue
        if type(value) is dict:ordered(value)
        else:numeric(value)
    if name=='MathPower':project_numeric(fields['base'],fields['exponent'],'Power')
    if name in ('MathFloor','MathCeil','MathNumberConvert'):
        project_integer_conversion(fields.get('value',fields.get('number_value')))

def finish(*values):
    for value in values:
        if type(value) is str:tree_stats((value,),True)
        else:numeric(value,True)
    return values

def fold_step(a,b,operation):
    project_numeric(a,b,operation)
    # Original caller still performs its own source operator.

def geometry(shape):
    if type(shape) not in (list,tuple) or len(shape)>32 or any(type(n) is not int or n<0 for n in shape):
        raise TypeError('LogicMath dense rank32 tensor geometry required')
    count=math.prod(shape)
    if count>MAX_ELEMENTS:raise ValueError('LogicMath selected tensor geometry budget exceeded')
    return count

def tensor_plan(shapes,held_bytes=0,native_conversion_error=False):
    counts=[geometry(shape) for shape in shapes]
    input_owned=held_bytes+2*sum(counts)*16
    if input_owned>MAX_OWNERSHIP:
        raise ValueError('LogicMath projected tensor input/snapshot ownership budget exceeded')
    if native_conversion_error:
        return {'native_conversion_error':True,'projected_bytes':input_owned}
    aligned=list(zip(*[(1,)*(max(map(len,shapes))-len(shape))+tuple(shape) for shape in shapes]))
    dims=[]
    for dim in aligned:
        non_one={n for n in dim if n!=1}
        if len(non_one)>1:
            # No tensor work can occur before the original native shape error.
            return {'native_broadcast_error':True,'input_bytes':sum(counts)*16,'projected_bytes':input_owned}
        dims.append(next(iter(non_one)) if non_one else 1)
    count=math.prod(dims);output=count*16
    projected=held_bytes+2*sum(counts)*16+4*output
    if output>MAX_OUTPUT or projected>MAX_OWNERSHIP or count>MAX_WORK:
        raise ValueError('LogicMath projected tensor output/ownership/work budget exceeded')
    return {'shape':dims,'output_bytes':output,'projected_bytes':projected,'work':count}

def run_guarded(a,b,operation,original_operation):
    project_tree(a,b,operation)
    result=original_operation(a,b)
    tree_stats((result,),True)
    return result
