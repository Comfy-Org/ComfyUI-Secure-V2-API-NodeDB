# Secure Nodes V2 conversion

Upstream: `https://github.com/mittimi/ComfyUI_mittimiRecalculateSize`

Pinned commit: `07a7185aba4a52629a05f986d06651d42b6293d2`

The single scalar node is supported with its exact IDs, schema, integer
truncation, and output names. It runs with no capabilities. Upstream declares
`WEB_DIRECTORY = "./js"`, but the pinned repository contains no `js` directory
or frontend source; the secure package therefore declares no frontend module.
