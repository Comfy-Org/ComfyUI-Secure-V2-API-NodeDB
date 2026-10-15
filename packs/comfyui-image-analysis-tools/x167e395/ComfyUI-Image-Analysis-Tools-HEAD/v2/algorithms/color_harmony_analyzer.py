import numpy as np
import cv2
import torch
from .. import _render as plt
from sklearn.cluster import KMeans
from ._utils import fig_to_tensor, empty_image, to_rgb_uint8

def hue_distance(h1, h2):
    return min(abs(h1 - h2), 180 - abs(h1 - h2))

def match_harmony(hues):
    if not hues or len(hues) < 2:
        return ('Insufficient hues', 0.0)
    scores = {}
    diffs = [hue_distance(hues[i], hues[j]) for i in range(len(hues)) for j in range(i + 1, len(hues))]
    if any((170 <= d <= 190 for d in diffs)):
        scores['Complementary'] = 1.0
    if all((d < 30 for d in diffs)):
        scores['Analogous'] = 1.0
    if any((110 <= d <= 130 for d in diffs)) and len(hues) >= 3:
        scores['Triadic'] = 1.0
    if len(hues) >= 3:
        sorted_hues = np.sort(hues)
        for i in range(len(sorted_hues)):
            base = sorted_hues[i]
            others = sorted_hues[:i].tolist() + sorted_hues[i + 1:].tolist()
            split1 = (base + 150) % 180
            split2 = (base + 210) % 180
            split_hits = sum((hue_distance(o, s) < 20 for o in others for s in [split1, split2]))
            if split_hits >= 2:
                scores['Split-Complementary'] = 1.0
                break
    if len(hues) >= 4:
        extended_hues = sorted(hues + [(hues[0] + 180) % 180])
        for i in range(len(extended_hues)):
            base = extended_hues[i]
            others = extended_hues[:i] + extended_hues[i + 1:]
            target_diffs = [hue_distance(base, o) for o in others]
            if all((40 <= d <= 60 for d in target_diffs[:2])):
                scores['Tetradic'] = 1.0
    if scores:
        best = max(scores.items(), key=lambda x: x[1])
        return (best[0], best[1])
    return ('No clear harmony', 0.0)

def compute(image, num_clusters, visualize_harmony, *, rng):
    try:
        uint8_img = to_rgb_uint8(image)
        hsv_img = cv2.cvtColor(uint8_img, cv2.COLOR_RGB2HSV)
        h = hsv_img[:, :, 0].reshape(-1, 1)
        kmeans = KMeans(n_clusters=num_clusters, n_init='auto', random_state=rng).fit(h)
        if len(kmeans.cluster_centers_) == 0:
            return (0.0, 'No dominant hues found', empty_image())
        dominant_hues = sorted([int(center[0]) for center in kmeans.cluster_centers_])
        if not dominant_hues:
            return (0.0, 'No dominant hues found', empty_image())
        harmony_type, score = match_harmony(dominant_hues)
        if visualize_harmony:
            fig, ax = plt.subplots(figsize=(5, 5), subplot_kw={'projection': 'polar'})
            hue_angles = [2 * np.pi * h / 180 for h in dominant_hues]
            ax.set_theta_direction(-1)
            ax.set_theta_zero_location('N')
            ax.set_yticklabels([])
            ax.set_xticks(np.linspace(0, 2 * np.pi, 12, endpoint=False))
            ax.set_xticklabels(['0°', '30°', '60°', '90°', '120°', '150°', '180°', '210°', '240°', '270°', '300°', '330°'])
            for hue in hue_angles:
                ax.plot([hue], [1], marker='o', markersize=12, color=plt.cm.hsv(hue / (2 * np.pi)))
            ax.set_title(harmony_type, fontsize=10)
            vis_tensor = fig_to_tensor(fig)
        else:
            vis_tensor = empty_image()
        return (float(score), harmony_type, vis_tensor)
    except Exception as e:
        print(f'[ColorHarmonyAnalyzer] Error: {e}')
        return (0.0, 'Error during processing', empty_image())
