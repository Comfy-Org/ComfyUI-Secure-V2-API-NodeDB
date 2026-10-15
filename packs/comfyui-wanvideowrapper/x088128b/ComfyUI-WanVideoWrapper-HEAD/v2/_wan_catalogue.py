"""Logical catalogue-name validation without host I/O or broker calls."""
def valid_catalogue_name(value):
    return (isinstance(value, str) and bool(value) and len(value.encode("utf-8")) <= 4096
            and not any(character in value for character in ("\x00", "\\", ":"))
            and all(part not in ("", ".", "..") for part in value.split("/")))
