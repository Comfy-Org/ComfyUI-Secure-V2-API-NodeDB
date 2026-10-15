"""Four pack-owned image/video algorithms with bounded raw pixels only."""
import math
import torch
from comfy_api.latest import io,sdk
from . import _algorithm as alg

CONTRACT = {
  "EmptyImageBBTools": {
    "inputs": {
      "width": [
        "INT",
        {
          "default": 512,
          "min": 8,
          "max": 16384,
          "step": 8
        }
      ],
      "height": [
        "INT",
        {
          "default": 512,
          "min": 8,
          "max": 16384,
          "step": 8
        }
      ],
      "batch": [
        "INT",
        {
          "default": 1,
          "min": 1,
          "max": 10000,
          "step": 1
        }
      ],
      "red": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 255,
          "step": 1
        }
      ],
      "green": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 255,
          "step": 1
        }
      ],
      "blue": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 255,
          "step": 1
        }
      ],
      "alpha": [
        "FLOAT",
        {
          "default": 0,
          "min": 0,
          "max": 1,
          "step": 0.01
        }
      ]
    },
    "outputs": [
      "IMAGE",
      "MASK",
      "IMAGE"
    ],
    "output_names": [
      "Image RGB",
      "Alpha as Mask",
      "Image RGBA"
    ],
    "display_name": "🅱🅱空白图片|Empty Image",
    "category": "🅱🅱Tools"
  },
  "ReplaceColorBBTools": {
    "inputs": {
      "image": [
        "IMAGE"
      ],
      "target_red": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 255,
          "step": 1
        }
      ],
      "target_green": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 255,
          "step": 1
        }
      ],
      "target_blue": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 255,
          "step": 1
        }
      ],
      "replace_red": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 255,
          "step": 1
        }
      ],
      "replace_green": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 255,
          "step": 1
        }
      ],
      "replace_blue": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 255,
          "step": 1
        }
      ],
      "threshold": [
        "FLOAT",
        {
          "default": 0,
          "min": 0,
          "max": 1,
          "step": 0.01
        }
      ]
    },
    "outputs": [
      "IMAGE"
    ],
    "output_names": [
      "IMAGE"
    ],
    "display_name": "🅱🅱色彩替换|Replace Color",
    "category": "🅱🅱Tools"
  },
  "VideosConcatWithCrossFadeBBTools": {
    "inputs": {
      "images1": [
        "IMAGE"
      ],
      "images2": [
        "IMAGE"
      ],
      "cross_fade_frames": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 10000,
          "step": 1,
          "display": "number"
        }
      ]
    },
    "outputs": [
      "IMAGE"
    ],
    "output_names": [
      "IMAGE"
    ],
    "display_name": "🅱🅱视频淡入拼接|Videos Concat with CrossFade",
    "category": "image"
  },
  "VideosConcatWithCrossFadeLoopbackBBTools": {
    "inputs": {
      "images1": [
        "IMAGE"
      ],
      "images2": [
        "IMAGE"
      ],
      "cross_fade_frames1": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 10000,
          "step": 1,
          "display": "number"
        }
      ],
      "cross_fade_frames2": [
        "INT",
        {
          "default": 0,
          "min": 0,
          "max": 10000,
          "step": 1,
          "display": "number"
        }
      ]
    },
    "outputs": [
      "IMAGE"
    ],
    "output_names": [
      "IMAGE"
    ],
    "display_name": "🅱🅱循环视频淡入拼接|Loopback Videos Concat with CrossFade",
    "category": "image"
  }
}
MAX_INPUT_BYTES=64*1024*1024
MAX_OUTPUT_BYTES=64*1024*1024
MAX_WORK_BYTES=192*1024*1024

def schema(node_id):
    row=CONTRACT[node_id];inputs=[]
    for name,spec in row["inputs"].items():
        options=dict(spec[1]) if len(spec)>1 else {}
        if "display" in options:
            options["display_mode"]=io.NumberDisplay(options.pop("display"))
        inputs.append(getattr(io,spec[0].title()).Input(name,**options))
    outputs=[]
    for typ,name in zip(row["outputs"],row["output_names"],strict=True):
        outputs.append(getattr(io,typ.title()).Output(display_name=name) if name!=typ else getattr(io,typ.title()).Output())
    return io.Schema(node_id=node_id,display_name=row["display_name"],category=row["category"],inputs=inputs,outputs=outputs)

def integer(value,name,limit=10000):
    if isinstance(value,bool) or not isinstance(value,int) or abs(value)>limit:
        raise ValueError(name+" must be a bounded integer")

def image_bounds(images):
    total=0
    for image in images:
        if not isinstance(image,torch.Tensor) or image.layout!=torch.strided or image.ndim!=4:
            raise ValueError("dense BHWC images required")
        if image.shape[0]>64 or image.shape[1]>4096 or image.shape[2]>4096 or image.shape[3]>8:
            raise ValueError("image dimensions exceed bounds")
        total+=max(image.numel()*image.element_size(),image.untyped_storage().nbytes())
    if total>MAX_INPUT_BYTES:raise ValueError("input byte budget exceeded")
    return total

def preflight_video(a,b):
    total=image_bounds((a,b))
    output=(a.shape[0]+b.shape[0])*a.shape[1]*a.shape[2]*max(a.shape[3],b.shape[3])*max(4,a.element_size(),b.element_size())
    resized=b.shape[0]*a.shape[1]*a.shape[2]*b.shape[3]*max(4,b.element_size())
    if output>MAX_OUTPUT_BYTES or total+resized+4*output>MAX_WORK_BYTES:
        raise ValueError("video output/workspace byte budget exceeded")

def loopback_zero(a,b,n,m):
    # Approved empty-transition repair, no positive-branch formula changes.
    if a.shape[1:]!=b.shape[1:]:
        raise ValueError("crossfadevideosloopback: 拼接图片类型或尺寸不一致\nImage Type or Dimension Mismatch")
    if n>a.shape[0] or n>b.shape[0] or m>a.shape[0] or m>b.shape[0]:
        raise ValueError("crossfadevideosloopback: 拼接图片数目应大于过渡数目\nVideo Length should be longer than CrossLength")
    if n+m>min(a.shape[0],b.shape[0]):
        raise ValueError("crossfadevideosloopback: 两组过渡帧数量之和大于输入图片数量\nVideo Length should be longer than the sum of Cross Lengths")
    if n<0 or m<0:
        # Preserve source negative-count failures rather than invent slicing.
        return alg.cross_fade_videos_loopback(a,b,n,m)
    if n==0 and m==0:return torch.cat((a,b),dim=0)
    if m==0:
        return alg.cross_fade_videos(a,b,n)
    # The second end transition wraps b into a and precedes central a then b.
    weights=[(i+1)/(m+1) for i in range(m)]
    blend=torch.cat([b[[-m+i],]*(1-alpha)+a[[i],]*alpha for i,alpha in enumerate(weights)],dim=0)
    return torch.cat((blend,a[m:],b[:-m]),dim=0)

class EmptyImageSecure(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=("raw",)
    @classmethod
    def define_schema(cls):return schema("EmptyImageBBTools")
    @classmethod
    def execute(cls,width,height,batch,red,green,blue,alpha):
        for name,value in (("width",width),("height",height),("batch",batch),("red",red),("green",green),("blue",blue)):integer(value,name,16384)
        if isinstance(alpha,bool) or not isinstance(alpha,(int,float)) or not math.isfinite(alpha) or abs(alpha)>10000:raise ValueError("finite bounded alpha required")
        if width>4096 or height>4096 or batch>64:raise ValueError("dimensions exceed bounds")
        count=max(0,width)*max(0,height)*max(0,batch)
        if count*32>MAX_OUTPUT_BYTES or count*64>MAX_WORK_BYTES:raise ValueError("empty output/workspace budget exceeded")
        result=alg.emptyimage(width,height,batch,(red,green,blue,alpha))
        return io.NodeOutput(result["RGB"],result["MASK"],result["RGBA"])

class ReplaceColorSecure(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=("raw",)
    @classmethod
    def define_schema(cls):return schema("ReplaceColorBBTools")
    @classmethod
    def execute(cls,image,target_red,target_green,target_blue,replace_red,replace_green,replace_blue,threshold):
        total=image_bounds((image,))
        for name,value in (("target_red",target_red),("target_green",target_green),("target_blue",target_blue),("replace_red",replace_red),("replace_green",replace_green),("replace_blue",replace_blue)):integer(value,name)
        if isinstance(threshold,bool) or not isinstance(threshold,(int,float)) or not math.isfinite(threshold) or abs(threshold)>10000:raise ValueError("finite threshold required")
        pixels=image.shape[0]*image.shape[1]*image.shape[2]
        if pixels*max(1,image.shape[3])*4>MAX_OUTPUT_BYTES or total+pixels*320>MAX_WORK_BYTES:raise ValueError("replace output/workspace budget exceeded")
        target_color=(target_red,target_green,target_blue);replace_color=(replace_red,replace_green,replace_blue)
        img_list=[alg.tensor2pil(frame) for frame in image]
        replaced_list=[alg.convert_color(img,target_color,replace_color,threshold) for img in img_list]
        tensor_list=[alg.pil2tensor(img) for img in replaced_list]
        return io.NodeOutput(torch.stack([tensor.squeeze() for tensor in tensor_list]))

class CrossFadeSecure(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=("raw",)
    @classmethod
    def define_schema(cls):return schema("VideosConcatWithCrossFadeBBTools")
    @classmethod
    async def execute(cls,images1,images2,cross_fade_frames):
        integer(cross_fade_frames,"cross_fade_frames")
        a=await images1.raw();b=await images2.raw()
        preflight_video(a,b)
        if a.shape[1:]!=b.shape[1:]:
            b=await (await images2.resize(a.shape[2],a.shape[1],method="bilinear",crop="center")).raw()
        if cross_fade_frames>a.shape[0] or cross_fade_frames>b.shape[0]:
            raise ValueError("图片数量必须大于等于过渡帧数量\nimage lengths must be larger than cross_fade_frames")
        if cross_fade_frames==0:
            # Source helper shape checks precede the approved zero branch.
            if a.ndim!=b.ndim:raise ValueError("ImageType Mismatch")
            if a[[0],].shape!=b[[0],].shape:raise ValueError("ImageSize Mismatch")
            result=torch.cat((a,b),dim=0)
        else:result=alg.cross_fade_videos(a,b,cross_fade_frames)
        return io.NodeOutput(await sdk.TensorRef.from_value(result))

class CrossFadeLoopbackSecure(io.ComfyNode):
    SDK_REFS=True
    SDK_PERMISSIONS=("raw",)
    @classmethod
    def define_schema(cls):return schema("VideosConcatWithCrossFadeLoopbackBBTools")
    @classmethod
    async def execute(cls,images1,images2,cross_fade_frames1,cross_fade_frames2):
        integer(cross_fade_frames1,"cross_fade_frames1");integer(cross_fade_frames2,"cross_fade_frames2")
        a=await images1.raw();b=await images2.raw()
        preflight_video(a,b)
        if a.shape[1:]!=b.shape[1:]:
            b=await (await images2.resize(a.shape[2],a.shape[1],method="bilinear",crop="center")).raw()
        if cross_fade_frames1==0 or cross_fade_frames2==0:
            result=loopback_zero(a,b,cross_fade_frames1,cross_fade_frames2)
        else:result=alg.cross_fade_videos_loopback(a,b,cross_fade_frames1,cross_fade_frames2)
        return io.NodeOutput(await sdk.TensorRef.from_value(result))

NODE_CLASS_MAPPINGS={"EmptyImageBBTools":EmptyImageSecure,"ReplaceColorBBTools":ReplaceColorSecure,"VideosConcatWithCrossFadeBBTools":CrossFadeSecure,"VideosConcatWithCrossFadeLoopbackBBTools":CrossFadeLoopbackSecure}
NODE_DISPLAY_NAME_MAPPINGS={key:row["display_name"] for key,row in CONTRACT.items()}
