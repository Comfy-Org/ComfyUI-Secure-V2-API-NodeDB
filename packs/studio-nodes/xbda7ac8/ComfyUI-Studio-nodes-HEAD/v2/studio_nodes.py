"""Studio3 public V2 boundary; extracted upstream compute is unchanged."""
from comfy_api.latest import io, sdk
import numpy as np
import torch
from PIL import Image


class AspectRatioImageSize(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='AspectRatioImageSize', display_name='🧩 Aspect Ratio Image Size', category='utils',
            inputs=[io.Int.Input("width", default=512, min=64, max=4096, step=8),
                io.Combo.Input("aspect_ratio", options=['1:1', '16:9', '5:4', '4:3', '3:2', '2.39:1', '21:9', '18:9', '17:9', '1.85:1'], default="1:1"),
                io.Combo.Input("direction", options=["Horizontal", "Vertical"], default="Horizontal"),
                io.String.Input("info", default='Example widths: 512, 768, 1024, 1280, 1920', multiline=True, extra_dict={"editable": False})],
            outputs=[io.Int.Output(display_name="width"), io.Int.Output(display_name="height"), io.String.Output(display_name="resolution_label")])

    @classmethod
    async def execute(cls, width, aspect_ratio, direction, info) -> io.NodeOutput:
        return io.NodeOutput(*cls().calculate_size(width, aspect_ratio, direction, info))

    def calculate_size(self, width, aspect_ratio, direction, info):
        ratios = {
            "1:1": (1, 1), "16:9": (16, 9), "5:4": (5, 4), "4:3": (4, 3),
            "3:2": (3, 2), "2.39:1": (2.39, 1), "21:9": (21, 9),
            "18:9": (18, 9), "17:9": (17, 9), "1.85:1": (1.85, 1)
        }
        w, h = ratios.get(aspect_ratio, (1, 1))
        if direction == "Vertical":
            w, h = h, w
        height = int(round(width * h / w))
        return width, height, f"{width}x{height}"



class AspectRatioResizeImage(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='AspectRatioResizeImage', display_name='🖼️ Resize to Aspect Ratio', category='image/resize',
            inputs=[io.Image.Input("image"),
                io.Int.Input("width", default=512, min=64, max=4096, step=8),
                io.Combo.Input("aspect_ratio", options=['1:1', '16:9', '5:4', '4:3', '3:2', '2.39:1', '21:9', '18:9', '17:9', '1.85:1'], default="1:1"),
                io.Combo.Input("direction", options=["Horizontal", "Vertical"], default="Horizontal"),
                io.Combo.Input("crop_method", options=["Stretch", "Crop"], default="Stretch"),
                io.String.Input("info", default='Example widths: 512, 768, 1024, 1280, 1920', multiline=True, extra_dict={"editable": False})],
            outputs=[io.Image.Output(display_name="resized_image"), io.String.Output(display_name="resolution_label")])

    @classmethod
    async def execute(cls, image, width, aspect_ratio, direction, crop_method, info) -> io.NodeOutput:
        pixels = await image.raw()
        resized, label = cls().resize_image(pixels, width, aspect_ratio, direction, crop_method, info)
        return io.NodeOutput(await sdk.ImageRef.from_tensor(resized), label)

    def resize_image(self, image, width, aspect_ratio, direction, crop_method, info):
        # Aspect ratio dictionary
        ratios = {
            "1:1": (1, 1), "16:9": (16, 9), "5:4": (5, 4), "4:3": (4, 3),
            "3:2": (3, 2), "2.39:1": (2.39, 1), "21:9": (21, 9),
            "18:9": (18, 9), "17:9": (17, 9), "1.85:1": (1.85, 1)
        }

        w_ratio, h_ratio = ratios.get(aspect_ratio, (1, 1))
        if direction == "Vertical":
            w_ratio, h_ratio = h_ratio, w_ratio

        target_height = int(round(width * h_ratio / w_ratio))
        target_width = width

        # ComfyUI image format is BHWC (batch, height, width, channels)
        # Extract the first image from the batch
        image_tensor = image[0]  # Shape: (H, W, C)
        
        # Convert tensor to numpy array (already in HWC format)
        image_np = image_tensor.cpu().numpy()
        
        # Convert from [0,1] float to [0,255] uint8
        image_np = np.clip(image_np * 255.0, 0, 255).astype(np.uint8)

        pil_image = Image.fromarray(image_np)
        original_width, original_height = pil_image.size

        if crop_method == "Crop":
            # Calculate the aspect ratio of the original image
            original_aspect_ratio = original_width / original_height
            target_aspect_ratio = target_width / target_height

            if original_aspect_ratio > target_aspect_ratio:
                # Original is wider than target, need to crop width to match target aspect ratio
                # Calculate new width based on original height and target aspect ratio
                new_width = int(original_height * target_aspect_ratio)
                left = (original_width - new_width) // 2
                right = left + new_width
                cropped_image = pil_image.crop((left, 0, right, original_height))
            else:
                # Original is taller than target, need to crop height to match target aspect ratio
                # Calculate new height based on original width and target aspect ratio
                new_height = int(original_width / target_aspect_ratio)
                top = (original_height - new_height) // 2
                bottom = top + new_height
                cropped_image = pil_image.crop((0, top, original_width, bottom))
            
            # Now resize the cropped image to the target dimensions without stretching
            pil_image = cropped_image.resize((target_width, target_height), Image.LANCZOS)
        else: # Stretch
            pil_image = pil_image.resize((target_width, target_height), Image.LANCZOS)

        # Convert back to tensor format for ComfyUI (BHWC)
        resized_np = np.array(pil_image).astype(np.float32) / 255.0
        
        # Add batch dimension back: (H, W, C) -> (1, H, W, C)
        resized_tensor = torch.from_numpy(resized_np).unsqueeze(0)

        return (resized_tensor, f"{target_width}x{target_height}")



class MarkdownModelNote(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MarkdownModelNote', display_name='📄 Markdown Link Generator', category='utils',
            inputs=[io.String.Input("url", default=""), io.String.Input("filename", default="model.safetensors"), io.String.Input("folder", default="App\\ComfyUI\\models\\clip")],
            outputs=[io.String.Output(display_name="markdown_note")])

    @classmethod
    async def execute(cls, url, filename, folder) -> io.NodeOutput:
        return io.NodeOutput(*cls().create_markdown(url, filename, folder))

    def create_markdown(self, url, filename, folder):
        note = f"""### Model: [{filename}]({url})  
**Output folder:**  
`{folder}`

---"""
        return (note,)


NODE_CLASS_MAPPINGS = {
    'AspectRatioImageSize': AspectRatioImageSize,
    'AspectRatioResizeImage': AspectRatioResizeImage,
    'MarkdownModelNote': MarkdownModelNote,
}

NODE_DISPLAY_NAME_MAPPINGS = {'AspectRatioImageSize': '🧩 Aspect Ratio Image Size', 'AspectRatioResizeImage': '🖼️ Resize to Aspect Ratio', 'MarkdownModelNote': '📄 Markdown Link Generator'}
