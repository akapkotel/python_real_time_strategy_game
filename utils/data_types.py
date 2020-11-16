#!/usr/bin/env python

from typing import Union, Tuple, Dict

# typing aliases:
Number = Union[int, float]
Point = Tuple[Number, Number]
GridPosition = SectorId = Tuple[int, int]
FactionId = UnitId = BuildingId = PlayerId = TechnologyId = int
Vector2D = Tuple[float, float]
Viewport = Tuple[float, float, float, float]
SavedGames = Dict[str, str]
