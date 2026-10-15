"""
File    : predefined_palettes.py
Purpose : Provides access to all predefined palettes through the `PREDEFINED_PALETTES` object
Author  : Martin Rizzo | <martinrizzo@gmail.com>
Date    : May 29, 2026
Repo    : https://github.com/martin-rizzo/ComfyUI-ZImagePowerNodes
License : MIT
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
                          ComfyUI-ZImagePowerNodes
         ComfyUI nodes designed specifically for the "Z-Image" model.
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
"""
import re
from typing          import Final
from pathlib         import Path
from collections     import defaultdict
from ..core.palette  import Palette, PaletteSet
from ..core.helpers  import get_project_root
from ..core.system   import logger
VersionTuple = tuple[int, int, int]


#=========================== PredefinedPalettes ============================#
class PredefinedPalettes:
    """
    A central repository that stores every registered Palette object.

    Palettes are internally grouped by version, and callers can obtain a
    `PaletteSet` that contains only palettes belonging to a specific release.
    """

    # Constant used to identify valid palette configuration files.
    # Any configuration file that does not start with this string is ignored.
    FILE_IDENTIFIER = b"@PALETTES"

    def __init__(self) -> None:
        self._palettes_by_versiontup: dict[VersionTuple, PaletteSet] = defaultdict(PaletteSet)


    def load_from_directory(self, directory: Path | str) -> tuple[int, int]:
        """
        Load palette definitions from all palette config files in the give directory.

        This method searches the given directory for text files that start with
        the "@PALETTES" identifier. For each matching file, the method extracts
        the palette definitions and adds them to the internal collection. It
        returns a tuple containing the number of files processed and the total
        number of palettes loaded.

        Args:
            directory: Path to the directory containing palette files.
        Returns:
            A tuple of (number of files processed, total palettes loaded).
        """
        loaded_files     = 0
        total_palettes   = 0
        for path in Path(directory).iterdir():
            if not path.is_file():
                continue
            try:
                # read the identifier and check if it's a palette file
                with open(path, "rb") as f:
                    header = f.read(len(self.FILE_IDENTIFIER))
                if header != self.FILE_IDENTIFIER:
                    continue

                # extract version from file name and read the content
                parts   = path.stem.replace('.','-').replace('_','-').split('-')
                version = next((p for p in parts if re.match(r"^v\d+$", p)), "v0")
                content = path.read_text(encoding='utf-8')

                # load the palettes
                total_palettes += self.add_palettes_from_string(content, version=version)
                loaded_files   += 1

            except (OSError, IOError) as e:
                logger.warning(f"Could not process file {path.name}: {e}")

        return loaded_files, total_palettes


    def add_palettes_from_string(self,
                                 string: str,
                                 /, *,
                                 version: str | tuple[int,int,int] = "0.0.0",
                                 ) -> int:
        """
        Adds all palettes found in a configuration string.

        For more information about the input string format,
        refer to `PaletteSet.add_palettes_from_string()`.
        Args:
            string  : The input string containing palette definitions.
            version : Default version assigned to palettes that do not specify one.
        Returns:
            The number of palettes successfully added.
        """
        palettes = PaletteSet.from_string(string, version=version)
        return self.add_palettes(palettes)


    def add_palettes(self, palettes: PaletteSet | list[Palette]) -> int:
        """Bulk-register palettes and return the count of successfully added items."""
        return sum(1 for p in palettes if self.add_palette(p))


    def add_palette(self, palette: Palette) -> bool:
        """Add a single Palette to the library."""
        return self._palettes_by_versiontup[palette.version_tuple].add_palette(palette)


    def by_version(self, version: str | VersionTuple) -> PaletteSet:
        """Return the full PaletteSet for a specific version (or empty set when not found)."""
        versiontup = Palette.make_version_tuple(version) if isinstance(version, str) else version
        return self._palettes_by_versiontup.get(versiontup, PaletteSet())


    def versions(self) -> list[str]:
        """Return a list of all versions currently in the library."""
        return [ ".".join(map(str, vertion_tuple)) for vertion_tuple in self._palettes_by_versiontup ]

    def __len__(self) -> int:
        """Return the total number of palettes stored."""
        return sum( len(palettes) for palettes in self._palettes_by_versiontup.values() )

    def __repr__(self) -> str:
        """
        Return a string representation of the `PredefinedPalettes` instance,
        displaying versions and their respective palette counts in a structured format.
        """
        items = []
        for versiontup, palettes in self._palettes_by_versiontup.items():
            version = ".".join(map(str, versiontup))
            items.append(f"  {{ version: {version}, palette_count: {len(palettes)} }}")
        joined_items = ",\n".join(items)
        return f"PredefinedPalettes({{\n{joined_items}\n}})"


#====================== 'PREDEFINED_PALETTES' OBJECT =======================#
#                global instance of the predefined palettes                 #

PREDEFINED_PALETTES: Final = PredefinedPalettes()
PREDEFINED_PALETTES.load_from_directory( get_project_root() / "styles" )

