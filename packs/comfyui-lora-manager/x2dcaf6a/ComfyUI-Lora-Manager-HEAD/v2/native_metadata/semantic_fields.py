"""No inference of semantic fields absent from the owned metadata snapshot."""

class UnsupportedMetadataField(ValueError):
    pass


def model_patcher_to_name(value):
    if value is None:
        return None
    raise UnsupportedMetadataField('Wired model name is not present in the owned metadata projection')


def sampler_object_to_name(value):
    if value is None:
        return None
    raise UnsupportedMetadataField('Wired sampler function name is not present in the owned metadata projection')
