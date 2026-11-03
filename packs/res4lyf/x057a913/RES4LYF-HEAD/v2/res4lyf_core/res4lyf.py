"""Guest stand-in for upstream res4lyf.py.

The upstream module also registers HTTP routes on the ComfyUI server and reads a local config file, and neither
exists in the guest. The loop needs only the logging helper and two flags, so this module defines just those.
RESplain and is_debug_logging_enabled are copied from upstream res4lyf.py:204-232. Both config-driven flags take
upstream's defaults: displayCategory False, and the deprecated updatedTimestepScaling patch off.
"""
import logging

logger = logging.getLogger("RES4LYF")
logger.setLevel(logging.INFO)


def get_display_sampler_category():
    return False


def is_debug_logging_enabled():
    return logger.isEnabledFor(logging.DEBUG)


def RESplain(*args, level='info', debug=None):
    if debug is not None:
        if isinstance(debug, bool):
            level = 'debug' if debug else 'info'
        else:
            level = str(debug).lower()
    elif isinstance(level, bool):
        level = 'debug' if level else 'info'
    else:
        level = str(level).lower()

    if not args:
        return

    log_level = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL,
    }.get(level, logging.INFO)

    if logger.isEnabledFor(log_level):
        message = " ".join(map(str, args))
        logger.log(log_level, message)
