# Secure Nodes V2 conversion

- Upstream: `https://github.com/BobRandomNumber/ComfyUI-Crystools-MonitorOnly`
- Commit: `779aa6d8537e44acf0db1534a35d813bdd1ad452`
- Source tree: `d2331b7d4565bec51f58c35904f5b462e0b4033b`
- Release key: `x779aa6d`
- Frozen Python contract: `8800a3ac91604c8b67185bcac307a202d644ed253c2f6ffe66251a32a3cfa9c9`
- Frozen TypeScript contract: `152c7fab547fe9ec7dd09ec256e4172af5106b8634e098ddce0eee78d5c99758`

The pinned pack registers no backend nodes and exactly one frontend extension,
`CrysMonitor.monitor`. The extension is supported. Rejected: 0. Pending: 0.

The original starts a daemon thread at import, probes hardware through `psutil`
and NVIDIA's management library, registers six HTTP routes, and pushes a custom
event. V2 starts none of that pack-owned machinery. It requests the bounded,
cached `comfy.system.monitor()` projection documented by D27 and polls no faster
than 250 ms. The frontend declares only `system.monitor`.

CPU, RAM, selected-volume, GPU-utilization, VRAM, and temperature readouts stay
separately configurable. Refresh zero stops polling and resets visible values.
The old mount-path combo is an opaque volume-id combo with sanitized labels;
mount paths never enter the worker. Unsupported sensors remain visibly
unavailable instead of using a magic negative value.

The host renders the values as top-bar badges. Width, height, smoothing, and
numbers-only settings remain declared so existing stored preferences survive,
but styling and layout are host-owned. The extension does not access the DOM,
patch menu chrome, load pack CSS, use ambient fetch, or register backend routes.
