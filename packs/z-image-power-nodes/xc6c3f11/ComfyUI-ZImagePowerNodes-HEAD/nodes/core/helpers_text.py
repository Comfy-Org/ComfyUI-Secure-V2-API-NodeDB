"""
File    : helpers_text.py
Purpose : Helpers functions for text handling in PIL images
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Mar 27, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
from PIL     import ImageDraw, ImageFont, Image
from pathlib import Path
Number = int | float


class TextBox(tuple):
    """
    Immutable 2-D axis-aligned rectangle for text boxes.

    Each `TextBox` is stored as a 4-element tuple `(left, top, right, bottom)`
    and exposes convenient properties and helpers for everyday geometry tasks
    (translation, resizing, anchoring, centering, …).
    All numeric values are preserved exactly as given; no rounding is performed
    internally.

    Args:
        left   : Left edge coordinate.
        top    : Top edge coordinate.
        right  : Right edge coordinate. Must be greater than or equal to `left`.
        bottom : Bottom edge coordinate. Must be greater than or equal to `top`.
    OR:
        coordinates : A single 4-element tuple containing (left, top, right, bottom).

    Attributes & Properties:
        left   : Left edge coordinate.
        top    : Top edge coordinate.
        right  : Right edge coordinate.
        bottom : Bottom edge coordinate.
        width  : The width of the box, calculated as `right - left`.
        height : The height of the box, calculated as `bottom - top`.
        center : The center point of the box, represented as a tuple (cx, cy).

    Examples:
    >>> box = TextBox(5, 100, 35, 120)
    >>> box.width
    30
    >>> box.center
    (20, 110)
    """

    def __new__(cls,
                left_or_tuple  : Number | tuple[Number, Number, Number, Number],
                top            : Number | None = None,
                right          : Number | None = None,
                bottom         : Number | None = None,
                ):
        # allow Box((l, t, r, b))
        if isinstance(left_or_tuple, (tuple, list)) and len(left_or_tuple) == 4:
            left, top, right, bottom = left_or_tuple
        elif isinstance(left_or_tuple, Number):
            left = left_or_tuple

        if top is None or right is None or bottom is None:
            raise ValueError("Either provide four numeric arguments or a single 4-element tuple/list.")

        if right < left:
            raise ValueError("right edge must be >= left edge")
        if bottom < top:
            raise ValueError("bottom edge must be >= top edge")

        return super().__new__(cls, (left, top, right, bottom))


    #====================== TextBox: FACTORY HELPERS =======================#

    @classmethod
    def bounding_for_text(cls,
                          text: str,
                          font: ImageFont.FreeTypeFont
                          ) -> "TextBox":
        """
        Returns the bounding box of a single-line string rendered with `font`.
        """
        return cls(font.getbbox(text))


    @classmethod
    def multiline_textbbox(cls,
                           draw   : ImageDraw.ImageDraw,
                           xy     : tuple[Number, Number],
                           text   : str,
                           font   : ImageFont.FreeTypeFont,
                           anchor : str | None = None,
                           spacing: float      = 4,
                           align  : str        = "left",
                           ) -> "TextBox":
        """
        Returns the bounding box of multi-line text as measured by Pillow.
        """
        return cls(
            draw.multiline_textbbox(
                xy, text, font=font, anchor=anchor, spacing=spacing, align=align
            )
        )

    @classmethod
    def container_for_text(cls,
                           text: str,
                           font: ImageFont.FreeTypeFont
                           ) -> "TextBox":
        """
        Returns the minimal box that can contain *text* rendered with *font*.
        Origin is placed at (0, 0).
        """
        ascent, descent = font.getmetrics()
        width = font.getlength(text)
        return cls(0, 0, width, ascent + descent)


    #========================= TextBox: PROPERTIES =========================#

    @property
    def left(self) -> Number:
        return self[0]

    @property
    def top(self) -> Number:
        return self[1]

    @property
    def right(self) -> Number:
        return self[2]

    @property
    def bottom(self) -> Number:
        return self[3]

    @property
    def width(self) -> Number:
        return self.right - self.left

    @property
    def height(self) -> Number:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[Number, Number]:
        return ((self.left + self.right) * 0.5, (self.top + self.bottom) * 0.5)


    #===================== TextBox: GEOMETRIC HELPERS ======================#

    def get_size(self) -> tuple[Number, Number]:
        """Return (width, height)."""
        return (self.width, self.height)


    def get_pos(self, anchor: str | None = None) -> tuple[Number, Number]:
        """
        Return the coordinates of a specific anchor point.

        Args:
            anchor : Optional position name of the anchor point (top-left if not specified).
                - 'lt' : top-left corner
                - 'rt' : top-right corner
                - 'lb' : bottom-left corner
                - 'rb' : bottom-right corner
                - 'c'` : center
        Returns:
            A tuple of (x, y) coordinates for the requested anchor.
        """
        if anchor is None or anchor == "lt" or anchor == "tl":
            return (self.left, self.top)
        if anchor == "rt" or anchor == "tr":
            return (self.right, self.top)
        if anchor == "lb" or anchor == "bl":
            return (self.left, self.bottom)
        if anchor == "rb" or anchor == "br":
            return (self.right, self.bottom)
        if anchor == "c":
            return self.center
        raise ValueError(
            f"Unknown anchor {anchor!r}.  Valid: 'lt', 'rt', 'lb', 'rb', 'c'."
        )


    def with_size(self, width: Number, height: Number, anchor: str | None = None) -> "TextBox":
        """Return a new box with the same top-left corner but the given size."""
        anchor = (anchor or "lt").lower()
        if anchor not in {"lt", "tl", "rt", "tr", "lb", "bl", "rb", "br", "c"}:
            raise ValueError(f"Unknown anchor {anchor!r}.  Valid: 'lt', 'rt', 'lb', 'rb', 'c'.")

        new_left = self.left
        new_top  = self.top
        if 'r' in anchor:
            new_left = self.right - width
        if 'b' in anchor:
            new_top = self.bottom - height
        if anchor == 'c':
            center = self.center
            new_left = center[0] - (width /2)
            new_top  = center[1] - (height/2)

        return TextBox(new_left, new_top, new_left + width, new_top + height)


    def with_pos(self, left: Number, top: Number) -> "TextBox":
        """Return a new box with the same size but the given top-left position."""
        width, height = self.get_size()
        return TextBox(left, top, left + width, top + height)

    def moved_to(self,
        x: Number | tuple[Number, Number],
        y: Number | None = None,
        anchor: str | None = None,
    ) -> "TextBox":
        """
        Move the box so that *anchor* lands on (*x*, *y*).

        If *x* is a tuple it is unpacked as (x, y).
        """
        if isinstance(x, tuple):
            x, y = x
        if y is None:
            raise ValueError("y coordinate required when x is not a tuple")
        current_x, current_y = self.get_pos(anchor)
        return self.moved_by(x - current_x, y - current_y)


    def moved_by(self, dx: Number, dy: Number) -> "TextBox":
        """Returns a new box with the same size but moved by (dx, dy)."""
        return TextBox(self.left+dx, self.top+dy, self.right+dx, self.bottom+dy)


    def centered_in(self, container: "TextBox") -> "TextBox":
        """Returns a copy of this box centered inside `container`."""
        offset_x = (container.left + container.right - self.left - self.right ) * 0.5
        offset_y = (container.top + container.bottom - self.top  - self.bottom) * 0.5
        return self.moved_by(offset_x, offset_y)


    def shrunken(self, dx: Number, dy: Number) -> "TextBox":
        """
        Returns a box whose edges are pulled inward.

        This method pulls the edges of the box inward by `dx` (horizontal)
        and `dy` (vertical).  Negative values grow the box.
        """
        return TextBox(self.left+dx, self.top+dy, self.right-dx, self.bottom-dy)


    #======================= TextBox: REPRESENTATION =======================#

    def __repr__(self) -> str:
        return (
            f"Box(left={self.left}, top={self.top}, "
            f"right={self.right}, bottom={self.bottom})"
        )



#================================== FONTS ==================================#

def load_system_font(font_size: int) -> ImageFont.FreeTypeFont | None:
    fallback_fonts = ["arial.ttf", "DejaVuSans.ttf", "Verdana.ttf", "Helvetica.ttc"]
    for font_name in fallback_fonts:
        try:
            return ImageFont.truetype(font_name, font_size)
        except:
            continue
    return None

def load_font(name: str, font_size: int) -> ImageFont.FreeTypeFont | None:
    script_path   = Path(__file__).resolve()
    script_dir    = script_path.parent

    # normalize name before checking if the font exists
    name = name.replace(" ", "_").replace("-", "_").lower()
    if name=="open_sans":
        font_path = script_dir / "font-opensans_semicondensed-semibold.ttf"
    elif name=="roboto_slab":
        font_path = script_dir / "font-robotoslab-black.ttf"
    else:
        raise ValueError(f"Font {name!r} not found.")

    font = None
    if font_path.exists():
        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            pass

    return font or load_system_font(font_size)


def select_font_variation(font      : ImageFont.FreeTypeFont,
                          variations: list[str] | tuple[str, ...]
                          ) -> None:
    """
    Sets the font variation to the first in the list that is available in the font.
    Args:
        font       : The font object whose variation needs to be set.
        variations : A list or tuple of variation names to try.
    Returns:
        None, the function modifies the font object in place.
    """
    try:
        available_variations = [
            v.decode('utf-8') if isinstance(v, bytes) else v for v in font.get_variation_names() ]

        for variation in variations:
            if variation not in available_variations:
                continue
            # the variation is available!, set it and return
            font.set_variation_by_name(variation)
            return

    except:
        # if the font doesn't support variations, do nothing
        pass


#======================== COMPLEX DRAWING FUNCTIONS ========================#

def wrap_text(text: str, font: ImageFont.FreeTypeFont, width: int) -> tuple[list[str], float]:
    """Splits text into lines that fit within the given width.

    Args:
        text      (str) : The input text to be split.
        font (ImageFont): Font used for rendering the text.
        width     (int) : Maximum width in pixels that each line of text can occupy.

    Returns:
        A list of lines (strings)
        and the percentage length of the last line.
    """
    words = text.split()
    lines = []
    current_line = ""
    for i, word in enumerate(words):
        test_line = f"{current_line} {word}" if i>0 else word
        if font.getlength(test_line) <= width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)

    last_line_percent = 100.0 * len(lines[-1]) / len(lines[0])
    return lines, last_line_percent


def write_text_in_box(image               : Image.Image,
                      text                : str,
                      box                 : TextBox,
                      *,
                      font                : ImageFont.FreeTypeFont,
                      spacing             : float      = 4,
                      align               : str        = 'left',
                      color               : str        = 'black',
                      back_color          : str | None = None,
                      padding             : int | None = None,
                      abort_if_not_fitting: bool       = False
                      ) -> bool:
    """
    Attempts to write the provided text within the rectangle defined by the Box object.

    The function ensures that the last line is not excessively short. 

    The text is aligned according to the specified alignment (left, center, or right).
    If the text cannot fit within the box and the `abort_if_not_fitting` flag is set,
    the function does not write the text and returns False.

    Parameters:
        image      : The image object where the text will be written.
        box        : The bounding box object defining the area where the text should be placed.
        text       : The text to be written.
        font       : The font to be used for the text.
        spacing    : The spacing between lines. Default is 4.
        align      : The alignment of the text within the box ('left', 'center', 'right').
                      Default is 'left'.
        color      : The color of the text. Default is 'black'.
        back_color : The optional background color for the box.
                      If None (default), no background is filled.
        abort_if_not_fitting: If True, the function returns False if the text cannot fit within the box.

    Returns:
        True if the text was successfully written, False otherwise.
    """
    draw = ImageDraw.Draw(image)

    # the container rectangle can optionally be of a certain color
    if back_color:
        draw.rectangle(box, fill=back_color)

    # return `True` immediately if no text is provided
    if not text:
        return True

    # apply padding to the box if specified
    if padding:
        box = box.shrunken(padding, padding)

    # split the text into lines within the box width and adjust the box size
    # dynamically to prevent excessively short final line (ensuring last_line>35%)
    for i in range(1, 10):
        lines, last_line_percent = wrap_text( text, font, int(box.width) )
        if last_line_percent > 35  or  box.width < 300:
            break
        box = box.shrunken(20,0)

    # join all lines with newline characters
    text = '\n'.join(lines)

    # set the appropriate position based on alignment
    if align == 'center':
        x, y   = box.center[0], box.top
        anchor = 'ma'
    elif align == 'right':
        x, y   = box.right, box.top
        anchor = 'ra'
    else:
        align  = 'left'
        x, y   = box.left, box.top
        anchor = 'la'

    textbbox = TextBox.multiline_textbbox( draw, (0,0), text, font=font, anchor=anchor, spacing=spacing, align=align )
    top_offset = textbbox.top
    _, descent = font.getmetrics()

    textbbox = textbbox.centered_in( box )
    y = textbbox.top - top_offset + (descent/4)

    if abort_if_not_fitting and textbbox.top < box.top:
        return False

    draw.multiline_text( (x,y), text, font=font, anchor=anchor, spacing=spacing, align=align, fill=color)
    return True
