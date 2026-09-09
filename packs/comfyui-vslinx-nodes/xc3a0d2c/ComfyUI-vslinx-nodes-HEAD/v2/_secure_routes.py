"""The wildcard names this pack's multiline text widget offers.

The legacy widget read Impact Pack's process-global catalogue over that pack's
own HTTP route. One confined pack cannot reach into another, and should not:
the picker is this pack's affordance, so the list it offers is this pack's
record. Names live in this pack's storage and the node itself stays a
passthrough — expansion remains whatever downstream node consumes the text.
"""
from comfy_api.latest import sdk

KEY = "vslinx:wildcards"
MAX_NAMES = 4096
MAX_NAME_LENGTH = 1024


async def list_wildcards(request):
    import json

    stored = await sdk.ctx().storage.get(KEY)
    names = stored if isinstance(stored, list) else []
    bounded = [
        str(name) for name in names[:MAX_NAMES]
        if isinstance(name, str) and 0 < len(name) <= MAX_NAME_LENGTH
    ]
    return {"body": json.dumps(bounded)}
