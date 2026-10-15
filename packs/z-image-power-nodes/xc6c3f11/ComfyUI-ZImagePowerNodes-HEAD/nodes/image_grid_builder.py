"""
File    : image_grid_builder.py
Purpose : No to generate a grid of images.
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Mar 28, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

  ComfyUI V3 schema documentation can be found here:
  - https://docs.comfy.org/custom-nodes/v3_migration

_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
import torch
import numpy as np
from PIL                 import Image, ImageDraw
from comfy_api.latest    import io
from .core.helpers_text  import TextBox, load_font, write_text_in_box
if hasattr(Image, 'Resampling'):  LANCZOS = Image.Resampling.LANCZOS
else:                             LANCZOS = Image.LANCZOS # type: ignore


class ImageGridBuilder(io.ComfyNode):
    xTITLE         = "Image Grid Builder"
    xDESCRIPTION   = "Generate a grid containing all images passed as input. "
    xCATEGORY      = ""
    xCOMFY_NODE_ID = ""
    xDEPRECATED    = False

    @classmethod
    def define_schema(cls):
        autogrow_template = io.Autogrow.TemplatePrefix(io.Image.Input("image"), prefix="image", min=2, max=50)
        return io.Schema(
            display_name  = cls.xTITLE,
            description   = cls.xDESCRIPTION,
            category      = cls.xCATEGORY,
            node_id       = cls.xCOMFY_NODE_ID,
            is_deprecated = cls.xDEPRECATED,
            inputs=[
                io.Autogrow.Input("images", template=autogrow_template
                ),
                io.Combo.Input("banner", default="none",
                    options=["none", "header", "footer"],
                    tooltip="Choose to add a header, footer, or no banner to the grid. ",
                ),
                io.Int.Input("banner_height", default=144, min=0, max=2048, step=4,
                    tooltip="The height of the banner in pixels. "
                ),
                io.String.Input("text", placeholder="banner text", multiline=True,
                    tooltip="The text to be displayed in the header or footer. ",
                ),
                io.String.Input("text_color", default="#555",
                    tooltip="The color of the text in the banner, expressed in hexadecimal format (e.g., #FFFFFF for white). ",
                ),
                io.String.Input("lines_color", default="#000",
                    tooltip="The color of the lines in the grid, expressed in hexadecimal format (e.g., #000000 for black). ",
                ),
                io.String.Input("banner_color", default="#FFF",
                    tooltip="The background color of the banner, expressed in hexadecimal format (e.g., #FFFFFF for white). ",
                ),
                io.Combo.Input("font_name", default="open_sans",
                    options=["roboto_slab", "open_sans"],
                    tooltip="The font to be used for the banner text. ",
                ),
                io.Int.Input("font_size", default=64, min=8, max=256, step=1,
                    tooltip="Size of the font used for the banner text. ",
                ),
                io.Int.Input("columns", default=0, min=0, max=64,
                    tooltip="The number of columns in the grid. Set to 0 for unlimited columns, arranging images horizontally. ",
                ),
                io.Float.Input("image_scale", default=0.5, min=0.0, max=1.0, step=0.1,
                    tooltip="Adjust the scale of the images in the grid. ",
                ),
                io.Int.Input("image_spacing", default=8, min=0, max=256,
                    tooltip="The spacing between images in the grid. ",
                ),
            ],
            outputs=[
                io.Image.Output(
                    tooltip="Output image with the grid and the optional banner text. ",
                )
            ]
        )

    @classmethod
    def execute(cls,
                images          : io.Autogrow.Type,
                banner          : str,
                banner_height   : int,
                text            : str,
                text_color      : str,
                lines_color     : str,
                banner_color    : str,
                font_name       : str,
                font_size       : int,
                columns         : int,
                image_scale     : float,
                image_spacing   : int,
                ) -> io.NodeOutput:
        numpy_images_dtype = np.float16
        spacing = image_spacing

        # build the list of tuples (tensor, index) and check that at least one image exists
        tensor_index_list = build_tensor_index_list( list(images.values()) )
        if not tensor_index_list:
            return io.NodeOutput( images )

        # use the first tensor (image) as base to know the device and data type
        device = tensor_index_list[0][0].device
        dtype  = tensor_index_list[0][0].dtype

        # calculate the number of columns and rows of the grid
        if columns<=0:
            columns = len( tensor_index_list )
        rows = ((len( tensor_index_list ) - 1 ) // columns) + 1


        cell_height, cell_width, _ = tensor_index_list[0][0].shape[-3:]
        cell_height = int( cell_height * image_scale )
        cell_width  = int( cell_width  * image_scale )
        output_width  = columns * cell_width  + (columns+1) * spacing
        output_height = rows    * cell_height + (rows+1)    * spacing

        if banner == "none":
            banner_position = -1
            grid_position   = 0
            output_height  += 0

        elif banner == "header":
            banner_position = 0
            grid_position   = banner_height
            output_height  += banner_height

        elif banner == "footer":
            grid_position   = 0
            banner_position = output_height
            output_height  += banner_height

        # create a large enough image and draw the grid with all its images
        output_image = Image.new("RGB", (output_width, output_height), color=lines_color)
        draw_grid(output_image, tensor_index_list=tensor_index_list,
                  columns   = columns,
                  rows      = rows,
                  step      = (cell_width+spacing, cell_height+spacing),
                  offset    = (spacing, grid_position + spacing),
                  cell_size = (cell_width, cell_height),
                  )

        # write the banner, which can function as a header or footer
        if banner_position>=0:
            banner_box = TextBox(0, banner_position, output_width, banner_position+banner_height)
            font = load_font(font_name, int(font_size))
            if font:
                write_text_in_box(output_image, text, banner_box,
                                  color      = text_color,
                                  back_color = banner_color,
                                  font       = font,
                                  padding    = 6,
                                  align      = "center")

        # return `output_image` as a pytorch tensor
        numpy_image = np.array(output_image.convert("RGB"), dtype=numpy_images_dtype) / 255.0
        return io.NodeOutput( torch.from_numpy(numpy_image[None, ...]).to(device=device, dtype=dtype) )



def build_tensor_index_list(image_list: list[torch.Tensor]) -> list[tuple[torch.Tensor, int]]:
    """
    Build a list of tuples that map every image in `image_list` to its
    owning tensor and the intra-tensor index.

    Args:
        image_list : A list of 4-D tensors whose first dimension is the batch size.

    Returns:
        A list of tuples `(tensor, index)` where `tensor` is the original
        tensor that contains the image and `index` is the position of the
        image inside that tensor's batch dimension.
    """
    index_list: list[tuple[torch.Tensor, int]] = []
    for tensor in image_list:
        batch_count = tensor.shape[0]
        for index in range(batch_count):
            index_list.append((tensor, index))
    return index_list



def draw_grid(output_image     : Image.Image,
              tensor_index_list: list[tuple[torch.Tensor, int]],
              *,
              columns  : int,
              rows     : int,
              offset   : tuple[int,int],
              step     : tuple[int,int],
              cell_size: tuple[int,int],
              ):
    draw = ImageDraw.Draw(output_image)

    for column in range(columns):
        for row in range(rows):
            position = row * columns + column
            if position >= len(tensor_index_list):
                break

            # convierte el tensor en la imagen a ubicar dentro de la celda
            tensor, i = tensor_index_list[ position ]
            array = (tensor[i].cpu().numpy() * 255).clip(0, 255).astype(np.uint8)

            # resize to exact cell size and paste
            cell_image = Image.fromarray(array).resize(cell_size, LANCZOS)
            x = offset[0] + column * step[0]
            y = offset[1] + row    * step[1]
            output_image.paste(cell_image, (x, y))

