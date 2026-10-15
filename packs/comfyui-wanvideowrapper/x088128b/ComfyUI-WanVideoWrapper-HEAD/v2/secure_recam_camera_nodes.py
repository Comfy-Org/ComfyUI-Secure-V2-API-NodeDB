"""Exact ReCam geometry with immutable pack data; no model/camera inference."""
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
import math
from einops import rearrange
from comfy_api.latest import io

RESOURCE_SIZE = 81121
RESOURCE_SHA256 = "02992636a7350e00b7024fb98ac7e88bed60a315b81cd728bb50d11d2dca815c"
MAX_INPUT_ELEMENTS = 16777216
MAX_WORK_BYTES = 67108864
CAMERAS = ["pan_right", "pan_left", "tilt_up", "tilt_down", "zoom_in",
           "zoom_out", "translate_up", "translate_down", "arc_left", "arc_right"]

def _camera_data():
    root = Path(__file__).resolve().parent
    path = root/"recammaster"/"recam_extrinsics.json"
    if path.is_symlink() or path.resolve() != path:
        raise ValueError("ReCam camera resource must be immutable and in-pack")
    with path.open("rb") as stream:
        data = stream.read(RESOURCE_SIZE+1)
    if len(data) != RESOURCE_SIZE or hashlib.sha256(data).hexdigest() != RESOURCE_SHA256:
        raise ValueError("ReCam camera resource size/hash mismatch")
    return json.loads(data)

def parse_matrix(matrix_str):
    rows = matrix_str.strip().split('] [')
    matrix = []
    for row in rows:
        row = row.replace('[', '').replace(']', '')
        matrix.append(list(map(float, row.split())))
    return np.array(matrix)

class WanVideoReCamMasterDefaultCamera(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="WanVideoReCamMasterDefaultCamera",
            display_name="WanVideo ReCamMaster Default Camera",category="WanVideoWrapper",
            description="https://github.com/KwaiVGI/ReCamMaster",
            inputs=[io.Combo.Input("camera_type",options=CAMERAS,default="pan_right",tooltip="Camera type to use"),
                    io.Latent.Input("latents",tooltip="source video")],
            outputs=[io.Custom("CAMERAPOSES").Output(display_name="camera_poses")])
    @classmethod
    def execute(cls,camera_type,latents):
        value = latents["samples"]
        if isinstance(value,torch.Tensor):
            if value.device.type != "cpu":
                raise ValueError("ReCam geometry staging requires admitted CPU value buffers")
            if value.numel() > MAX_INPUT_ELEMENTS or value.numel()*value.element_size()*3 > MAX_WORK_BYTES:
                raise ValueError("ReCam input exceeds bounded element/wire work")
        if isinstance(camera_type,str) and len(camera_type.encode("utf-8",errors="surrogatepass")) > 65536:
            raise ValueError("ReCam camera name exceeds 64 KiB")
        cam_data = _camera_data()
        samples = value.squeeze(0)
        C,T,H,W = samples.shape
        num_frames = (T-1)*4+1
        if num_frames > 4000:
            raise ValueError("ReCam projected frame-index work exceeds 4000")
        camera_type_map = {name:index+1 for index,name in enumerate(CAMERAS)}
        cam_idx = list(range(num_frames))[::4]
        traj = [parse_matrix(cam_data[f"frame{idx}"][f"cam{int(camera_type_map[camera_type]):02d}"]) for idx in cam_idx]
        traj = np.stack(traj).transpose(0,2,1)
        return io.NodeOutput(traj)

class WanVideoReCamMasterGenerateOrbitCamera(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="WanVideoReCamMasterGenerateOrbitCamera",
            display_name="WanVideo ReCamMaster Generate Orbit Camera",category="WanVideoWrapper",
            description="https://github.com/KwaiVGI/ReCamMaster",
            inputs=[io.Int.Input("num_frames",default=81,min=1,max=1000,step=1,tooltip="Number of frames to generate"),
                    io.Int.Input("degrees",default=90,min=-180,max=180,step=1,tooltip="Degrees to orbit")],
            outputs=[io.Custom("CAMERAPOSES").Output(display_name="camera_poses")])
    @classmethod
    def execute(cls,degrees,num_frames):
        if isinstance(num_frames,int) and num_frames > 1000:
            raise ValueError("ReCam orbit exceeds 1000 projected frames")
        if isinstance(degrees,(int,float)) and not np.isfinite(degrees):
            raise ValueError("ReCam orbit angle must be finite")
        return io.NodeOutput(_orbit(degrees,num_frames))

class Camera:
    def __init__(self,c2w):
        c2w_mat = np.array(c2w).reshape(4,4)
        self.c2w_mat = c2w_mat
        self.w2c_mat = np.linalg.inv(c2w_mat)

class WanVideoReCamMasterCameraEmbed(io.ComfyNode):
    SDK_REFS = False
    SDK_PERMISSIONS = ("raw",)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="WanVideoReCamMasterCameraEmbed",
            display_name="WanVideo ReCamMaster Camera Embed",category="WanVideoWrapper",
            description="https://github.com/KwaiVGI/ReCamMaster",
            inputs=[io.Custom("CAMERAPOSES").Input("camera_poses"),
                    io.Latent.Input("latents",tooltip="source video")],
            outputs=[io.Custom("WANVIDIMAGE_EMBEDS").Output(display_name="camera_embeds"),
                     io.Custom("CAMERAPOSES").Output(display_name="camera_poses")])
    @classmethod
    def execute(cls,camera_poses,latents):
        value = latents["samples"]
        if isinstance(value,torch.Tensor):
            if value.device.type != "cpu":
                raise ValueError("ReCam embedding staging requires admitted CPU value buffers")
            if value.numel() > MAX_INPUT_ELEMENTS or value.numel()*value.element_size()*3 > MAX_WORK_BYTES:
                raise ValueError("ReCam embedding input exceeds bounded element/wire work")
        if isinstance(camera_poses,(list,tuple)) or (
                isinstance(camera_poses,(np.ndarray,torch.Tensor)) and camera_poses.ndim > 0):
            if len(camera_poses) > 1000:
                raise ValueError("ReCam embedding exceeds 1000 projected camera poses")
        if isinstance(camera_poses,np.ndarray):
            if camera_poses.size > MAX_INPUT_ELEMENTS or camera_poses.nbytes*4 > MAX_WORK_BYTES:
                raise ValueError("ReCam pose input exceeds bounded element/wire work")
        if isinstance(camera_poses,torch.Tensor):
            if camera_poses.device.type != "cpu":
                raise ValueError("ReCam pose staging requires admitted CPU value buffers")
            if camera_poses.numel() > MAX_INPUT_ELEMENTS or camera_poses.numel()*camera_poses.element_size()*4 > MAX_WORK_BYTES:
                raise ValueError("ReCam pose input exceeds bounded element/wire work")
        if isinstance(camera_poses,(list,tuple)):
            elements = bytes_count = 0
            for pose in camera_poses:
                if isinstance(pose,np.ndarray):
                    elements += pose.size
                    bytes_count += pose.nbytes
                elif isinstance(pose,torch.Tensor):
                    if pose.device.type != "cpu":
                        raise ValueError("ReCam pose staging requires admitted CPU value buffers")
                    elements += pose.numel()
                    bytes_count += pose.numel()*pose.element_size()
                if elements > MAX_INPUT_ELEMENTS or bytes_count*4 > MAX_WORK_BYTES:
                    raise ValueError("ReCam pose list exceeds bounded aggregate/wire work")
        return cls._source_process(camera_poses,latents)
    @classmethod
    def _source_process(cls,camera_poses,latents):
        samples = latents["samples"].squeeze(0)
        C,T,H,W = samples.shape
        num_frames = (T-1)*4+1
        c2ws = []
        for c2w in camera_poses:
            c2w = c2w[:, [1,2,0,3]]
            c2w[:3,1] *= -1.
            c2w[:3,3] /= 100
            c2ws.append(c2w)
        tgt_cam_params = [Camera(cam_param) for cam_param in c2ws]
        relative_poses = []
        for i in range(len(tgt_cam_params)):
            relative_pose = cls.get_relative_pose([tgt_cam_params[0],tgt_cam_params[i]])
            relative_poses.append(torch.as_tensor(relative_pose)[:,:3,:][1])
        pose_embedding = torch.stack(relative_poses,dim=0)
        pose_embedding = rearrange(pose_embedding,'b c d -> b (c d)')
        seq_len = math.ceil((H*W)/4*((num_frames-1)//4+1))
        embeds = {
            "max_seq_len":seq_len, "target_shape":samples.shape, "num_frames":num_frames,
            "recammaster":{"camera_embed":pose_embedding,"source_latents":samples}
        }
        return io.NodeOutput(embeds,camera_poses)
    @classmethod
    def get_relative_pose(cls,cam_params):
        abs_w2cs = [cam_param.w2c_mat for cam_param in cam_params]
        abs_c2ws = [cam_param.c2w_mat for cam_param in cam_params]
        cam_to_origin = 0
        target_cam_c2w = np.array([
            [1,0,0,0], [0,1,0,-cam_to_origin],
            [0,0,1,0], [0,0,0,1]
        ])
        abs2rel = target_cam_c2w @ abs_w2cs[0]
        ret_poses = [target_cam_c2w,] + [abs2rel @ abs_c2w for abs_c2w in abs_c2ws[1:]]
        ret_poses = np.array(ret_poses,dtype=np.float32)
        return ret_poses

def _orbit(degrees,num_frames):
    def generate_orbit(num_frames=num_frames, degrees=degrees):
        camera_data = []
        center = np.array([3390, 1380, 240])
        for i in range(num_frames):
            angle = i * degrees / (num_frames - 1)
            angle_rad = np.radians(angle)
            x = center[0] - np.cos(angle_rad)
            y = center[1] - np.sin(angle_rad)
            z = center[2]
            camera_pos = np.array([x, y, z])
            dir_to_center = center - camera_pos
            look_angle = np.arctan2(dir_to_center[1], dir_to_center[0])
            cos_look = np.cos(look_angle)
            sin_look = np.sin(look_angle)
            transform = np.array([
                [cos_look, -sin_look, 0, x],
                [sin_look, cos_look, 0, y],
                [0, 0, 1, z],
                [0, 0, 0, 1]
            ])
            camera_data.append(transform)
        return camera_data
    camera_transforms = generate_orbit(num_frames=num_frames, degrees=degrees)
    traj = camera_transforms[::4]
    traj = np.stack(traj)
    return traj

NODE_CLASS_MAPPINGS = {
    "WanVideoReCamMasterDefaultCamera":WanVideoReCamMasterDefaultCamera,
    "WanVideoReCamMasterGenerateOrbitCamera":WanVideoReCamMasterGenerateOrbitCamera,
    "WanVideoReCamMasterCameraEmbed":WanVideoReCamMasterCameraEmbed,
}
