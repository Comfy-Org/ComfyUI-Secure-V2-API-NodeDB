"""Pinned first-frame metadata/pixel parser; managed bytes supplied by caller."""
import io
import json
import re
from PIL import Image, ImageOps
import numpy as np
import torch
from .._bounds import image_work, text as text_bound

def parse_image(data,filename):
    im=Image.open(io.BytesIO(data))
    image_work(None,*im.size)
    for value in im.info.values():
        if isinstance(value,str):text_bound(value)
    # Start ai-info.py section, with no exif
    def type_changer(value):
        if value.isnumeric():
            return int(value)
        else:
            return value

    im.load()

    prompt = {}
    if "prompt" in im.info.keys():
        # comfyui, workflow is also available but we aren't getting that today
        # prompt = {}
        prompt.update({"prompt": json.loads(im.info["prompt"])})
    else:
        # automatic111, gosh this is a mess.
        if "parameters" in im.info.keys():
            parameters = im.info["parameters"]
            prompt = {"parameters": {}}
            parameters = re.split(
                "(Negative prompt): |(Negative Template): |(Template): |(ControlNet): |\n",
                parameters,
            )

            # removes None and new lines
            parameters_clean_none = []
            for i in range(0, len(parameters)):
                if parameters[i] is None:
                    pass
                elif parameters[i] == "":
                    pass
                else:
                    parameters_clean_none.append(parameters[i])
            parameters = parameters_clean_none

            # settings field
            parameters_settings = {}
            for i in range(0, len(parameters)):
                if parameters[i].split(":", 1)[0] == "Steps":
                    parameters[i] = re.split(", ", parameters[i])
                    for k in parameters[i]:
                        k = k.split(": ", 1)
                        if len(k) == 2:
                            k[1] = type_changer(k[1])

                            # makes "Size" : "(widthxheight)" into two keys
                            if k[0] == "Size":
                                k[1] = k[1].split("x")
                                for s in range(0, len(k[1])):
                                    k[1][s] = type_changer(k[1][s])
                                parameters_settings.update(
                                    {"width": k[1][0]})
                                parameters_settings.update(
                                    {"height": k[1][1]})

                            else:
                                parameters_settings.update({k[0]: k[1]})

                    parameters[i] = parameters_settings

            # builder
            parameters_built = {}
            for i in range(0, len(parameters)):
                match parameters[i]:
                    case "Negative prompt":
                        parameters_built.update(
                            {parameters[i]: parameters[i + 1]})
                    case "Negative Template":
                        parameters_built.update(
                            {parameters[i]: parameters[i + 1]})
                    case "Template":
                        parameters_built.update(
                            {parameters[i]: parameters[i + 1]})
                    case "ControlNet":
                        parameters_built.update(
                            {parameters[i]: parameters[i + 1]})
                    case dict():
                        parameters_built.update(parameters[i])
                    case _:
                        if i == 0:
                            parameters_built.update(
                                {"Positive prompt": parameters[i]}
                            )
                        pass

            prompt["parameters"] = parameters_built
    if type(prompt) is dict:
        prompt = json.dumps(prompt, indent=2)

    elif type(prompt) is str:
        prompt = json.dumps(json.loads(prompt), indent=2)

    # end section

    im = ImageOps.exif_transpose(im)
    image = im.convert("RGB")
    image = np.array(image).astype(np.float32) / 255.0
    image = torch.from_numpy(image)[None,]
    shape = image.shape
    width = shape[2]
    height = shape[1]
    if "A" in im.getbands():
        mask = np.array(im.getchannel("A")).astype(np.float32) / 255.0
        mask = 1.0 - torch.from_numpy(mask)
    else:
        mask = torch.zeros((64, 64), dtype=torch.float32, device="cpu")

    return image,mask.unsqueeze(0),None,filename,str(prompt),width,height
