# Secure Nodes 2.0 conversion

Pinned upstream commit: `50c7b71a6a224734cc9b21963c6d1926816a97f1`.

- Backend nodes converted: 1/1.
- Rejected nodes: 0.
- Frontend modules requiring conversion: 0.
- The legacy `.pt` pickle whitelist and `weights_only=False` fallback are not present in the secure conversion.

## UltralyticsDetectorProvider (fidelity repair r1)

- It accepts any model in the host's Ultralytics catalogues and resolves it the way upstream does: the
  `ultralytics` catalogue first, then `ultralytics_bbox` or `ultralytics_segm` by the name's `bbox/` or `segm/`
  prefix. An unknown name fails with upstream's message.
- The menu lists the host's `ultralytics_bbox` names, because a host menu cannot add upstream's `bbox/`
  prefix. So `validate_inputs` also accepts saved `bbox/...` and `segm/...` values, and treats a bare name as
  a bbox model.
- It returns plain descriptors (catalogue, name, menu value) and loads nothing. As upstream does, a `bbox`
  name gives only a BBOX_DETECTOR (`None` stands for NO_SEGM_DETECTOR), and any other name also gives a
  SEGM_DETECTOR over the same model.
- Impact Pack's v2 reads the weight through the engine, rebuilds the model in its own guest and runs upstream
  detection code there.
