"""Closed workload admission around the literal pinned algorithms."""
from functools import wraps
import inspect
import numpy as np
import torch
from comfy_api.latest import io, sdk
from . import _admission as guard

TENSOR_KINDS=frozenset(('TENSOR','IMAGE','MASK','SIGMAS'))

def install(node):
    name=node.__name__
    source=node.execute
    signature=inspect.signature(source)
    node.SDK_PERMISSIONS=('raw','inspect') if name=='MathOperation' else ()
    node.SDK_REFS=name in ('MathOperation','LogicIF')
    if name=='MathDivide':
        native_validate=node.validate_inputs
        @wraps(native_validate.__func__)
        def validate(cls,operands,handle_zero):
            guard.ordered(operands);guard.numeric(handle_zero)
            return native_validate(operands,handle_zero)
        node.validate_inputs=classmethod(validate)
    if name=='LogicIF':
        @wraps(source.__func__)
        def choose(cls,if_condition,when_true,when_false=None):
            if type(if_condition) not in (bool,np.bool_):
                raise TypeError('LogicMath Boolean condition required')
            return source(if_condition,when_true,when_false)
        node.execute=classmethod(choose)
        return node
    if name=='MathOperation':
        @wraps(source.__func__)
        async def execute(cls,value_a,value_b,operation):
            if type(operation) is not str:raise TypeError('LogicMath operation label required')
            guard.tree_stats((operation,))
            operands=[value_a,value_b]
            has_tensor=any(isinstance(v,sdk.Ref) or type(v) in (torch.Tensor,np.ndarray) for v in operands)
            shapes=[]
            conversion_extra=0;native_conversion_error=False
            for value in operands:
                if isinstance(value,sdk.Ref):
                    if value.kind not in TENSOR_KINDS:
                        raise TypeError('LogicMath opaque arithmetic is outside the admitted profile')
                    description=await value.describe(max_value_chars=32)
                    shape=description.get('shape')
                    guard.geometry(shape)
                    shapes.append(shape)
                elif type(value) in (torch.Tensor,np.ndarray):
                    dense(value);shapes.append(list(value.shape))
                else:
                    if has_tensor:
                        projected=guard.sequence_projection(value)
                        shapes.append(projected['shape'] if projected['shape'] is not None else [projected['elements']])
                        conversion_extra+=2*projected['extra_bytes']
                        native_conversion_error|=projected['native_conversion_error']
                    else:
                        guard.tree_stats((value,));shapes.append([])
            if has_tensor:guard.tensor_plan(shapes,held_bytes=conversion_extra,native_conversion_error=native_conversion_error)
            else:guard.project_tree(value_a,value_b,operation)
            raw=[]
            for value in operands:
                if isinstance(value,sdk.Ref):
                    tensor=value if isinstance(value,sdk.TensorRef) else await sdk.TensorRef.from_ref(value)
                    value=await tensor.raw();dense(value)
                raw.append(value)
            result=source(*raw,operation).result[0]
            if type(result) is torch.Tensor:
                dense(result);guard.geometry(list(result.shape))
                return io.NodeOutput(await sdk.TensorRef.from_value(result))
            if type(result) is np.ndarray:
                # Native NumPy scalar/list ufunc outputs remain NumPy buffers,
                # not a cast to Torch. Bounded plain source operands above.
                if result.dtype.kind not in 'biufc' or result.dtype.itemsize>16:
                    raise TypeError('LogicMath closed NumPy result dtype required')
                guard.tensor_plan([list(result.shape)])
                return io.NodeOutput(await sdk.ValueRef.from_value(result))
            guard.tree_stats((result,),output=True)
            return io.NodeOutput(result)
    else:
        @wraps(source.__func__)
        def execute(cls,*args,**kwargs):
            bound=signature.bind(*args,**kwargs);bound.apply_defaults()
            guard.node_inputs(name,bound.arguments)
            result=source(*args,**kwargs)
            guard.finish(*result.result)
            return result
    node.execute=classmethod(execute)
    return node

def dense(value):
    if type(value) is np.ndarray:
        if value.dtype.kind not in 'biufc' or value.dtype.hasobject or value.dtype.itemsize>16:
            raise TypeError('LogicMath plain numeric ndarray profile required')
        guard.geometry(list(value.shape))
        return
    if type(value) is not torch.Tensor or value.layout!=torch.strided or value.is_nested:
        raise TypeError('LogicMath dense nonnested tensor profile required')
    if value.element_size()>16:raise TypeError('LogicMath tensor dtype exceeds worst16B profile')
