#!/usr/bin/env python
from __future__ import annotations

from functools import wraps
from typing import Optional, Tuple, List, Set, Dict

from data_containers import PriorityQueue
from gameobject import GameObject
from buildings import Building
from units import Unit, UnitWeight
from game import Game


TILE_WIDTH = 50
TILE_HEIGHT = 40

# typing aliases:
TileId = SectorId = Tuple[int, int]


class Map:
    game: Optional[Game] = None
    instance: Optional[Map] = None

    def __init__(self, rows: int, cols: int):
        self.bounds = (rows, cols)
        self.tiles: Dict[TileId, MapTile] = {}
        self.regions: List[List[TileId]] = []
        MapTile.map = self

    @staticmethod
    def in_map_bounds(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            max_row, max_col = Map.instance.bounds
            positions = func(*args, **kwargs)
            return [
                p for p in positions if 0 < p[0] <= max_col and 0 < p[1] <= max_row
            ]
        return wrapper


class MapTile:
    map: Optional[Map] = None

    def __init__(self, x, y):
        self.x: int = x
        self.y: int = y
        self.position = (x, y)
        self.map_region: int
        self.adjacent: Set[MapTile] = set()

        self.ground_sprite: Optional[GameObject] = None
        self.objects: List[Optional[GameObject]] = []

    @property
    def unit(self) -> Optional[Unit]:
        for obj in self.objects:
            if isinstance(obj, Unit): return obj

    @property
    def building(self) -> Optional[Building]:
        for obj in self.objects:
            if isinstance(obj, Building): return obj

    def walkable(self, weight: UnitWeight = 0) -> bool:
        if self.objects:
            return all((obj.destructible(weight) for obj in self.objects))
        return False

    @Map.in_map_bounds
    def adjacent(self):
        return [(self.x + n[0], self.y + n[1]) for n in [
            (-1, -1), (-1, 0), (-1, +1), (0, 0), (+1, -1), (+1, 0), (+1, +1)
        ]]


