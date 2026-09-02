"""Secure Nodes V2 entrypoint for Derfuu's simple/modded nodes."""

from .metadata_nodes import ConditioningAreaScale_Ratio, ShowDataDebug
from .scalar_nodes import (
    ABSNode,
    AsDynamicPromptsStringNode,
    CeilNode,
    CosNode,
    DivideNode,
    FloatNode,
    FloorNode,
    Int2Float,
    IntegerNode,
    LogicNode,
    MultilineStringNode,
    MultiplyNode,
    PowNode,
    RandomValue,
    SearchInText,
    SinNode,
    SquareRootNode,
    StringConcat,
    StringNode,
    StringReplace,
    SubtractNode,
    SumNode,
    tgNode,
)
from .scale_nodes import (
    ImageScale_Ratio,
    ImageScale_Side,
    LatentScale_Ratio,
    LatentScale_Side,
)
from .size_nodes import GetImageSize, GetLatentSize


NODE_CLASS_MAPPINGS = {
    "DF_Float": FloatNode,
    "DF_Integer": IntegerNode,
    "DF_Text": StringNode,
    "DF_Text_Box": MultilineStringNode,
    "DF_DynamicPrompts_Text_Box": AsDynamicPromptsStringNode,
    "DF_String_Concatenate": StringConcat,
    "DF_String_Replace": StringReplace,
    "DF_Search_In_Text": SearchInText,
    "DF_To_text_(Debug)": ShowDataDebug,
    "DF_Random": RandomValue,
    "DF_Int_to_Float": Int2Float,
    "DF_Ceil": CeilNode,
    "DF_Floor": FloorNode,
    "DF_Absolute_value": ABSNode,
    "DF_Get_latent_size": GetLatentSize,
    "DF_Get_image_size": GetImageSize,
    "DF_Sum": SumNode,
    "DF_Subtract": SubtractNode,
    "DF_Multiply": MultiplyNode,
    "DF_Divide": DivideNode,
    "DF_Power": PowNode,
    "DF_Square_root": SquareRootNode,
    "DF_Sinus": SinNode,
    "DF_Cosines": CosNode,
    "DF_Tangent": tgNode,
    "DF_Logic_node": LogicNode,
    "DF_Latent_Scale_by_ratio": LatentScale_Ratio,
    "DF_Latent_Scale_to_side": LatentScale_Side,
    "DF_Image_scale_by_ratio": ImageScale_Ratio,
    "DF_Image_scale_to_side": ImageScale_Side,
    "DF_Conditioning_area_scale_by_ratio": ConditioningAreaScale_Ratio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    key: key.replace("DF_", "").replace("_", " ")
    for key in NODE_CLASS_MAPPINGS
}

WEB_DIRECTORY = "./scripts"

__all__ = [
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "WEB_DIRECTORY",
]
