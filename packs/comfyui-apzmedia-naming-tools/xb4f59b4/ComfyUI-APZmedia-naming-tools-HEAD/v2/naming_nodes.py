"""Actual stateless V2 adapters; full14-purpose pack remains unfinished/unrun."""
from comfy_api.latest import io

from .algorithms.APZnamefromtext import CleanFileNameNode as _CleanFileNameNode
from .algorithms.APZgeneratePathNode import GenerateFilePathNode as _GenerateFilePathNode
from .algorithms.APZfileNameBuilder import APZmediaStandardFilenameBuilder as _APZmediaStandardFilenameBuilder
from .algorithms.APZreadWidget import APZmediaReadWidget as _APZmediaReadWidget
from .algorithms.APZdictionaryReplace import APZmediaDictionaryReplace as _APZmediaDictionaryReplace
from .algorithms.APZtextToHash import APZmediaTextToHash as _APZmediaTextToHash
from .algorithms.APZvfxFilename import APZmediaVFXFilename as _APZmediaVFXFilename
from .algorithms.APZadFilename import APZmediaAdFilename as _APZmediaAdFilename
from .algorithms.APZfashionEditorialFilename import APZmediaFashionEditorialFilename as _APZmediaFashionEditorialFilename
from .algorithms.APZfashionEcomFilename import APZmediaFashionEcomFilename as _APZmediaFashionEcomFilename
from .algorithms.APZecomFilename import APZmediaEcomFilename as _APZmediaEcomFilename
from .algorithms.APZstringStripper import APZmediaStringStripper as _APZmediaStringStripper


class CleanFileNameNode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='CleanFileNameNode', display_name='APZmedia Clean File Name Node',
            category='APZmedia',
            inputs=[io.String.Input('input_text', multiline=False, default=''), io.String.Input('replacement_char', multiline=False, default='-'), io.String.Input('invalid_chars', multiline=False, default=' #%&{}\\\\<>*?/ $!\'\\":@+`|=.'), io.String.Input('prefix', multiline=False, default=''), io.Int.Input('char_limit', default=255, min=1, max=4096, step=1, display_mode=io.NumberDisplay.number)],
            outputs=[io.String.Output(display_name='cleaned_text')])

    @classmethod
    def execute(cls, input_text, replacement_char, invalid_chars, prefix, char_limit):
        return io.NodeOutput(*_CleanFileNameNode().clean_text(input_text, replacement_char, invalid_chars, prefix, char_limit))

    @classmethod
    def fingerprint_inputs(cls, input_text, replacement_char, invalid_chars, prefix, char_limit):
        return _CleanFileNameNode.IS_CHANGED(input_text, replacement_char, invalid_chars, prefix, char_limit)


class GenerateFilePathNode(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaGenerateFilePath', display_name='APZmedia Generate File Path',
            category='APZmedia',
            inputs=[io.String.Input('root_folder', multiline=False, default=''), io.String.Input('project_name', multiline=False, default=''), io.String.Input('episode_name', multiline=False, default=''), io.String.Input('shot_name', multiline=False, default=''), io.String.Input('pass_name', multiline=False, default=''), io.Combo.Input('slash_type', options=['Forward (/)', 'Backslash (\\)', 'Auto']), io.Combo.Input('toggle_root_folder', options=['Include', 'Exclude'], default='Include'), io.Combo.Input('toggle_project_name', options=['Include', 'Exclude'], default='Include'), io.Combo.Input('toggle_episode_name', options=['Include', 'Exclude'], default='Include'), io.Combo.Input('toggle_shot_name', options=['Include', 'Exclude'], default='Include'), io.Combo.Input('toggle_pass_name', options=['Include', 'Exclude'], default='Include')],
            outputs=[io.String.Output(display_name='generated_path')])

    @classmethod
    def execute(cls, root_folder, project_name, episode_name, shot_name, pass_name, slash_type, toggle_root_folder, toggle_project_name, toggle_episode_name, toggle_shot_name, toggle_pass_name):
        return io.NodeOutput(*_GenerateFilePathNode().generate_path(root_folder, project_name, episode_name, shot_name, pass_name, slash_type, toggle_root_folder, toggle_project_name, toggle_episode_name, toggle_shot_name, toggle_pass_name))

    @classmethod
    def fingerprint_inputs(cls, root_folder, project_name, episode_name, shot_name, pass_name, slash_type, toggle_root_folder, toggle_project_name, toggle_episode_name, toggle_shot_name, toggle_pass_name):
        return _GenerateFilePathNode.IS_CHANGED(root_folder, project_name, episode_name, shot_name, pass_name, slash_type, toggle_root_folder, toggle_project_name, toggle_episode_name, toggle_shot_name, toggle_pass_name)


class APZmediaStandardFilenameBuilder(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaStandardFilenameBuilder', display_name='APZmedia Standard Filename Builder',
            category='APZmedia',
            inputs=[io.String.Input('project_name', multiline=False, default=''), io.String.Input('episode_name', multiline=False, default=''), io.String.Input('shot_name', multiline=False, default=''), io.String.Input('pass_name', multiline=False, default=''), io.String.Input('delimiter', multiline=False, default='-'), io.Combo.Input('toggle_project_name', options=['Include', 'Exclude'], default='Include'), io.Combo.Input('toggle_episode_name', options=['Include', 'Exclude'], default='Include'), io.Combo.Input('toggle_shot_name', options=['Include', 'Exclude'], default='Include'), io.Combo.Input('toggle_pass_name', options=['Include', 'Exclude'], default='Include')],
            outputs=[io.String.Output(display_name='concatenated_name')])

    @classmethod
    def execute(cls, project_name, episode_name, shot_name, pass_name, delimiter, toggle_project_name, toggle_episode_name, toggle_shot_name, toggle_pass_name):
        return io.NodeOutput(*_APZmediaStandardFilenameBuilder().concatenate_names(project_name, episode_name, shot_name, pass_name, delimiter, toggle_project_name, toggle_episode_name, toggle_shot_name, toggle_pass_name))

    @classmethod
    def fingerprint_inputs(cls, project_name, episode_name, shot_name, pass_name, delimiter, toggle_project_name, toggle_episode_name, toggle_shot_name, toggle_pass_name):
        return _APZmediaStandardFilenameBuilder.IS_CHANGED(project_name, episode_name, shot_name, pass_name, delimiter, toggle_project_name, toggle_episode_name, toggle_shot_name, toggle_pass_name)


class APZmediaReadWidget(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaReadWidget', display_name='Read Widget',
            category='APZmedia',
            inputs=[io.String.Input('text', multiline=False, default='')],
            outputs=[io.String.Output()])

    @classmethod
    def execute(cls, text):
        return io.NodeOutput(*_APZmediaReadWidget().get_text(text))


class APZmediaDictionaryReplace(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaDictionaryReplace', display_name='APZmedia Dictionary Based String Replacement',
            category='APZmedia',
            inputs=[io.AnyType.Input('input_text'), io.String.Input('dictionary', multiline=True, default='"key" | "value"\n"another key" | "another value"')],
            outputs=[io.String.Output(display_name='replaced_text'), io.Int.Output(display_name='replacement_count')])

    @classmethod
    def execute(cls, input_text, dictionary):
        return io.NodeOutput(*_APZmediaDictionaryReplace().replace_text(input_text, dictionary))

    @classmethod
    def fingerprint_inputs(cls, input_text, dictionary):
        return _APZmediaDictionaryReplace.IS_CHANGED(input_text, dictionary)


class APZmediaTextToHash(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ('raw',)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaTextToHash', display_name='APZmedia Text To Hash',
            category='APZmedia',
            inputs=[io.AnyType.Input('input_value'), io.Int.Input('hash_length', default=8, min=1, max=64, step=1, display_mode=io.NumberDisplay.number)],
            outputs=[io.String.Output(display_name='hash')])

    @classmethod
    def execute(cls, input_value, hash_length):
        return io.NodeOutput(*_APZmediaTextToHash().compute_hash(input_value, hash_length))

    @classmethod
    def fingerprint_inputs(cls, input_value, hash_length):
        return _APZmediaTextToHash.IS_CHANGED(input_value, hash_length)


class APZmediaVFXFilename(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaVFXFilename', display_name='APZmedia VFX Filename',
            category='APZmedia/Naming',
            inputs=[io.String.Input('show', multiline=False, default=''), io.Combo.Input('toggle_show', options=['Include', 'Exclude']), io.String.Input('sequence', multiline=False, default=''), io.Combo.Input('toggle_sequence', options=['Include', 'Exclude']), io.String.Input('shot', multiline=False, default=''), io.Combo.Input('toggle_shot', options=['Include', 'Exclude']), io.String.Input('pass_name', multiline=False, default=''), io.Combo.Input('toggle_pass', options=['Include', 'Exclude']), io.String.Input('version', multiline=False, default=''), io.Combo.Input('toggle_version', options=['Include', 'Exclude']), io.String.Input('delimiter', multiline=False, default='_')],
            outputs=[io.String.Output(display_name='filename')])

    @classmethod
    def execute(cls, show, toggle_show, sequence, toggle_sequence, shot, toggle_shot, pass_name, toggle_pass, version, toggle_version, delimiter):
        return io.NodeOutput(*_APZmediaVFXFilename().build_filename(show, toggle_show, sequence, toggle_sequence, shot, toggle_shot, pass_name, toggle_pass, version, toggle_version, delimiter))

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return _APZmediaVFXFilename.IS_CHANGED(**kwargs)


class APZmediaAdFilename(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaAdFilename', display_name='APZmedia Ad Filename',
            category='APZmedia/Naming',
            inputs=[io.String.Input('brand', multiline=False, default=''), io.Combo.Input('toggle_brand', options=['Include', 'Exclude']), io.String.Input('campaign', multiline=False, default=''), io.Combo.Input('toggle_campaign', options=['Include', 'Exclude']), io.String.Input('format_type', multiline=False, default=''), io.Combo.Input('toggle_format', options=['Include', 'Exclude']), io.String.Input('placement', multiline=False, default=''), io.Combo.Input('toggle_placement', options=['Include', 'Exclude']), io.String.Input('ratio', multiline=False, default=''), io.Combo.Input('toggle_ratio', options=['Include', 'Exclude']), io.String.Input('version', multiline=False, default=''), io.Combo.Input('toggle_version', options=['Include', 'Exclude']), io.String.Input('delimiter', multiline=False, default='_')],
            outputs=[io.String.Output(display_name='filename')])

    @classmethod
    def execute(cls, brand, toggle_brand, campaign, toggle_campaign, format_type, toggle_format, placement, toggle_placement, ratio, toggle_ratio, version, toggle_version, delimiter):
        return io.NodeOutput(*_APZmediaAdFilename().build_filename(brand, toggle_brand, campaign, toggle_campaign, format_type, toggle_format, placement, toggle_placement, ratio, toggle_ratio, version, toggle_version, delimiter))

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return _APZmediaAdFilename.IS_CHANGED(**kwargs)


class APZmediaFashionEditorialFilename(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaFashionEditorialFilename', display_name='APZmedia Fashion Editorial Filename',
            category='APZmedia/Naming',
            inputs=[io.String.Input('season', multiline=False, default=''), io.Combo.Input('toggle_season', options=['Include', 'Exclude']), io.String.Input('collection', multiline=False, default=''), io.Combo.Input('toggle_collection', options=['Include', 'Exclude']), io.String.Input('look', multiline=False, default=''), io.Combo.Input('toggle_look', options=['Include', 'Exclude']), io.String.Input('shot', multiline=False, default=''), io.Combo.Input('toggle_shot', options=['Include', 'Exclude']), io.String.Input('version', multiline=False, default=''), io.Combo.Input('toggle_version', options=['Include', 'Exclude']), io.String.Input('delimiter', multiline=False, default='_')],
            outputs=[io.String.Output(display_name='filename')])

    @classmethod
    def execute(cls, season, toggle_season, collection, toggle_collection, look, toggle_look, shot, toggle_shot, version, toggle_version, delimiter):
        return io.NodeOutput(*_APZmediaFashionEditorialFilename().build_filename(season, toggle_season, collection, toggle_collection, look, toggle_look, shot, toggle_shot, version, toggle_version, delimiter))

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return _APZmediaFashionEditorialFilename.IS_CHANGED(**kwargs)


class APZmediaFashionEcomFilename(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaFashionEcomFilename', display_name='APZmedia Fashion E-com Filename',
            category='APZmedia/Naming',
            inputs=[io.String.Input('brand', multiline=False, default=''), io.Combo.Input('toggle_brand', options=['Include', 'Exclude']), io.String.Input('sku', multiline=False, default=''), io.Combo.Input('toggle_sku', options=['Include', 'Exclude']), io.String.Input('colorcode', multiline=False, default=''), io.Combo.Input('toggle_colorcode', options=['Include', 'Exclude']), io.String.Input('view', multiline=False, default=''), io.Combo.Input('toggle_view', options=['Include', 'Exclude']), io.String.Input('sequence', multiline=False, default=''), io.Combo.Input('toggle_sequence', options=['Include', 'Exclude']), io.String.Input('delimiter', multiline=False, default='_')],
            outputs=[io.String.Output(display_name='filename')])

    @classmethod
    def execute(cls, brand, toggle_brand, sku, toggle_sku, colorcode, toggle_colorcode, view, toggle_view, sequence, toggle_sequence, delimiter):
        return io.NodeOutput(*_APZmediaFashionEcomFilename().build_filename(brand, toggle_brand, sku, toggle_sku, colorcode, toggle_colorcode, view, toggle_view, sequence, toggle_sequence, delimiter))

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return _APZmediaFashionEcomFilename.IS_CHANGED(**kwargs)


class APZmediaEcomFilename(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaEcomFilename', display_name='APZmedia E-com Filename',
            category='APZmedia/Naming',
            inputs=[io.String.Input('brand', multiline=False, default=''), io.Combo.Input('toggle_brand', options=['Include', 'Exclude']), io.String.Input('product', multiline=False, default=''), io.Combo.Input('toggle_product', options=['Include', 'Exclude']), io.String.Input('variant', multiline=False, default=''), io.Combo.Input('toggle_variant', options=['Include', 'Exclude']), io.String.Input('view', multiline=False, default=''), io.Combo.Input('toggle_view', options=['Include', 'Exclude']), io.String.Input('sequence', multiline=False, default=''), io.Combo.Input('toggle_sequence', options=['Include', 'Exclude']), io.String.Input('delimiter', multiline=False, default='_')],
            outputs=[io.String.Output(display_name='filename')])

    @classmethod
    def execute(cls, brand, toggle_brand, product, toggle_product, variant, toggle_variant, view, toggle_view, sequence, toggle_sequence, delimiter):
        return io.NodeOutput(*_APZmediaEcomFilename().build_filename(brand, toggle_brand, product, toggle_product, variant, toggle_variant, view, toggle_view, sequence, toggle_sequence, delimiter))

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return _APZmediaEcomFilename.IS_CHANGED(**kwargs)


class APZmediaStringStripper(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ()

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='APZmediaStringStripper', display_name='APZmedia String Stripper',
            category='APZmedia',
            inputs=[io.String.Input('input_text', multiline=False, default=''), io.Combo.Input('mode', options=['Simple', 'Regex']), io.String.Input('pattern', multiline=False, default='project-episode-shot-pass'), io.String.Input('terms_to_keep', multiline=False, default='shot'), io.String.Input('output_delimiter', multiline=False, default='-')],
            outputs=[io.String.Output(display_name='result'), io.Boolean.Output(display_name='matched')])

    @classmethod
    def execute(cls, input_text, mode, pattern, terms_to_keep, output_delimiter):
        return io.NodeOutput(*_APZmediaStringStripper().strip_string(input_text, mode, pattern, terms_to_keep, output_delimiter))

    @classmethod
    def fingerprint_inputs(cls, input_text, mode, pattern, terms_to_keep, output_delimiter):
        return _APZmediaStringStripper.IS_CHANGED(input_text, mode, pattern, terms_to_keep, output_delimiter)


NODE_CLASS_MAPPINGS = {
    'CleanFileNameNode': CleanFileNameNode,
    'APZmediaGenerateFilePath': GenerateFilePathNode,
    'APZmediaStandardFilenameBuilder': APZmediaStandardFilenameBuilder,
    'APZmediaReadWidget': APZmediaReadWidget,
    'APZmediaDictionaryReplace': APZmediaDictionaryReplace,
    'APZmediaTextToHash': APZmediaTextToHash,
    'APZmediaVFXFilename': APZmediaVFXFilename,
    'APZmediaAdFilename': APZmediaAdFilename,
    'APZmediaFashionEditorialFilename': APZmediaFashionEditorialFilename,
    'APZmediaFashionEcomFilename': APZmediaFashionEcomFilename,
    'APZmediaEcomFilename': APZmediaEcomFilename,
    'APZmediaStringStripper': APZmediaStringStripper,
}
