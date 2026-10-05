# ComfyUI Better Strings — Secure Nodes V2

This conversion preserves the Better Multiline String node from upstream commit
`43b21384353cc94f23cdfde65f586d779f91ba47`.

The node exposes a required multiline string editor and an optional linked
string input. A nonblank linked value is right-trimmed, given one trailing
comma when needed, separated from the editor value by two newlines, and then
returned. It runs in the isolated guest without host capabilities.
