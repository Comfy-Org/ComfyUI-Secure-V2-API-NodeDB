# Secure Nodes V2 conversion

Upstream: `https://github.com/Firetheft/ComfyUI-Animate-Progress`

Pinned commit: `f6f177643e4fd260fbc6419e3ed4690af1ad38d9`

Pinned tree: `b17240b0f39a8cbf43b5d145975a3038ea084b7d`

The exact census is supported: zero Python nodes and one frontend extension.
The upstream GET route only enumerated 34 pack-owned GIF filenames, so the
converted extension uses a closed in-module catalogue and needs no backend
route or filesystem authority.

The fixed progress surface and settings launcher are mounted as typed viewport
panels. The settings interface is a host-owned modal, preferences live in
bounded pack-owned per-user storage, and execution progress is consumed from
the typed backend/queue surfaces. Every subscription, DOM listener, pending
animation frame, timeout, modal, and panel is released on remount or teardown.

All 34 shipped runners, random and explicit selection, 12 settings, eight bar
styles, progress positioning, shadow, and fade behavior are preserved.

One deliberate deployment boundary remains: an administrator can no longer
add GIFs by writing into the installed pack directory at runtime. Secure cloud
packages are immutable; broad server-directory enumeration or write authority
would be disproportionate to an animated progress indicator.
