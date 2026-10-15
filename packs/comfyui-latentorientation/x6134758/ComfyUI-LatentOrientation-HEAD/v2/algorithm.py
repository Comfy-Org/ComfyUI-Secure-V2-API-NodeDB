import torch
import torch.nn.functional as F


class LatentOrient:

	@classmethod
	def INPUT_TYPES(s):
		return {
		    "required": {
		        "samples": ("LATENT", ),
		        "orientation": (["portrait", "landscape", "min square", "max square", "avg square"], ),
		    }
		}

	RETURN_TYPES = ("LATENT", )
	FUNCTION = "op"

	CATEGORY = "latent/transform"

	def op(self, samples, orientation):
		s = samples.copy()
		latent = s["samples"]
		h = latent.shape[2]
		w = latent.shape[3]

		if orientation == "portrait":
			if h < w:
				s["samples"] = torch.rot90(latent, k=1, dims=[3, 2])
		elif orientation == "landscape":
			if h > w:
				s["samples"] = torch.rot90(latent, k=1, dims=[3, 2])
		elif orientation == "min square":
			side = min(h, w)
			if h != w:
				if h > w:
					start = (h - side) // 2
					s["samples"] = latent[:, :, start:start + side, :]
				else:
					start = (w - side) // 2
					s["samples"] = latent[:, :, :, start:start + side]
		elif orientation == "max square":
			side = max(h, w)
			if h != w:
				if h < w:
					pad_total = side - h
					pad1 = pad_total // 2
					pad2 = pad_total - pad1
					s["samples"] = F.pad(latent, (0, 0, pad1, pad2), mode="constant", value=0.0)
				else:
					pad_total = side - w
					pad1 = pad_total // 2
					pad2 = pad_total - pad1
					s["samples"] = F.pad(latent, (pad1, pad2, 0, 0), mode="constant", value=0.0)
		elif orientation == "avg square":
			side = (h + w) // 2
			if h != w:
				s["samples"] = F.interpolate(latent, size=(side, side), mode="bilinear", align_corners=False)

		return (s, )


NODE_CLASS_MAPPINGS = {
    "LatentOrient": LatentOrient,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "LatentOrient": "Orient Latent",
}
