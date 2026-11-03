"""Stand-in for ``comfy.nested_tensor``: nested (multi-stream) latents are refused before sampling, so no value in
the guest is ever an instance of this class and every isinstance check in the vendored code is False."""


class NestedTensor:
    def __init__(self, *_args, **_kwargs):
        from ._refuse import refuse
        refuse("nested multi-stream latents (comfy.nested_tensor.NestedTensor)")
