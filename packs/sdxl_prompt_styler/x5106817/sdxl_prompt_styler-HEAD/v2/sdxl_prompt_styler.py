from comfy_api.latest import io
from ._style_data import STYLE_DATA, STYLE_NAMES

def read_sdxl_styles(json_data):
    """
    Returns style names from the provided JSON data.
    """
    if not isinstance(json_data, list):
        print("Error: input data must be a list")
        return []

    return [item['name'] for item in json_data if isinstance(item, dict) and 'name' in item]

def validate_json_data(json_data):
    """
    Validates the structure of the JSON data.
    """
    if not isinstance(json_data, list):
        return False
    for template in json_data:
        if 'name' not in template or 'prompt' not in template:
            return False
    return True

def find_template_by_name(json_data, template_name):
    """
    Returns a template from the JSON data by name or None if not found.
    """
    for template in json_data:
        if template['name'] == template_name:
            return template
    return None

def split_template_advanced(template: str) -> tuple:
    """
    Splits a template into two parts based on a specific pattern.
    """
    if " . " in template:
        template_prompt_g, template_prompt_l = template.split(" . ", 1)
        template_prompt_g = template_prompt_g.strip()
        template_prompt_l = template_prompt_l.strip()
    else:
        template_prompt_g = template
        template_prompt_l = ""

    return template_prompt_g, template_prompt_l

def replace_prompts_in_template(template, positive_prompt, negative_prompt):
    """
    Replace the placeholders in a given template with the provided prompts.
    
    Args:
    - template (dict): The template containing prompt placeholders.
    - positive_prompt (str): The positive prompt to replace '{prompt}' in the template.
    - negative_prompt (str): The negative prompt to be combined with any existing negative prompt in the template.

    Returns:
    - tuple: A tuple containing the replaced positive and negative prompts.
    """
    positive_result = template['prompt'].replace('{prompt}', positive_prompt)

    json_negative_prompt = template.get('negative_prompt', "")
    negative_result = f"{json_negative_prompt}, {negative_prompt}" if json_negative_prompt and negative_prompt else json_negative_prompt or negative_prompt

    return positive_result, negative_result

def deduplicate_merge(prompt_1, prompt_2):
    """
    Merge two prompts, deduplicating the tokens.

    Args:
    - prompt1 (str): The first prompt.
    - prompt2 (str): The second prompt.

    Returns:
    - str: The merged and deduplicated prompt.
    """
    if not prompt_2:
        return prompt_1
    elif not prompt_1:
        return prompt_2

    token_prompt_1 = list(map(lambda x: x.strip(), prompt_1.split(",")))
    token_prompt_2 = list(map(lambda x: x.strip(), prompt_2.split(",")))

    # deduplicate common prompt parts
    for token in token_prompt_1:
        if token in token_prompt_2:
            token_prompt_2.remove(token)

    token_prompt_1.extend(token_prompt_2)

    prompt_out = ", ".join(token_prompt_1)

    return prompt_out

def replace_prompts_in_template_advanced(template, positive_prompt_g, positive_prompt_l, negative_prompt, negative_prompt_to, copy_to_l):
    """
    Replace the placeholders in a given template with the provided prompts and split them accordingly.
    
    Args:
    - template (dict): The template containing prompt placeholders.
    - positive_prompt_g (str): The main positive prompt to replace '{prompt}' in the template.
    - positive_prompt_l (str): The auxiliary positive prompt to be combined in a specific manner.
    - negative_prompt (str): The negative prompt to be combined with any existing negative prompt in the template.
    - negative_prompt_to (str): The negative prompt destination {Both, G only, L only}.
    - copy_to_l (bool): Copy the G positive prompt to L.

    Returns:
    - tuple: A tuple containing the replaced main positive, auxiliary positive, combined positive,  main negative, auxiliary negative, and negative prompts.
    """
    template_prompt_g, template_prompt_l_template = split_template_advanced(template['prompt'])

    text_g_positive = template_prompt_g.replace("{prompt}", positive_prompt_g)

    text_l_positive = f"{template_prompt_l_template.replace('{prompt}', positive_prompt_g)}, {positive_prompt_l}" if template_prompt_l_template and positive_prompt_l else template_prompt_l_template.replace('{prompt}', positive_prompt_g) or positive_prompt_l

    if copy_to_l and positive_prompt_g and "{prompt}" not in template_prompt_l_template:
        text_l_positive = deduplicate_merge(text_g_positive, text_l_positive)

    text_positive = deduplicate_merge(text_g_positive, text_l_positive) if text_l_positive else text_g_positive

    json_negative_prompt = template.get('negative_prompt', "")
    text_negative = f"{json_negative_prompt}, {negative_prompt}" if json_negative_prompt and negative_prompt else json_negative_prompt or negative_prompt

    text_g_negative = ""
    if negative_prompt_to in ("Both", "G only"):
        text_g_negative = text_negative

    text_l_negative = ""
    if negative_prompt_to in ("Both", "L only"):
        text_l_negative = text_negative

    return text_g_positive, text_l_positive, text_positive, text_g_negative, text_l_negative, text_negative

def read_sdxl_templates_replace_and_combine(json_data, template_name, positive_prompt, negative_prompt):
    """
    Find a specific template by its name, then replace and combine its placeholders with the provided prompts.
    
    Args:
    - json_data (list): The list of templates.
    - template_name (str): The name of the desired template.
    - positive_prompt (str): The positive prompt to replace placeholders.
    - negative_prompt (str): The negative prompt to be combined.

    Returns:
    - tuple: A tuple containing the replaced and combined positive and negative prompts.
    """
    if not validate_json_data(json_data):
        return positive_prompt, negative_prompt

    template = find_template_by_name(json_data, template_name)

    if template:
        return replace_prompts_in_template(template, positive_prompt, negative_prompt)
    else:
        return positive_prompt, negative_prompt

def read_sdxl_templates_replace_and_combine_advanced(json_data, template_name, positive_prompt_g, positive_prompt_l, negative_prompt, negative_prompt_to, copy_to_l):
    """
    Find a specific template by its name, then replace and combine its placeholders with the provided prompts in an advanced manner.
    
    Args:
    - json_data (list): The list of templates.
    - template_name (str): The name of the desired template.
    - positive_prompt_g (str): The main positive prompt.
    - positive_prompt_l (str): The auxiliary positive prompt.
    - negative_prompt (str): The negative prompt to be combined.
    - negative_prompt_to (str): The negative prompt destination {Both, G only, L only}.
    - copy_to_l (bool): Copy the G positive prompt to L.

    Returns:
    - tuple: A tuple containing the replaced and combined main positive, auxiliary positive, combined positive, main negative, auxiliary negative, and negative prompts.
    """
    if not validate_json_data(json_data):
        return positive_prompt_g, positive_prompt_l, f"{positive_prompt_g} . {positive_prompt_l}", negative_prompt, negative_prompt, negative_prompt

    template = find_template_by_name(json_data, template_name)

    if template:
        return replace_prompts_in_template_advanced(template, positive_prompt_g, positive_prompt_l, negative_prompt, negative_prompt_to, copy_to_l)
    else:
        return positive_prompt_g, positive_prompt_l, f"{positive_prompt_g} . {positive_prompt_l}", negative_prompt, negative_prompt, negative_prompt

class SDXLPromptStyler(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    def __init__(self):
        self.json_data = STYLE_DATA

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="SDXLPromptStyler", display_name="SDXL Prompt Styler", category="utils",
            inputs=[io.String.Input("text_positive", default="", multiline=True),
                    io.String.Input("text_negative", default="", multiline=True),
                    io.Combo.Input("style", options=list(STYLE_NAMES)),
                    io.Boolean.Input("log_prompt", default=True, label_on="yes", label_off="no"),
                    io.Boolean.Input("style_positive", default=True, label_on="yes", label_off="no"),
                    io.Boolean.Input("style_negative", default=True, label_on="yes", label_off="no")],
            outputs=[io.String.Output(display_name="text_positive"), io.String.Output(display_name="text_negative")])

    @classmethod
    async def execute(cls, text_positive, text_negative, style, log_prompt, style_positive, style_negative) -> io.NodeOutput:
        return io.NodeOutput(*cls().prompt_styler(text_positive, text_negative, style, log_prompt, style_positive, style_negative))

    def prompt_styler(self, text_positive, text_negative, style, log_prompt, style_positive, style_negative):
        # Process and combine prompts in templates
        # The function replaces the positive prompt placeholder in the template,
        # and combines the negative prompt with the template's negative prompt, if they exist.
        text_positive_styled, text_negative_styled = read_sdxl_templates_replace_and_combine(self.json_data, style, text_positive, text_negative)

        # If style_negative is disabled, set text_negative_styled to text_negative
        if not style_positive:
            text_positive_styled = text_positive
            if log_prompt:
                print(f"style_positive: disabled")

        # If style_negative is disabled, set text_negative_styled to text_negative
        if not style_negative:
            text_negative_styled = text_negative
            if log_prompt:
                print(f"style_negative: disabled")
 
        # If logging is enabled (log_prompt is set to "Yes"), 
        # print the style, positive and negative text, and positive and negative prompts to the console
        if log_prompt:
            print(f"style: {style}")
            print(f"text_positive: {text_positive}")
            print(f"text_negative: {text_negative}")
            print(f"text_positive_styled: {text_positive_styled}")
            print(f"text_negative_styled: {text_negative_styled}")

        return text_positive_styled, text_negative_styled

class SDXLPromptStylerAdvanced(io.ComfyNode):
    SDK_REFS = True
    SDK_PERMISSIONS = ()

    def __init__(self):
        self.json_data = STYLE_DATA

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="SDXLPromptStylerAdvanced", display_name="SDXL Prompt Styler Advanced", category="utils",
            inputs=[io.String.Input("text_positive_g", default="", multiline=True),
                    io.String.Input("text_positive_l", default="", multiline=True),
                    io.String.Input("text_negative", default="", multiline=True),
                    io.Combo.Input("style", options=list(STYLE_NAMES)),
                    io.Combo.Input("negative_prompt_to", options=["Both", "G only", "L only"], default="Both"),
                    io.Boolean.Input("copy_to_l", default=False, label_on="yes", label_off="no"),
                    io.Boolean.Input("log_prompt", default=False, label_on="yes", label_off="no")],
            outputs=[io.String.Output(display_name=name) for name in
                ("text_positive_g", "text_positive_l", "text_positive", "text_negative_g", "text_negative_l", "text_negative")])

    @classmethod
    async def execute(cls, text_positive_g, text_positive_l, text_negative, style, negative_prompt_to, copy_to_l, log_prompt) -> io.NodeOutput:
        return io.NodeOutput(*cls().prompt_styler_advanced(text_positive_g, text_positive_l, text_negative, style, negative_prompt_to, copy_to_l, log_prompt))

    def prompt_styler_advanced(self, text_positive_g, text_positive_l, text_negative, style, negative_prompt_to, copy_to_l, log_prompt):
        # Process and combine prompts in templates
        # The function replaces the positive prompt placeholder in the template,
        # and combines the negative prompt with the template's negative prompt, if they exist.
        text_positive_g_styled, text_positive_l_styled, text_positive_styled, text_negative_g_styled, text_negative_l_styled, text_negative_styled = read_sdxl_templates_replace_and_combine_advanced(self.json_data, style, text_positive_g, text_positive_l, text_negative, negative_prompt_to, copy_to_l)
 
        # If logging is enabled (log_prompt is set to "Yes"), 
        # print the style, positive and negative text, and positive and negative prompts to the console
        if log_prompt:
            print(f"style: {style}")
            print(f"text_positive_g: {text_positive_g}")
            print(f"text_positive_l: {text_positive_l}")
            print(f"text_negative: {text_negative}")
            print(f"text_positive_g_styled: {text_positive_g_styled}")
            print(f"text_positive_l_styled: {text_positive_l_styled}")
            print(f"text_positive_styled: {text_positive_styled}")
            print(f"text_negative_g_styled: {text_negative_g_styled}")
            print(f"text_negative_l_styled: {text_negative_l_styled}")
            print(f"text_negative_styled: {text_negative_styled}")

        return text_positive_g_styled, text_positive_l_styled, text_positive_styled, text_negative_g_styled, text_negative_l_styled, text_negative_styled

NODE_CLASS_MAPPINGS = {
    "SDXLPromptStyler": SDXLPromptStyler,
    "SDXLPromptStylerAdvanced": SDXLPromptStylerAdvanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SDXLPromptStyler": "SDXL Prompt Styler",
    "SDXLPromptStylerAdvanced": "SDXL Prompt Styler Advanced",
}
