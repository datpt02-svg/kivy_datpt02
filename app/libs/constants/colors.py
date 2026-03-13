"""
Color Definitions Module

This module defines common color constants used throughout the Kivy UI,
organized in the `Colors` enumeration. It provides both hexadecimal
and RGBA formats and a helper class (`ColorsClass`) for convenient
lookup and retrieval by name.

It depends on:
    - `kivy.utils.get_color_from_hex` for converting hex → RGBA.
    - `kivy.logger.Logger` for fallback warnings.
"""

from enum import Enum

from kivy.logger import Logger
from kivy.utils import get_color_from_hex


class Colors(Enum):
    """COMMON COLORS"""
    # Blues
    BLUE = "#3498DB"
    LIGHT_BLUE = "#3399FF"
    PALE_BLUE = "#D6EAF8"
    ALICE_BLUE = "#F0F8FF"
    SKY_BLUE = "#228BE6"
    DARK_BLUE = "#233240"
    # Reds
    RED = "#E74C3C"
    LIGHT_RED = "#FF4136"
    DARK_RED = "#CC0000"
    # Greens
    GREEN = "#28A745"
    LIGHT_GREEN= "#2ECC70"
    CYAN = "#1ABC9C"
    # Darks
    BLACK = "#1D1D1D"
    MEDIUM_BLACK = "#333333"
    LIGHT_BLACK = "#7F8C8D"
    BLUE_BLACK = "#2C3E50"
    MEDIUM_GRAY = "#555555FF"
    LIGHT_BLUE_GRAY = '#BDC3C7'
    LIGHT_GRAY = "#CCCCCC"
    VERY_LIGHT_GRAY = "#DDDDDD"
    WHITE_GRAY = "#EEEEEE"
    GRAY_TRANSPARENT=  "#00000033"
    BLUE_GRAY = "#233240"
    # Whites / Near-Whites
    WHITE = "#FFFFFF"
    ALMOST_WHITE = "#FCFCFC"
    WHITE_SMOKE = "#F9F9F9"
    DOVE_WHITE = "#F0F0F0"
    DARK_DOVE_WHITE = "#bababa"
    WHITE_BLUE = "#ECF0F1"
    WHITE_TRANSPARENT = "#FFFFFF99"
    WHITE_SEMI_TRANSPARENT = "#FFFFFFB3"
    TRANSPARENT = "#00000000"

    #Yellow
    YELLOW = "#FFFF00"

    """CUSTOM COLORS"""
    #Menu
    MENU_SECTION_LINE = '#3b5168'
    #DataTable
    DATA_TABLE_BACKGROUND = '#ECEEF1FF'
    #PaginationButton
    PAGINATION_TEXT_DISABLED = '#808080'
    PAGINATION_BG_DISABLED = '#E9ECEF'
    PAGINATION_BORDER_DISABLED = '#ced4da'
    PAGINATION_BORDER_NORMAL = '#dee2e6'
    #ImageFrame
    IMAGE_FRAME_BACKGROUND = '#E9ECEF'
    #MyPopup
    MYPOPUP_BACKGROUND = '#F7F7F7'

    @property
    def rgba(self):
        """Return the RGBA color value converted from hexadecimal."""
        return get_color_from_hex(self.value)

    @property
    def hex(self):
        """Return the hexadecimal color value."""
        return self.value


class ColorsClass:
    """Helper class for accessing color values from the Colors enum by name."""

    def get(self, name, color_format="rgba"):
        """Get a color value by name from the Colors enum.

        Args:
            name: The name of the color from the Colors enum.
            color_format: The format to return the color in ('rgba' or 'hex'). Defaults to 'rgba'.

        Returns:
            The color value in the specified format. Returns RGBA format by default.
            Falls back to LIGHT_BLACK in RGBA format if the color name is not found.
        """
        try:
            color = Colors[name]
            if color_format == "rgba":
                return color.rgba
            if color_format == "hex":
                return color.hex
            Logger.warning(
                "Invalid format '%s'. Using rgba as fallback.",
                color_format
            )
            return color.rgba
        except KeyError:
            Logger.warning(
                "Color '%s' not found. Using LIGHT_BLACK as fallback.",
                name
            )
            return Colors.LIGHT_BLACK.rgba

    def __getitem__(self, name):
        return self.get(name, 'rgba')

COLORS = ColorsClass()
