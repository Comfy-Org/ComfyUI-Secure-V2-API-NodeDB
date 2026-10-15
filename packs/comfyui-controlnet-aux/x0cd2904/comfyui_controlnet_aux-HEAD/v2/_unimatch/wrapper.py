from .detector import UnimatchDetector
import torch
import numpy as np

class Unimatch_OptFlowPreprocessor:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": dict(
                image=("IMAGE",),
                ckpt_name=(
                    ["gmflow-scale1-mixdata.pth", "gmflow-scale2-mixdata.pth", "gmflow-scale2-regrefine6-mixdata.pth"],
                    {"default": "gmflow-scale2-regrefine6-mixdata.pth"}
                ),
                backward_flow=("BOOLEAN", {"default": False}),
                bidirectional_flow=("BOOLEAN", {"default": False})
            )
        }

    RETURN_TYPES = ("OPTICAL_FLOW", "IMAGE")
    RETURN_NAMES = ("OPTICAL_FLOW", "PREVIEW_IMAGE")
    FUNCTION = "estimate"

    CATEGORY = "ControlNet Preprocessors/Optical Flow"

    async def estimate(self, image, ckpt_name, backward_flow=False, bidirectional_flow=False, *, selection):
        assert len(image) > 1, "[Unimatch] Requiring as least two frames as an optical flow estimator. Only use this node on video input."    
        tensor_images = image
        model = (await UnimatchDetector.from_managed(filename=ckpt_name, selection=selection)).to(selection['device'])
        flows, vis_flows = [], []
        for i in range(len(tensor_images) - 1):
            image0, image1 = np.asarray(image[i:i+2].cpu() * 255., dtype=np.uint8)
            flow, vis_flow = model(image0, image1, output_type="np", pred_bwd_flow=backward_flow, pred_bidir_flow=bidirectional_flow)
            flows.append(torch.from_numpy(flow).float())
            vis_flows.append(torch.from_numpy(vis_flow).float() / 255.)
        del model
        return (torch.stack(flows, dim=0), torch.stack(vis_flows, dim=0))
