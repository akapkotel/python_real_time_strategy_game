#!/usr/bin/env python

from enum import IntEnum


class TerrainCost(IntEnum):
    ASPHALT = 1
    GROUND = 2
    GRASS = 3
    SAND = 4
    MUD = 5
