import torch
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont
import numpy as np

def tensor2pil(image):
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

def pil2tensor(image):
    return torch.from_numpy(np.array(image).astype(np.float32) / 255.0).unsqueeze(0)

def emptyimage(width, height, batch_size=1, color=(0,0,0,0)):
    r = torch.full([batch_size, height, width, 1], color[0] / 255, dtype=torch.float32, device="cpu")
    g = torch.full([batch_size, height, width, 1], color[1] / 255, dtype=torch.float32, device="cpu")
    b = torch.full([batch_size, height, width, 1], color[2] / 255, dtype=torch.float32, device="cpu")
    a = torch.full([batch_size, height, width, 1], color[3], dtype=torch.float32, device="cpu")
    result_rgb = torch.cat((r, g, b), dim=-1)
    result_rgba = torch.cat((r, g, b, a), dim=-1)
    result_mask = torch.full((batch_size, height, width), color[3], dtype=torch.float32, device="cpu")
    return {
        'RGB': result_rgb,
        'RGBA': result_rgba,
        'MASK':result_mask
    }

def color_variance(color1, color2):
    red_vs = (color1[0] - color2[0]) ** 2
    green_vs = (color1[1] - color2[1]) ** 2
    blue_vs = (color1[2] - color2[2]) ** 2
    variance = (red_vs + green_vs + blue_vs) ** 0.5
    variance_unified = variance / (255 * 3 ** 0.5)
    return variance_unified

def convert_color(image, origin_color, new_color, tolerance):
    data = image.getdata()
    new_data = []
    for item in data:
        if color_variance(item[:3], origin_color) < tolerance:
            new_data.append(new_color)
        else:
            new_data.append(item[:3])
    image.putdata(new_data)
    return image

def cross_fade_videos(video1, video2, num_corssfade_frame):
    if video1.ndim != video2.ndim:
        raise ValueError("crossfadevideos: 拼接图片类型不一致\nImageType Mismatch")
    if video1[[0],].shape != video2[[0],].shape:
        raise ValueError("crossfadevideos: 拼接图片尺寸不一致\nImageSize Mismatch")
    if num_corssfade_frame > video1.shape[0] or num_corssfade_frame > video2.shape[0]:
        raise ValueError("crossfadevideos: 拼接图片数目应大于过渡数目\nVideoLength should be longer than CrossLength")
    video_slice1 = video1[:-num_corssfade_frame]
    video_slice2 = video1[-num_corssfade_frame:]
    video_slice3 = video2[:num_corssfade_frame]
    video_slice4 = video2[num_corssfade_frame:]
    alpha_list = []
    count = num_corssfade_frame + 1
    while count > 1:
        alpha_list.append((count - 1) / (num_corssfade_frame + 1))
        count -= 1
    alpha_list.reverse()
    blend_list = []
    index = 0
    for alpha in alpha_list:
        mixed = video_slice2[[index],] * (1 - alpha) + video_slice3[[index],] * alpha
        blend_list.append(mixed)
        index += 1
    blended_slice = torch.cat(blend_list, dim=0)
    result = torch.cat((video_slice1, blended_slice, video_slice4), dim=0)
    return result

def cross_fade_videos_loopback(video1, video2, cross_fade_frames1, cross_fade_frames2):
    if video1.shape[1:] != video2.shape[1:]:
        raise ValueError("crossfadevideosloopback: 拼接图片类型或尺寸不一致\nImage Type or Dimension Mismatch")
    if cross_fade_frames1 > video1.shape[0] or cross_fade_frames1 > video2.shape[0] or cross_fade_frames2 > video1.shape[0] or cross_fade_frames2 > video2.shape[0]:
        raise ValueError("crossfadevideosloopback: 拼接图片数目应大于过渡数目\nVideo Length should be longer than CrossLength")
    if cross_fade_frames1 + cross_fade_frames2 > min(video1.shape[0], video2.shape[0]):
        raise ValueError("crossfadevideosloopback: 两组过渡帧数量之和大于输入图片数量\nVideo Length should be longer than the sum of Cross Lengths")
    
    video_slice1 = video1[0:cross_fade_frames2]
    video_slice2 = video1[cross_fade_frames2:-cross_fade_frames1]
    video_slice3 = video1[-cross_fade_frames1:]
    video_slice4 = video2[0:cross_fade_frames1]
    video_slice5 = video2[cross_fade_frames1:-cross_fade_frames2]
    video_slice6 = video2[-cross_fade_frames2:]
    alpha_list1 = []
    alpha_list2 = []

    count1 = cross_fade_frames1 + 1
    while count1 > 1:
        alpha_list1.append((count1 - 1) / (cross_fade_frames1 + 1))
        count1 -= 1
    alpha_list1.reverse()

    count2 = cross_fade_frames2 + 1
    while count2 > 1:
        alpha_list2.append((count2 - 1) / (cross_fade_frames2 + 1))
        count2 -= 1
    alpha_list2.reverse()

    blend_list = []
    index1 = 0
    for alpha in alpha_list1:
        mixed = video_slice3[[index1],] * (1 - alpha) + video_slice4[[index1],] * alpha
        blend_list.append(mixed)
        index1 += 1
    blended_mix1 = torch.cat(blend_list, dim=0)
    blended_mix1 = torch.cat((video_slice2, blended_mix1, video_slice5), dim=0)

    blend_list2 = []
    index2 = 0
    for alpha in alpha_list2:
        mixed = video_slice6[[index2],] * (1 - alpha) + video_slice1[[index2],] * alpha
        blend_list2.append(mixed)
        index2 += 1
    blended_mix2 = torch.cat(blend_list2, dim=0)
    blended_mix_all = torch.cat((blended_mix1, blended_mix2), dim=0)
    result = torch.cat((blended_mix_all[-cross_fade_frames2:], blended_mix_all[0:-cross_fade_frames2]), dim=0)

    return result


