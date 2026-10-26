class VideoReverseNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "frames": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("frames",)
    FUNCTION = "reverse"
    CATEGORY = "SBCODE"

    def reverse(self, frames):
        if frames is None or (hasattr(frames, "numel") and frames.numel() == 0):
            print("[VideoReverseNode] No frames received.")
            return (frames,)

        reversed_frames = frames.flip(0)

        print("[VideoReverseNode] The video frames have been reversed.")

        return (reversed_frames,)


NODE_CLASS_MAPPINGS = {"VideoReverseNode": VideoReverseNode}
NODE_DISPLAY_NAME_MAPPINGS = {"VideoReverseNode": "Video Reverse"}
