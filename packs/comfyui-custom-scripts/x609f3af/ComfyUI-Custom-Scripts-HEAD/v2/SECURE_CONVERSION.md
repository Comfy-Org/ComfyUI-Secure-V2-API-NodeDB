# Secure conversion status

Pinned upstream commit: `609f3afaa74b2f88ef9ce8d939626065e3247469`.

All 13 upstream backend node mappings are supported and execute through the V2
guest boundary. No node mapping is rejected.

- `CheckpointLoader|pysssss`
- `ConstrainImageforVideo|pysssss`
- `ConstrainImage|pysssss`
- `LoadText|pysssss`
- `LoraLoader|pysssss`
- `MathExpression|pysssss`
- `PlaySound|pysssss`
- `Repeater|pysssss`
- `ReroutePrimitive|pysssss`
- `SaveText|pysssss`
- `ShowText|pysssss`
- `StringFunction|pysssss`
- `SystemNotification|pysssss`

The following legacy behaviors are deliberately unavailable without rejecting
their nodes:

- Repeater `multi` mode rewrote the completed prompt and downstream consumers.
  `single` mode supports both reuse and fresh producer instances through bounded,
  declarative graph expansion.
- SaveText cannot modify the input directory. It writes confined files under
  output or temp.
- PlaySound cannot fetch arbitrary URLs. It can play audio packaged with this
  node pack through the host audio command.
