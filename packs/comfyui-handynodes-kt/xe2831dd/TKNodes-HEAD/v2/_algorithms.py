"""Pinned pack-side algorithms. Only managed runtime tensor/audio libraries imported."""
import math
import json
import io
from pathlib import Path
import torch
import torch.nn.functional as F
import torchaudio
import numpy as np
import cv2
from pydub import AudioSegment
from pydub.silence import detect_silence
from ._pcm import tensor as _pcm_tensor

any_type = type("AnyType", (str,), {"__ne__": lambda self, o: False})
ANY = any_type("*")


class TKPromptEnhanced:

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):

        return {
            "required": {
            
                "positve_prompt": ("STRING", {
                    "multiline": True, #True if you want the field to look like the one on the ClipTextEncode node
                    "default": "Positve prompt here!",
                           }),
                "negative_prompt": ("STRING", {
                    "multiline": True, #True if you want the field to look like the one on the ClipTextEncode node
                    "default": "Incorrect body proportions. bad drawing, bad anatomy, bad body shape, blurred details, awkward poses, incorrect shadows, unrealistic expressions, lack of texture, poor composition, text, logo, out of aspect ratio, body not fully visible, ugly, defects, noise, fuzzy, oversaturated, soft, blurry, out of focus, frame",
                    "lazy": True             }),
               
                "use_cam_options" : ("BOOLEAN", {
                    "default" : True, "description":"Disable/Enable Camera options.  These camera descriptions simply get appended to the positive text."}),
                
                "camera_shot_size": ([
                            "-",
                            "The camera takes an extreme closeup. ",
                            "The camera takes a closeup. ",
                            "The camera takes a medium shot ",
                            "The camera takes a medium full shot. ",
                            "The camera takes a full shot. ",
                            "The camera takes an extreme wide shot",
                            "The camera takes a wide shot",
                               ],),
                "camera_focus": ([
                            "-",
                            "The main person is in focus. ",
                            "The main person is in focus, the background objects are out of focus. ",
                            "All objects in the scene are in focus. ",
                            "The camera takes a tilt-shift focus shot. ",
                            "The camera takes a shot with soft focus. ",
                            "The camera takes a split diopeter shot. ",
                               ],),
                            
                "camera_angle":([
                            "-",
                           
                            "The camera is filming at eye level. ",
                            "The camera is filming at low angle.",       
                            "The camera is filming at hip level.", 
                            "The camera is filming at a knee level.", 
                            "The camera is filming at a ground level.", 
                            "The camera is filming at a low angle.", 
                            "The camera is filming at a shoulder level.", 
                            "The camera is overhead.", 
                            "The camera is taking an aerial shot.", 

                            ],),
                            
                "camera_movement":([
                            "-",
                            "The camera is stationary.",
                            "The camera is jittery",
                            "The camera is zooming in. ",
                            "The camera is zooming out. ",       
                            "The camera is panning right. ", 
                            "The camera is panning right. ", 
                            "The camera tilts up. ", 
                            "The camera tilts down. ", 
                            "The camera orbits. ", 
 
                            ],),
                            
                "light": (["-",
                            "Scene has warm light. ",
                            "Scene has midday light.",
                            "Scene has morning light. ",
                            "Scene  has evening light. ",
                            "There is a spotlight on the subject. ",
                            "The scene has backlighting. ",
                            "The scene has dramatic lighting. ",
                            "The scene has bright neon lighting. ",
                            "The scene has low light. ",
                            "The scene has harsh shadows. ",
                            "The scene has specular lighting. ",
                            "The scene has soft diffused lighting. ",
                            "The scene has radiant rays. ",
                            "The scene is luminescent.     ",    ],), 
                            

                                      
                }
            }
        

    RETURN_TYPES = ("STRING","STRING")
    RETURN_NAMES = ("positive","negative")
    FUNCTION = "tkpromptenhanced"
    #OUTPUT_NODE = False
    CATEGORY = "TKNodes"
    DESCRIPTION = "Enhanced prompt, contains camera controls which are appended to the positive prompt"

    
    def tkpromptenhanced(self, positve_prompt, negative_prompt,use_cam_options, camera_shot_size, camera_angle, camera_focus, camera_movement, light):
        
        
        pos = positve_prompt 
        
        if use_cam_options == True:
           pos =    positve_prompt+ ". "+ camera_angle+". "+ camera_focus+". "+ camera_movement+". "+ camera_shot_size+". "+ light
        
            
        return (pos,negative_prompt)


class TKVideoUserInputs:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "width":  ("INT", {"default": 1280, "min": 100, "max": 1288, "step": 32}),
                "height": ("INT", {"default": 1280, "min": 100, "max": 1288, "step": 32}),
                "length_selector": (
                                ["Use # Seconds", "Use # Frames"], # "Use # Seconds" is now the default
                                {"default": "Use # Seconds"}       # Explicitly defining the default
                            ),
                "total_frames": ("INT", {"default": 97,   "min": 10, "max": 1000, "tooltip" : "This value applies when length_selector = Use Frames"}),
                "num_seconds": ("FLOAT", {"default": 5.0, "min": 2.0, "max": 1000, "tooltip" : "This value applies when length_selector = Use Seconds"}),
                "fps":         ("FLOAT", {"default": 24.0, "min": 16.0, "max": 60.0, "tooltip" : "FPS from video info node"}),
                

            },
        }

    RETURN_TYPES = ("INT",              "INT",         "INT",    "FLOAT", "FLOAT")
    RETURN_NAMES = ("video_width", "video_height", "total_frames","fps", "totalSeconds")
    FUNCTION = "main"
    CATEGORY = "TKNodes"
    DESCRIPTION = "GUI for setting video resolution , frames, duration"

    def main(self, width, height, total_frames, length_selector, fps, num_seconds, ):
     
        returnSecs = num_seconds
        if (length_selector=="Use # Seconds") :
            total_frames = int(fps * num_seconds)
        else :
            returnSecs =   float(total_frames) / fps;
        

        return (width, height, total_frames, fps, returnSecs )


class TKVideoUserInputsBasic:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "width":  ("INT", {"default": 1280, "min": 100, "max": 1288, "step": 32}),
                "height": ("INT", {"default": 1280, "min": 100, "max": 1288, "step": 32}),
               
               },
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("video_width", "video_height")
    FUNCTION = "main"
    CATEGORY = "TKNodes"
    DESCRIPTION = "Common Video User Inputs- Basic"

    def main(self, width, height ):
     
        
        return (width, height )


class TKPhotoUserInputs:
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "width":  ("INT", {"default": 3000, "min": 100, "max": 3000, "step": 64}),
                "height": ("INT", {"default": 3000, "min": 100, "max": 3000, "step": 64}),
               
               },
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("photo_width", "photo_height")
    FUNCTION = "main"
    CATEGORY = "TKNodes"
    DESCRIPTION = "Photo User Inputs"

    def main(self, width, height ):
     
        
        return (width, height )


class TKFadeInVideo:
    DESCRIPTION="Fade in Video"
    """Fades in the first N frames of a video from black (or a chosen color)
    to full opacity. Frame 1 = 0% opaque, frame N = 100% opaque, frames
    after N are untouched. Intended to run right after VAE Decode."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE", {"tooltip": "Decoded video frames [N, H, W, C]"}),
                "fade_frames": ("INT", {"default": 5, "min": 1, "max": 240,
                                         "tooltip": "Number of frames to fade in over. "
                                                     "Frame 'fade_frames' reaches 100%."}),
                "start_alpha": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
                                           "tooltip": "Starting opacity at frame 1 (0.5 = 50%). "
                                                       "Ramps up to 1.0 by fade_frames."}),
            },
            "optional": {
                "fade_color": ("STRING", {"default": "0,0,0",
                                           "tooltip": "R,G,B (0-255) to fade in from. Default black."}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "fade_in"
    CATEGORY = "TKNodes"

    def fade_in(self, images, fade_frames, start_alpha=0.5, fade_color="0,0,0"):
        import torch
           
        total_frames = images.shape[0]
        n = min(fade_frames, total_frames)

        # Parse fade color -> normalized 0-1 tensor matching channel count
        try:
            r, g, b = [float(c.strip()) / 255.0 for c in fade_color.split(",")]
        except Exception:
            r, g, b = 0.0, 0.0, 0.0

        channels = images.shape[-1]
        if channels == 4:
            color = torch.tensor([r, g, b, 1.0], dtype=images.dtype, device=images.device)
        else:
            color = torch.tensor([r, g, b], dtype=images.dtype, device=images.device)

        result = images.clone()

        # Opacity ramps linearly from start_alpha -> 1.0 (fully opaque/original)
        # frame 1 -> start_alpha, frame n -> 1.0
        alpha_range = 1.0 - start_alpha
        for i in range(n):
            alpha = start_alpha + alpha_range * ((i + 1) / n)
            frame = images[i]
            faded = frame * alpha + color * (1.0 - alpha)
            result[i] = faded.clamp(0.0, 1.0)

        return (result,)


class TKCrossDissolve:
    DESCRIPTION="Cross Dissolve two video segments together to make transition seamless"
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "curr_scene": ("IMAGE",  {  "tooltip": "the current video segment. "}),
                "curve": (["linear", "ease_in_out"],  { "tooltip": "select Cross dissolve effect. "}),
            },
            "optional": {
                "prev_tail": ("IMAGE",  {"tooltip": "previous video segment to cross-dissolve. "}),  # absent/empty on segment 1
                "numDissolveFrames": ("INT", {"default": 20, "min": 0, "max": 1000, "tooltip": "number of frames to cross-dissolve. if <=0, uses the full length of prev_tail instead."}),
            }
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "blend"
    CATEGORY = "TKNodes"

    def blend(self, curr_scene, curve, prev_tail=None, numDissolveFrames=0):

        if prev_tail is None or prev_tail.shape[0] == 0:
            return (curr_scene,)

        if numDissolveFrames is not None and numDissolveFrames > 0:
            # take only the last numDissolveFrames of prev_tail, clamped to what's available
            tail_n = min(numDissolveFrames, prev_tail.shape[0])
            prev_tail = prev_tail[-tail_n:]

        n = min(prev_tail.shape[0], curr_scene.shape[0])
        print(f"[dissolve] n={n}, curve={curve}")

        curr_head = curr_scene[:n]
        curr_rest = curr_scene[n:]

        alphas = torch.linspace(0, 1, n)
        if curve == "ease_in_out":
            alphas = alphas * alphas * (3 - 2 * alphas)

        blended = torch.stack([
            (1 - a) * prev_tail[i] + a * curr_head[i]
            for i, a in enumerate(alphas)
        ])

        out = torch.cat([blended, curr_rest], dim=0)
        return (out,)


class TKTrimFrames:
    DESCRIPTION = "Trim an image sequence and/or matching audio down to an exact target duration"
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "frame_count": ("INT", {"default": 1, "min": 1, "max": 100000, "tooltip": "true target frame count (video)"}),
                "target_fps": ("FLOAT", {"default": 25.0, "min": 1.0, "max": 240.0}),
            },
            "optional": {
                "images": ("IMAGE",),
                "audio": ("AUDIO",),
            }
        }
    RETURN_TYPES = ("IMAGE", "AUDIO")
    RETURN_NAMES = ("images", "audio")
    FUNCTION = "trim"
    CATEGORY = "TKNodes"

    def trim(self, frame_count, target_fps, images=None, audio=None):
        out_images = None
        if images is not None:
            n = min(frame_count, images.shape[0])
            out_images = images[:n]

        out_audio = None
        if audio is not None:
            waveform = audio["waveform"]
            sample_rate = audio["sample_rate"]
            target_duration = frame_count / target_fps
            target_samples = int(round(target_duration * sample_rate))
            target_samples = min(target_samples, waveform.shape[-1])
            out_audio = {
                "waveform": waveform[..., :target_samples],
                "sample_rate": sample_rate,
            }

        return (out_images, out_audio)


class TKVideoAudioFuse :
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):

        return {
            "required": {
                "image": ("IMAGE",{"tooltip":"the video part - so it can be merged with up to 3 audio streams"}),
                              
                "audio1": ("AUDIO",{"tooltip":"1st Audio Stream - will be fused/merged with video, the images"}),  
            
                "audio1_volume" : ("INT", {"default":0,"min":-10,"max":10, "tooltip":"Enter volume -10 lowest, 0 = normal, 10 = loudest"}),                

            },
        
            "optional": {
            
                "audio2": ("AUDIO",{"tooltip":"2nd Audio Stream - will be fused/merged with video and all audio tracks"}),    
                "audio2_volume" : ("INT", {"default":0,"min":-10,"max":10, "tooltip":"Enter volume -10 lowest, 0 = normal, 10 = loudest"}),                    

                "audio3": ("AUDIO",{"tooltip":"2nd Audio Stream - will be fused/merged with video and all audio tracks"}),    
                "audio3_volume" : ("INT", {"default":0,"min":-10,"max":10, "tooltip":"Enter volume -10 lowest, 0 = normal, 10 = loudest"}),                    
            }
        }
        

    RETURN_TYPES = ("IMAGE",  "AUDIO")
    RETURN_NAMES = ("image",  "audio")


    FUNCTION = "tkvideoaudiofuse"

    #OUTPUT_NODE = False

    CATEGORY = "TKNodes"
    DESCRIPTION = "Fuse/Overlayt up to 3 audio streams and 1 video together.  "

    
    def tkvideoaudiofuse(self, image, audio1,  audio1_volume,   audio2_volume,  audio3_volume, audio2=None, audio3=None, ):
        audio_tensor1 = audio1['waveform']      
        sr = audio1["sample_rate"]
        avg1 = self.adjustVolume(audio_tensor1, audio1_volume)
        
 
        if  audio2 is not None :
            sr2 =audio2["sample_rate"]
            aud2 =  self.adjustVolume(audio2["waveform"], audio2_volume)
            (avg1, sr) = self.average_audio_tensors(avg1, aud2, sr, sr2 )
        
        if audio3 is not None :
            sr3 =audio3["sample_rate"]
            aud3 =  self.adjustVolume(audio3["waveform"], audio3_volume)
            (avg1, sr) = self.average_audio_tensors(avg1, aud3, sr, sr3 )
    
        audio = {
           "waveform": avg1,
           "sample_rate": sr
        }
        return ( image, audio)
        

    def adjustVolume(self, tensor, vol) :
        gain_in_db = vol*3

        # Apply the volume transform
        vol_transform = torchaudio.transforms.Vol(gain=gain_in_db, gain_type='db')
        new_tensor = vol_transform(tensor)
        
        return new_tensor
        
        
    def average_audio_tensors(self,
        audio1,
        audio2,
        sr1,
        sr2
    ) :
        """
        Averages two audio tensors of potentially different lengths and channel counts.

        It resamples tensors to a common sample rate, converts them to mono, pads the 
        shorter tensor with zeros, and then averages the result.

        Args:
            audio1 (torch.Tensor): The first audio tensor.
                                   Expected shape: [channels, frames].
            audio2 (torch.Tensor): The second audio tensor.
                                   Expected shape: [channels, frames].
            sr1 (int): The sample rate of the first audio tensor.
            sr2 (int): The sample rate of the second audio tensor.

        Returns:
            torch.Tensor: A new tensor representing the average of the two inputs, 
                          as a mono signal.
        """
        
        if not isinstance(audio1, torch.Tensor) or not isinstance(audio2, torch.Tensor):
            raise TypeError("Inputs must be PyTorch tensors.")

        # Step 1: Resample tensors to a common sample rate
        target_sr = min(sr1, sr2)
        if sr1 != target_sr:
            resampler = torchaudio.transforms.Resample(orig_freq=sr1, new_freq=target_sr)
            audio1 = resampler(audio1)
        if sr2 != target_sr:
            resampler = torchaudio.transforms.Resample(orig_freq=sr2, new_freq=target_sr)
            audio2 = resampler(audio2)

        # Step 2: Convert tensors to mono if they have more than one channel
        # This is done by averaging the channels
        if audio1.shape[1] > 1:
            audio1 = torch.mean(audio1, dim=0, keepdim=True)
        if audio2.shape[1] > 1:
            audio2 = torch.mean(audio2, dim=0, keepdim=True)

        # Step 3: Pad the shorter tensor to match the length of the longer tensor

        max_len = max(audio1.shape[2], audio2.shape[2])
        
        if audio1.shape[2] < max_len:
            padding_needed = max_len - audio1.shape[2]
            padded_audio1 = F.pad(audio1, (0, padding_needed), 'constant', 0)
        else:
            padded_audio1 = audio1

        if audio2.shape[2] < max_len:
            padding_needed = max_len - audio2.shape[2]
            padded_audio2 = F.pad(audio2, (0, padding_needed), 'constant', 0)
        else:
            padded_audio2 = audio2

        # Step 4: Average the padded tensors
        averaged_audio = (padded_audio1 + padded_audio2) / 2

        return (averaged_audio, target_sr)


class TKAudioFuse :
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):

        return {
            "required": {
                "audio1": ("AUDIO", {"tooltip":"Fuse or merge two to 3 audio streams together producing 1 final audio"}),  
                "audio1_volume" : ("INT", {"default":0,"min":-10,"max":10, "tooltip":"Enter volume -10 lowest, 0 = normal, 10 = loudest"}),                
                "audio2": ("AUDIO",{"tooltip":"Fuse or merge two to 3 audio streams together producing 1 final audio"}),    
                "audio2_volume" : ("INT", {"default":0,"min":-10,"max":10, "tooltip":"Enter volume -10 lowest, 0 = normal, 10 = loudest"}),   
            },
            "optional": {
                "audio3": ("AUDIO",),    
                "audio3_volume" : ("INT", {"default":0,"min":-10,"max":10, "tooltip":"Enter volume -10 lowest, 0 = normal, 10 = loudest"}),                    
            }
        }
        
    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "tkaudiofuse"
    #OUTPUT_NODE = False
    CATEGORY = "TKNodes"
    DESCRIPTION = "Fuse/Overlay up to 3 audio streams together"

    
    def tkaudiofuse(self, audio1,  audio1_volume,   audio2 , audio2_volume,  audio3_volume,  audio3 =None, ):
       
        vidaud_obj = TKVideoAudioFuse()
        

        audio_tensor1 = audio1['waveform']      
        sr = audio1["sample_rate"]
        avg1 = vidaud_obj.adjustVolume(audio_tensor1, audio1_volume)
        
 
        if  audio2 is not None :
            sr2 =audio2["sample_rate"]
            aud2 =  vidaud_obj.adjustVolume(audio2["waveform"], audio2_volume)
            (avg1, sr) = vidaud_obj.average_audio_tensors(avg1, aud2, sr, sr2 )
        
        if audio3 is not None :
            sr3 =audio3["sample_rate"]
            aud3 =  vidaud_obj.adjustVolume(audio3["waveform"], audio3_volume)
            (avg1, sr) = vidaud_obj.average_audio_tensors(avg1, aud3, sr, sr3 )
            
        print(avg1.shape )
        audio = {
           "waveform": avg1,
           "sample_rate": sr,
        }
     
        return (audio,)


class TKAudioUnwrap:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"audio": ("AUDIO",)}}

    RETURN_TYPES = (ANY,)
    RETURN_NAMES = ("waveform",)
    FUNCTION = "unwrap"
    CATEGORY = "audio"
    DESCRIPTION = "Unwrap an audio latent - return the waveform. "


    def unwrap(self, audio):
        return (audio["waveform"],)


class TKPrintValueToLog:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (ANY,{"tooltip" : "Value to be printed to comfyui.log"}),
                "label": ("STRING", {"default": "mylog","tooltip": "Label for your log"}),
            }
        }

    RETURN_TYPES = (ANY,)
    RETURN_NAMES = ("value",)
    OUTPUT_NODE = True
    FUNCTION = "log"
    CATEGORY = "debug"
    DESCRIPTION = "Print to Log - useful for debugging nodes "


    def log(self, value, label):
        print(f"[{label}] : {value}")
        return (value,)


class TKMergeAudioList:
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "audio_list": ("AUDIO", {"tooltip" : "a list of audio to convert to 1 audio stream"})
            }
        }
    
    # This is essential: it collects all clips into one list instead of looping the node
    INPUT_IS_LIST = True 
    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "merge"
    CATEGORY = "HandyNodes-KT"
    DESCRIPTION = " Takes a list of audio files and join them to create on stream"

    def merge(self, audio_list):
        waveforms = [item['waveform'] for item in audio_list]
        sample_rate = audio_list[0]['sample_rate']
        
        # 1. Create a tiny fade (0.1 seconds) to hide the 'pop'
        fade_len = int(sample_rate * 0.1) 
        fade_in = torch.linspace(0.0, 1.0, fade_len)
        fade_out = torch.linspace(1.0, 0.0, fade_len)


        # 2. Process the list to apply fades to the joins
        merged_waveform = waveforms[0]
        for i in range(1, len(waveforms)):
            current_clip = waveforms[i]
            
            # --- SAFETY CHECK ADDED HERE ---
            # Ensure fade_len is not longer than the available audio in either clip
            actual_fade = min(fade_len, merged_waveform.shape[-1], current_clip.shape[-1])
            
            # If the clips are too short, adjust the fade tensors to match the actual_fade size
            current_fade_out = fade_out[:actual_fade] if actual_fade < fade_len else fade_out
            current_fade_in = fade_in[:actual_fade] if actual_fade < fade_len else fade_in
            # -------------------------------

            # Apply fades using the safe 'actual_fade' size
            merged_waveform[:, :, -actual_fade:] *= current_fade_out
            current_clip[:, :, :actual_fade] *= current_fade_in
                    
            merged_waveform = torch.cat([merged_waveform, current_clip], dim=-1)
            

        # 3. Flatten to Batch 1 as we did before
        if merged_waveform.shape[0] > 1:
            merged_waveform = merged_waveform.reshape(1, merged_waveform.shape[1], -1)

        return ({"waveform": merged_waveform, "sample_rate": sample_rate},)


class TKPromptLooper:
    DESCRIPTION = "Prompt Looper - Loops between 1 to 4 prompts/images.  It keeps alternating prompt and image for the workflow"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "index": ("INT", {"default": 0, "min": 0, "max": 100, "step": 1}),
                "prompt1": ("STRING", {"tooltip": "prompt 1", "multiline": True}),
                "image1": ("IMAGE", ),

            },
            "optional": {
                "prompt2": ("STRING", {"tooltip": "prompt 2", "multiline": True}),
                "image2": ("IMAGE", ),
                "prompt3": ("STRING", {"tooltip": "prompt 3", "multiline": True}),
                "image3": ("IMAGE", ),
                "prompt4": ("STRING", {"tooltip": "prompt 4", "multiline": True}),
                "image4": ("IMAGE", ),
            }
        }

    RETURN_TYPES = ("INT", "STRING", "IMAGE")
    RETURN_NAMES = ("index", "prompt", "image")
    FUNCTION = "getResultsAtIndex"
    CATEGORY = "TKNodes"

    def getResultsAtIndex(self, index, prompt1, image1, prompt2=None, image2=None,
                       prompt3=None, image3=None, prompt4=None, image4=None):

        candidates = [
            (prompt1, image1),
            (prompt2, image2),
            (prompt3, image3),
            (prompt4, image4),
        ]

        items = []
        for prompt, image in candidates:
            if prompt is None or prompt.strip() == "":
                break
            items.append((prompt, image))

        count = len(items)
        if count == 0:
            raise ValueError("TKPromptLooper: no valid prompt/image pairs were supplied.")

        wrapped_index = index % count

        result_prompt, result_image = items[wrapped_index]

        return (wrapped_index, result_prompt, result_image)


class TKPromptLooperAdv:
    DESCRIPTION = (
        "Prompt Looper (List) - Loops through the entries of a "
        "TK_IMAGE_PROMPT_LIST (e.g. from TKMultiImagePrompt), alternating "
        "prompt and image for the workflow based on index, wrapping around "
        "when index exceeds the list length."
    )

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "index": ("INT", {"default": 0, "min": 0, "max": 100, "step": 1}),
                
            },
            "optional": {
                "image_prompt_list": ("TK_IMAGE_PROMPT_LIST", {}),
                "image_list": ("TK_IMAGE_LIST", {}),
            },
        }

    RETURN_TYPES = ("INT", "STRING", "IMAGE","INT")
    RETURN_NAMES = ("index", "prompt", "image", "total_cnt")
    FUNCTION = "getResultsAtIndex"
    CATEGORY = "TKNodes"

    def getResultsAtIndex(self, index, image_prompt_list=None, image_list=None):

        if (image_prompt_list is not None) :
            return self.getListWithPrompts(index, image_prompt_list)

        
        if (image_list is not None) :
            return self.getListWithoutPrompts(index, image_list)
        
        raise ValueError("TKPromptLooperAdv: no valid prompt/image pairs were supplied.")


    

    def getListWithPrompts(self, index, image_prompt_list):

        print(f" got here in getListWithPrompts")
        # Keep entries sorted by their original slot number so pairing order
        # is deterministic (image_1 <-> prompt_1, image_2 <-> prompt_2, ...)
        # even if the incoming list isn't already in slot order.
        sorted_entries = sorted(
            image_prompt_list, key=lambda e: e.get("slot", 0)
        )

        # Only keep entries where BOTH an image and a non-empty prompt are
        # present. An image with no prompt (or a prompt with no image) is
        # ignored entirely rather than passed through with a blank pairing.
        items = []
        for entry in sorted_entries:
            prompt = entry.get("prompt")
            image = entry.get("image")

            if image is None:
                continue
            if prompt is None or prompt.strip() == "":
                continue

            items.append((prompt, image))

        count = len(items)
        if count == 0:
            raise ValueError(
                "TKMultiImage: no valid prompt/image entries were "
                "supplied in image_prompt_list."
            )

        wrapped_index = index % count

        result_prompt, result_image = items[wrapped_index]

        return (wrapped_index, result_prompt, result_image, count)



    def getListWithoutPrompts(self, index, image_list):

        print(f" got here in getListWithoutPrompts")
        # Keep entries sorted by their original slot number so pairing order
        # is deterministic (image_1 <-> prompt_1, image_2 <-> prompt_2, ...)
        # even if the incoming list isn't already in slot order.
        sorted_entries = sorted(
            image_list, key=lambda e: e.get("slot", 0)
        )

        # Only keep entries where BOTH an image and a non-empty prompt are
        # present. An image with no prompt (or a prompt with no image) is
        # ignored entirely rather than passed through with a blank pairing.
        items = []
        for entry in sorted_entries:
            image = entry.get("image")

            if image is None:
                continue

            items.append((image))

        count = len(items)
        if count == 0:
            raise ValueError(
                "TKMultiImage: no images passed in "
                "supplied in image_list."
            )

        wrapped_index = index % count

        result_image = items[wrapped_index]

        return (wrapped_index, None, result_image, count)


class TKSmartVideoChunker:
    DESCRIPTION = "Silence-based video/audio chunking for LTX 2.3 / Wan 2.2.   Looks for silence in audio to create chunk breaks.   This is helpful when speakers take a breath and we don't cut off speaker while talking. Chunking is required to get around VRAM issues.  For Low VRAM set chunk size lower"

    """Silence-based video/audio chunking for LTX 2.3 or Wan 2.2. Slices at
    native fps, resamples to target_fps, and snaps to a valid frame count
    for the selected model:
        - LTX -> 8n+1
        - WAN -> 4n+1

    Carries actual_end_time forward across loop iterations (via
    start_time_override) so chunk boundaries stay sample/frame accurate
    even when snapping trims or pads a chunk's true length.
    """

    # frame-count boundary divisor per model (valid counts are divisor*n + 1)
    MODEL_DIVISORS = {
        "LTX": 8,
        "WAN": 4,
    }

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "video": ("IMAGE", {"tooltip": "Source video"}),
                "audio": ("AUDIO", {"tooltip": "Source audio"}),
                "index": ("INT", {"default": 0, "min": 0, "max": 9999, "tooltip": "Index from Loop - zero based"}),
                "chunk_secs": ("INT", {"default": 10, "tooltip": "Size of each video segment in seconds"}),
                "variation": ("INT", {"default": 2, "tooltip": "Num seconds variation.  chunks_secs +/- variation adds flexiblity to find silence"}),
                "source_fps": ("FLOAT", {"default": 30.0, "min": 1.0, "max": 240.0, "step": 0.01,
                                          "tooltip": "TRUE fps of incoming video tensor"}),
                "target_fps": ("FLOAT", {"default": 25.0, "min": 1.0, "max": 240.0, "step": 0.01,
                                          "tooltip": "fps required by target model - 25 for LTX, 16 for WAN (typical)"}),

            },
            "optional": {
                "start_time_override": ("FLOAT", {"default": -1.0, "min": -1.0, "max": 999999.0, "step": 0.001,
                                                    "tooltip": "Use -1 for index 0, used to maintain exact timing of chunks."}),
                "model_type": (["LTX", "WAN"], {"default": "LTX",
                                                    "tooltip": "Target model frame-count boundary: LTX=8n+1, WAN=4n+1"}),
            },
        }

    RETURN_TYPES = ("INT",          "IMAGE",         "AUDIO",       "INT",           "FLOAT",           "FLOAT",           "FLOAT",            "INT",)
    RETURN_NAMES = ("num_chunks", "chunkOImages", "chunkOfAudio", "numberFrames", "actual_end_time", "actual_start_time", "chunk_duration", "numGenerationFrames",)
        # Add tooltips corresponding to each output slot
    OUTPUT_TOOLTIPS = (
        "Number Chunks Calculated for the Video.",
        "Video",
        "Audio",
        "# Frames after Snapping",
        "end time in video of chunk",
        "start time of chunk in video",
        "length of chunk",
        "num Frames requested by user w/o snapping",

    )


    
    FUNCTION = "get_video_chunk_at_index"
    CATEGORY = "TKNodes"

    def get_video_chunk_at_index(self, video, audio, index, chunk_secs, variation,
                                  source_fps, target_fps,  start_time_override=-1.0, model_type="LTX",):
        import torch

        divisor = self.MODEL_DIVISORS.get(model_type, 8)

        # 1. Silence-based timing, real seconds, fps-agnostic
        audio_chunker = TKSmartAudioChunker()
        num_chunks, chunk_size, start_time, total_duration = audio_chunker.calculate(
            audio, index, chunk_secs, variation
        )

        # 1b. Override start_time with the carried actual end of the previous
        #     chunk, so boundaries stay contiguous regardless of snapping.
        if start_time_override is not None:
            if start_time_override >= 0.0:
                start_time = start_time_override

        # 2. Slice video at native fps
        total_frames = video.shape[0]
        start_frame = int(round(start_time * source_fps))
        true_end_frame = int(round((start_time + chunk_size) * source_fps))
        start_frame = max(0, min(start_frame, total_frames - 1))
        true_end_frame = max(start_frame + 1, min(true_end_frame, total_frames))

        # extend the native window so resampling has enough real frames
        # to round UP to the next (divisor*n + 1) boundary (never short)
        pad_native_frames = int(round(divisor * (source_fps / target_fps))) + 1
        end_frame = min(true_end_frame + pad_native_frames, total_frames)

        native_chunk = video[start_frame:end_frame]
        native_frame_count = native_chunk.shape[0]
        true_native_frame_count = true_end_frame - start_frame  # unpadded, real target

        # 3. Resample native_fps -> target_fps
        true_chunk_duration = true_native_frame_count / source_fps
        true_target_frame_count = max(1, int(round(true_chunk_duration * target_fps)))

        actual_chunk_duration = native_frame_count / source_fps
        target_frame_count = max(1, int(round(actual_chunk_duration * target_fps)))

        if target_fps == source_fps:
            resampled_chunk = native_chunk
        else:
            src_indices = torch.round(
                torch.arange(target_frame_count, dtype=torch.float32) * (source_fps / target_fps)
            ).long()
            src_indices = torch.clamp(src_indices, 0, native_frame_count - 1)
            resampled_chunk = native_chunk[src_indices]


        # 4. Snap to valid frame count for the selected model (divisor*n + 1),
        #    round UP, never down.
        #    generation_frames = what we ask the model to generate (always >= true target)
        #    true_target_frame_count = what we trim back down to before writing to disk
        raw_count = resampled_chunk.shape[0]
        generation_frames = min(
            raw_count,
            divisor * ((true_target_frame_count - 1) // divisor + 1) + 1
        )
        video_chunk = resampled_chunk[:generation_frames]
        number_frames = min(true_target_frame_count, generation_frames)  # trim target

        # 5. Slice audio to match, sample-accurate
        exact_video_duration = number_frames / target_fps
        print(f"[DEBUG] idx={index} model={model_type} divisor={divisor} target_fps={target_fps} "
              f"user frames={number_frames} snap frames={generation_frames} chunk_duration={exact_video_duration}")

        waveform = audio['waveform']
        sample_rate = audio['sample_rate']
        total_samples = waveform.shape[-1]

        start_sample = int(round(start_time * sample_rate))
        end_sample = start_sample + int(round(exact_video_duration * sample_rate))
        start_sample = max(0, min(start_sample, total_samples - 1))

        if end_sample > total_samples:
            existing_waveform = waveform[..., start_sample:total_samples]
            missing_samples = end_sample - total_samples
            silence_pad = torch.zeros(
                (waveform.shape[0], waveform.shape[1], missing_samples),
                dtype=waveform.dtype, device=waveform.device
            )
            sliced_waveform = torch.cat([existing_waveform, silence_pad], dim=-1)
        else:
            sliced_waveform = waveform[..., start_sample:end_sample]

        audio_chunk = {"waveform": sliced_waveform, "sample_rate": sample_rate}

        # 6. Carry the real end time forward for the next iteration
        actual_end_time = start_time + exact_video_duration

        return (num_chunks, video_chunk, audio_chunk, number_frames, actual_end_time, start_time, exact_video_duration, generation_frames, )


class TKSmartAudioChunker:

    DESCRIPTION = "Smart Audio Chunker is used to take an audio segment and split it up in chunks.  It searches for silence to split up the audio.  It also adds some silence to the chunks specifically for LTX"


    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "audio": ("AUDIO",{"tooltip":"the Full audio that will get chunked"}), # Connect the gray wire here
                "index": ("INT", {"default": 0, "tooltip": "Index from the for loop" }),
                "chunk_secs": ("INT", {"default": 10, "tooltip": "Size of an Audio Chunk, for low VRAM use 5"}),
                "variation": ("INT", {"default": 2, "tooltip": "we separate when we find silence, this tells how far back and forward to search for silence"}),
            },
        }

    RETURN_TYPES = ("INT", "FLOAT", "FLOAT", "FLOAT")
    RETURN_NAMES = ("num_chunks", "chunk_size", "start_time", "total_duration")
    OUTPUT_TOOLTIPS = (
            "Number Chunks Calculated for the audio.",
            "length of chunk in seconds",
            "start time of chunk in audio",
            "end time in chunk in audio",
    )
    
    
    FUNCTION = "calculate"
    CATEGORY = "HandyNodes-KT"

    def calculate(self, audio, index, chunk_secs, variation):
        # Run the private logic using the audio wire data
        splits = self.get_silence_splits_from_audio(audio, chunk_secs, variation)

        num_chunks = len(splits) - 1
        idx = max(0, min(index, num_chunks - 1))
        
        start_ms = splits[idx]
        end_ms = splits[idx + 1]
        
        chunkSizeMs = float((end_ms - start_ms) )     # chunk_size
        origChunkSize = chunkSizeMs


       
        startChunkMs = float(start_ms)       # start_time
             
        durMs = float(splits[-1])         # total_duration


        return (
            num_chunks, 
            chunkSizeMs/1000.0,
            startChunkMs/1000.0,
            durMs  / 1000.0,
        )
    

    def get_silence_splits_from_audio(self, audio_data, chunk_size, variation):
        # 1. Extract data from the ComfyUI Audio dictionary
        waveform = audio_data['waveform']      # Shape: [Batch, Channels, Samples]
        sample_rate = audio_data['sample_rate']
        
        # 2. Convert PyTorch tensor to raw bytes for pydub
        # We flatten all channels into a single mono stream for silence detection
        if waveform.dim() > 2:
            waveform = waveform.mean(dim=1) # Convert to mono
        
        # Scale float32 (-1.0 to 1.0) to int16 for pydub compatibility
        audio_np = (waveform.cpu().numpy() * 32767).astype(np.int16)
        raw_data = audio_np.tobytes()
        
        # 3. Create pydub AudioSegment from raw bytes
        audio = AudioSegment(
            data=raw_data,
            sample_width=2, # 16-bit (2 bytes)
            frame_rate=sample_rate,
            channels=1
        )
        
        # 4. Same splitting logic as before
        total_ms = len(audio)
        target, var = chunk_size * 1000, variation * 1000
        splits, curr = [0], 0
        
        while curr + (target - var) < total_ms:
            win_start = curr + (target - var)
            win_end = min(curr + (target + var), total_ms)
            window = audio[win_start:win_end]
            
            silence = detect_silence(window, min_silence_len=300, silence_thresh=-40)
            if silence:
                s_start, s_end = silence[0]
                split_at = win_start + s_start + (s_end - s_start) // 2
            else:
                split_at = curr + target
                
            splits.append(split_at)
            curr = split_at


        # add this fix to avoid 0 length    
        if splits[-1] < total_ms:
            splits.append(total_ms)
        return splits


class TKTrimImageOverlap:
    DESCRIPTION="Trims overlap frames from video segments when they have been previously paddded for various reasons"
    """
    Trims overlap frames from video segments based on position in sequence.

    - First segment  (idx == 0):              trim end only
    - Middle segments (0 < idx < total - 1):  trim both start and end
    - Last segment   (idx == total - 1):      trim start only

    Inputs:
        image           : IMAGE batch (N, H, W, C)
        idx             : int  – current loop index (0-based)
        total_segments  : int  – total number of segments
        start_frames    : int  – frames to remove from start (overlap on front)
        end_frames      : int  – frames to remove from end   (overlap on back)

    Output:
        IMAGE batch with overlap frames removed
    """
    # This is what ComfyUI looks for to display a node-level description



    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image":           ("IMAGE",{"tooltip":"source image with padding "}),
                "idx":             ("INT", {"default": 0, "min": 0, "max": 9999, "tooltip": "Index for audio chunks"}),
                "total_segments":  ("INT", {"default": 1, "min": 1, "max": 9999, "tooltip": "total audio chunks"}),
                "start_frames":    ("INT", {"default": 12, "min": 0, "max": 9999, "tooltip": "start frame to remove"}),
                "end_frames":      ("INT", {"default": 13, "min": 0, "max": 9999, "tooltip": "end framess to remove"}),
            }
        }

    RETURN_TYPES  = ("IMAGE",)
    RETURN_NAMES  = ("image",)
    FUNCTION      = "trim"
    CATEGORY      = "TKNodes/video"

    def trim(self, image: torch.Tensor, idx: int, total_segments: int,
             start_frames: int, end_frames: int) -> tuple:

        total_frames = image.shape[0]

        is_first  = (idx == 0)
        is_last   = (idx == total_segments - 1)

        trim_start = not is_first   # trim start on middle + last
        trim_end   = not is_last    # trim end   on first  + middle

        start = start_frames if trim_start else 0
        end   = total_frames - end_frames if trim_end else total_frames

        # Safety clamp so we never produce an empty batch
        start = max(0, min(start, total_frames - 1))
        end   = max(start + 1, min(end, total_frames))

        trimmed = image[start:end]

        print(f"[TKTrimImageOverlap] idx={idx}/{total_segments-1} | "
              f"frames={total_frames} → {trimmed.shape[0]} | "
              f"trim_start={trim_start}({start_frames}f) "
              f"trim_end={trim_end}({end_frames}f)")

        return (trimmed,)


class TKCalcLTXFrames:
    DESCRIPTION = "LTX requires very specific frame counts.. this guarantees perfect LTX boundries"

    """
    Converts a bare chunk duration (NO overlap) to a valid LTX frame count,
    and computes the exact overlap needed so trimming is perfectly accurate.

    LTX requires frame counts where (n - 1) % 8 == 0
    Valid values: 1, 9, 17, 25, ... 225, 233, 241, ...

    Workflow:
        1. Pass the RAW chunk duration (no overlap added yet).
        2. This node rounds UP to the next valid LTX frame count.
        3. The extra frames are split evenly into start/end overlap.
        4. Pass overlap_ms to Smart Audio Chunker instead of a hardcoded value.
        5. Pass start_trim_frames / end_trim_frames to TKTrimImageOverlap.

    Inputs:
        chunk_secs      : FLOAT   – chunk duration in seconds (NO overlap)
        fps             : INT     – frames per second (default 25)

    Outputs:
        frame_count     : INT   – LTX-compatible frame count (with overlap)
        overlap_ms      : FLOAT – milliseconds to add to each side of chunk
        start_trim_frames : INT – frames to trim from start (for TKTrimImageOverlap)
        end_trim_frames   : INT – frames to trim from end   (for TKTrimImageOverlap)
        actual_secs     : FLOAT – total duration represented by frame_count
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "chunk_secs": ("FLOAT", {"default": 1.0, "min": 0.01, "max": 9999.0, "step": 0.001, "tooltip": "Seconds duration of audio chunk"}),
                "fps":        ("INT",   {"default": 25,  "min": 1,    "max": 240, "tooltip": "Frame per sec -usually 25 "}),
            }
        }

    RETURN_TYPES  = ("INT",         "FLOAT",      "INT",               "INT",             "FLOAT")
    RETURN_NAMES  = ("frame_count", "overlap_ms", "start_trim_frames", "end_trim_frames", "actual_secs")
    FUNCTION      = "calc"
    CATEGORY      = "TKNodes/video"

    def calc(self, chunk_secs: float, fps: int) -> tuple:
        raw = chunk_secs * fps

        # Round UP to next valid LTX frame count: n = 8k + 1
        k = math.ceil((raw - 1) / 8)
        k = max(0, k)
        frame_count = 8 * k + 1
        actual_secs = frame_count / fps

        # Extra frames added by rounding — split evenly between start and end
        extra_frames = frame_count - math.ceil(raw)
        end_trim   = extra_frames // 2
        start_trim = extra_frames - end_trim   # start gets the remainder if odd

        overlap_ms = (extra_frames / fps) * 1000 / 2  # ms per side

        print(f"[TKCalcLTXFrames] {chunk_secs:.3f}s × {fps}fps = {raw:.2f} raw → "
              f"{frame_count} frames ({actual_secs:.3f}s) | "
              f"extra={extra_frames}f | overlap={overlap_ms:.1f}ms/side | "
              f"trim start={start_trim}f end={end_trim}f")

        return (frame_count, overlap_ms, start_trim, end_trim, actual_secs)


class TKTrimAudioWithBooleans:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "fullaudio": ("AUDIO",),

            },
            "optional": {
                "shouldTrimStart": ("BOOLEAN", {"default": False}),
                "trimStartMs": ("INT", {"default": 0, "min": 0, "max": 1000, "step": 100}),
                "shouldTrimEnd": ("BOOLEAN", {"default": False}),
                "trimEndMs": ("INT", {"default": 0, "min": 0, "max": 1000, "step": 100}),
            }
        }

    RETURN_TYPES = ("AUDIO",)
    RETURN_NAMES = ("trimmedAudio",)
    FUNCTION = "trimAudio"
    CATEGORY = "TKNodes"
    DESCRIPTION = "Trim audio with Booleans"

    def trimAudio(self, fullaudio, shouldTrimStart, trimStartMs, shouldTrimEnd, trimEndMs):
        waveform = fullaudio["waveform"]  # shape: [batch, channels, samples]
        sample_rate = fullaudio["sample_rate"]

        total_samples = waveform.shape[-1]

        # Convert ms to sample counts
        start_trim_samples = int((trimStartMs / 1000.0) * sample_rate) if shouldTrimStart else 0
        end_trim_samples   = int((trimEndMs   / 1000.0) * sample_rate) if shouldTrimEnd   else 0

        # Clamp so we never trim more than the total audio length
        start_trim_samples = min(start_trim_samples, total_samples)
        end_trim_samples   = min(end_trim_samples,   total_samples - start_trim_samples)

        # Calculate slice indices
        start_idx = start_trim_samples
        end_idx   = total_samples - end_trim_samples

        # Guard: if nothing would remain, return silence of 1 sample
        if end_idx <= start_idx:
            trimmed = torch.zeros(
                (waveform.shape[0], waveform.shape[1], 1),
                device=waveform.device,
                dtype=waveform.dtype
            )
        else:
            trimmed = waveform[:, :, start_idx:end_idx]

        return ({"waveform": trimmed, "sample_rate": sample_rate},)


class TKSpeakerAudioTrackExtractor:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "fullaudio": ("AUDIO",),
                "combinedTrackInfo1": ("STRING", {"forceInput": True , "tooltip": "Speaker 1 track info."}),
                "combinedTrackInfo2": ("STRING", {"forceInput": True,  "tooltip": "Speaker 2 track info."}),
                "padAudioForLtx" : ("BOOLEAN", {"default": True, "tooltip": "pad audio track with silence..helps lip sync."}),
                "index": ("INT", {"default": 1, "min": 1, "max": 10, "tooltip": "the track number from ALL tracks"}),
            },
            "optional" :{
                "addBreathNoise" : ("BOOLEAN", {"default": False, "tooltip": "This will add human breath to start of audio, turn this ON increases chances of lip sync working."}),
            }
        }

    RETURN_TYPES = ("AUDIO",        "INT"  ,        "INT"      ,"INT"       ,      "INT" ,         "INT")
    RETURN_NAMES = ("audioTrack","totalTracks", "numFrames" , "speakerNum"   , "front_pad_ms", "end_pad_ms")
    FUNCTION = "extractSpeakerTrackAudio"
    CATEGORY = "TKNodes"
    DESCRIPTION ="This node extracts all the track info enterd by the user  and then sorts them and combines them so it can subsequentally loop thru them in the workflow"

    def extractSpeakerTrackAudio(self, fullaudio, combinedTrackInfo1, combinedTrackInfo2, 
                                      index, padAudioForLtx , addBreathNoise=False):
        # 1. Get the startTime and EndTime by calling the helper function

        print(f"track info combined={combinedTrackInfo1} {combinedTrackInfo2}")
        combinedTrackInfo = self.mergeAndSortTracks(combinedTrackInfo1, combinedTrackInfo2)
        start_time, end_time, speaker = TKAudioSpeakerTalkTime.getTrack(index, combinedTrackInfo)

        print(f"INDEX {index}: start={start_time}, end={end_time}, duration={end_time-start_time:.2f}s")

        if (speaker == "speaker1"):
            speakerNum = 1
        elif (speaker == "speaker2"):
            speakerNum = 2
        else:
            speakerNum = 0

        # Extract the waveform and sample rate
        waveform = fullaudio["waveform"]  # shape: [batch, channels, samples]
        sample_rate = fullaudio["sample_rate"]

        # Calculate sample indices
        start_sample = int(start_time * sample_rate)
        end_sample = int(end_time * sample_rate)

        # Bounds checking to prevent index errors
        max_samples = waveform.shape[-1]
        max_duration = max_samples / sample_rate

        # Validate before slicing
        if start_time > max_duration+0.1:
            raise ValueError(f"INDEX {index}: ERROR start_time {start_time:.2f}s exceeds audio length {max_duration:.2f}s")
        if end_time > max_duration+0.1:
            raise ValueError(f"INDEX {index}: ERROR end_time {end_time:.2f}s exceeds audio length {max_duration:.2f}s — ERROR - Make sure you entered correct Speaker Times!")

        start_idx = max(0, min(start_sample, max_samples))
        end_idx = max(0, min(end_sample, max_samples))

        print(f"sample_rate={sample_rate}")
        print(f"waveform.shape={waveform.shape}")
        print(f"max_samples={max_samples}")
        print(f"start_sample={start_sample}, end_sample={end_sample}")
        print(f"start_idx={start_idx}, end_idx={end_idx}")

        # Helper: load the pad audio asset, resample if needed, and trim/tile to exact sample count
        def load_breather_pad_file(target_samples, device, dtype):
  
            # Exact immutable assigned resource, including synthetic guest
            # package loaders with no importlib.resources traversable spec.
            resource = Path(__file__).parent / "assets" / "breather.wav"
            with resource.open("rb") as stream:
                payload = stream.read(1048577)
            if len(payload) > 1048576:
                raise ValueError("bundled breath resource exceeds 1MiB")
            # Explicit approved backend adaptation: pinned immutable PCM only.
            pad_waveform, pad_sr = _pcm_tensor(payload)

            if pad_sr != sample_rate:
                resampler = torchaudio.transforms.Resample(orig_freq=pad_sr, new_freq=sample_rate)
                pad_waveform = resampler(pad_waveform)

            # Match channel count
            target_channels = waveform.shape[1]
            if pad_waveform.shape[0] < target_channels:
                pad_waveform = pad_waveform.expand(target_channels, -1)
            elif pad_waveform.shape[0] > target_channels:
                pad_waveform = pad_waveform[:target_channels, :]

            # Trim to exact target (handles any minor resampling rounding)
            pad_waveform = pad_waveform[:, :target_samples]

            return pad_waveform.unsqueeze(0).to(device=device, dtype=dtype)

        # pad audio withe silence and/or breath
        
        front_pad_ms=0
        end_pad_ms=0

        extraFrames=0
        if (padAudioForLtx):

            # Get speech waveform first (used in both branches)
            new_waveform = waveform[:, :, start_idx:end_idx]

            batch_size = waveform.shape[0]
            target_channels = waveform.shape[1]

            # Create 500ms of silence: [batch, channels, sample_rate // 2]
            half_second_samples = sample_rate // 2
            silence_500ms = torch.zeros(
                (batch_size, target_channels, half_second_samples),
                device=waveform.device,
                dtype=waveform.dtype
            )

            if addBreathNoise:
                extra_frames = 25 + 13
                front_pad_ms=1000  # specify ammount to be deleted later.

                #  breather +500ms silence + original audio + 500ms silence
                breather_pad = load_breather_pad_file(sample_rate, waveform.device, waveform.dtype)
                final_waveform = torch.cat([breather_pad, new_waveform, silence_500ms], dim=-1)

            else:
                extra_frames =13
                front_pad_ms=0

                # No breather noise -         original audio + 500ms silence
                final_waveform = torch.cat([new_waveform, silence_500ms], dim=-1)


        else:  # USER SELECTED 0 PADDING!

            final_waveform = waveform[:, :, start_idx:end_idx]
            new_waveform = final_waveform
                

        print(
            f"Get Track - INDEX {index}: start={start_time}, end={end_time}, "
            f"duration={end_time-start_time:.2f}s | "
            f"new_waveform={new_waveform.shape[-1]} samples | "
            f"final_waveform={final_waveform.shape[-1]} samples")

        totalTracks, last_time_stamp = self.getTotalTracks(combinedTrackInfo)
        if (last_time_stamp > max_duration):
            if (last_time_stamp - max_duration > 0.1):
               raise ValueError(f" ERROR: Your timings exceeds the Audio Length - Fix your inputs - size {last_time_stamp} > {max_duration} seconds")


        nFrames = int(round((end_time - start_time) * 25) + extra_frames)

        # Force all numeric outputs to pure integers
        return (
            {"waveform": final_waveform, "sample_rate": sample_rate},
            int(totalTracks),
            int(nFrames),
            int(speakerNum),
            int(front_pad_ms),
            int(end_pad_ms),
        
        )


    def mergeAndSortTracks(self, combined_string1, combined_string2):
        # 1. Helper to parse string into pairs with a speaker label
        def parse_to_labeled_pairs(s, speaker_label):
            raw = [float(x.strip()) for x in s.split(",") if x.strip()]
            it = iter(raw)
            # Only keep tracks that aren't (0.0, 0.0)
            return [(start, end, speaker_label) for start, end in zip(it, it) 
                    if start != 0.0 or end != 0.0]

        # 2. Parse both inputs
        tracks1 = parse_to_labeled_pairs(combined_string1, "speaker1")
        tracks2 = parse_to_labeled_pairs(combined_string2, "speaker2")

        # 3. Combine and sort by start time
        all_tracks = sorted(tracks1 + tracks2)

        # 4. Flatten into strings and Debug
        final_values = []
        print(f"\n{'#' : <5} | {'Speaker' : <10} | {'Start' : <10} | {'End' : <10}")
        print("-" * 45)
        
        for i, (start, end, speaker) in enumerate(all_tracks, 1):
            # Debug Print
            print(f" {i : <5} | {speaker : <10} | {start : <10} | {end : <10}")
            
            # Append to result list
            final_values.extend([str(start), str(end), speaker])

        # 5. Join with commas
        return ",".join(final_values)


    



    def getTotalTracks(self, combined_string):
        if isinstance(combined_string, tuple):
            combined_string = combined_string[0]

        if not combined_string or not str(combined_string).strip():
            return 0, 0.0
            
        parts = str(combined_string).split(",")
        num_parts = len(parts)
        total_populated = 0
        max_end_time = 0.0 
        
        # Step through in chunks of 3 (start, end, label)
        for i in range(0, num_parts - 2, 3):
            try:
                start_val = parts[i].strip()
                end_val = parts[i+1].strip()
                
                # Basic string check to ensure we have numbers
                if not start_val or not end_val:
                    continue
                    
                start = float(start_val)
                end = float(end_val)

                # 1. Check for 'Empty/Padding' tracks (0,0)
                # If we hit 0,0, we assume the data ends here and stop counting
                if start == 0.0 and end == 0.0:
                    break 

                # 2. STRICT VALIDATION: If data exists but is nonsensical, 
                # return 0 for everything to block further processing.
                if start < 0 or end < 0 or start >= end:
                    print(f"*****  CRITICAL ERROR: Check to make sure your timings that you entered are correct.  Invalid timestamps found (Start: {start}, End: {end})")
                    return 0, 0.0

                # 3. Track valid data
                total_populated += 1
                if end >= max_end_time:
                    max_end_time = end
                
            except (ValueError, IndexError):
                print(f"CRITICAL ERROR: Non-numeric track data at index {i}")
                return 0, 0.0

        return int(total_populated), float(max_end_time)


class TKSpeakerDataFromTrack:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "trackIndex": ("INT", {"default": 1, "min": 1, "max": 100}),
                "speakerNum": ("INT", {"forceInput": True}),
                "image1": ("IMAGE",),
                "prompt1": ("STRING", {"multiline": True, "default": ""}),
                "image2": ("IMAGE",),
                "prompt2": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING", "INT")
    RETURN_NAMES = ("selectedImage", "selectedText", "currentIndex")
    FUNCTION = "select_data"
    CATEGORY = "TKNodes"
    DESCRIPTION ="Given the Speaker, select the appropriate PROMPT and START IMAGE. since they alternate we need this"

    def select_data(self, trackIndex, speakerNum, image1, prompt1, image2, prompt2):
        # 1. Logic to pick based on the speakerNum provided by your extractor
        if speakerNum == 1:
            img, txt = image1, prompt1
        elif speakerNum == 2:
            img, txt = image2, prompt2
        else:
            # Fallback for index 0 or unknown
            img, txt = image1, prompt1 

        return (img, txt, trackIndex)


class TKTotalTracksInAudio:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "combinedTrackInfo1": ("STRING", {"forceInput": True, "tooltip":"Speaker 1 defined track times"}),
                "combinedTrackInfo2": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("totalTracks",)
    FUNCTION = "calculate_total"
    CATEGORY = "TKNodes"
    DESCRIPTION = "Get the total talks tracks between the 2 Speakers"

    def calculate_total(self, combinedTrackInfo1, combinedTrackInfo2):
        # We use a temporary instance of your extractor to reuse the logic
        # Same selected class is in this module; no eager archival Sherpa import.
        extractor = TKSpeakerAudioTrackExtractor()
        
        # 1. Merge the strings using your existing logic
        merged = extractor.mergeAndSortTracks(combinedTrackInfo1, combinedTrackInfo2)
        
        # 2. Get the total count
        total, last_end_time = extractor.getTotalTracks(merged)
        
        return (int(total),)


class TKAudioSpeakerTalkTime:
    @classmethod
    def INPUT_TYPES(s):
        inputs = {
            "required": {
                "track_start_1": ("FLOAT", {"default": 0.00, "min": 0.00, "max": 500.0, }),
                "track_end_1": ("FLOAT", {"default": 0.00, "min": 0.00, "max": 500.0, }),
              
            },
            "optional": {
                "track_start_2": ("FLOAT", {"default": 0.00, "min": 0.00, "max": 500.0, }),
                "track_end_2": ("FLOAT", {"default": 0.00, "min": 0.00, "max": 500.0, }),
                "track_start_3": ("FLOAT", {"default": 0.00, "min": 0.00, "max": 500.0, }),
                "track_end_3": ("FLOAT", {"default": 0.00, "min": 0.00, "max": 500.0, }),                
                "track_start_4": ("FLOAT", {"default": 0.00, "min": 0.00, "max": 500.0, }),
                "track_end_4": ("FLOAT", {"default": 0.00, "min": 0.00, "max": 500.0, }),                
                "track_start_5": ("FLOAT", {"default": 0.00, "min": 0.00, "max": 500.0, }),
                "track_end_5": ("FLOAT", {"default": 0.00, "min": 0.00, "max": 500.0, }),                

            }
        }
        return inputs

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("trackTimesCombined",)
    FUNCTION = "speakerTalkTimes"
    CATEGORY = "TKNodes"

    def speakerTalkTimes(self, track_start_1, track_end_1, track_start_2 , track_end_2 ,
                                track_start_3, track_end_3,track_start_4 , track_end_4,
                                track_start_5, track_end_5,  ):

        
        # Group inputs into pairs
        tracks = [
            (track_start_1, track_end_1),
            (track_start_2, track_end_2),
            (track_start_3, track_end_3),
            (track_start_4, track_end_4),
            (track_start_5, track_end_5)
        ]

        # Flatten the pairs and convert to strings, ignoring pairs that are both 0.0
        values = []
        for start, end in tracks:
            if start != 0.0 or end != 0.0:
                values.extend([str(start), str(end)])

        # Concatenate with commas
        combined_string = ",".join(values)
        
        return (combined_string,)


   
    @staticmethod
    def getTrack(index, combined_string_of_tracks):
        # Fix: If ComfyUI sends this as a tuple, grab the first item (the string)
        if isinstance(combined_string_of_tracks, tuple):
            combined_string_of_tracks = combined_string_of_tracks[0]
        
        # Check for None or empty strings to prevent crashes
        if not combined_string_of_tracks or not isinstance(combined_string_of_tracks, str):
            return 0.0, 0.0, ""

        # Split the string back into a list of individual values
        parts = [p.strip() for p in combined_string_of_tracks.split(",") if p.strip()]
        
        # Calculate the starting position (1-based index)
        # Changed multiplier to 3 because each track is now [start, end, speaker]
        start_pos = (index - 1) * 3
        
        try:
            # Pull the start, end, and speaker values
            starttime = float(parts[start_pos])
            endtime = float(parts[start_pos + 1])
            speaker = parts[start_pos + 2]
            return starttime, endtime, speaker
        except (IndexError, ValueError) as e:
            # Log the error and the problematic index
            print(f"Error retrieving track at index {index}: {e}")
            # Return 0.0 and empty string if the index doesn't exist
            return 0.0, 0.0, ""


class TKAudioToFPSMatcher:
    DESCRIPTION = "Aligns and pads an original audio track to perfectly match the duration of a target FPS video timeline, preventing VHS truncation.  Mainly needed for V2V"
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "audio": ("AUDIO", {"tooltip": "Original master audio"}),
                "video": ("IMAGE", {"tooltip": "Your newly generated video tensor"}),
                "video_fps": ("FLOAT", {"default": 16.0, "min": 1.0, "max": 60.0, "step": 0.01, "tooltip": "The FPS of your generated video (e.g., 16.0)"}),
            },
        }

    RETURN_TYPES = ("AUDIO", "FLOAT",)
    RETURN_NAMES = ("matched_audio", "exact_duration_seconds",)
    FUNCTION = "match_audio_to_video"
    CATEGORY = "TKNodes"

    # --- FUNCTION 1: DROP FRAMES (STRICTLY VIDEO AND TARGET FPS INPUTS) ---
    def drop_video_frames(self, video, video_fps):
        # 1. Total frame sequence count coming directly from the image tensor link
        total_source_frames = video.shape[0]
        
        # 2. Extract the physical layout length (seconds) directly from the tensor's native indices
        # This determines the runtime boundaries natively, removing the hardcoded 30.0
        calculated_source_fps = total_source_frames / (total_source_frames / video_fps)

        # 3. Calculate exactly how many frames to keep for your 16fps target container limit
        # Example: (300 total frames * 16fps target) / 30fps dynamic source = 160 frames
        required_frame_count = math.ceil((total_source_frames * video_fps) / calculated_source_fps)

        if total_source_frames > required_frame_count:
            # Drops frames mathematically across the tensor index layout to match the container target
            indices = torch.linspace(0, total_source_frames - 1, steps=required_frame_count, dtype=torch.long, device=video.device)
            return video[indices]
        return video
    
    def match_audio_to_video(self, audio, video, video_fps):
        if audio is None or video is None:
            return (audio, 0.0)


        newvideo  = self.drop_video_frames(  video, video_fps)

        waveform = audio.get("waveform")  # Shape: [channels, samples]
        sample_rate = audio.get("sample_rate")
        
        if waveform is None or sample_rate is None:
            return (audio, 0.0)

        # 1. Calculate exactly how long the video container is at 16 FPS
        total_video_frames = newvideo.shape[0]
        video_duration_seconds = total_video_frames / video_fps

        # 2. Calculate the exact number of audio samples needed for this duration
        required_audio_samples = math.ceil(video_duration_seconds * sample_rate)
        current_audio_samples = waveform.shape[-1]

        # 3. Match the audio length to the video length perfectly
        if current_audio_samples > required_audio_samples:
            # Audio is too long: Trim it cleanly so VHS Combine doesn't force-chop it
            clean_waveform = waveform[..., :required_audio_samples]
        elif current_audio_samples < required_audio_samples:
            # Audio is too short: Pad with absolute silence to fill the microsecond gap
            padding_size = required_audio_samples - current_audio_samples
            padding = torch.zeros((*waveform.shape[:-1], padding_size), dtype=waveform.dtype, device=waveform.device)
            clean_waveform = torch.cat([waveform, padding], dim=-1)
        else:
            clean_waveform = waveform

        matched_audio = {"waveform": clean_waveform, "sample_rate": sample_rate}
        return (matched_audio, video_duration_seconds)


class TKSnapFrames:
    DESCRIPTION = "Snap Frames - Rounds num_frames UP to the nearest valid (multiple*n + 1) frame count for the target model"

    MODEL_MULTIPLES = {
        "WAN": 4,
        "LTX": 8,
    }

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": (list(s.MODEL_MULTIPLES.keys()), {"default": "WAN", "tooltip": "Target model - determines the valid frame-count multiple (n+1)"}),
                "num_frames": ("INT", {"default": 17, "min": 1, "max": 9999, "tooltip": "Requested frame count before snapping"}),
            },
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("snapped_frames",)
    FUNCTION = "snap"
    CATEGORY = "TKNodes"

    def snap(self, model, num_frames):
        multiple = self.MODEL_MULTIPLES[model]
        snapped_frames = math.ceil((num_frames - 1) / multiple) * multiple + 1
        return (snapped_frames,)


def _tensor_batch_to_gray_small(images, analysis_width: int = 160):
    """
    images: torch tensor [N, H, W, C], float 0-1 (standard ComfyUI IMAGE type)
    Returns: list of small grayscale uint8 numpy frames, resized to analysis_width.
    Downscaling is purely for speed - detection doesn't need full resolution.
    torch is only needed here (inside the ComfyUI node path), not for
    detect_boundaries() itself, which is pure numpy/opencv and testable standalone.
    """
    import torch  # local import: only required when running inside ComfyUI
    n, h, w, c = images.shape
    scale = analysis_width / float(w)
    new_w = analysis_width
    new_h = max(1, int(round(h * scale)))

    frames_np = (images.clamp(0, 1) * 255.0).to(torch.uint8).cpu().numpy()  # [N,H,W,C]

    gray_frames = []
    for i in range(n):
        frame = frames_np[i]
        if c == 4:
            frame = frame[:, :, :3]
        if c == 1:
            gray = cv2.resize(frame[:, :, 0], (new_w, new_h), interpolation=cv2.INTER_AREA)
        else:
            small = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
        gray_frames.append(gray)
    return gray_frames


def _hist_distance(a: np.ndarray, b: np.ndarray) -> float:
    """1 - histogram correlation. 0 = identical, ~1-2 = very different."""
    hist_a = cv2.calcHist([a], [0], None, [64], [0, 256])
    hist_b = cv2.calcHist([b], [0], None, [64], [0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    corr = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
    return 1.0 - corr


def _edge_density(frame: np.ndarray) -> float:
    """Fraction of pixels that are Canny edges. Dips during dissolves."""
    edges = cv2.Canny(frame, 60, 150)
    return float(np.count_nonzero(edges)) / edges.size


def _causal_baseline(arr: np.ndarray, window: int, lag: int) -> np.ndarray:
    """
    Backward-looking median: baseline[i] = median(arr[i-lag-window : i-lag]).
    Deliberately does NOT look at recent frames (within `lag`), so that if a
    dip/dissolve is currently happening at frame i, the baseline still
    reflects the stable shot *before* the dip started, rather than being
    dragged down by the dip itself (a centered window would straddle the
    dip and dilute the drop we're trying to detect).
    """
    n = len(arr)
    out = np.empty(n, dtype=np.float64)
    for i in range(n):
        hi = max(1, i - lag)
        lo = max(0, hi - window)
        if lo >= hi:
            out[i] = arr[i]
        else:
            out[i] = np.median(arr[lo:hi])
    return out


def detect_boundaries(
    gray_frames,
    fps: float,
    max_segment_seconds: float,
    cut_z_thresh: float,
    dissolve_dip_ratio: float,
    dissolve_min_len: int,
    baseline_window: int,
    return_debug: bool = False,
):
    """
    Always returns a (boundaries, debug_rows) tuple - debug_rows is simply
    an empty list when return_debug is False. Keeping the return shape
    constant (rather than sometimes a bare list, sometimes a tuple) avoids
    static-type ambiguity in callers.
    """
    n = len(gray_frames)
    if n < 2:
        result = [{"frame": n - 1, "time": (n - 1) / fps, "type": "end"}]
        return result, []

    # --- per-frame signals ---
    hist_dist = np.zeros(n)
    edge_dens = np.zeros(n)
    edge_dens[0] = _edge_density(gray_frames[0])
    for i in range(1, n):
        hist_dist[i] = _hist_distance(gray_frames[i - 1], gray_frames[i])
        edge_dens[i] = _edge_density(gray_frames[i])

    # --- hard cut detection: rolling z-score over hist_dist ---
    mean = np.mean(hist_dist[1:])
    std = np.std(hist_dist[1:]) + 1e-6
    z = (hist_dist - mean) / std

    # A hard cut is an ISOLATED spike: frame i is very different from i-1,
    # but frame i's neighbors are NOT also spiking. A dissolve instead shows
    # a sustained run of moderately-elevated distance across many frames -
    # that run gets handled by the edge-density dip logic below, not here.
    cut_frames = set()
    for i in range(1, n):
        if z[i] <= cut_z_thresh:
            continue
        neighbor_lo = max(1, i - 2)
        neighbor_hi = min(n, i + 3)
        neighborhood = np.delete(z[neighbor_lo:neighbor_hi], np.where(np.arange(neighbor_lo, neighbor_hi) == i))
        if neighborhood.size == 0 or np.max(neighborhood) < (cut_z_thresh * 0.5):
            cut_frames.add(i)

    # --- dissolve detection: edge density dip vs pre-dip baseline ---
    # lag must be >= the longest dip we expect, so the baseline window never
    # includes frames from inside the dip itself.
    baseline_lag = max(dissolve_min_len * 3, 15)
    baseline = _causal_baseline(edge_dens, baseline_window, baseline_lag)
    dip_mask = edge_dens < (baseline * dissolve_dip_ratio)

    dissolve_end_frames = set()
    i = 1
    while i < n:
        if dip_mask[i] and i not in cut_frames:
            start = i
            while i < n and dip_mask[i]:
                i += 1
            end = i  # first frame after the dip = dissolve considered finished
            if (end - start) >= dissolve_min_len:
                dissolve_end_frames.add(min(end, n - 1))
        else:
            i += 1

    # --- merge cuts + dissolve ends into one boundary list ---
    boundaries = []
    for f in sorted(cut_frames):
        boundaries.append({"frame": f, "time": f / fps, "type": "cut"})
    for f in sorted(dissolve_end_frames):
        boundaries.append({"frame": f, "time": f / fps, "type": "dissolve_end"})
    boundaries.sort(key=lambda b: b["frame"])

    # de-dupe boundaries that land within a few frames of each other
    deduped = []
    for b in boundaries:
        if deduped and (b["frame"] - deduped[-1]["frame"]) <= 3:
            continue
        deduped.append(b)
    boundaries = deduped

    # --- enforce max_segment_seconds: insert forced boundaries into gaps ---
    max_frames = int(round(max_segment_seconds * fps))
    final = []
    last = 0
    for b in boundaries:
        while (b["frame"] - last) > max_frames:
            forced_frame = last + max_frames
            final.append({"frame": forced_frame, "time": forced_frame / fps, "type": "forced"})
            last = forced_frame
        final.append(b)
        last = b["frame"]

    # tail: from last boundary to end of video
    last_frame_idx = n - 1
    while (last_frame_idx - last) > max_frames:
        forced_frame = last + max_frames
        final.append({"frame": forced_frame, "time": forced_frame / fps, "type": "forced"})
        last = forced_frame

    if not final or final[-1]["frame"] != last_frame_idx:
        final.append({"frame": last_frame_idx, "time": last_frame_idx / fps, "type": "end"})

    debug_rows = []
    if return_debug:
        edge_ratio = edge_dens / np.maximum(baseline, 1e-9)
        for i in range(n):
            debug_rows.append({
                "frame": i,
                "time": round(i / fps, 3),
                "hist_dist": round(float(hist_dist[i]), 5),
                "z_score": round(float(z[i]), 3),
                "edge_density": round(float(edge_dens[i]), 5),
                "edge_baseline": round(float(baseline[i]), 5),
                "edge_ratio": round(float(edge_ratio[i]), 3),
                "flagged_cut": i in cut_frames,
                "flagged_dip": bool(dip_mask[i]),
            })

    return final, debug_rows


class TKTransitionDetector:
    """
    Inputs an IMAGE batch (e.g. from VHS Load Video), outputs segment
    boundary frames: hard cuts, dissolve-finish frames, and forced
    boundaries wherever a segment would otherwise exceed max_segment_seconds.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "fps": ("FLOAT", {"default": 25.0, "min": 1.0, "max": 240.0, "step": 0.01}),
                "max_segment_seconds": ("FLOAT", {"default": 10.0, "min": 1.0, "max": 120.0, "step": 0.5}),
                "cut_z_thresh": ("FLOAT", {"default": 3.0, "min": 1.0, "max": 10.0, "step": 0.1}),
                "dissolve_dip_ratio": ("FLOAT", {"default": 0.70, "min": 0.1, "max": 0.95, "step": 0.01}),
                "dissolve_min_len": ("INT", {"default": 5, "min": 2, "max": 60}),
                "analysis_width": ("INT", {"default": 160, "min": 64, "max": 640}),
                "debug_mode": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("STRING", "INT", "STRING", "INT", "STRING")
    RETURN_NAMES = ("boundaries_json", "boundary_count", "report", "boundary_frames", "debug_csv")
    OUTPUT_IS_LIST = (False, False, False, True, False)
    FUNCTION = "run"
    CATEGORY = "TKNodes/video"

    def run(
        self,
        images,
        fps,
        max_segment_seconds,
        cut_z_thresh,
        dissolve_dip_ratio,
        dissolve_min_len,
        analysis_width,
        debug_mode,
    ):
        gray_frames = _tensor_batch_to_gray_small(images, analysis_width=analysis_width)
        baseline_window = max(11, dissolve_min_len * 4 + 1)  # odd window, scales with dip length

        boundaries, debug_rows = detect_boundaries(
            gray_frames=gray_frames,
            fps=fps,
            max_segment_seconds=max_segment_seconds,
            cut_z_thresh=cut_z_thresh,
            dissolve_dip_ratio=dissolve_dip_ratio,
            dissolve_min_len=dissolve_min_len,
            baseline_window=baseline_window,
            return_debug=debug_mode,
        )

        boundaries_json = json.dumps(boundaries, indent=2)

        lines = [f"{len(boundaries)} boundaries detected (fps={fps}):"]
        for b in boundaries:
            lines.append(f"  frame {b['frame']:>6}  t={b['time']:.2f}s  [{b['type']}]")
        report = "\n".join(lines)

        boundary_frames = [b["frame"] for b in boundaries if b["type"] != "end"]
        if not boundary_frames:
            boundary_frames = [b["frame"] for b in boundaries]  # fallback: nothing but 'end'

        if debug_mode and debug_rows:
            cols = ["frame", "time", "hist_dist", "z_score", "edge_density", "edge_baseline", "edge_ratio", "flagged_cut", "flagged_dip"]
            csv_lines = [",".join(cols)]
            for r in debug_rows:
                csv_lines.append(",".join(str(r[c]) for c in cols))
            debug_csv = "\n".join(csv_lines)
        else:
            debug_csv = "debug_mode is off - enable it to get per-frame z_score/edge_ratio values"

        return (boundaries_json, len(boundaries), report, boundary_frames, debug_csv)


NODE_CLASS_MAPPINGS = {
    'TKPromptEnhanced': TKPromptEnhanced,
    'TKVideoUserInputs': TKVideoUserInputs,
    'TKPhotoUserInputs': TKPhotoUserInputs,
    'TKVideoUserInputsBasic': TKVideoUserInputsBasic,
    'TKVideoAudioFuse': TKVideoAudioFuse,
    'TKAudioFuse': TKAudioFuse,
    'TKAudioUnwrap': TKAudioUnwrap,
    'TKSmartAudioChunker': TKSmartAudioChunker,
    'TKSmartVideoChunker': TKSmartVideoChunker,
    'TKPrintValueToLog': TKPrintValueToLog,
    'TKMergeAudioList': TKMergeAudioList,
    'TKSpeakerAudioTrackExtractor': TKSpeakerAudioTrackExtractor,
    'TKTotalTracksInAudio': TKTotalTracksInAudio,
    'TKSpeakerDataFromTrack': TKSpeakerDataFromTrack,
    'TKTrimImageOverlap': TKTrimImageOverlap,
    'TKCalcLTXFrames': TKCalcLTXFrames,
    'TKTrimAudioWithBooleans': TKTrimAudioWithBooleans,
    'TKAudioSpeakerTalkTime': TKAudioSpeakerTalkTime,
    'TKFadeInVideo': TKFadeInVideo,
    'TKCrossDissolve': TKCrossDissolve,
    'TKPromptLooper': TKPromptLooper,
    'TKTrimFrames': TKTrimFrames,
    'TKTransitionDetector': TKTransitionDetector,
    'TKSnapFrames': TKSnapFrames,
    'TKAudioToFPSMatcher': TKAudioToFPSMatcher,
    'TKPromptLooperAdv': TKPromptLooperAdv,
}
NODE_DISPLAY_NAME_MAPPINGS = {'TKPromptEnhanced': 'Enhanced Prompt with camera descriptives', 'TKTrimAudioWithBooleans': 'Trim Audio (Booleans)', 'TKCalcLTXFrames': 'Calculate LTX Frames ', 'TKVideoUserInputs': 'Video User Inputs', 'TKPhotoUserInputs': 'GUI - Photo User Inputs', 'TKVideoUserInputsBasic': 'Video User Inputs Basic', 'TKVideoAudioFuse': 'Video Audio Fuse', 'TKAudioFuse': 'Audio Merge/Fuse', 'TKSmartAudioChunker': 'Smart Audio Chunker', 'TKSmartVideoChunker': 'Smart Video Chunker', 'TKSimpleVideoChunker': 'Simple Video Chunker', 'TKAudioUnwrap': 'Audio → Waveform Tensor', 'TKPrintValueToLog': 'Print Value to log', 'TKSpeakerAudioTrackExtractor': 'Extract nTh Audio track', 'TKMergeAudioList': 'Merge audio list to master audio', 'TKTotalTracksInAudio': 'User supplied tracks', 'TKLocateSpeakersUsingSilenceBreaks': 'Identify Speakers using Silence Breaks', 'TKTrimImageOverlap': 'Trim Padding used for Smooth Transition', 'TKSpeakerDataFromTrack': 'Get a Track details from Track', 'TKAudioSpeakerTalkTime': 'Speaker Talk Times', 'TKFadeInVideo': 'Fade in Video', 'TKPromptLooper': 'Prompt Looper', 'TKCrossDissolve': 'Cross Dissolve Effect', 'TKTrimFrames': 'Trim Frames and Audio', 'TKTransitionDetector': 'Video Transition Detector', 'TKSnapFrames': 'Snap Frames to boundry rules', 'TKAudioToFPSMatcher': 'Resample Audio for new FPS', 'TKMultiImagePrompt': 'Multi Image + Prompt', 'TKPromptLooperAdv': 'Prompt Looper Advanced', 'TKMultiImageSelect': 'Multi Image Select'}
