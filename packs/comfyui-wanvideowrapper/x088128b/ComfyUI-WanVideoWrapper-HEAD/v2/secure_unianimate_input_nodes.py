"""Pack-owned UniAnimate tensor layout, not pose estimation or model loading."""
import torch
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES


def _preflight(pose_images, reference_pose_image, strength, start_percent, end_percent):
    _bound_payload((pose_images, reference_pose_image, strength, start_percent, end_percent))
    tensors = [value for value in (pose_images, reference_pose_image) if isinstance(value, torch.Tensor)]
    # Source makes contiguous copies but does not select another device. Bound
    # input/copy overlap without treating hardware discovery as authority.
    projected = 2 * sum(value.numel() * value.element_size() for value in tensors)
    if projected > MAX_PAYLOAD_BYTES:
        raise ValueError("Wan UniAnimate projected layout copies exceed64MiB bounds")


class WanVideoUniAnimatePoseInput(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="WanVideoUniAnimatePoseInput", display_name="WanVideo UniAnimate Pose Input",
            category="WanVideoWrapper", inputs=[
                io.Image.Input("pose_images", tooltip="Pose images"),
                io.Float.Input("strength", default=1.0, min=0.0, max=1.0, step=0.01,
                    tooltip="Strength of the pose control"),
                io.Float.Input("start_percent", default=0.0, min=0.0, max=1.0, step=0.01,
                    tooltip="Start percentage for the pose control"),
                io.Float.Input("end_percent", default=1.0, min=0.0, max=1.0, step=0.01,
                    tooltip="End percentage for the pose control"),
                io.Image.Input("reference_pose_image", optional=True, tooltip="Reference pose image"),
            ], outputs=[io.Custom("UNIANIMATE_POSE").Output(display_name="unianimate_poses")])

    @classmethod
    def execute(cls, pose_images, strength, start_percent, end_percent, reference_pose_image=None):
        _preflight(pose_images, reference_pose_image, strength, start_percent, end_percent)
        pose = pose_images.permute(3, 0, 1, 2).unsqueeze(0).contiguous()
        ref = None
        if reference_pose_image is not None:
            ref = reference_pose_image.permute(0, 3, 1, 2).contiguous()
        unianim_poses = {
            "pose": pose,
            "ref": ref,
            "strength": strength,
            "start_percent": start_percent,
            "end_percent": end_percent
        }
        return io.NodeOutput(unianim_poses)


NODE_CLASS_MAPPINGS = {"WanVideoUniAnimatePoseInput": WanVideoUniAnimatePoseInput}
