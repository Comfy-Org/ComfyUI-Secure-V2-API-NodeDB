"""Pack-owned bounded Agg camera raster; no pyplot registry or model access."""
import io as _bytes_io
import math
import numpy as np
import torch
import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PIL import Image
from torchvision.transforms import ToTensor
from comfy_api.latest import io
from .secure_tensor_nodes import _bound_payload, MAX_PAYLOAD_BYTES, MAX_TENSOR_ELEMENTS


def get_c2w(w2cs, transform_matrix, relative_c2w=True):
    if relative_c2w:
        target_cam_c2w = np.array([[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
        abs2rel = target_cam_c2w @ w2cs[0]
        ret_poses = [target_cam_c2w, ] + [abs2rel @ np.linalg.inv(w2c) for w2c in w2cs[1:]]
    else:
        ret_poses = [np.linalg.inv(w2c) for w2c in w2cs]
    ret_poses = [transform_matrix @ x for x in ret_poses]
    return np.array(ret_poses, dtype=np.float32)


def _preflight(camera_poses, scale, base_xval, zval, arrow_length):
    _bound_payload(camera_poses)
    if isinstance(camera_poses, (np.ndarray, torch.Tensor, list, tuple)) and len(camera_poses)>512:
        raise ValueError("Wan ReCam raster exceeds512 camera frames")
    for value in (scale, base_xval, zval, arrow_length):
        if isinstance(value,(int,float)) and (not math.isfinite(value) or abs(value)>100):
            raise ValueError("Wan ReCam raster parameter exceeds finite100 bound")
    if isinstance(camera_poses,torch.Tensor) and (camera_poses.device.type!="cpu" or camera_poses.layout!=torch.strided):
        raise ValueError("Wan ReCam raster requires dense CPU camera values")
    dpi = mpl.rcParams["figure.dpi"]
    if not isinstance(dpi,(int,float)) or not math.isfinite(dpi) or dpi<=0:
        raise ValueError("Wan ReCam raster requires a finite positive managed DPI")
    # Fixed18x7 figure; reserve full uncropped Agg/PIL/tensor work, not merely
    # observed tightly-cropped output. This is a projected guard, not a physical
    # model/profile allocation grant.
    elements = math.ceil(18*dpi)*math.ceil(7*dpi)*4
    if elements>MAX_TENSOR_ELEMENTS or elements*9>MAX_PAYLOAD_BYTES:
        raise ValueError("Wan ReCam raster projected figure exceeds tensor/64MiB bounds")


class _ReCamRaster:
    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'plot'
    CATEGORY = 'WanVideoWrapper'
    DESCRIPTION = '\nVisualizes the camera poses, from Animatediff-Evolved CameraCtrl Pose  \nor a .txt file with RealEstate camera intrinsics and coordinates, in a 3D plot. \n'

    def plot(self, camera_poses, scale, base_xval, zval, arrow_length):
        x_min = -2.0 * scale
        x_max = 2.0 * scale
        y_min = -2.0 * scale
        y_max = 2.0 * scale
        z_min = -2.0 * scale
        z_max = 2.0 * scale
        self.fig = Figure(figsize=(18, 7))
        FigureCanvasAgg(self.fig)
        self.fig.patch.set_facecolor('#353535')
        self.ax = self.fig.add_subplot(projection='3d')
        self.ax.set_facecolor('#353535')
        self.ax.grid(color='#999999', linestyle='-', linewidth=0.5)
        self.plotly_data = None
        self.ax.set_aspect('auto')
        self.ax.set_xlim(x_min, x_max)
        self.ax.set_ylim(y_min, y_max)
        self.ax.set_zlim(z_min, z_max)
        self.ax.set_xlabel('x', color='#999999')
        self.ax.set_ylabel('y', color='#999999')
        self.ax.set_zlabel('z', color='#999999')
        for text in self.ax.get_xticklabels() + self.ax.get_yticklabels() + self.ax.get_zticklabels():
            text.set_color('#999999')
        print('initialize camera pose visualizer')
        total_frames = len(camera_poses)
        w2cs = []
        for cam in camera_poses:
            if cam.shape[0] == 3:
                cam = np.vstack((cam, np.array([[0, 0, 0, 1]])))
            cam = cam[:, [1, 2, 0, 3]]
            cam[:3, 1] *= -1.0
            w2cs.append(np.linalg.inv(cam))
        transform_matrix = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
        c2ws = get_c2w(w2cs, transform_matrix, True)
        scale = max((max(abs(c2w[:3, 3])) for c2w in c2ws))
        if scale > 0.001:
            for c2w in c2ws:
                c2w[:3, 3] /= scale
        for frame_idx, c2w in enumerate(c2ws):
            self.extrinsic2pyramid(c2w, frame_idx / total_frames, hw_ratio=1, base_xval=base_xval, zval=zval)
            if arrow_length > 0:
                pos = c2w[:3, 3]
                forward = c2w[:3, 2]
                arrow_start = pos + forward * base_xval
                arrow_length = arrow_length
                self.ax.quiver(arrow_start[0], arrow_start[1], arrow_start[2], forward[0], forward[1], forward[2], color='black', length=arrow_length, arrow_length_ratio=0.1)
        cmap = mpl.cm.rainbow
        norm = mpl.colors.Normalize(vmin=0, vmax=total_frames)
        colorbar = self.fig.colorbar(mpl.cm.ScalarMappable(norm=norm, cmap=cmap), ax=self.ax, orientation='vertical')
        colorbar.set_label('Frame', color='#999999')
        colorbar.ax.yaxis.set_tick_params(colors='#999999')
        ticks = np.arange(0, total_frames, 10)
        colorbar.ax.yaxis.set_ticks(ticks)
        self.ax.set_title('')
        self.fig.canvas.draw()
        buf = _bytes_io.BytesIO()
        self.fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
        if buf.getbuffer().nbytes > 8388608:
            buf.close()
            raise ValueError("Wan ReCam raster PNG exceeds8MiB buffer bound")
        buf.seek(0)
        img = Image.open(buf)
        if img.width * img.height * 4 > MAX_TENSOR_ELEMENTS or img.width * img.height * 4 * 9 > MAX_PAYLOAD_BYTES:
            img.close()
            buf.close()
            raise ValueError("Wan ReCam raster cropped output exceeds tensor/64MiB bounds")
        tensor_img = ToTensor()(img)
        img.close()
        buf.close()
        tensor_img = tensor_img.permute(1, 2, 0).unsqueeze(0)
        return (tensor_img,)

    def extrinsic2pyramid(self, extrinsic, color_map='red', hw_ratio=9 / 16, base_xval=1, zval=3):
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        vertex_std = np.array([[0, 0, 0, 1], [base_xval, -base_xval * hw_ratio, zval, 1], [base_xval, base_xval * hw_ratio, zval, 1], [-base_xval, base_xval * hw_ratio, zval, 1], [-base_xval, -base_xval * hw_ratio, zval, 1]])
        vertex_transformed = vertex_std @ extrinsic.T
        meshes = [[vertex_transformed[0, :-1], vertex_transformed[1][:-1], vertex_transformed[2, :-1]], [vertex_transformed[0, :-1], vertex_transformed[2, :-1], vertex_transformed[3, :-1]], [vertex_transformed[0, :-1], vertex_transformed[3, :-1], vertex_transformed[4, :-1]], [vertex_transformed[0, :-1], vertex_transformed[4, :-1], vertex_transformed[1, :-1]], [vertex_transformed[1, :-1], vertex_transformed[2, :-1], vertex_transformed[3, :-1], vertex_transformed[4, :-1]]]
        color = color_map if isinstance(color_map, str) else mpl.cm.rainbow(color_map)
        self.ax.add_collection3d(Poly3DCollection(meshes, facecolors=color, linewidths=0.3, edgecolors=color, alpha=0.35))

class ReCamMasterPoseVisualizer(io.ComfyNode):
    SDK_REFS=False
    SDK_PERMISSIONS=("raw",)
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="ReCamMasterPoseVisualizer", display_name="ReCamMaster Pose Visualizer",
            category="WanVideoWrapper", description=_ReCamRaster.DESCRIPTION, inputs=[
                io.Custom("CAMERAPOSES").Input("camera_poses"),
                io.Float.Input("base_xval",default=0.2,min=0,max=100,step=0.01),
                io.Float.Input("zval",default=0.3,min=0,max=100,step=0.01),
                io.Float.Input("scale",default=1.0,min=0.01,max=10.0,step=0.01),
                io.Float.Input("arrow_length",default=1,min=0,max=100,step=0.01),
            ],outputs=[io.Image.Output()])
    @classmethod
    def execute(cls,camera_poses,scale,base_xval,zval,arrow_length):
        _preflight(camera_poses,scale,base_xval,zval,arrow_length)
        # Raw transport can deliver CAMERA POSES as CPU tensors. Native raster
        # geometry expects NumPy; keep every matrix value before inversion.
        camera_poses = np.asarray(camera_poses)
        renderer=_ReCamRaster()
        try:
            with mpl.rc_context({"text.color":"#999999"}):
                result=renderer.plot(camera_poses,scale,base_xval,zval,arrow_length)[0]
            _bound_payload(result)
            return io.NodeOutput(result)
        finally:
            if hasattr(renderer,"fig"):
                renderer.fig.clear()
                renderer.fig.set_canvas(None)
                del renderer.fig
            if hasattr(renderer,"ax"):
                renderer.ax=None


NODE_CLASS_MAPPINGS={"ReCamMasterPoseVisualizer":ReCamMasterPoseVisualizer}
