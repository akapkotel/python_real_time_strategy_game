#!/usr/bin/env python

from enum import IntEnum


class UnitWeight(IntEnum):
    """
    Each Unit can demolish GameObjects it encounters when entering a MapTile.
    Unit can destroy only objects with robustness lower than it's weight.
    """
    INFANTRY = 0
    LIGHT = 1
    MEDIUM = 2
    HEAVY = 3


class Robustness(IntEnum):
    """
    When GameObject occupies a MapTile, it can block it (mak it not-walkable).
    But if heavy-enough Unit try to enter the tile, it can destroy an object if
    only its UnitWeight is equal or larger than object's robustness.
    """
    LIGHT = 1  # light, wheeled vehicles
    MEDIUM = 2  # light, tracked vehicles
    HEAVY = 3  # only heavy, tracked vehicles
    INDESTRUCTIBLE = 4  # no Unit can ever destroy this object


class TerrainCost(IntEnum):
    ASPHALT = 1
    GROUND = 1.25
    GRASS = 1.5
    SAND = 1.75
    MUD = 2
    SWAMP = 3
