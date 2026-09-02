# Secure Nodes 2.0 conversion

Pinned upstream commit: `50c7b71a6a224734cc9b21963c6d1926816a97f1`.

- Backend nodes converted: 1/1.
- Rejected nodes: 0.
- Frontend modules requiring conversion: 0.
- The legacy `.pt` pickle whitelist and `weights_only=False` fallback are not
  present in the secure conversion.
- The provider exposes a fixed, tensor-only YOLOv8 detector recipe backed by
  `model.safetensors` from a pinned Hugging Face revision and SHA-256.
- The pinned file contains 595 tensors and strict-loads into the fixed
  two-class YOLOv8x architecture under Ultralytics 8.3.162 with no missing or
  unexpected keys. A real CPU forward/NMS smoke pass also completed against
  those weights (one batch, two-class output), rather than stopping at a
  mocked model boundary.
- The weight is declared on-demand: selecting the provider installs it once;
  subsequent executions use the verified local cache without contacting the
  Hub again.
- YOLO preprocessing, inference, NMS, and conversion to Impact `SEGS` remain
  pack-side in the consuming Impact Pack. Core only brokers the declared
  SafeTensors state dictionary.
