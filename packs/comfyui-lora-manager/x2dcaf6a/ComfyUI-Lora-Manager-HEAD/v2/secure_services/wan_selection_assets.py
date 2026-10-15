"""Public asset boundary after native cache identity selection.

Native request names can omit extensions or use cache aliases. They are not
necessarily exact public catalogue names. The caller must establish cache
identity and authored metadata before invoking this single-asset boundary.
No original selector is registered until those contracts are implemented.
"""
from __future__ import annotations

from comfy_api.latest import sdk


async def resolve_selected_lora_asset(
    selected_logical_name: str,
) -> tuple[str, sdk.AssetRef]:
    """Resolve an owner-selected catalogue identity; keep the AssetRef local.

    Keep the original requested name separately for the native active_loras
    summary. WANVIDLORA.path carries this selected logical name, never the
    value returned by assets.path or a native absolute business path.

    Native get_lora_info_absolute returns an unresolved request with empty
    words. It does not skip that row or check file existence. Widget queue
    validation is a separate operation; the text selector has no equivalent.
    This boundary does not emulate either unresolved or queue behavior, and
    broker errors propagate. Do not convert them to skipped rows.

    Authored trigger words and native root-relative display names still need
    their actual owner before append_resolved_entry. The eventual node must
    declare the actual assets capability.
    """
    asset = await sdk.ctx().assets.resolve('loras', selected_logical_name)
    return selected_logical_name, asset
