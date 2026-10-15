import cv2
import numpy as np
import torch
from torch.nn import functional as F
from PIL import Image
from einops import rearrange
from ._image_math import HWC3,nms,resize_image_with_pad,safe_step,common_input_validate
class PidiNetDetector:

    def __init__(self, netNetwork):
        self.netNetwork = netNetwork
        self.device = 'cpu'

    def __call__(self, input_image, detect_resolution=512, safe=False, output_type='pil', scribble=False, apply_filter=False, upscale_method='INTER_CUBIC', **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        detected_map, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)
        detected_map = detected_map[:, :, ::-1].copy()
        with torch.no_grad():
            image_pidi = torch.from_numpy(detected_map).float().to(self.device)
            image_pidi = image_pidi / 255.0
            image_pidi = rearrange(image_pidi, 'h w c -> 1 c h w')
            edge = self.netNetwork(image_pidi)[-1]
            edge = edge.cpu().numpy()
            if apply_filter:
                edge = edge > 0.5
            if safe:
                edge = safe_step(edge)
            edge = (edge * 255.0).clip(0, 255).astype(np.uint8)
        detected_map = edge[0, 0]
        if scribble:
            detected_map = nms(detected_map, 127, 3.0)
            detected_map = cv2.GaussianBlur(detected_map, (0, 0), 3.0)
            detected_map[detected_map > 4] = 255
            detected_map[detected_map < 255] = 0
        detected_map = HWC3(remove_pad(detected_map))
        if output_type == 'pil':
            detected_map = Image.fromarray(detected_map)
        return detected_map

def deccode_output_score_and_ptss(tpMap, topk_n=200, ksize=5):
    """
    tpMap:
    center: tpMap[1, 0, :, :]
    displacement: tpMap[1, 1:5, :, :]
    """
    b, c, h, w = tpMap.shape
    assert b == 1, 'only support bsize==1'
    displacement = tpMap[:, 1:5, :, :][0]
    center = tpMap[:, 0, :, :]
    heat = torch.sigmoid(center)
    hmax = F.max_pool2d(heat, (ksize, ksize), stride=1, padding=(ksize - 1) // 2)
    keep = (hmax == heat).float()
    heat = heat * keep
    heat = heat.reshape(-1)
    scores, indices = torch.topk(heat, topk_n, dim=-1, largest=True)
    yy = torch.floor_divide(indices, w).unsqueeze(-1)
    xx = torch.fmod(indices, w).unsqueeze(-1)
    ptss = torch.cat((yy, xx), dim=-1)
    ptss = ptss.detach().cpu().numpy()
    scores = scores.detach().cpu().numpy()
    displacement = displacement.detach().cpu().numpy()
    displacement = displacement.transpose((1, 2, 0))
    return (ptss, scores, displacement)

def pred_lines(image, model, input_shape=[512, 512], score_thr=0.1, dist_thr=20.0):
    h, w, _ = image.shape
    device = next(iter(model.parameters())).device
    h_ratio, w_ratio = [h / input_shape[0], w / input_shape[1]]
    resized_image = np.concatenate([cv2.resize(image, (input_shape[1], input_shape[0]), interpolation=cv2.INTER_AREA), np.ones([input_shape[0], input_shape[1], 1])], axis=-1)
    resized_image = resized_image.transpose((2, 0, 1))
    batch_image = np.expand_dims(resized_image, axis=0).astype('float32')
    batch_image = batch_image / 127.5 - 1.0
    batch_image = torch.from_numpy(batch_image).float()
    batch_image = batch_image.to(device)
    outputs = model(batch_image)
    pts, pts_score, vmap = deccode_output_score_and_ptss(outputs, 200, 3)
    start = vmap[:, :, :2]
    end = vmap[:, :, 2:]
    dist_map = np.sqrt(np.sum((start - end) ** 2, axis=-1))
    segments_list = []
    for center, score in zip(pts, pts_score):
        y, x = center
        distance = dist_map[y, x]
        if score > score_thr and distance > dist_thr:
            disp_x_start, disp_y_start, disp_x_end, disp_y_end = vmap[y, x, :]
            x_start = x + disp_x_start
            y_start = y + disp_y_start
            x_end = x + disp_x_end
            y_end = y + disp_y_end
            segments_list.append([x_start, y_start, x_end, y_end])
    lines = 2 * np.array(segments_list)
    lines[:, 0] = lines[:, 0] * w_ratio
    lines[:, 1] = lines[:, 1] * h_ratio
    lines[:, 2] = lines[:, 2] * w_ratio
    lines[:, 3] = lines[:, 3] * h_ratio
    return lines

class MLSDdetector:

    def __init__(self, model):
        self.model = model

    def __call__(self, input_image, thr_v=0.1, thr_d=0.1, detect_resolution=512, output_type='pil', upscale_method='INTER_AREA', **kwargs):
        input_image, output_type = common_input_validate(input_image, output_type, **kwargs)
        detected_map, remove_pad = resize_image_with_pad(input_image, detect_resolution, upscale_method)
        img = detected_map
        img_output = np.zeros_like(img)
        try:
            with torch.no_grad():
                lines = pred_lines(img, self.model, [img.shape[0], img.shape[1]], thr_v, thr_d)
                for line in lines:
                    x_start, y_start, x_end, y_end = [int(val) for val in line]
                    cv2.line(img_output, (x_start, y_start), (x_end, y_end), [255, 255, 255], 1)
        except Exception as e:
            pass
        detected_map = remove_pad(HWC3(img_output[:, :, 0]))
        if output_type == 'pil':
            detected_map = Image.fromarray(detected_map)
        return detected_map
