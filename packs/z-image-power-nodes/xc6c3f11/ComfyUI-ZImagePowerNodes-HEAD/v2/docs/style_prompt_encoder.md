# ⚡| Style & Prompt Encoder
![text](style_prompt_encoder.jpg)

Encodes the result of fusing a prompt with a visual style, generating embeddings that guide the diffusion process. This node is similar to ComfyUI's native "CLIP Text Encode (Prompt)", but it includes the option to select a visual style for the generated image.


## Inputs

### clip
The text encoder model used to encode the prompt and style.

### customization
Optional input that can remain disconnected, allows redefining the internal settings of predefined styles.  
You can connect either a multi-line string containing the custom configurations or a "My Top-10 Styles" node.  
If a multi-line string node is connected, its text should follow this format: each style definition starts with ">>>" followed by the name, then includes lines describing the style template. The template must include "{$@}" where the user's prompt will be inserted.

Example:
```
>>>Phone Photo
YOUR CONTEXT:
Your photographs has android phone cam-quality.
Your photographs exhibit surprising compositions, sharp complex backgrounds,
natural lighting, and candid moments that feel immediate and authentic.
Your photographs are actual gritty candid photographic background.
YOUR PHOTO:
{$@}


>>>Casual Photo
YOUR CONTEXT:
You are an amateur documentary photographer taking low quality photos.
Your photographs exhibit sharp backgrounds, unpolished realism with natural lighting,
and candid friendship-level moments that feel immediate and authentic.
YOUR PHOTO:
{$@}
```

### style
Displays the currently active style, or "none" if no style will be applied.

### \<Select Style button\>
Opens the style gallery to browse and choose from available styles easily.  
This includes search functionality, filtering options, and a sample image
showing what each style would look like.

### text
This is where you input your prompt. For better style application, avoid including messages in the prompt that might interfere with the selected style.


## Outputs

### conditioning
The encoded prompt embeddings with applied style, used to guide the model during generation.

### string
The prompt text after applying the selected style. Typically not used, but can be employed for advanced purposes.

