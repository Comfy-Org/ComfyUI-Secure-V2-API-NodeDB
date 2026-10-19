from comfy_api.latest import ComfyExtension
from .nodes.data_tool import KeyValue, SerializeJsonObject, DeserializeJsonString, Calculate, ConvertNumType
from .nodes.image_crop import CropImage, SafeImageCrop
from .nodes.image_resize import ResizeImage, ResizeImageV2, ResizeImageByMaxSize, ResizeImageByMinSize, ResizeImageByRatio, AspectRatioPadder
from .nodes.light_tool import LoadImage, LoadImageFromURL, LoadImagesFromDir, ImageMaskApply, MaskToImage, ImageToMask, MaskImageToTransparent, BoundingBoxCropping, MaskBoundingBoxCropping, InvertMask, AddBackground, ImageOverlay, SimpleImageOverlay, AddBackgroundV2, IsTransparent, PhantomTankEffect, MaskContourExtractor, AdvancedSolidColorBackground, RGB2RGBA, RGBA2RGB, InputText, ShowText, ShowAnything, PreviewVideo, LoadVideo, SaveVideo, SaveToAliyunOSS, GetImageSize, ImageConcat, TextConnect, SimpleTextConnect, InputTextList, MorphologicalTF, Hex2RGB, RGB2Hex, ScaleImage, UpscaleImage, LoadMetadataFromURL, SaveMetadata, GetImagesCount, GetSideLength, TextReplace

WEB_DIRECTORY = "./web"

NODES = [KeyValue, SerializeJsonObject, DeserializeJsonString, Calculate, ConvertNumType, CropImage, SafeImageCrop, ResizeImage, ResizeImageV2, ResizeImageByMaxSize, ResizeImageByMinSize, ResizeImageByRatio, AspectRatioPadder, LoadImage, LoadImageFromURL, LoadImagesFromDir, ImageMaskApply, MaskToImage, ImageToMask, MaskImageToTransparent, BoundingBoxCropping, MaskBoundingBoxCropping, InvertMask, AddBackground, ImageOverlay, SimpleImageOverlay, AddBackgroundV2, IsTransparent, PhantomTankEffect, MaskContourExtractor, AdvancedSolidColorBackground, RGB2RGBA, RGBA2RGB, InputText, ShowText, ShowAnything, PreviewVideo, LoadVideo, SaveVideo, SaveToAliyunOSS, GetImageSize, ImageConcat, TextConnect, SimpleTextConnect, InputTextList, MorphologicalTF, Hex2RGB, RGB2Hex, ScaleImage, UpscaleImage, LoadMetadataFromURL, SaveMetadata, GetImagesCount, GetSideLength, TextReplace]

class LightToolExtension(ComfyExtension):
    async def get_node_list(self):
        return NODES

async def comfy_entrypoint():
    return LightToolExtension()
