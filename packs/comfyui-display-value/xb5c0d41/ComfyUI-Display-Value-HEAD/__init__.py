from .display_value import DisplayValue

NODE_CLASS_MAPPINGS = {
    "DisplayValue": DisplayValue,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DisplayValue": "Display Value",
}

WEB_DIRECTORY = "./web"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
