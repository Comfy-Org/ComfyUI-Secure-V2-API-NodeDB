import random
import math

from comfy_api.latest import io


class RandomIntegerNodeEfficientAdvanced(io.ComfyNode):
    # Constant for max attempts in Gaussian sampling
    MAX_GAUSSIAN_ATTEMPTS = 100

    @classmethod
    def define_schema(cls) -> io.Schema:
        visible = {"visible": {"on": "maintain_aspect_ratio", "value": True}}
        return io.Schema(
            node_id="RandomIntegerNodeEfficientAdvanced",
            display_name="Advanced Random Integer Generator",
            category="Custom/Random",
            not_idempotent=True,
            inputs=[
                io.Int.Input("min_width", default=256),
                io.Int.Input("max_width", default=1024),
                io.String.Input(
                    "width_divisors", default="64",
                    tooltip="Comma-separated divisors for width",
                ),
                io.Int.Input("min_height", default=256),
                io.Int.Input("max_height", default=1024),
                io.String.Input(
                    "height_divisors", default="64",
                    tooltip="Comma-separated divisors for height",
                ),
                io.Boolean.Input("randomize_width", default=True),
                io.Boolean.Input("randomize_height", default=True),
                io.Boolean.Input("maintain_aspect_ratio", default=False),
                io.Float.Input("aspect_ratio", default=1.0, extra_dict=visible),
                io.Combo.Input(
                    "aspect_ratio_basis", options=["width", "height"],
                    default="width", extra_dict=visible,
                ),
                io.Float.Input(
                    "max_aspect_ratio_deviation", default=10.0,
                    extra_dict=visible,
                ),
                io.Combo.Input(
                    "randomization_type", options=["Uniform", "Gaussian"],
                    default="Uniform",
                ),
                io.Int.Input("gaussian_mean_width", default=512),
                io.Int.Input("gaussian_std_width", default=128),
                io.Int.Input("gaussian_mean_height", default=512),
                io.Int.Input("gaussian_std_height", default=128),
                io.String.Input(
                    "exclude_widths", default="",
                    tooltip="Comma-separated widths to exclude",
                ),
                io.String.Input(
                    "exclude_heights", default="",
                    tooltip="Comma-separated heights to exclude",
                ),
                io.Float.Input(
                    "max_total_megapixels", default=1.0,
                    tooltip="Maximum total megapixels",
                ),
                io.Float.Input(
                    "max_aspect_ratio_any_direction", default=4.0,
                    tooltip="Maximum allowed aspect ratio in any direction",
                ),
            ],
            outputs=[
                io.Int.Output("Width", display_name="Width"),
                io.Int.Output("Height", display_name="Height"),
            ],
        )

    @classmethod
    def execute(
        cls,
        min_width,
        max_width,
        width_divisors,
        min_height,
        max_height,
        height_divisors,
        randomize_width,
        randomize_height,
        maintain_aspect_ratio,
        # (when MAR is on)
        aspect_ratio,
        # (when MAR is on)
        aspect_ratio_basis,
        # (when MAR is on)
        max_aspect_ratio_deviation,
        randomization_type,
        gaussian_mean_width,
        gaussian_std_width,
        gaussian_mean_height,
        gaussian_std_height,
        exclude_widths,
        exclude_heights,
        max_total_megapixels,
        max_aspect_ratio_any_direction,
    ):
        # Convert megapixels to pixels
        max_total_pixels = int(max_total_megapixels * 1_000_000) if max_total_megapixels else None

        # ---------- Helper Functions ----------
        def parse_divisors(divisors_str):
            """Parse and validate divisor strings into a list of integers."""
            try:
                divisors = [int(d.strip()) for d in divisors_str.split(',') if d.strip()]
                if not divisors:
                    raise ValueError("No valid divisors provided.")
                if any(divisor == 0 for divisor in divisors):
                    raise ValueError("Divisors cannot be zero.")
                return divisors
            except ValueError:
                raise ValueError("Divisors must be integers separated by commas.")

        def parse_exclusions(exclusions_str):
            """Parse exclusion strings into a list of integers."""
            try:
                return [int(e.strip()) for e in exclusions_str.split(',') if e.strip()]
            except ValueError:
                raise ValueError("Exclusions must be integers separated by commas.")

        def calculate_valid_multiples(min_val, max_val, divisors, exclusions):
            """Calculate valid multiples within a range based on divisors and exclusions."""
            valid = set()
            for divisor in divisors:
                # Calculate the smallest multiple of divisor >= min_val
                start = min_val if min_val % divisor == 0 else min_val + (divisor - (min_val % divisor))
                # Generate multiples within range
                for val in range(start, max_val + 1, divisor):
                    if val not in exclusions and min_val <= val <= max_val:
                        valid.add(val)
            return sorted(valid)

        def sample_uniform(valid_values):
            """Sample a value uniformly from valid values."""
            if not valid_values:
                return None
            return random.choice(valid_values)

        def sample_gaussian(mean, std, valid_values, min_val, max_val):
            """Sample a value using Gaussian distribution from valid values."""
            if not valid_values:
                return None
            for _ in range(cls.MAX_GAUSSIAN_ATTEMPTS):
                sample = int(random.gauss(mean, std))
                # Clamp sample within range
                sample = max(min_val, min(sample, max_val))
                # Find nearest multiple
                nearest = min_valid_multiple(sample, valid_values)
                if nearest is not None:
                    return nearest
            # Fallback if no valid sample found
            return min(valid_values, key=lambda x: abs(x - mean)) if valid_values else None

        def min_valid_multiple(target, valid_values):
            """Find the closest value in valid_values to target."""
            return min(valid_values, key=lambda x: abs(x - target), default=None)

        def calculate_aspect_ratio(width, height):
            """Calculate the aspect ratio of width to height."""
            if height == 0:
                return float('inf')
            return width / height

        # ---------- Input Validation ----------
        if min_width > max_width:
            raise ValueError("Minimum width cannot be greater than maximum width.")
        if min_height > max_height:
            raise ValueError("Minimum height cannot be greater than maximum height.")
        if aspect_ratio <= 0:
            raise ValueError("Aspect ratio must be a positive number.")
        if max_aspect_ratio_any_direction <= 0:
            raise ValueError("Max aspect ratio in any direction must be positive.")

        # ---------- Parse Divisors and Exclusions ----------
        width_divisors_list = parse_divisors(width_divisors)
        height_divisors_list = parse_divisors(height_divisors)
        exclude_widths_list = parse_exclusions(exclude_widths)
        exclude_heights_list = parse_exclusions(exclude_heights)

        # ---------- Prepare Valid Values ----------
        valid_widths = calculate_valid_multiples(min_width, max_width, width_divisors_list, exclude_widths_list)
        valid_heights = calculate_valid_multiples(min_height, max_height, height_divisors_list, exclude_heights_list)

        # Fallback defaults
        default_width = min_width if min_width in valid_widths else valid_widths[0] if valid_widths else min_width
        default_height = min_height if min_height in valid_heights else valid_heights[0] if valid_heights else min_height

        # ---------- Sampling Functions ----------
        def sample_width():
            """Sample a width value based on the randomization type."""
            if randomization_type == "Uniform":
                return sample_uniform(valid_widths)
            elif randomization_type == "Gaussian":
                return sample_gaussian(gaussian_mean_width, gaussian_std_width, valid_widths, min_width, max_width)
            return None

        def sample_height():
            """Sample a height value based on the randomization type."""
            if randomization_type == "Uniform":
                return sample_uniform(valid_heights)
            elif randomization_type == "Gaussian":
                return sample_gaussian(gaussian_mean_height, gaussian_std_height, valid_heights, min_height, max_height)
            return None

        # ---------- Generate Dimensions ----------
        width = height = None

        try:
            if maintain_aspect_ratio:
                if aspect_ratio_basis == "width":
                    # Randomize or set width
                    width = sample_width() if randomize_width else default_width
                    width = width or default_width  # Ensure width is set

                    # Calculate height based on aspect ratio
                    calculated_height = width / aspect_ratio
                    # Round and snap to valid height
                    calculated_height = int(round(calculated_height))
                    height = min_valid_multiple(calculated_height, valid_heights)
                    if height is None:
                        raise ValueError("No valid height found to maintain aspect ratio.")
                elif aspect_ratio_basis == "height":
                    # Randomize or set height
                    height = sample_height() if randomize_height else default_height
                    height = height or default_height  # Ensure height is set

                    # Calculate width based on aspect ratio
                    calculated_width = height * aspect_ratio
                    # Round and snap to valid width
                    calculated_width = int(round(calculated_width))
                    width = min_valid_multiple(calculated_width, valid_widths)
                    if width is None:
                        raise ValueError("No valid width found to maintain aspect ratio.")
                else:
                    raise ValueError("Invalid aspect_ratio_basis value.")

                # Validate dimensions within min/max ranges
                if not (min_width <= width <= max_width) or not (min_height <= height <= max_height):
                    raise ValueError("Dimensions out of bounds after applying aspect ratio.")

            else:
                # Independently randomize width and height
                width = sample_width() if randomize_width else default_width
                height = sample_height() if randomize_height else default_height
                width = width or default_width  # Ensure width is set
                height = height or default_height  # Ensure height is set

            # Apply Cross-Dimensional Constraints
            # Constraint 1: Total Pixel Area
            if max_total_pixels:
                total_pixels = width * height
                if total_pixels > max_total_pixels:
                    scaling_factor = math.sqrt(max_total_pixels / total_pixels)
                    scaled_width = int(width * scaling_factor)
                    scaled_height = int(height * scaling_factor)

                    # Snap to nearest valid multiples
                    scaled_width = min_valid_multiple(scaled_width, valid_widths) or default_width
                    scaled_height = min_valid_multiple(scaled_height, valid_heights) or default_height

                    width, height = scaled_width, scaled_height

            # Constraint 2: Aspect Ratio Deviation (when MAR is on)
            if maintain_aspect_ratio and max_aspect_ratio_deviation:
                current_aspect = calculate_aspect_ratio(width, height)
                deviation = abs((current_aspect - aspect_ratio) / aspect_ratio) * 100
                if deviation > max_aspect_ratio_deviation:
                    # Adjust dimensions to reduce deviation
                    if aspect_ratio_basis == "width":
                        # Adjust height
                        calculated_height = width / aspect_ratio
                        calculated_height = int(round(calculated_height))
                        height = min_valid_multiple(calculated_height, valid_heights) or height
                    else:
                        # Adjust width
                        calculated_width = height * aspect_ratio
                        calculated_width = int(round(calculated_width))
                        width = min_valid_multiple(calculated_width, valid_widths) or width

            # Constraint 3: Max Aspect Ratio in Any Direction
            if max_aspect_ratio_any_direction:
                aspect_ratio_wh = width / height if width >= height else height / width
                if aspect_ratio_wh > max_aspect_ratio_any_direction:
                    # Adjust dimensions to meet the aspect ratio constraint
                    if width >= height:
                        # Reduce width
                        adjusted_width = height * max_aspect_ratio_any_direction
                        adjusted_width = int(round(adjusted_width))
                        adjusted_width = min_valid_multiple(adjusted_width, valid_widths)
                        if adjusted_width and min_width <= adjusted_width <= max_width:
                            width = adjusted_width
                        else:
                            # As a fallback, set to max allowed width based on aspect ratio
                            width = min_valid_multiple(int(height * max_aspect_ratio_any_direction), valid_widths) or width
                    else:
                        # Reduce height
                        adjusted_height = width * max_aspect_ratio_any_direction
                        adjusted_height = int(round(adjusted_height))
                        adjusted_height = min_valid_multiple(adjusted_height, valid_heights)
                        if adjusted_height and min_height <= adjusted_height <= max_height:
                            height = adjusted_height
                        else:
                            # As a fallback, set to max allowed height based on aspect ratio
                            height = min_valid_multiple(int(width * max_aspect_ratio_any_direction), valid_heights) or height

            # Final Validation
            if width not in valid_widths or height not in valid_heights:
                raise ValueError("Final dimensions are invalid.")

        except ValueError as e:
            # Handle specific exceptions and provide feedback
            print(f"Warning: {e}. Using default dimensions.")
            width = width or default_width
            height = height or default_height

            # Ensure fallback values adhere to constraints
            width = min_valid_multiple(width, valid_widths) or default_width
            height = min_valid_multiple(height, valid_heights) or default_height

        return io.NodeOutput(width, height)
