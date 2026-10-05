# Radar Weights Node — Secure Nodes V2 conversion

- Upstream: <https://github.com/FunnyFinger/ComfyUi-RadarWeightNode>
- Pinned commit: `64bd1a505fad852f25ef7b5894669b53e1bb4ed0`
- Release key: `x64bd1a5`
- Census: one Python node, one frontend extension, four legacy routes.

The four HTTP routes and source-adjacent JSON file were synchronization
plumbing for one node's radar values. The V2 conversion stores those values in
the node's existing `_weights_sync` input, so each workflow owns its state and
different users, graphs, and nodes cannot overwrite one another. The radar is
rendered in an isolated mounted canvas. It keeps the legacy 3–10 axes, radial
port placement, drag projection, two-decimal values, shrink/regrow memory, and
ten-value backend output contract without filesystem, network, or backend-route
authority.
