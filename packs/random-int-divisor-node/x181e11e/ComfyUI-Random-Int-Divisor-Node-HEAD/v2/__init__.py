from .random_integer_node_efficient import RandomIntegerNodeEfficient
from .random_integer_node_list import RandomIntegerNodeList
from .random_integer_node_efficient_advanced import RandomIntegerNodeEfficientAdvanced

NODE_CLASS_MAPPINGS = {
       "RandomIntegerNodeEfficient": RandomIntegerNodeEfficient,
       "RandomIntegerNodeList": RandomIntegerNodeList,
       "RandomIntegerNodeEfficientAdvanced": RandomIntegerNodeEfficientAdvanced,
   }

NODE_DISPLAY_NAME_MAPPINGS = {
       "RandomIntegerNodeEfficient": "Efficient Random Integer Generator",
       "RandomIntegerNodeList": "Random Integer Generator Using List",
       "RandomIntegerNodeEfficientAdvanced": "Advanced Random Integer Generator",
   }
