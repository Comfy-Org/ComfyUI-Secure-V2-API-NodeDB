"""
File    : predefined_styles.py
Purpose : Provides access to all predefined styles through the `PREDEFINED_STYLES` object
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : Apr 30, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
from typing          import Final
from pathlib         import Path
from collections     import defaultdict
from ..core.style    import Style, StyleSet
from ..core.helpers  import get_project_root
from ..core.system   import logger
VersionTuple = tuple[int, int, int]


#============================== StyleLibrary ===============================#
#             this class represents the full style library                  #

class StyleLibrary:
    """
    A central repository that stores every registered Style object.

    Styles are internally grouped by version, and callers can obtain a `StyleSet`
    that contains only targets belonging to a specific release.
    """

    # Constant used to identify valid style configuration files.
    # Any configuration file that does not start with this string is ignored.
    FILE_IDENTIFIER = b"@STYLES"

    def __init__(self) -> None:
        self._styles_by_versiontup: dict[VersionTuple, StyleSet] = defaultdict(StyleSet)


    def load_from_directory(self,
                            directory: Path | str
                            ) -> tuple[int, int]:
        """
        Load style definitions from all compatible files within a directory.

        This method scans the specified directory for text files whose names
        follow the naming convention `styles_<version>_<category>.txt` (e.g.,
        "styles_v1_illustration.txt"). Each matching file is parsed and its
        styles are added to the library under the extracted category and version.

        Args:
            directory: Path to the directory containing style definition files.
                       Can be a `str` or `pathlib.Path`.
        Returns:
            A tuple containing:
                - The number of files that were successfully processed.
                - The total number of styles loaded from those files.
        """
        loaded_files  = 0
        total_styles = 0
        for path in Path(directory).iterdir():
            if not path.is_file():
                continue
            try:
                # read the identifier and check if it's a style definition file
                with open(path, "rb") as f:
                    header = f.read(len(self.FILE_IDENTIFIER))
                if header != self.FILE_IDENTIFIER:
                    continue

                name_parts = path.stem.replace('.','-').replace('_','-').split('-')
                if len(name_parts) < 3 or name_parts[0] != 'styles' or not name_parts[1].startswith('v'):
                    logger.warning(f"Invalid style filename: {path.name}")
                    continue

                # extract version and category from the file name
                version  = _normalize_version( name_parts[1].strip() )
                category = name_parts[2].strip().rstrip("0123456789")
                content  = path.read_text(encoding='utf-8')

                if version and category:
                    loaded_files += 1
                    total_styles += self.add_styles_from_string(content, category=category, version=version)

            except (OSError, IOError) as e:
                logger.warning(f"Could not process file {path.name}: {e}")

        return loaded_files, total_styles


    def add_styles_from_string(self,
                               string : str,
                               /,*,
                               category : str                = "",
                               version  : str | VersionTuple = (0,0,0),
                               ) -> int:
        """
        Adds all styles found in a configuration string.

        For more information about the input string format,
        refer to `StyleSet.add_styles_from_string()`.
        Args:
            string  : The input string containing style definitions to be loaded.
            category: Default category assigned to styles that do not specify one.
            version : Default version assigned to styles that do not specify one.
        Returns:
            The number of styles successfully added.
        """
        styles = StyleSet.from_string(string, category=category, version=version)
        return self.add_styles( styles )


    def add_styles(self, styles: StyleSet | list[Style]) -> int:
        """Bulk-register styles and return the count of successfully added items."""
        return sum(1 for s in styles if self.add_style(s))


    def add_style(self, style: Style) -> bool:
        """Add a Style into the library."""
        return self._styles_by_versiontup[style.version_tuple].add_style(style)


    def by_version(self, version: str | VersionTuple) -> StyleSet:
        """Return the full StyleSet for a specific version (or empty set when not found)."""
        versiontup = Style.make_version_tuple(version) if isinstance(version, str) else version
        return self._styles_by_versiontup.get(versiontup, StyleSet())


    def versions(self) -> list[str]:
        """Return a list of all versions currently in the library."""
        return [ ".".join(map(str, version_tuple)) for version_tuple in self._styles_by_versiontup.keys() ]

    def __len__(self) -> int:
        """Returns the number of styles currently stored inside the library."""
        return sum( len(styles) for styles in self._styles_by_versiontup.values() )

    def __repr__(self) -> str:
        """
        Return a string representation of the `StyleLibrary` instance,
        displaying versions and their respective style counts in a structured format.
        """
        items = []
        for versiontup, styles in self._styles_by_versiontup.items():
            version = ".".join(map(str, versiontup))
            items.append(f"  {{ version: {version}, style_count: {len(styles)} }}")
        joined_items = ",\n".join(items)
        return f"StyleLibrary({{\n{joined_items}\n}})"





#================================= HELPERS =================================#

def _normalize_version(version_str: str) -> str:
    """
    Convert a compact version string to standard semver format (X.Y.Z).

    Args:
        version_str: A string starting with 'v' followed by digits.
                     Examples: 'v08', 'v1', 'v201', 'V42'
    Returns:
        A version string with exactly 3 components, padded with zeros if needed.
        Examples: '0.8.0', '1.0.0', '2.0.1', '4.2.0'
        Returns an empty string if the input doesn't start with 'v' or 'V'.
    """
    # Return empty string if it doesn't start with 'v' or 'V'
    if not version_str or (version_str[0] != 'v' and version_str[0] != 'V'):
        return ''

    # remove the leading 'v' (case insensitive)
    version_part = version_str.lstrip('vV')

    # extract all digits from the remaining string
    # and pad with zeros to ensure exactly 3 components
    digits = [c for c in version_part if c.isdigit()]
    if len(digits) < 3:
        digits.extend(['0', '0', '0'])

    # take only the first 3 digits
    return '.'.join(digits[:3])


#======================= 'PREDEFINED_STYLES' OBJECT ========================#
#                 global instance of the predefined styles                  #

PREDEFINED_STYLES: Final = StyleLibrary()
PREDEFINED_STYLES.load_from_directory( get_project_root() / "styles" )
