"""All 53 exact pinned IDs: explicit public V2 nodes, pack-owned arithmetic."""
import math
import numpy
from comfy_api.latest import ComfyExtension, io
from .algorithms import bool as bops, int as iops, float as fops, number as nops, vec as vops, graphics as gops
from .bounds import preflight, output_guard

class BoolToInt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_BoolToInt', display_name='BoolToInt', category='math/conversion',
            inputs=[io.Boolean.Input('a', default=False)],
            outputs=[io.Int.Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_BoolToInt', locals())
        return output_guard(io.NodeOutput(int(a)))


class IntToBool(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_IntToBool', display_name='IntToBool', category='math/conversion',
            inputs=[io.Int.Input('a', default=0)],
            outputs=[io.Boolean.Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_IntToBool', locals())
        return output_guard(io.NodeOutput(a != 0))


class FloatToInt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_FloatToInt', display_name='FloatToInt', category='math/conversion',
            inputs=[io.Float.Input('a', default=0.0, round=False)],
            outputs=[io.Int.Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_FloatToInt', locals())
        return output_guard(io.NodeOutput(int(a)))


class IntToFloat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_IntToFloat', display_name='IntToFloat', category='math/conversion',
            inputs=[io.Int.Input('a', default=0)],
            outputs=[io.Float.Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_IntToFloat', locals())
        return output_guard(io.NodeOutput(float(a)))


class IntToNumber(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_IntToNumber', display_name='IntToNumber', category='math/conversion',
            inputs=[io.Int.Input('a', default=0)],
            outputs=[io.Custom('NUMBER').Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_IntToNumber', locals())
        return output_guard(io.NodeOutput(a))


class NumberToInt(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_NumberToInt', display_name='NumberToInt', category='math/conversion',
            inputs=[io.Custom('NUMBER').Input('a')],
            outputs=[io.Int.Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_NumberToInt', locals())
        return output_guard(io.NodeOutput(int(a)))


class FloatToNumber(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_FloatToNumber', display_name='FloatToNumber', category='math/conversion',
            inputs=[io.Float.Input('a', default=0.0, round=False)],
            outputs=[io.Custom('NUMBER').Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_FloatToNumber', locals())
        return output_guard(io.NodeOutput(a))


class NumberToFloat(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_NumberToFloat', display_name='NumberToFloat', category='math/conversion',
            inputs=[io.Custom('NUMBER').Input('a')],
            outputs=[io.Float.Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_NumberToFloat', locals())
        return output_guard(io.NodeOutput(float(a)))


class ComposeVec2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_ComposeVec2', display_name='ComposeVec2', category='math/conversion',
            inputs=[io.Float.Input('x', default=0.0, round=False), io.Float.Input('y', default=0.0, round=False)],
            outputs=[io.Custom('VEC2').Output()])

    @classmethod
    async def execute(cls, x, y):
        preflight('CM_ComposeVec2', locals())
        return output_guard(io.NodeOutput((x, y)))


class ComposeVec3(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_ComposeVec3', display_name='ComposeVec3', category='math/conversion',
            inputs=[io.Float.Input('x', default=0.0), io.Float.Input('y', default=0.0), io.Float.Input('z', default=0.0)],
            outputs=[io.Custom('VEC3').Output()])

    @classmethod
    async def execute(cls, x, y, z):
        preflight('CM_ComposeVec3', locals())
        return output_guard(io.NodeOutput((x, y, z)))


class ComposeVec4(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_ComposeVec4', display_name='ComposeVec4', category='math/conversion',
            inputs=[io.Float.Input('x', default=0.0), io.Float.Input('y', default=0.0), io.Float.Input('z', default=0.0), io.Float.Input('w', default=0.0)],
            outputs=[io.Custom('VEC4').Output()])

    @classmethod
    async def execute(cls, x, y, z, w):
        preflight('CM_ComposeVec4', locals())
        return output_guard(io.NodeOutput((x, y, z, w)))


class BreakoutVec2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_BreakoutVec2', display_name='BreakoutVec2', category='math/conversion',
            inputs=[io.Custom('VEC2').Input('a')],
            outputs=[io.Float.Output(), io.Float.Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_BreakoutVec2', locals())
        return output_guard(io.NodeOutput(a[0], a[1]))


class BreakoutVec3(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_BreakoutVec3', display_name='BreakoutVec3', category='math/conversion',
            inputs=[io.Custom('VEC3').Input('a')],
            outputs=[io.Float.Output(), io.Float.Output(), io.Float.Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_BreakoutVec3', locals())
        return output_guard(io.NodeOutput(a[0], a[1], a[2]))


class BreakoutVec4(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_BreakoutVec4', display_name='BreakoutVec4', category='math/conversion',
            inputs=[io.Custom('VEC4').Input('a')],
            outputs=[io.Float.Output(), io.Float.Output(), io.Float.Output(), io.Float.Output()])

    @classmethod
    async def execute(cls, a):
        preflight('CM_BreakoutVec4', locals())
        return output_guard(io.NodeOutput(a[0], a[1], a[2], a[3]))


class BoolUnaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_BoolUnaryOperation', display_name='BoolUnaryOperation', category='math/bool',
            inputs=[io.Combo.Input('op', options=['Not']), io.Boolean.Input('a', default=False)],
            outputs=[io.Boolean.Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_BoolUnaryOperation', locals())
        return output_guard(io.NodeOutput(bops.BOOL_UNARY_OPERATIONS[op](a)))


class BoolBinaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_BoolBinaryOperation', display_name='BoolBinaryOperation', category='math/bool',
            inputs=[io.Combo.Input('op', options=['Nor', 'Xor', 'Nand', 'And', 'Xnor', 'Or', 'Eq', 'Neq']), io.Boolean.Input('a', default=False), io.Boolean.Input('b', default=False)],
            outputs=[io.Boolean.Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_BoolBinaryOperation', locals())
        return output_guard(io.NodeOutput(bops.BOOL_BINARY_OPERATIONS[op](a, b)))


class IntUnaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_IntUnaryOperation', display_name='IntUnaryOperation', category='math/int',
            inputs=[io.Combo.Input('op', options=['Abs', 'Neg', 'Inc', 'Dec', 'Sqr', 'Cube', 'Not', 'Factorial']), io.Int.Input('a', default=0)],
            outputs=[io.Int.Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_IntUnaryOperation', locals())
        return output_guard(io.NodeOutput(iops.INT_UNARY_OPERATIONS[op](a)))


class IntUnaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_IntUnaryCondition', display_name='IntUnaryCondition', category='math/int',
            inputs=[io.Combo.Input('op', options=['IsZero', 'IsNonZero', 'IsPositive', 'IsNegative', 'IsEven', 'IsOdd']), io.Int.Input('a', default=0)],
            outputs=[io.Custom('BOOL').Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_IntUnaryCondition', locals())
        return output_guard(io.NodeOutput(iops.INT_UNARY_CONDITIONS[op](a)))


class IntBinaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_IntBinaryOperation', display_name='IntBinaryOperation', category='math/int',
            inputs=[io.Combo.Input('op', options=['Add', 'Sub', 'Mul', 'Div', 'Mod', 'Pow', 'And', 'Nand', 'Or', 'Nor', 'Xor', 'Xnor', 'Shl', 'Shr', 'Max', 'Min']), io.Int.Input('a', default=0), io.Int.Input('b', default=0)],
            outputs=[io.Int.Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_IntBinaryOperation', locals())
        return output_guard(io.NodeOutput(iops.INT_BINARY_OPERATIONS[op](a, b)))


class IntBinaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_IntBinaryCondition', display_name='IntBinaryCondition', category='math/int',
            inputs=[io.Combo.Input('op', options=['Eq', 'Neq', 'Gt', 'Lt', 'Geq', 'Leq']), io.Int.Input('a', default=0), io.Int.Input('b', default=0)],
            outputs=[io.Custom('BOOL').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_IntBinaryCondition', locals())
        return output_guard(io.NodeOutput(iops.INT_BINARY_CONDITIONS[op](a, b)))


class FloatUnaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_FloatUnaryOperation', display_name='FloatUnaryOperation', category='math/float',
            inputs=[io.Combo.Input('op', options=['Neg', 'Inc', 'Dec', 'Abs', 'Sqr', 'Cube', 'Sqrt', 'Exp', 'Ln', 'Log10', 'Log2', 'Sin', 'Cos', 'Tan', 'Asin', 'Acos', 'Atan', 'Sinh', 'Cosh', 'Tanh', 'Asinh', 'Acosh', 'Atanh', 'Round', 'Floor', 'Ceil', 'Trunc', 'Erf', 'Erfc', 'Gamma', 'Radians', 'Degrees']), io.Float.Input('a', default=0.0, step=0.001, round=False)],
            outputs=[io.Float.Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_FloatUnaryOperation', locals())
        return output_guard(io.NodeOutput(fops.FLOAT_UNARY_OPERATIONS[op](a)))


class FloatUnaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_FloatUnaryCondition', display_name='FloatUnaryCondition', category='math/float',
            inputs=[io.Combo.Input('op', options=['IsZero', 'IsPositive', 'IsNegative', 'IsNonZero', 'IsPositiveInfinity', 'IsNegativeInfinity', 'IsNaN', 'IsFinite', 'IsInfinite', 'IsEven', 'IsOdd']), io.Float.Input('a', default=0.0, step=0.001, round=False)],
            outputs=[io.Boolean.Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_FloatUnaryCondition', locals())
        return output_guard(io.NodeOutput(fops.FLOAT_UNARY_CONDITIONS[op](a)))


class FloatBinaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_FloatBinaryOperation', display_name='FloatBinaryOperation', category='math/float',
            inputs=[io.Combo.Input('op', options=['Add', 'Sub', 'Mul', 'Div', 'Mod', 'Pow', 'FloorDiv', 'Max', 'Min', 'Log', 'Atan2']), io.Float.Input('a', default=0.0, step=0.001, round=False), io.Float.Input('b', default=0.0, step=0.001, round=False)],
            outputs=[io.Float.Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_FloatBinaryOperation', locals())
        return output_guard(io.NodeOutput(fops.FLOAT_BINARY_OPERATIONS[op](a, b)))


class FloatBinaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_FloatBinaryCondition', display_name='FloatBinaryCondition', category='math/float',
            inputs=[io.Combo.Input('op', options=['Eq', 'Neq', 'Gt', 'Gte', 'Lt', 'Lte']), io.Float.Input('a', default=0.0, step=0.001, round=False), io.Float.Input('b', default=0.0, step=0.001, round=False)],
            outputs=[io.Boolean.Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_FloatBinaryCondition', locals())
        return output_guard(io.NodeOutput(fops.FLOAT_BINARY_CONDITIONS[op](a, b)))


class NumberUnaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_NumberUnaryOperation', display_name='NumberUnaryOperation', category='math/number',
            inputs=[io.Combo.Input('op', options=['Neg', 'Inc', 'Dec', 'Abs', 'Sqr', 'Cube', 'Sqrt', 'Exp', 'Ln', 'Log10', 'Log2', 'Sin', 'Cos', 'Tan', 'Asin', 'Acos', 'Atan', 'Sinh', 'Cosh', 'Tanh', 'Asinh', 'Acosh', 'Atanh', 'Round', 'Floor', 'Ceil', 'Trunc', 'Erf', 'Erfc', 'Gamma', 'Radians', 'Degrees']), io.Custom('NUMBER').Input('a')],
            outputs=[io.Custom('NUMBER').Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_NumberUnaryOperation', locals())
        return output_guard(io.NodeOutput(fops.FLOAT_UNARY_OPERATIONS[op](float(a))))


class NumberUnaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_NumberUnaryCondition', display_name='NumberUnaryCondition', category='math/Number',
            inputs=[io.Combo.Input('op', options=['IsZero', 'IsPositive', 'IsNegative', 'IsNonZero', 'IsPositiveInfinity', 'IsNegativeInfinity', 'IsNaN', 'IsFinite', 'IsInfinite', 'IsEven', 'IsOdd']), io.Custom('NUMBER').Input('a')],
            outputs=[io.Custom('BOOL').Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_NumberUnaryCondition', locals())
        return output_guard(io.NodeOutput(fops.FLOAT_UNARY_CONDITIONS[op](float(a))))


class NumberBinaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_NumberBinaryOperation', display_name='NumberBinaryOperation', category='math/number',
            inputs=[io.Combo.Input('op', options=['Add', 'Sub', 'Mul', 'Div', 'Mod', 'Pow', 'FloorDiv', 'Max', 'Min', 'Log', 'Atan2']), io.Custom('NUMBER').Input('a'), io.Custom('NUMBER').Input('b')],
            outputs=[io.Custom('NUMBER').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_NumberBinaryOperation', locals())
        return output_guard(io.NodeOutput(fops.FLOAT_BINARY_OPERATIONS[op](float(a), float(b))))


class NumberBinaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_NumberBinaryCondition', display_name='NumberBinaryCondition', category='math/float',
            inputs=[io.Combo.Input('op', options=['Eq', 'Neq', 'Gt', 'Gte', 'Lt', 'Lte']), io.Custom('NUMBER').Input('a'), io.Custom('NUMBER').Input('b')],
            outputs=[io.Custom('BOOL').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_NumberBinaryCondition', locals())
        return output_guard(io.NodeOutput(fops.FLOAT_BINARY_CONDITIONS[op](float(a), float(b))))


class Vec2UnaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec2UnaryOperation', display_name='Vec2UnaryOperation', category='math/vec2',
            inputs=[io.Combo.Input('op', options=['Neg', 'Normalize']), io.Custom('VEC2').Input('a')],
            outputs=[io.Custom('VEC2').Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_Vec2UnaryOperation', locals())
        return output_guard(io.NodeOutput(vops._vec2_from_numpy(vops.VEC_UNARY_OPERATIONS[op](numpy.array(a)))))


class Vec2UnaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec2UnaryCondition', display_name='Vec2UnaryCondition', category='math/vec2',
            inputs=[io.Combo.Input('op', options=['IsZero', 'IsNotZero', 'IsNormalized', 'IsNotNormalized']), io.Custom('VEC2').Input('a')],
            outputs=[io.Custom('BOOL').Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_Vec2UnaryCondition', locals())
        return output_guard(io.NodeOutput(vops.VEC_UNARY_CONDITIONS[op](numpy.array(a))))


class Vec2ToScalarUnaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec2ToScalarUnaryOperation', display_name='Vec2ToScalarUnaryOperation', category='math/vec2',
            inputs=[io.Combo.Input('op', options=['Norm']), io.Custom('VEC2').Input('a')],
            outputs=[io.Float.Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_Vec2ToScalarUnaryOperation', locals())
        return output_guard(io.NodeOutput(vops.VEC_TO_SCALAR_UNARY_OPERATION[op](numpy.array(a))))


class Vec2BinaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec2BinaryOperation', display_name='Vec2BinaryOperation', category='math/vec2',
            inputs=[io.Combo.Input('op', options=['Add', 'Sub', 'Cross']), io.Custom('VEC2').Input('a'), io.Custom('VEC2').Input('b')],
            outputs=[io.Custom('VEC2').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec2BinaryOperation', locals())
        return output_guard(io.NodeOutput(vops._vec2_from_numpy(vops.VEC_BINARY_OPERATIONS[op](numpy.array(a), numpy.array(b)))))


class Vec2BinaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec2BinaryCondition', display_name='Vec2BinaryCondition', category='math/vec2',
            inputs=[io.Combo.Input('op', options=['Eq', 'Neq']), io.Custom('VEC2').Input('a'), io.Custom('VEC2').Input('b')],
            outputs=[io.Custom('BOOL').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec2BinaryCondition', locals())
        return output_guard(io.NodeOutput(vops.VEC_BINARY_CONDITIONS[op](numpy.array(a), numpy.array(b))))


class Vec2ToScalarBinaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec2ToScalarBinaryOperation', display_name='Vec2ToScalarBinaryOperation', category='math/vec2',
            inputs=[io.Combo.Input('op', options=['Dot', 'Distance']), io.Custom('VEC2').Input('a'), io.Custom('VEC2').Input('b')],
            outputs=[io.Float.Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec2ToScalarBinaryOperation', locals())
        return output_guard(io.NodeOutput(vops.VEC_TO_SCALAR_BINARY_OPERATION[op](numpy.array(a), numpy.array(b))))


class Vec2ScalarOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec2ScalarOperation', display_name='Vec2ScalarOperation', category='math/vec2',
            inputs=[io.Combo.Input('op', options=['Mul', 'Div']), io.Custom('VEC2').Input('a'), io.Float.Input('b')],
            outputs=[io.Custom('VEC2').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec2ScalarOperation', locals())
        return output_guard(io.NodeOutput(vops._vec2_from_numpy(vops.VEC_SCALAR_OPERATION[op](numpy.array(a), b))))


class Vec3UnaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec3UnaryOperation', display_name='Vec3UnaryOperation', category='math/vec3',
            inputs=[io.Combo.Input('op', options=['Neg', 'Normalize']), io.Custom('VEC3').Input('a')],
            outputs=[io.Custom('VEC3').Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_Vec3UnaryOperation', locals())
        return output_guard(io.NodeOutput(vops._vec3_from_numpy(vops.VEC_UNARY_OPERATIONS[op](numpy.array(a)))))


class Vec3UnaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec3UnaryCondition', display_name='Vec3UnaryCondition', category='math/vec3',
            inputs=[io.Combo.Input('op', options=['IsZero', 'IsNotZero', 'IsNormalized', 'IsNotNormalized']), io.Custom('VEC3').Input('a')],
            outputs=[io.Custom('BOOL').Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_Vec3UnaryCondition', locals())
        return output_guard(io.NodeOutput(vops.VEC_UNARY_CONDITIONS[op](numpy.array(a))))


class Vec3ToScalarUnaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec3ToScalarUnaryOperation', display_name='Vec3ToScalarUnaryOperation', category='math/vec3',
            inputs=[io.Combo.Input('op', options=['Norm']), io.Custom('VEC3').Input('a')],
            outputs=[io.Float.Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_Vec3ToScalarUnaryOperation', locals())
        return output_guard(io.NodeOutput(vops.VEC_TO_SCALAR_UNARY_OPERATION[op](numpy.array(a))))


class Vec3BinaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec3BinaryOperation', display_name='Vec3BinaryOperation', category='math/vec3',
            inputs=[io.Combo.Input('op', options=['Add', 'Sub', 'Cross']), io.Custom('VEC3').Input('a'), io.Custom('VEC3').Input('b')],
            outputs=[io.Custom('VEC3').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec3BinaryOperation', locals())
        return output_guard(io.NodeOutput(vops._vec3_from_numpy(vops.VEC_BINARY_OPERATIONS[op](numpy.array(a), numpy.array(b)))))


class Vec3BinaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec3BinaryCondition', display_name='Vec3BinaryCondition', category='math/vec3',
            inputs=[io.Combo.Input('op', options=['Eq', 'Neq']), io.Custom('VEC3').Input('a'), io.Custom('VEC3').Input('b')],
            outputs=[io.Custom('BOOL').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec3BinaryCondition', locals())
        return output_guard(io.NodeOutput(vops.VEC_BINARY_CONDITIONS[op](numpy.array(a), numpy.array(b))))


class Vec3ToScalarBinaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec3ToScalarBinaryOperation', display_name='Vec3ToScalarBinaryOperation', category='math/vec3',
            inputs=[io.Combo.Input('op', options=['Dot', 'Distance']), io.Custom('VEC3').Input('a'), io.Custom('VEC3').Input('b')],
            outputs=[io.Float.Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec3ToScalarBinaryOperation', locals())
        return output_guard(io.NodeOutput(vops.VEC_TO_SCALAR_BINARY_OPERATION[op](numpy.array(a), numpy.array(b))))


class Vec3ScalarOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec3ScalarOperation', display_name='Vec3ScalarOperation', category='math/vec3',
            inputs=[io.Combo.Input('op', options=['Mul', 'Div']), io.Custom('VEC3').Input('a'), io.Float.Input('b')],
            outputs=[io.Custom('VEC3').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec3ScalarOperation', locals())
        return output_guard(io.NodeOutput(vops._vec3_from_numpy(vops.VEC_SCALAR_OPERATION[op](numpy.array(a), b))))


class Vec4UnaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec4UnaryOperation', display_name='Vec4UnaryOperation', category='math/vec4',
            inputs=[io.Combo.Input('op', options=['Neg', 'Normalize']), io.Custom('VEC4').Input('a')],
            outputs=[io.Custom('VEC4').Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_Vec4UnaryOperation', locals())
        return output_guard(io.NodeOutput(vops._vec4_from_numpy(vops.VEC_UNARY_OPERATIONS[op](numpy.array(a)))))


class Vec4UnaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec4UnaryCondition', display_name='Vec4UnaryCondition', category='math/vec4',
            inputs=[io.Combo.Input('op', options=['IsZero', 'IsNotZero', 'IsNormalized', 'IsNotNormalized']), io.Custom('VEC4').Input('a')],
            outputs=[io.Custom('BOOL').Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_Vec4UnaryCondition', locals())
        return output_guard(io.NodeOutput(vops.VEC_UNARY_CONDITIONS[op](numpy.array(a))))


class Vec4ToScalarUnaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec4ToScalarUnaryOperation', display_name='Vec4ToScalarUnaryOperation', category='math/vec4',
            inputs=[io.Combo.Input('op', options=['Norm']), io.Custom('VEC4').Input('a')],
            outputs=[io.Float.Output()])

    @classmethod
    async def execute(cls, op, a):
        preflight('CM_Vec4ToScalarUnaryOperation', locals())
        return output_guard(io.NodeOutput(vops.VEC_TO_SCALAR_UNARY_OPERATION[op](numpy.array(a))))


class Vec4BinaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec4BinaryOperation', display_name='Vec4BinaryOperation', category='math/vec4',
            inputs=[io.Combo.Input('op', options=['Add', 'Sub', 'Cross']), io.Custom('VEC4').Input('a'), io.Custom('VEC4').Input('b')],
            outputs=[io.Custom('VEC4').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec4BinaryOperation', locals())
        return output_guard(io.NodeOutput(vops._vec4_from_numpy(vops.VEC_BINARY_OPERATIONS[op](numpy.array(a), numpy.array(b)))))


class Vec4BinaryCondition(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec4BinaryCondition', display_name='Vec4BinaryCondition', category='math/vec4',
            inputs=[io.Combo.Input('op', options=['Eq', 'Neq']), io.Custom('VEC4').Input('a'), io.Custom('VEC4').Input('b')],
            outputs=[io.Custom('BOOL').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec4BinaryCondition', locals())
        return output_guard(io.NodeOutput(vops.VEC_BINARY_CONDITIONS[op](numpy.array(a), numpy.array(b))))


class Vec4ToScalarBinaryOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec4ToScalarBinaryOperation', display_name='Vec4ToScalarBinaryOperation', category='math/vec4',
            inputs=[io.Combo.Input('op', options=['Dot', 'Distance']), io.Custom('VEC4').Input('a'), io.Custom('VEC4').Input('b')],
            outputs=[io.Float.Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec4ToScalarBinaryOperation', locals())
        return output_guard(io.NodeOutput(vops.VEC_TO_SCALAR_BINARY_OPERATION[op](numpy.array(a), numpy.array(b))))


class Vec4ScalarOperation(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_Vec4ScalarOperation', display_name='Vec4ScalarOperation', category='math/vec4',
            inputs=[io.Combo.Input('op', options=['Mul', 'Div']), io.Custom('VEC4').Input('a'), io.Float.Input('b')],
            outputs=[io.Custom('VEC4').Output()])

    @classmethod
    async def execute(cls, op, a, b):
        preflight('CM_Vec4ScalarOperation', locals())
        return output_guard(io.NodeOutput(vops._vec4_from_numpy(vops.VEC_SCALAR_OPERATION[op](numpy.array(a), b))))


class SDXLResolution(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_SDXLResolution', display_name='SDXLResolution', category='math/graphics',
            inputs=[io.Combo.Input('resolution', options=['1024x1024', '1152x896', '896x1152', '1216x832', '832x1216', '1344x768', '768x1344', '1536x640', '640x1536'])],
            outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height')])

    @classmethod
    async def execute(cls, resolution):
        preflight('CM_SDXLResolution', locals())
        width, height = resolution.split('x')
        return output_guard(io.NodeOutput(int(width), int(height)))


class NearestSDXLResolution(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_NearestSDXLResolution', display_name='NearestSDXLResolution', category='math/graphics',
            inputs=[io.Image.Input('image')],
            outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height')])

    @classmethod
    async def execute(cls, image):
        preflight('CM_NearestSDXLResolution', locals())
        image_height, image_width = await image.spatial_shape()
        print(f'Input image resolution: {image_width}x{image_height}')
        image_ratio = image_width / image_height
        differences = [(abs(image_ratio - resolution[2]), resolution) for resolution in gops.SDXL_SUPPORTED_RESOLUTIONS]
        smallest = None
        for difference in differences:
            if smallest is None:
                smallest = difference
            elif difference[0] < smallest[0]:
                smallest = difference
        if smallest is not None:
            width = smallest[1][0]
            height = smallest[1][1]
        else:
            width = 1024
            height = 1024
        print(f'Selected resolution: {width}x{height}')
        return output_guard(io.NodeOutput(width, height))


class SDXLExtendedResolution(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_SDXLExtendedResolution', display_name='SDXLExtendedResolution', category='math/graphics',
            inputs=[io.Combo.Input('resolution', options=['512x2048', '512x1984', '512x1920', '512x1856', '576x1792', '576x1728', '576x1664', '640x1600', '640x1536', '704x1472', '704x1408', '704x1344', '768x1344', '768x1280', '832x1216', '832x1152', '896x1152', '896x1088', '960x1088', '960x1024', '1024x1024', '1024x960', '1088x960', '1088x896', '1152x896', '1152x832', '1216x832', '1280x768', '1344x768', '1408x704', '1472x704', '1536x640', '1600x640', '1664x576', '1728x576', '1792x576', '1856x512', '1920x512', '1984x512', '2048x512'])],
            outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height')])

    @classmethod
    async def execute(cls, resolution):
        preflight('CM_SDXLExtendedResolution', locals())
        width, height = resolution.split('x')
        return output_guard(io.NodeOutput(int(width), int(height)))


class NearestSDXLExtendedResolution(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CM_NearestSDXLExtendedResolution', display_name='NearestSDXLExtendedResolution', category='math/graphics',
            inputs=[io.Image.Input('image')],
            outputs=[io.Int.Output(display_name='width'), io.Int.Output(display_name='height')])

    @classmethod
    async def execute(cls, image):
        preflight('CM_NearestSDXLExtendedResolution', locals())
        image_height, image_width = await image.spatial_shape()
        print(f'Input image resolution: {image_width}x{image_height}')
        image_ratio = image_width / image_height
        differences = [(abs(image_ratio - resolution[2]), resolution) for resolution in gops.SDXL_EXTENDED_RESOLUTIONS]
        smallest = None
        for difference in differences:
            if smallest is None:
                smallest = difference
            elif difference[0] < smallest[0]:
                smallest = difference
        if smallest is not None:
            width = smallest[1][0]
            height = smallest[1][1]
        else:
            width = 1024
            height = 1024
        print(f'Selected resolution: {width}x{height}')
        return output_guard(io.NodeOutput(width, height))


NODE_CLASS_MAPPINGS = {
    'CM_BoolToInt': BoolToInt,
    'CM_IntToBool': IntToBool,
    'CM_FloatToInt': FloatToInt,
    'CM_IntToFloat': IntToFloat,
    'CM_IntToNumber': IntToNumber,
    'CM_NumberToInt': NumberToInt,
    'CM_FloatToNumber': FloatToNumber,
    'CM_NumberToFloat': NumberToFloat,
    'CM_ComposeVec2': ComposeVec2,
    'CM_ComposeVec3': ComposeVec3,
    'CM_ComposeVec4': ComposeVec4,
    'CM_BreakoutVec2': BreakoutVec2,
    'CM_BreakoutVec3': BreakoutVec3,
    'CM_BreakoutVec4': BreakoutVec4,
    'CM_BoolUnaryOperation': BoolUnaryOperation,
    'CM_BoolBinaryOperation': BoolBinaryOperation,
    'CM_IntUnaryOperation': IntUnaryOperation,
    'CM_IntUnaryCondition': IntUnaryCondition,
    'CM_IntBinaryOperation': IntBinaryOperation,
    'CM_IntBinaryCondition': IntBinaryCondition,
    'CM_FloatUnaryOperation': FloatUnaryOperation,
    'CM_FloatUnaryCondition': FloatUnaryCondition,
    'CM_FloatBinaryOperation': FloatBinaryOperation,
    'CM_FloatBinaryCondition': FloatBinaryCondition,
    'CM_NumberUnaryOperation': NumberUnaryOperation,
    'CM_NumberUnaryCondition': NumberUnaryCondition,
    'CM_NumberBinaryOperation': NumberBinaryOperation,
    'CM_NumberBinaryCondition': NumberBinaryCondition,
    'CM_Vec2UnaryOperation': Vec2UnaryOperation,
    'CM_Vec2UnaryCondition': Vec2UnaryCondition,
    'CM_Vec2ToScalarUnaryOperation': Vec2ToScalarUnaryOperation,
    'CM_Vec2BinaryOperation': Vec2BinaryOperation,
    'CM_Vec2BinaryCondition': Vec2BinaryCondition,
    'CM_Vec2ToScalarBinaryOperation': Vec2ToScalarBinaryOperation,
    'CM_Vec2ScalarOperation': Vec2ScalarOperation,
    'CM_Vec3UnaryOperation': Vec3UnaryOperation,
    'CM_Vec3UnaryCondition': Vec3UnaryCondition,
    'CM_Vec3ToScalarUnaryOperation': Vec3ToScalarUnaryOperation,
    'CM_Vec3BinaryOperation': Vec3BinaryOperation,
    'CM_Vec3BinaryCondition': Vec3BinaryCondition,
    'CM_Vec3ToScalarBinaryOperation': Vec3ToScalarBinaryOperation,
    'CM_Vec3ScalarOperation': Vec3ScalarOperation,
    'CM_Vec4UnaryOperation': Vec4UnaryOperation,
    'CM_Vec4UnaryCondition': Vec4UnaryCondition,
    'CM_Vec4ToScalarUnaryOperation': Vec4ToScalarUnaryOperation,
    'CM_Vec4BinaryOperation': Vec4BinaryOperation,
    'CM_Vec4BinaryCondition': Vec4BinaryCondition,
    'CM_Vec4ToScalarBinaryOperation': Vec4ToScalarBinaryOperation,
    'CM_Vec4ScalarOperation': Vec4ScalarOperation,
    'CM_SDXLResolution': SDXLResolution,
    'CM_NearestSDXLResolution': NearestSDXLResolution,
    'CM_SDXLExtendedResolution': SDXLExtendedResolution,
    'CM_NearestSDXLExtendedResolution': NearestSDXLExtendedResolution,
}
NODE_DISPLAY_NAME_MAPPINGS = {'CM_BoolToInt': 'BoolToInt', 'CM_IntToBool': 'IntToBool', 'CM_FloatToInt': 'FloatToInt', 'CM_IntToFloat': 'IntToFloat', 'CM_IntToNumber': 'IntToNumber', 'CM_NumberToInt': 'NumberToInt', 'CM_FloatToNumber': 'FloatToNumber', 'CM_NumberToFloat': 'NumberToFloat', 'CM_ComposeVec2': 'ComposeVec2', 'CM_ComposeVec3': 'ComposeVec3', 'CM_ComposeVec4': 'ComposeVec4', 'CM_BreakoutVec2': 'BreakoutVec2', 'CM_BreakoutVec3': 'BreakoutVec3', 'CM_BreakoutVec4': 'BreakoutVec4', 'CM_BoolUnaryOperation': 'BoolUnaryOperation', 'CM_BoolBinaryOperation': 'BoolBinaryOperation', 'CM_IntUnaryOperation': 'IntUnaryOperation', 'CM_IntUnaryCondition': 'IntUnaryCondition', 'CM_IntBinaryOperation': 'IntBinaryOperation', 'CM_IntBinaryCondition': 'IntBinaryCondition', 'CM_FloatUnaryOperation': 'FloatUnaryOperation', 'CM_FloatUnaryCondition': 'FloatUnaryCondition', 'CM_FloatBinaryOperation': 'FloatBinaryOperation', 'CM_FloatBinaryCondition': 'FloatBinaryCondition', 'CM_NumberUnaryOperation': 'NumberUnaryOperation', 'CM_NumberUnaryCondition': 'NumberUnaryCondition', 'CM_NumberBinaryOperation': 'NumberBinaryOperation', 'CM_NumberBinaryCondition': 'NumberBinaryCondition', 'CM_Vec2UnaryOperation': 'Vec2UnaryOperation', 'CM_Vec2UnaryCondition': 'Vec2UnaryCondition', 'CM_Vec2ToScalarUnaryOperation': 'Vec2ToScalarUnaryOperation', 'CM_Vec2BinaryOperation': 'Vec2BinaryOperation', 'CM_Vec2BinaryCondition': 'Vec2BinaryCondition', 'CM_Vec2ToScalarBinaryOperation': 'Vec2ToScalarBinaryOperation', 'CM_Vec2ScalarOperation': 'Vec2ScalarOperation', 'CM_Vec3UnaryOperation': 'Vec3UnaryOperation', 'CM_Vec3UnaryCondition': 'Vec3UnaryCondition', 'CM_Vec3ToScalarUnaryOperation': 'Vec3ToScalarUnaryOperation', 'CM_Vec3BinaryOperation': 'Vec3BinaryOperation', 'CM_Vec3BinaryCondition': 'Vec3BinaryCondition', 'CM_Vec3ToScalarBinaryOperation': 'Vec3ToScalarBinaryOperation', 'CM_Vec3ScalarOperation': 'Vec3ScalarOperation', 'CM_Vec4UnaryOperation': 'Vec4UnaryOperation', 'CM_Vec4UnaryCondition': 'Vec4UnaryCondition', 'CM_Vec4ToScalarUnaryOperation': 'Vec4ToScalarUnaryOperation', 'CM_Vec4BinaryOperation': 'Vec4BinaryOperation', 'CM_Vec4BinaryCondition': 'Vec4BinaryCondition', 'CM_Vec4ToScalarBinaryOperation': 'Vec4ToScalarBinaryOperation', 'CM_Vec4ScalarOperation': 'Vec4ScalarOperation', 'CM_SDXLResolution': 'SDXLResolution', 'CM_NearestSDXLResolution': 'NearestSDXLResolution', 'CM_SDXLExtendedResolution': 'SDXLExtendedResolution', 'CM_NearestSDXLExtendedResolution': 'NearestSDXLExtendedResolution'}

class ComfyMathExtension(ComfyExtension):
    async def get_node_list(self):
        return list(NODE_CLASS_MAPPINGS.values())

async def comfy_entrypoint():
    return ComfyMathExtension()
