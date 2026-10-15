"""
File    : style_prompt_encoder.py
Purpose : Node to get conditioning embeddings from a given style + prompt.
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Jan 16, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

 ComfyUI V3 Schema oficial documentation:
 - https://docs.comfy.org/custom-nodes/v3_migration

"""
from typing                    import Final
from functools                 import cache
from comfy_api.latest          import io
from ..core.style              import StyleSet
from ..data.predefined_styles  import PREDEFINED_STYLES
_STL_VERSION: Final[str] = "0.9.0" #< the version of style definitions this node uses


class StylePromptEncoder(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()
    xTITLE         = '❌[DEPRECATED] Style & Prompt Encoder (old version)'
    xDESCRIPTION   = (
        'Transforms a text prompt into embeddings, automatically adapting the prompt to match the selected style. This node takes a prompt, adjusts its visual style according to the chosen option, and then encodes it using the provided text encoder (clip) to generate an embedding that will guide image generation.'
        )
    xCATEGORY      = '⚡Z-Image/__deprecated'
    xCOMFY_NODE_ID = 'StylePromptEncoder //ZImagePowerNodes'
    xDEPRECATED    = True

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
                io.Clip.Input  ("clip",
                                tooltip="The CLIP model used for encoding the text."
                               ),
                io.String.Input("customization", optional=True, multiline=True, force_input=True,
                                tooltip=(
                                  'An optional multi-line string to customize existing styles. '
                                  'Each style definition must start with ">>>" followed by the style name, and then include '
                                  'its description on the next lines. The description should incorporate "{$@}" where the '
                                  'main text prompt will be inserted.'),
                               ),
                io.Combo.Input ("category", options=['photo', 'illustration', 'wild', 'custom'],
                                tooltip="The category of styles you want to select from.",
                               ),
                io.Combo.Input ("style", options=['none', '"Phone Photo"', '"Casual Photo"', '"Vintage Photo"', '"Portra Film Photo"', '"70s Memories Photo"', '"Flash 90s Photo"', '"Production Photo"', '"Classic Film Photo"', '"Noir Photo"', '"80s Dark Fantasy Photo"', '"Lomography"', '"Spotlight Stage Photo"', '"Unconventional Viewpoint"', '"Dramatic Viewpoint"', '"Wide Angle / Peephole"', '"Drone Photo"', '"Minimalist Photo"', '"High-Key Fashion Photo"', '"Light and Airy Photo"', '"Teal and Orange Photo"', '"Orthochromatic Spirit Photo"', '"Synthwave Photo"', '"Quiet Luxury Photo"', '"Dark-Side Photo"', '"Dramatic Light & Shadow"', '"Pastel Dream Aesthetic"', '"Street Documentary Photo"', '"Tilt Shift / Toy Photo"', '"Pop Photo"', '"Comic 1"', '"Comic 2"', '"Comic 3"', '"Action Cover Art"', '"Explosive Cover Art"', '"Pop-Art"', '"Vintage Comic"', '"Vintage Illustration"', '"Modern Pin-Up Illustration"', '"Manga"', '"Anime"', '"Ultimate Anime"', '"Studio Anime"', '"Retro Anime 80s"', '"Dark Comic Illustration"', '"Digital Cyberpunk"', '"Electric Blue Outline"', '"Ink Frenzy"', '"Ink & Shadow"', '"Unsettling"', '"Epic Greg"', '"Cyber Idol"', '"Minimalist Digital Illustration"', '"Synthwave Digital Illustration"', '"Whimsical Watercolor"', '"Modern Ukiyo-e Print"', '"LowRes Pixel Art"', '"Low-Poly Render"', '"Simple 3D Render"', '"City Light Poster"', '"Vintage VGA Monitor"', '"Vintage Polaroid Photo"', '"Urban Wall Mural"', '"Retro Arcade Cabinet"', '"Neon Billboard"', '"Vintage Reel Frame"', '"Holographic Device"', '"Coffee-Cup Art Print"', '"Cassette Tape Sleeve"', '"Vintage Postcard"', '"Kawaii Pop Photo"', '"Custom 1"', '"Custom 2"', '"Custom 3"', '"Custom 4"'], default='"Phone Photo"',
                                tooltip="The style you want for your image.",
                               ),
                io.String.Input("text", multiline=True, dynamic_prompts=True,
                                tooltip="The prompt to encode.",
                               ),
            ],
            outputs=[
                io.Conditioning.Output(tooltip="The encoded text used to guide the image generation."),
                io.String.Output(tooltip="The prompt after applying the selected visual style."),
            ]
        )

    #__ FUNCTION __________________________________________
    @classmethod
    async def execute(cls,
                clip,
                category      : str,
                style         : str,
                text          : str,
                customization : str = ""
                ) -> io.NodeOutput:
        prompt        = text
        custom_styles = StyleSet.from_string(customization)

        # try to find the definition of the style selected by the user,
        # first search inside the custom styles that the user has defined (if any),
        # if not found, then try to find it in the predefined styles
        style_obj = custom_styles.get(style)
        if not style_obj:
            style_obj = PREDEFINED_STYLES.by_version(_STL_VERSION).get(style)

        # apply the style template to the prompt
        if style_obj:
            prompt = style_obj.apply_to_prompt(prompt)

        # encode the prompt using the provided text encoder (clip)
        tokens = await clip.tokenize(prompt)
        return io.NodeOutput( await clip.encode_from_tokens_scheduled(tokens), prompt )


    #__ VALIDATION ________________________________________
    @classmethod
    def validate_inputs(cls, **kwargs) -> bool | str:
        if kwargs["category"] not in cls.category_names():
            return f"The category name '{kwargs['category']}' is invalid. May be the node is from an older version."
        return True



    #__ internal functions ________________________________

    @staticmethod
    @cache
    def category_names() -> list[str]:
        """Returns all available category names."""
        return ['photo', 'illustration', 'wild', 'custom']


    @staticmethod
    @cache
    def style_names() -> list[str]:
        """Returns all available style names."""
        return (
            ["none"]
            + list( PREDEFINED_STYLES.by_version(_STL_VERSION).quoted_names() )
        )


    @staticmethod
    @cache
    def default_style_name() -> str:
        """Returns the default style name (the first one that is not 'none')."""
        style_names = StylePromptEncoder.style_names()
        return style_names[1 if len(style_names)>1 else 0]

