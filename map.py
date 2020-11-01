#!/usr/bin/env python
from __future__ import annotations

from functools import wraps
from typing import Optional, Tuple, List, Set, Dict

from arcade.arcade_types import Point

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

    def __init__(self,
                 map_width: int,
                 map_height: int,
                 tile_width: int,
                 tile_height: int):
        self.tile_size = (tile_width, tile_height)
        self.map_size = (map_width, map_height)
        self.bounds = ()

        # two-dimensional array of MapTiles allows for easy searching by ids
        # which are tuples of (x, y):
        self.tiles: List[List[MapTile]] = []

        self.regions: List[List[TileId]] = []
        MapTile.map = self

    def tile(self, position: Point) -> MapTile:
        row, column = self.position_to_id(*position)
        return self.tiles[row][column]

    @staticmethod
    def position_to_id(x, y) -> TileId:
        return x // TILE_WIDTH, y // TILE_HEIGHT

    def id_to_position(self, tile_id: TileId) -> Point:
        x, y = tile_id
        return TILE_WIDTH // 2 + x * TILE_WIDTH, TILE_HEIGHT // 2 + y * TILE_HEIGHT

    def build_map(self, tiles_rows: int, tiles_cols: int):
        for row in range(tiles_rows):
            new_tiles_row = []
            x = TILE_HEIGHT * row - TILE_HEIGHT // 2
            for col in range(tiles_cols):
                 new_tiles_row.append(
                     MapTile(x, TILE_WIDTH * col - TILE_WIDTH // 2)
                 )



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
        self.id = (x // TILE_WIDTH, y // TILE_HEIGHT)
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


