from typing_extensions import override
from comfy_api.latest import ComfyExtension, io
from .nodes_math import (
    MathAdd, MathSubtract, MathMultiply, MathDivide, MathPower,
    MathFloor, MathCeil, MathRound, MathModulo, MathAbs, MathSqrt,
    MathSin, MathCos, MathTan, MathMin, MathMax, MathClamp,
    MathNumberConvert, StringToNumber, NumberToString, MathCompare,
    MathOperation, MathAspectRatio
)
from .nodes_logic import (
    LogicIF, LogicAND, LogicOR, LogicNOT, LogicXOR
)

class LogicMathExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            MathAdd,
            MathSubtract,
            MathMultiply,
            MathDivide,
            MathPower,
            MathFloor,
            MathCeil,
            MathRound,
            MathModulo,
            MathAbs,
            MathSqrt,
            MathSin,
            MathCos,
            MathTan,
            MathMin,
            MathMax,
            MathClamp,
            MathNumberConvert,
            StringToNumber,
            NumberToString,
            MathCompare,
            MathOperation,
            MathAspectRatio,
            LogicIF,
            LogicAND,
            LogicOR,
            LogicNOT,
            LogicXOR,
        ]

async def comfy_entrypoint() -> LogicMathExtension:
    return LogicMathExtension()

# For backward compatibility with older ComfyUI versions if needed, 
# although V3 usually expects the entrypoint.
# We don't need NODE_CLASS_MAPPINGS here because V3 uses the extension system.
