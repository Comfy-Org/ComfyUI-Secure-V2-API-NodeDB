class ConstrainedNonnegativeIntNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 0, 
                    "min": 0, 
                    "max": 9000000000000000,
                    "step": 1, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 0:
            value = 0
            
        return (value,)

class ConstrainedPositiveInt4np1Node:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 1, 
                    "min": 1, 
                    "max": 9000000000000001,
                    "step": 4, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 1:
            value = 1
            
        constrained_value = ((value - 1) // 4) * 4 + 1
        
        return (constrained_value,)

class ConstrainedPositiveInt4np2Node:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 2, 
                    "min": 2, 
                    "max": 9000000000000002,
                    "step": 4, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 2:
            value = 2
            
        constrained_value = ((value - 2) // 4) * 4 + 2
        
        return (constrained_value,)

class ConstrainedPositiveInt4np3Node:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 3, 
                    "min": 3, 
                    "max": 9000000000000003,
                    "step": 4, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 3:
            value = 3
            
        constrained_value = ((value - 3) // 4) * 4 + 3
        
        return (constrained_value,)

class ConstrainedNonnegativeInt4nNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 0, 
                    "min": 0, 
                    "max": 9000000000000000,
                    "step": 4, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 0:
            value = 0
            
        constrained_value = (value // 4) * 4
        
        return (constrained_value,)

class ConstrainedPositiveInt4nNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 4, 
                    "min": 4, 
                    "max": 9000000000000000,
                    "step": 4, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 4:
            value = 4
            
        constrained_value = (value // 4) * 4
        
        return (constrained_value,)

class ConstrainedPositiveInt8np1Node:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 1, 
                    "min": 1, 
                    "max": 9000000000000001,
                    "step": 8, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 1:
            value = 1
            
        constrained_value = ((value - 1) // 8) * 8 + 1
        
        return (constrained_value,)

class ConstrainedNonnegativeInt16nNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 0, 
                    "min": 0, 
                    "max": 9000000000000000,
                    "step": 16, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 0:
            value = 0
            
        constrained_value = (value // 16) * 16
        
        return (constrained_value,)

class ConstrainedPositiveInt16nNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 16, 
                    "min": 16, 
                    "max": 9000000000000000,
                    "step": 16, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 16:
            value = 16
            
        constrained_value = (value // 16) * 16
        
        return (constrained_value,)

class ConstrainedNonnegativeInt32nNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 0, 
                    "min": 0, 
                    "max": 9000000000000000,
                    "step": 32, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 0:
            value = 0
            
        constrained_value = (value // 32) * 32
        
        return (constrained_value,)

class ConstrainedPositiveInt32nNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 32, 
                    "min": 32, 
                    "max": 9000000000000000,
                    "step": 32, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 32:
            value = 32
            
        constrained_value = (value // 32) * 32
        
        return (constrained_value,)

class ConstrainedPositiveIntNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("INT", {
                    "default": 1, 
                    "min": 1, 
                    "max": 9000000000000000,
                    "step": 1, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value):
        if value < 1:
            value = 1;
        
        return (value,)

'''
# This was too awkward.  It can't update itself properly when x changes without some weird extra plugin code,
# unless x is provided via a link from another node in which case the code needed becomes even weirder and more
# brittle, and sometimes probably cannot practically work at all (like when the workflow needs to be run to
# produce the x value).  Some new specialized simple int node could be introduced to link directly to x so that
# this node could then know to search for that specifically, with no intermediate reroutes or nodes in between,
# and that could probably work, but then maybe some random ComfyUI update would ruin it somehow...  not worth it

class ConstrainedPositiveInt4npxNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required":
            {
                "value": ("INT", {
                    "default": 4, 
                    "min": 1,
                    "max": 9000000000000001,
                    "step": 4,
                    "display": "number"
                }),
                "x": ("INT", {
                    "default": 0,
                    "min": 0, 
                    "max": 3,
                    "step": 1, 
                    "display": "number"
                }),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("INT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"

    def clamp(self, value, x):
        x = (x - 1) % 4 + 1

        if value < x:
            value = x
            
        constrained_value = ((value - x) // 4) * 4 + x
        
        return (constrained_value,)
'''

class ConstrainedFloat0to1Node:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "round": False,
                    "display": "number"
                }),
            }
        }
 
    RETURN_TYPES = ("FLOAT",)
    RETURN_NAMES = ("FLOAT",)
    FUNCTION = "clamp"
    CATEGORY = "constrained_numbers"
 
    def clamp(self, value):
        constrained_value = max(0.0, min(1.0, float(value)))
 
        return (constrained_value,)

NODE_CLASS_MAPPINGS = {
    "Constrained Int (n>=0)": ConstrainedNonnegativeIntNode,
    "Constrained Int (n>0)": ConstrainedPositiveIntNode,
    "Constrained Int (4n>=0)": ConstrainedNonnegativeInt4nNode,
    "Constrained Int (4n>0)": ConstrainedPositiveInt4nNode,
    "Constrained Int (4n+1>0)": ConstrainedPositiveInt4np1Node,
    "Constrained Int (4n+2>0)": ConstrainedPositiveInt4np2Node,
    "Constrained Int (4n+3>0)": ConstrainedPositiveInt4np3Node,
    "Constrained Int (8n+1>0)": ConstrainedPositiveInt8np1Node,
    "Constrained Int (16n>=0)": ConstrainedNonnegativeInt16nNode,
    "Constrained Int (16n>0)": ConstrainedPositiveInt16nNode,
    "Constrained Int (32n>=0)": ConstrainedNonnegativeInt32nNode,
    "Constrained Int (32n>0)": ConstrainedPositiveInt32nNode,
    "Constrained Float (0.0 to 1.0)": ConstrainedFloat0to1Node
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Constrained Int (n>=0)": "Int (n>=0)",
    "Constrained Int (n>0)": "Int (n>0)",
    "Constrained Int (4n>=0)": "Int (4n>=0)",
    "Constrained Int (4n>0)": "Int (4n>0)",
    "Constrained Int (4n+1>0)": "Int (4n+1>0)",
    "Constrained Int (4n+2>0)": "Int (4n+2>0)",
    "Constrained Int (4n+3>0)": "Int (4n+3>0)",
    "Constrained Int (8n+1>0)": "Int (8n+1>0)",
    "Constrained Int (16n>=0)": "Int (16n>=0)",
    "Constrained Int (16n>0)": "Int (16n>0)",
    "Constrained Int (32n>=0)": "Int (32n>=0)",
    "Constrained Int (32n>0)": "Int (32n>0)",
    "Constrained Float (0.0 to 1.0)": "Float ∈ [0.0, 1.0]"
}
