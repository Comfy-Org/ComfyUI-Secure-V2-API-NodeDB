# By Suzie1 and RockOfFire
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to
# deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""
@author: Suzie1
@title: Comfyroll Studio
@nickname: Comfyroll Studio
@description: 175 custom nodes for artists, designers and animators.
"""

from . import secure_pure, secure_lora, secure_aspects, secure_merge, secure_graphics, secure_schedules, secure_random_lora, secure_lists, secure_pipes, secure_text_artifacts, secure_utilities, secure_tensors, secure_layout, secure_patterns, secure_masked_text, secure_text_panels, secure_matplot, secure_seeded_random, secure_animation_values
from . import secure_cycle_models
from . import secure_animation_models
from . import secure_halftone
from . import secure_template_previews
from . import secure_vae
from . import secure_templates
from . import secure_select_model
from . import secure_controlnet
from . import secure_sdxl
from . import secure_scheduled_prompt
from . import secure_scheduled_loaders
from . import secure_managed_image_lists
from . import secure_image_batch
from . import secure_controlnet_stack
from . import secure_upscale
from . import secure_animation_inputs
from . import secure_style_bars
from . import secure_xy_input
from . import secure_output_writers
from . import secure_font_catalogues

NODE_CLASS_MAPPINGS = {
    **secure_pure.NODE_CLASS_MAPPINGS,
    **secure_lora.NODE_CLASS_MAPPINGS,
    **secure_aspects.NODE_CLASS_MAPPINGS,
    **secure_merge.NODE_CLASS_MAPPINGS,
    **secure_graphics.NODE_CLASS_MAPPINGS,
    **secure_schedules.NODE_CLASS_MAPPINGS,
    **secure_random_lora.NODE_CLASS_MAPPINGS,
    **secure_lists.NODE_CLASS_MAPPINGS,
    **secure_pipes.NODE_CLASS_MAPPINGS,
    **secure_text_artifacts.NODE_CLASS_MAPPINGS,
    **secure_utilities.NODE_CLASS_MAPPINGS,
    **secure_tensors.NODE_CLASS_MAPPINGS,
    **secure_layout.NODE_CLASS_MAPPINGS,
    **secure_patterns.NODE_CLASS_MAPPINGS,
    **secure_masked_text.NODE_CLASS_MAPPINGS,
    **secure_text_panels.NODE_CLASS_MAPPINGS,
    **secure_matplot.NODE_CLASS_MAPPINGS,
    **secure_seeded_random.NODE_CLASS_MAPPINGS,
    **secure_animation_values.NODE_CLASS_MAPPINGS,
    **secure_cycle_models.NODE_CLASS_MAPPINGS,
    **secure_animation_models.NODE_CLASS_MAPPINGS,
    **secure_halftone.NODE_CLASS_MAPPINGS,
    **secure_template_previews.NODE_CLASS_MAPPINGS,
    **secure_vae.NODE_CLASS_MAPPINGS,
    **secure_templates.NODE_CLASS_MAPPINGS,
    **secure_select_model.NODE_CLASS_MAPPINGS,
    **secure_controlnet.NODE_CLASS_MAPPINGS,
    **secure_sdxl.NODE_CLASS_MAPPINGS,
    **secure_scheduled_prompt.NODE_CLASS_MAPPINGS,
    **secure_scheduled_loaders.NODE_CLASS_MAPPINGS,
    **secure_managed_image_lists.NODE_CLASS_MAPPINGS,
    **secure_image_batch.NODE_CLASS_MAPPINGS,
    **secure_controlnet_stack.NODE_CLASS_MAPPINGS,
    **secure_upscale.NODE_CLASS_MAPPINGS,
    **secure_animation_inputs.NODE_CLASS_MAPPINGS,
    **secure_style_bars.NODE_CLASS_MAPPINGS,
    **secure_xy_input.NODE_CLASS_MAPPINGS,
    **secure_output_writers.NODE_CLASS_MAPPINGS,
    **secure_font_catalogues.NODE_CLASS_MAPPINGS,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    **secure_pure.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_lora.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_aspects.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_merge.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_graphics.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_schedules.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_random_lora.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_lists.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_pipes.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_text_artifacts.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_utilities.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_tensors.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_layout.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_patterns.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_masked_text.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_text_panels.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_matplot.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_seeded_random.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_animation_values.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_cycle_models.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_animation_models.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_halftone.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_template_previews.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_vae.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_templates.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_select_model.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_controlnet.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_sdxl.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_scheduled_prompt.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_scheduled_loaders.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_managed_image_lists.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_image_batch.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_controlnet_stack.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_upscale.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_animation_inputs.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_style_bars.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_xy_input.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_output_writers.NODE_DISPLAY_NAME_MAPPINGS,
    **secure_font_catalogues.NODE_DISPLAY_NAME_MAPPINGS,
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
