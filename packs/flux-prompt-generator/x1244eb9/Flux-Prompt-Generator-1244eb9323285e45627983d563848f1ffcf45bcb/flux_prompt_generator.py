# flux_prompt_generator.py
import subprocess
import sys
import random
import json
import os
import re

# --- Installation and JSON Loading (Keep as is) ---
def install_and_import(package):
    try:
        __import__(package)
    except ImportError:
        print(f"Package {package} not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    finally:
        globals()[package] = __import__(package)

def load_json_file(file_name):
    # Add basic error handling for file not found
    file_path = os.path.join(os.path.dirname(__file__), "data", file_name)
    if not os.path.exists(file_path):
        print(f"Warning: JSON file not found at {file_path}. Returning empty list.")
        return []
    try:
        with open(file_path, "r", encoding='utf-8') as file: # Added encoding
            data = json.load(file)

        if isinstance(data, list):
            # Simpler duplicate removal for lists of strings/simple objects
            # If items are dicts, the original method is better, but assumes hashable items after json.dumps
            try:
                data = list(dict.fromkeys(data)) # Faster for simple types
            except TypeError: # Fallback for unhashable types like dicts if json was complex
                 data = list({json.dumps(item, sort_keys=True) for item in data})
                 data = [json.loads(item) for item in data]
        elif isinstance(data, dict):
             # For now, assume lists are expected based on the sample.
             print(f"Warning: Expected a list in {file_name}, but got dict. Using keys or values might be needed.")
             # Example: return list(data.keys()) or list(data.values())
             return [] # Return empty list if structure is unexpected

        return data
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}. Returning empty list.")
        return []
    except Exception as e:
        print(f"Error loading {file_path}: {e}. Returning empty list.")
        return []


# --- Load Data (Keep as is, but consider adding error checks) ---
ARTFORM = load_json_file("artform.json")
ACCESSORIES = load_json_file("accessories.json")
ADDITIONAL_DETAILS = load_json_file("additional_details.json")
AGE_GROUP = load_json_file("age_group.json")
ARTIST = load_json_file("artist.json")
BACKGROUND = load_json_file("background.json")
BODY_MARKINGS = load_json_file("body_markings.json")
BODY_TYPES = load_json_file("body_types.json")
CLOTHING = load_json_file("clothing.json")
COMPOSITION = load_json_file("composition.json")
DEFAULT_TAGS = load_json_file("default_tags.json")
DEVICE = load_json_file("device.json")
DIGITAL_ARTFORM = load_json_file("digital_artform.json")
ETHNICITY = load_json_file("ethnicity.json")
EXPRESSION = load_json_file("expression.json")
EYE_COLORS = load_json_file("eye_colors.json")
FACE_FEATURES = load_json_file("face_features.json")
FACIAL_HAIR = load_json_file("facial_hair.json")
HAIR_COLOR = load_json_file("hair_color.json")
HAIRSTYLES = load_json_file("hairstyles.json")
LIGHTING = load_json_file("lighting.json")
MAKEUP_STYLES = load_json_file("makeup_styles.json")
PHOTO_TYPE = load_json_file("photo_type.json")
PHOTOGRAPHER = load_json_file("photographer.json")
PHOTOGRAPHY_STYLES = load_json_file("photography_styles.json")
PLACE = load_json_file("place.json")
POSE = load_json_file("pose.json")
ROLES = load_json_file("roles.json")
SKIN_TONE = load_json_file("skin_tone.json")
TATTOOS_SCARS = load_json_file("tattoos_scars.json")


# --- Helper Function for Cleaner Joining ---
def smart_join(elements, separator=", "):
    """Joins non-empty elements with a separator."""
    return separator.join(filter(None, elements))

# --- PromptGenerator Class (Refactored) ---
class PromptGenerator:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def _get_choice(self, input_value, default_choices):
        """Internal helper to get a single choice, handling random/disabled."""
        if not default_choices: # Handle empty JSON lists
            return input_value if input_value.lower() not in ["random", "disabled"] else ""

        input_lower = input_value.lower()
        if input_lower == "disabled":
            return ""
        elif "," in input_value: # Allow comma-separated specific choices from user
            choices = [choice.strip() for choice in input_value.split(",")]
            # Return one random choice from the user's list
            return self.rng.choice(choices) if choices else ""
        elif input_lower == "random":
            return self.rng.choice(default_choices)
        else:
            # Return the specific value provided by the user
            return input_value

    def _get_multiple_choices(self, input_value, default_choices, min_count=1, max_count=1):
        """Helper to get multiple choices, useful for things like lighting."""
        if not default_choices:
            return ""

        input_lower = input_value.lower()
        if input_lower == "disabled":
            return ""
        elif "," in input_value: # User provided specific items
             # Use user's specific items directly, joined
             return ", ".join(filter(None, [choice.strip() for choice in input_value.split(",")]))
        elif input_lower == "random":
            count = self.rng.randint(min_count, max_count)
            # Ensure sample size doesn't exceed population size
            actual_count = min(count, len(default_choices))
            if actual_count == 0: return "" # Handle case where default_choices is empty
            chosen = self.rng.sample(default_choices, actual_count)
            return ", ".join(chosen)
        else:
            # Specific single value chosen
            return input_value

    def clean_prompt_string(self, text):
        """Cleans up common prompt string issues."""
        if not text: return ""
        # Remove extra spaces around commas, then replace multiple commas with one
        text = re.sub(r'\s*,\s*', ', ', text)
        text = re.sub(r',+', ',', text)
        # Remove leading/trailing commas and spaces
        text = text.strip(', ')
        # Remove spaces before BREAK markers
        text = re.sub(r'\s+(BREAK_CLIP[GL])', r' \1', text)
         # Remove spaces after BREAK markers
        text = re.sub(r'(BREAK_CLIP[GL])\s+', r'\1 ', text)
        # Replace multiple spaces with a single space
        text = re.sub(r'\s+', ' ', text).strip()
        # Specific cleanup like 'of a as' -> 'of a' etc.
        text = text.replace(" of as ", " of ") # Check variations if needed
        text = text.replace(" a as ", " as ") # Example
        # Remove empty segments like ", ," or leading ", " after splits
        text = re.sub(r'^,\s*', '', text)
        text = re.sub(r'\s*,\s*$', '', text)
        text = re.sub(r',(\s*,)+', ',', text)
        return text

    def process_string_v2(self, combined_prompt, seed):
        """Uses regex to split the prompt based on BREAK markers."""
        clip_l_content = ""
        clip_g_content = ""
        t5xxl_content = combined_prompt # Start with full prompt for T5

        # Extract CLIP L content
        match_l = re.search(r'BREAK_CLIPL(.*?)BREAK_CLIPL', combined_prompt, re.DOTALL)
        if match_l:
            clip_l_content = match_l.group(1).strip()
            # Remove CLIP L block from T5
            t5xxl_content = t5xxl_content.replace(match_l.group(0), '', 1)

        # Extract CLIP G content
        match_g = re.search(r'BREAK_CLIPG(.*?)BREAK_CLIPG', combined_prompt, re.DOTALL)
        if match_g:
            clip_g_content = match_g.group(1).strip()
             # Remove CLIP G block from T5
            t5xxl_content = t5xxl_content.replace(match_g.group(0), '', 1)

        # Original prompt is T5 content with markers removed
        original_content = t5xxl_content.replace('BREAK_CLIPL', '').replace('BREAK_CLIPG', '')

        # Clean all parts
        original_clean = self.clean_prompt_string(original_content)
        t5xxl_clean = self.clean_prompt_string(t5xxl_content)
        clip_l_clean = self.clean_prompt_string(clip_l_content)
        clip_g_clean = self.clean_prompt_string(clip_g_content)

        return original_clean, seed, t5xxl_clean, clip_l_clean, clip_g_clean

    def generate_prompt(self, seed, **kwargs):
        # Use kwargs directly, simplifies passing arguments
        self.rng = random.Random(seed) # Re-seed for each generation if seed changes

        components = []

        # --- 1. Custom Prompt ---
        custom = kwargs.get("custom", "")
        if custom:
            components.append(custom)

        # --- 2. Artform / Style Lead-in ---
        artform = self._get_choice(kwargs.get("artform", "disabled"), ARTFORM)
        is_photographer = (artform.lower() == "photography")

        if is_photographer:
            photo_style = self._get_choice(kwargs.get("photography_styles", "random"), PHOTOGRAPHY_STYLES)
            if photo_style:
                components.append(photo_style)
            else:
                 # Fallback if random selects nothing or style is disabled
                 components.append("photography") # Default base style
            # Add "of" if a subject or default tag will follow
            if kwargs.get("subject") or kwargs.get("default_tags", "disabled").lower() != "disabled":
                 components.append("of") # Add connector word

        elif artform and artform.lower() != "disabled":
             components.append(artform)
             # Add "of" if a subject or default tag will follow and artform isn't inherently descriptive like 'illustration'
             if kwargs.get("subject") or kwargs.get("default_tags", "disabled").lower() != "disabled":
                 # Could refine this list if needed
                 if artform.lower() not in ["illustration", "painting", "drawing", "sketch"]:
                     components.append("of")

        # --- 3. Subject Definition ---
        subject = kwargs.get("subject", "")
        default_tags_input = kwargs.get("default_tags", "random")
        body_type_input = kwargs.get("body_types", "random")

        chosen_subject_elements = []
        if subject: # User provided subject takes precedence
            chosen_body_type = self._get_choice(body_type_input, BODY_TYPES)
            if chosen_body_type:
                 chosen_subject_elements.extend(["a", chosen_body_type]) # e.g., "a muscular"
            chosen_subject_elements.append(subject) # e.g., "a muscular woman"
        else: # No specific subject, use default tags
            chosen_default_tag = self._get_choice(default_tags_input, DEFAULT_TAGS)
            if chosen_default_tag: # Only proceed if default tag isn't disabled/empty
                chosen_body_type = self._get_choice(body_type_input, BODY_TYPES)
                # Check if tag starts with a/an, handle body type insertion
                starts_with_article = chosen_default_tag.lower().startswith(("a ", "an "))
                if chosen_body_type:
                    if starts_with_article:
                        # Insert body type after article: "a muscular woman"
                        parts = chosen_default_tag.split(" ", 1)
                        chosen_subject_elements.extend([parts[0], chosen_body_type, parts[1]])
                    else:
                        # Prepend "a" and body type: "a muscular subject"
                         chosen_subject_elements.extend(["a", chosen_body_type, chosen_default_tag])
                else:
                    # Just use the default tag
                     chosen_subject_elements.append(chosen_default_tag)

        if chosen_subject_elements:
            components.append(" ".join(chosen_subject_elements))

        # Store chosen tag for gender check later
        resolved_subject_desc = " ".join(chosen_subject_elements).lower()

        # --- 4. Core Details (Roles, Hairstyles, Additional Details) ---
        core_details = [
            self._get_choice(kwargs.get("roles", "random"), ROLES),
            self._get_choice(kwargs.get("hairstyles", "random"), HAIRSTYLES),
            self._get_choice(kwargs.get("additional_details", "random"), ADDITIONAL_DETAILS),
        ]
        components.append(smart_join(core_details))

        # --- 5. Clothing ---
        clothing = self._get_choice(kwargs.get("clothing", "random"), CLOTHING)
        if clothing:
            components.append(f"dressed in {clothing}")

        # --- 6. Composition & Pose ---
        comp_pose = [
            self._get_choice(kwargs.get("composition", "random"), COMPOSITION),
            self._get_choice(kwargs.get("pose", "random"), POSE),
        ]
        components.append(smart_join(comp_pose))

        # --- BREAK CLIP G 1 ---
        components.append("BREAK_CLIPG")

        # --- 7. Environment (Background, Place) ---
        environment = [
             self._get_choice(kwargs.get("background", "random"), BACKGROUND),
             self._get_choice(kwargs.get("place", "random"), PLACE),
        ]
        components.append(smart_join(environment))


        # --- 8. Lighting ---
        # Use multi-choice helper for lighting if random
        lighting_input = kwargs.get("lighting", "random")
        if lighting_input.lower() == "random":
             lighting = self._get_multiple_choices(lighting_input, LIGHTING, min_count=2, max_count=4) # Example: 2-4 items
        else:
             lighting = self._get_choice(lighting_input, LIGHTING)

        if lighting:
            components.append(lighting)


        # --- BREAK CLIP G 2 ---
        components.append("BREAK_CLIPG")

        # --- 9. Physical Features ---
        features = [
            self._get_choice(kwargs.get("face_features", "random"), FACE_FEATURES),
            self._get_choice(kwargs.get("eye_colors", "random"), EYE_COLORS),
            self._get_choice(kwargs.get("skin_tone", "random"), SKIN_TONE),
            self._get_choice(kwargs.get("age_group", "random"), AGE_GROUP),
            self._get_choice(kwargs.get("ethnicity", "random"), ETHNICITY),
            self._get_choice(kwargs.get("accessories", "random"), ACCESSORIES),
            self._get_choice(kwargs.get("expression", "random"), EXPRESSION),
            self._get_choice(kwargs.get("tattoos_scars", "random"), TATTOOS_SCARS),
            self._get_choice(kwargs.get("hair_color", "random"), HAIR_COLOR),
            self._get_choice(kwargs.get("body_markings", "random"), BODY_MARKINGS),
        ]
         # Conditional additions based on resolved subject/tag
        if "man" in resolved_subject_desc or "male" in resolved_subject_desc:
            features.append(self._get_choice(kwargs.get("facial_hair", "random"), FACIAL_HAIR))
        if "woman" in resolved_subject_desc or "female" in resolved_subject_desc:
             features.append(self._get_choice(kwargs.get("makeup_styles", "random"), MAKEUP_STYLES))

        components.append(smart_join(features))


        # --- BREAK CLIP L 1 ---
        components.append("BREAK_CLIPL")

        # --- 10. Technical/Artistic Details ---
        tech_artist_details = []
        if is_photographer:
            photo_type = self._get_choice(kwargs.get("photo_type", "random"), PHOTO_TYPE)
            if photo_type:
                # Apply random weight only if a specific photo type is chosen or randomly selected
                random_value = round(self.rng.uniform(1.1, 1.5), 1)
                tech_artist_details.append(f"({photo_type}:{random_value})")

            device = self._get_choice(kwargs.get("device", "random"), DEVICE)
            if device:
                tech_artist_details.append(f"shot on {device}")

            photographer = self._get_choice(kwargs.get("photographer", "random"), PHOTOGRAPHER)
            if photographer:
                tech_artist_details.append(f"photo by {photographer}")
        else:
            # Non-photographer artform
            digital_artform = self._get_choice(kwargs.get("digital_artform", "random"), DIGITAL_ARTFORM)
            if digital_artform:
                 tech_artist_details.append(digital_artform)

            artist = self._get_choice(kwargs.get("artist", "random"), ARTIST)
            if artist:
                tech_artist_details.append(f"by {artist}")

        components.append(smart_join(tech_artist_details))

        # --- BREAK CLIP L 2 ---
        components.append("BREAK_CLIPL")

        # --- Final Assembly & Processing ---
        # Join all collected components, using smart_join to handle potential empty strings between sections
        full_prompt_string = smart_join(components, separator=" ")

        # Process using the V2 splitter
        return self.process_string_v2(full_prompt_string, seed)


# --- ComfyUI Node Class (Updated RETURN_TYPES) ---
class FluxPromptGenerator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": random.randint(0, 30000), "min": 0, "max": 30000, "step": 1}),
                "custom": ("STRING", {"multiline": True, "default": ""}),
                "subject": ("STRING", {"multiline": True, "default": ""}),
                "accessories": (["disabled", "random"] + ACCESSORIES, {"default": "disabled"}),
                "additional_details": (["disabled", "random"] + ADDITIONAL_DETAILS, {"default": "disabled"}),
                "age_group": (["disabled", "random"] + AGE_GROUP, {"default": "disabled"}),
                "artform": (["disabled", "random"] + ARTFORM, {"default": "disabled"}),
                "artist": (["disabled", "random"] + ARTIST, {"default": "disabled"}),
                "background": (["disabled", "random"] + BACKGROUND, {"default": "disabled"}),
                "body_markings": (["disabled", "random"] + BODY_MARKINGS, {"default": "disabled"}),
                "body_types": (["disabled", "random"] + BODY_TYPES, {"default": "disabled"}),
                "clothing": (["disabled", "random"] + CLOTHING, {"default": "disabled"}),
                "composition": (["disabled", "random"] + COMPOSITION, {"default": "disabled"}),
                "default_tags": (["disabled", "random"] + DEFAULT_TAGS, {"default": "disabled"}),
                "device": (["disabled", "random"] + DEVICE, {"default": "disabled"}),
                "digital_artform": (["disabled", "random"] + DIGITAL_ARTFORM, {"default": "disabled"}),
                "ethnicity": (["disabled", "random"] + ETHNICITY, {"default": "disabled"}),
                "expression": (["disabled", "random"] + EXPRESSION, {"default": "disabled"}),
                "eye_colors": (["disabled", "random"] + EYE_COLORS, {"default": "disabled"}),
                "face_features": (["disabled", "random"] + FACE_FEATURES, {"default": "disabled"}),
                "facial_hair": (["disabled", "random"] + FACIAL_HAIR, {"default": "disabled"}),
                "hair_color": (["disabled", "random"] + HAIR_COLOR, {"default": "disabled"}),
                "hairstyles": (["disabled", "random"] + HAIRSTYLES, {"default": "disabled"}),
                "lighting": (["disabled", "random"] + LIGHTING, {"default": "disabled"}),
                "makeup_styles": (["disabled", "random"] + MAKEUP_STYLES, {"default": "disabled"}),
                "photographer": (["disabled", "random"] + PHOTOGRAPHER, {"default": "disabled"}),
                "photography_styles": (["disabled", "random"] + PHOTOGRAPHY_STYLES, {"default": "disabled"}),
                "photo_type": (["disabled", "random"] + PHOTO_TYPE, {"default": "disabled"}),
                "place": (["disabled", "random"] + PLACE, {"default": "disabled"}),
                "pose": (["disabled", "random"] + POSE, {"default": "disabled"}),
                "roles": (["disabled", "random"] + ROLES, {"default": "disabled"}),
                "skin_tone": (["disabled", "random"] + SKIN_TONE, {"default": "disabled"}),
                "tattoos_scars": (["disabled", "random"] + TATTOOS_SCARS, {"default": "disabled"}),
            }
        }

    # Correct RETURN_TYPES and add RETURN_NAMES
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)

    FUNCTION = "execute"
    CATEGORY = "Prompt"

    def execute(self, **kwargs):
        # Pass all arguments using kwargs
        seed = kwargs.get('seed', 0) # Extract seed separately if needed elsewhere
        prompt_generator = PromptGenerator(seed)
        prompt = prompt_generator.generate_prompt(**kwargs)
        # Return the generated prompt as a single string
        # Note: If you want to return multiple values, you can adjust RETURN_TYPES and RETURN_NAMES accordingly
        return (prompt)

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Trigger refresh based on seed or any other input change
        # Simple approach: always return True if any input changes (including seed)
        # You could implement more complex logic comparing old/new kwargs if needed
        return float('nan') # Standard ComfyUI way to indicate always refresh


# Node export details
NODE_CLASS_MAPPINGS = {"FluxPromptGenerator": FluxPromptGenerator}
NODE_DISPLAY_NAME_MAPPINGS = {"FluxPromptGenerator": "Flux Prompt Generator"}