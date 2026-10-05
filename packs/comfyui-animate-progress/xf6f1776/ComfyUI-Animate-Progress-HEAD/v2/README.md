# ComfyUI Animate Progress — Secure Nodes V2

Animate Progress replaces the plain execution indicator with a configurable
bottom-of-viewport progress bar and one of 34 bundled animated runners. Its
settings dialog preserves all eight bar styles, colors, opacity, runner size
and position, shadow, random selection, and fade behavior.

This frontend-only conversion uses typed viewport panels, a host modal,
pack-owned per-user storage, and bounded backend execution events. It does not
register a server route, inspect the filesystem, modify the ambient page DOM,
or install global browser listeners.

The 34 GIFs pinned in this release are available. The legacy installation
instruction to add more GIFs by mutating the installed server package is an
administrator deployment operation and is intentionally outside a secure
cloud pack's authority.

## License

MIT — see [LICENSE](LICENSE).
