"""Pack-owned native logger origin without utility import side effects.

Native cache_methods imports log from its parent utils module. Selecting that
same logger name does not import utils, probe devices or call basicConfig.
Handler/formatter configuration belongs to the admitted execution environment.
"""
import logging

log = logging.getLogger(f"{__package__}.utils")
