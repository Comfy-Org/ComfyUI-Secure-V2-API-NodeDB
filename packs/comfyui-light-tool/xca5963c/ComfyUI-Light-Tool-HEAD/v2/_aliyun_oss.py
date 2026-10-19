"""Original Aliyun file selection through managed assets and a named provider."""
from comfy_api.latest import sdk

SOURCE_PREFIX = "comfy-media-source:v1:"


async def save_to_aliyun(
    file, save_name, endpoint, bucket, oss_access_key_id, oss_access_key_secret,
    oss_session_token, use_cname, visit_endpoint, sign, timeout,
):
    if not isinstance(file, str) or not file or "\x00" in file:
        raise ValueError("Select a managed file or an HTTP(S) source URL")
    context = sdk.ctx()
    if file.startswith(SOURCE_PREFIX):
        # A preceding video node returns this account/pack-scoped handle in
        # place of its old host HTTP URL. Redeem the same managed bytes rather
        # than opening a host-local URL. Only the trusted provider sees paths.
        asset = await context.assets.resolve_media_source(file)
        filename = save_name.rsplit("/", 1)[-1] if save_name else None
    elif "http" in file:
        filename = save_name or file.split("?")[0].rsplit("/", 1)[-1]
        filename = filename.rsplit("/", 1)[-1]
        imported = await context.assets.import_url(
            file, max_bytes=64 * 1024 * 1024, timeout_seconds=5.0,
            follow_redirects=True, user_agent="light_tool_browser",
        )
        if not 200 <= imported["status_code"] < 300:
            raise RuntimeError("Aliyun source download failed with HTTP status " + str(imported["status_code"]))
        asset = imported["asset"]
    else:
        # The old raw-path branch becomes a logical managed catalogue name.
        # Basenames retain output-first, then input lookup; save_name remains
        # ignored for local files, exactly as in the original.
        if file.startswith(("/", "\\")) or "\\" in file or ":" in file or any(
            part in {"", ".", ".."} for part in file.split("/")
        ):
            raise ValueError("Select a relative managed input/output file; host paths are unavailable")
        name = file
        if file.startswith(("input/", "output/", "temp/")):
            folder, name = file.split("/", 1)
        else:
            folder = "output" if await context.assets.exists("output", name) else "input"
        asset = await context.assets.resolve(folder, name)
        filename = name.rsplit("/", 1)[-1]
    url = await context.integrations.call(
        "aliyun_oss", "upload", asset=asset, filename=filename, endpoint=endpoint, bucket=bucket,
        oss_access_key_id=oss_access_key_id, oss_access_key_secret=oss_access_key_secret,
        oss_session_token=oss_session_token, use_cname=use_cname, visit_endpoint=visit_endpoint,
        sign=sign, timeout=timeout,
    )
    return (url,)
