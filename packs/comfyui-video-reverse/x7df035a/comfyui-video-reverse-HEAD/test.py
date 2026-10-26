# python .\test.py
from __init__ import VideoReverseNode
import torch
frames = torch.arange(12).view(4, 3)  # pretend we have 4 frames
print("Before:", frames)
node = VideoReverseNode()
out = node.reverse(frames)
print("After:", out[0])
