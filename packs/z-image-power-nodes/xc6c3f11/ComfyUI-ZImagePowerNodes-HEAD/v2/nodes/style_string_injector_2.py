"""
File    : style_string_injector_2.py
Purpose : Inject a visual style into a prompt. (version 2)
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Jan 22, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

 ComfyUI V3 Schema oficial documentation:
 - https://docs.comfy.org/custom-nodes/v3_migration

"""
from typing                   import Final
from functools                import cache
from comfy_api.latest         import io
from .data.predefined_styles  import PREDEFINED_STYLES
from .                        import widgets as zi
_STL_VERSION: Final[str] = "1.0.0" #< the version of style definitions this node uses


class StyleStringInjector2(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    xTITLE         = '⚡| Style String Injector'
    xDESCRIPTION   = (
        'Injects a style to your prompt. This node takes a text prompt and modifies it according to the selected style'
        )
    xCATEGORY      = '⚡Z-Image'
    xCOMFY_NODE_ID = 'StyleStringInjector2 //ZImagePowerNodes'
    xDEPRECATED    = False

    #__ INPUT / OUTPUT ____________________________________
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            display_name  = cls.xTITLE,
            description   = cls.xDESCRIPTION,
            category      = cls.xCATEGORY,
            node_id       = cls.xCOMFY_NODE_ID,
            is_deprecated = cls.xDEPRECATED,
            inputs=[
                io.Combo.Input          ("style",
                                         options=['"Phone Photo"', '"Casual Photo"', '"Selfie"', '"Family Album Photo"', '"Low Quality Photo"', '"High Quality Photo"', '"Landscape Photo"', '"Vivid Daylight Photo"', '"Portra Film Photo"', '"Vibrant Analog Photo"', '"Vintage Photo"', '"70s Memories Photo"', '"Flash 90s Photo"', '"Production Photo"', '"Classic Film Photo"', '"High Key Cinematic Portrait"', '"Low Key Cinematic Portrait"', '"Sun-Kissed 35mm"', '"Dramatic Dark Lighting"', '"Noir Photo"', '"Unease Shadow Photo"', '"80s Dark Fantasy Photo"', '"Nostalgic Golden Hour"', '"Lomography"', '"Underwater Photo"', '"Spotlight Stage Photo"', '"Unconventional Viewpoint"', '"Dramatic Viewpoint"', '"Wide Angle / Peephole"', '"Drone Photo"', '"Minimalist Photo"', '"Grayscale with Red Accent"', '"Security Camera"', '"Modern Pin-Up photo"', '"Top-Tier Magazine Photo"', '"High-Key Fashion Photo"', '"Light and Airy Photo"', '"Nostalgic Warm Photo"', '"Teal and Orange Photo"', '"Ochre & Shadows Photo"', '"Orthochromatic Spirit Photo"', '"Synthwave Photo"', '"Quiet Luxury Photo"', '"Daylight Paparazzi"', '"Nightlife Paparazzi"', '"Dark-Side Photo"', '"Dramatic Light & Shadow"', '"Pastel Dream Aesthetic"', '"Theatrical Illusion"', '"Exposed Film Set"', '"Burning Man Playa"', '"Street Documentary Photo"', '"Tilt Shift / Toy Photo"', '"Pop Photo"', '"Comic 1"', '"Comic 2"', '"Comic 3"', '"Action Cover Art"', '"Explosive Cover Art"', '"Intense Pop Illustration"', '"Pop-Art"', '"Vintage Comic"', '"Vintage Illustration"', '"Modern Pin-Up Illustration"', '"Manga"', '"Anime"', '"Dark Anime"', '"Ultimate Anime"', '"Studio Anime"', '"Retro Anime 80s"', '"Simple Toon"', '"Joyful Cartoon Illustration"', '"Dark Comic Illustration"', '"Digital Cyberpunk"', '"Electric Blue Outline"', '"Neon Rampage Illustration"', '"Ink Frenzy"', '"Ink & Shadow"', '"Unsettling"', '"Digital Engraving"', '"Digital Risograph"', '"Surreal Illustration"', '"Neo Cubismo"', '"Epic Greg"', '"Cyber Idol"', '"Minimalist Digital Illustration"', '"Synthwave Digital Illustration"', '"Whimsical Watercolor"', '"Modern Ukiyo-e Print"', '"LowRes Pixel Art"', '"Fridge Magnet"', '"Low-Poly Render"', '"Simple 3D Render"', '"Vintage VGA Monitor"', '"Vintage Polaroid Photo"', '"Ancient D&D Character Sheet"', '"Retro Arcade Cabinet"', '"Retro Pinball Backglass"', '"Urban Wall Mural"', '"City Light Poster"', '"Neon Billboard"', '"Jigsaw Puzzle"', '"Christmas Window Display"', '"Classic Snow Globe"', '"90s Cereal Box"', '"Action Figure in Blister"', '"Antique Silver Coin"', '"Little Music Box"', '"Industrial Blueprint"', '"Ancient Cave Painting"', '"Classical Mosaic"', '"Folk-Art Mosaic"', '"Hallway Frame Sign"', '"Miniature Diorama"', '"Paper Cut Diorama"', '"Marble Statue"', '"Stamp"', '"Victorian Scrapbook Page"', '"Vintage Reel Frame"', '"Holographic Device"', '"Coffee-Cup Art Print"', '"Cassette Tape Sleeve"', '"Vintage Postcard"', '"Custom 1"', '"Custom 2"', '"Custom 3"', '"Custom 4"'],
                                         tooltip="The visual style you want for your image.",
                                        ),
                zi.StyleGalleryButton.Input("gallery",
                                         version="1.0", dialog_title="Select Style",
                                         tooltip="Open the style gallery to see all available styles."
                                        ),
                io.String.Input         ("string",
                                         multiline=True, dynamic_prompts=True, force_input=True,
                                         tooltip="The prompt to modify.",
                                        ),
            ],
            outputs=[
                io.String.Output(tooltip="The prompt after applying the selected style."),
            ]
        )

    #__ FUNCTION __________________________________________
    @classmethod
    def execute(cls, style: str, string: str, **kwargs) -> io.NodeOutput:
        style_obj = PREDEFINED_STYLES.by_version(_STL_VERSION).get(style)

        # apply the style template to the prompt
        prompt = string
        if style_obj:
            prompt = style_obj.apply_to_prompt(prompt)

        return io.NodeOutput( prompt )


    #__ VALIDATION ________________________________________
    @classmethod
    def validate_inputs(cls, **kwargs) -> bool | str:
        return True



    #__ internal functions ________________________________

    @staticmethod
    @cache
    def style_names() -> list[str]:
        """Returns all available style names."""
        return PREDEFINED_STYLES.by_version(_STL_VERSION).quoted_names()


