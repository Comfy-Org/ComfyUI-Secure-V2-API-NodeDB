"""Forward original parser, rounding, minima, preview and errors unchanged."""
def calculate(resolution, aspect_preset, width_ratio, height_ratio, multiplier):
    from .nodes import Resolution_Calculator_by_Steve_Lasmin
    return Resolution_Calculator_by_Steve_Lasmin().calculate(
        resolution, aspect_preset, width_ratio, height_ratio, multiplier)
