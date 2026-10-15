"""Two original library values selected by the actual gallery; TEST-only sink."""
import hashlib
import json
from comfy_api.latest import io
from .nodes.library_tokens import decode_style, decode_palette
from .native_reference.nodes.style_library_v10 import StyleLibraryV10 as NativeStyle
from .native_reference.nodes.palette_library_v20 import PaletteLibraryV20 as NativePalette


def state(value):
    return json.loads(json.dumps(vars(value), sort_keys=True))


class GalleryRegistryOracle(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='MOE_ZImageGalleryRegistryOracle_TestOnly',
                         display_name='Z-Image selected gallery workflow TEST', category='testing',
                         inputs=[io.Custom('ZIPN_STYLE').Input('style'),
                                 io.Custom('ZIPN_PALETTE').Input('palette'),
                                 io.String.Input('case_seed'), io.Boolean.Input('reject_control', default=False)],
                         outputs=[], is_output_node=True)

    @classmethod
    def execute(cls, style, palette, case_seed, reject_control=False):
        actual_style, actual_palette = decode_style(style), decode_palette(palette)
        assert actual_style.name == 'Phone Photo' and actual_palette.name == 'Ember Sunrise'
        native_style = NativeStyle.execute(actual_style.name).result[0]
        native_palette = NativePalette.execute(actual_palette.name).result[0]
        assert state(actual_style) == state(native_style)
        assert state(actual_palette) == state(native_palette)
        prompt = 'a red fox at sunrise, ' + case_seed
        actual = actual_style.apply_to_prompt(prompt, palette=actual_palette)
        expected = native_style.apply_to_prompt(prompt, palette=native_palette)
        assert actual == expected and actual != prompt
        assert not reject_control, 'MOE gallery registry expected-negative control'
        observation = {'style': actual_style.name, 'palette': actual_palette.name,
                       'case_seed': case_seed, 'native_full_state_equal': True,
                       'original_prompt_behavior_equal': True,
                       'styled_prompt_sha256': hashlib.sha256(actual.encode()).hexdigest(),
                       'model_inference': False}
        return io.NodeOutput(ui={'text': [json.dumps(observation, sort_keys=True)]})
