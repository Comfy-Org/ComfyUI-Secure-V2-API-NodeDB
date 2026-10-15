import re

class ShowAnyTextInCMDconsoleSG:
    
    # Standard ANSI colors for the dropdown list
    STANDARD_COLORS = {
        "RESET": "\033[0m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "black": "\033[90m"
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "forceInput": True, 
                }),
                
                "show_any_text_in_console": ("BOOLEAN", {
                    "default": True, 
                    "tooltip": "Toggle to enable or disable printing text to the command line."
                }),
                
                "color_preset": (["white", "red", "green", "yellow", "blue", "magenta", "cyan", "black"], {
                    "tooltip": "Quickly select a standard console color from this list.\n❗Does not work if Hex color is entered below"
                }),
                
                "hex_color": ("STRING", {
                    "default": "", 
                    "multiline": False,
                    "tooltip": "Enter a Hex Code (e.g., #FF0055) (Over Rides the list))\n❗Leave empty to use the dropdown list.\ncheck color codes at https://www.color-hex.com/"
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "display_text"
    OUTPUT_NODE = True
    CATEGORY = "utils"

    def display_text(self, text, show_any_text_in_console, color_preset="white", hex_color=""):
        # Only print to console if the switch is True
        if show_any_text_in_console:
            
            # 1. Determine the color code
            final_color_code = self.STANDARD_COLORS.get(color_preset, self.STANDARD_COLORS["white"])
            
            # 2. Check if a Hex Code was provided (overrides preset)
            if hex_color and len(hex_color.strip()) > 0:
                hex_ansi = self.hex_to_ansi(hex_color)
                if hex_ansi:
                    final_color_code = hex_ansi
            
            reset_code = self.STANDARD_COLORS["RESET"]
            
            # 3. Print with the determined color
            print(f"\n=====> Show Any Text In CMD console-SG =====>\n")
            print(f"{final_color_code}{text}{reset_code}")
            print(f"\n--------------------------------------------\n")

        # Return both UI display and output for next node
        return {
            "ui": {"text": [text]},
            "result": (text,)
        }

    def hex_to_ansi(self, hex_str):
        """Converts a hex string (e.g., '#FF0000' or 'FF0000') to an ANSI TrueColor escape sequence."""
        try:
            # Clean string
            hex_str = hex_str.strip().lstrip("#")
            
            # Check length (must be 6 chars)
            if len(hex_str) != 6:
                return None
                
            # Parse RGB
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            
            # Return ANSI TrueColor sequence: \033[38;2;R;G;Bm
            return f"\033[38;2;{r};{g};{b}m"
        except ValueError:
            return None

# Node registration
NODE_CLASS_MAPPINGS = {
    "ShowAnyTextInCMDconsoleSG": ShowAnyTextInCMDconsoleSG,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ShowAnyTextInCMDconsoleSG": "Show Any Text In CMD console-SG",
}
