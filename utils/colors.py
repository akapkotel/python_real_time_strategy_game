#!/usr/bin/env python

from arcade.arcade_types import Color, RGB, RGBA
from arcade.color import SAND as ARCADE_SAND

from utils.geometry import clamp


# RGBA colors:
RED: Color = (255, 0, 0, 255)
GREEN: Color = (0, 255, 0, 255)
BLUE: Color = (0, 0, 255, 255)
CLEAR_GREEN: Color = (0, 255, 0, 25)
MAP_GREEN: Color = (141, 182, 0, 255)
GRASS_GREEN: Color = (85, 107, 47, 255)
BROWN: Color = (165, 42, 42, 266)
YELLOW: Color = (255, 255, 0, 255)
SUN: Color = (255, 255, 224, 255)
SAND: Color = ARCADE_SAND
WHITE: Color = (255, 255, 255, 255)
DARK: Color = (32, 32, 32, 255)
LIGHT: Color = (192, 192, 192, 255)
FOG: Color = (32, 32, 32, 128)
GREY: Color = (128, 128, 128, 255)
BLACK: Color = (0, 0, 0, 255)
SHADOW: Color = (169, 169, 169, 255)
PLAYER_COLOR: Color = (18, 97, 128, 255)
CPU_COLOR: Color = (212, 0, 0, 255)
CIV_COLOR: Color = (250, 218, 94, 255)
AMBIENT_COLOR: Color = (125, 125, 75, 255)
NO_FOV_COLOR: Color = (0, 0, 0, 255)
TRANSPARENT: Color = (0, 0, 0, 0)


colors_names = {
    GREEN: 'green', RED: 'red', YELLOW: 'yellow', BLUE: 'blue'
}


def rgb_to_rgba(color: RGB, alpha: int) -> RGBA:
    return color[0], color[1], color[2], clamp(alpha, 255, 0)
