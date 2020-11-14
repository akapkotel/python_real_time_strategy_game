#!/usr/bin/env python

from typing import Union, Tuple

# typing aliases:
Number = Union[int, float]
Point = Tuple[Number, Number]
GridPosition = SectorId = Tuple[int, int]
FactionId = UnitId = BuildingId = PlayerId = int
Vector2D = Tuple[float, float]
Viewport = Tuple[float, float, float, float]
