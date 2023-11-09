#!/usr/bin/env python
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import IntEnum

from math import dist
from collections import deque, defaultdict
from functools import partial, cached_property, lru_cache, singledispatch, singledispatchmethod
from typing import (
    Deque, Dict, List, Optional, Set, Tuple, Union, Generator, Collection, Any,
)

from arcade import Sprite, Texture, load_spritesheet, make_soft_square_texture, create_isometric_grid_lines, Window, \
    ShapeElementList, SpriteList, load_texture, create_line_strip, draw_polygon_filled, draw_text

from game import PROFILING_LEVEL
from utils.constants import TILE_WIDTH, TILE_HEIGHT, VERTICAL_DIST, DIAGONAL_DIST, ADJACENT_OFFSETS, \
    OPTIMAL_PATH_LENGTH, NormalizedPoint, MapPath, PathRequest, TreeID
from gameobjects.gameobject import GameObject
from utils.colors import SAND, WATER_SHALLOW, BLACK, WHITE, rgb_to_rgba, GREEN
from utils.data_types import GridPosition, Number
from utils.priority_queue import PriorityQueue
from utils.scheduling import EventsCreator
from utils.functions import (
    get_path_to_file, all_files_of_type_named
)
from map.quadtree import CartesianQuadTree, IsometricQuadTree
from utils.game_logging import log_here, log_this_call
from utils.singleton import SingletonMeta
from utils.timing import timer
from utils.geometry import calculate_circular_area

# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!


MAP_TEXTURES = {
    'mud': load_spritesheet(
        get_path_to_file('mud_tileset_6x6.png'), 60, 50, 4, 16, 0)
}

random_value = random.random

MAP_TILE_TEXTURE_GROUND = make_soft_square_texture(TILE_WIDTH, SAND, 255, 225)
MAP_TILE_TEXTURE_WATER = make_soft_square_texture(TILE_WIDTH, WATER_SHALLOW, 255, 255)
MAP_TILE_TEXTURE_VOID = make_soft_square_texture(TILE_WIDTH, BLACK, 255, 0)

ADJACENCY_MATRIX = ((-1, -1), (-1, 0), (0, -1), (0, 1), (1, 1), (1, 0), (1, -1), (-1, 1))


def position_to_map_grid(x: Number, y: Number) -> GridPosition:
    """Return map-grid-normalised position."""
    return IsometricMap.instance.pos_to_iso_grid(x, y)


def normalize_position(x: Number, y: Number) -> NormalizedPoint:
    return map_grid_to_position((int(x // TILE_WIDTH), int(y // TILE_HEIGHT)))


@lru_cache(maxsize=62500)
@singledispatch
def map_grid_to_position(grid: Any, *args) -> tuple[int, int]:
    """Return (x, y) position of the map-grid-normalised Node."""
    raise NotImplementedError


@map_grid_to_position.register
def _(grid: tuple) -> tuple[int, int]:
    return IsometricMap.instance.iso_grid_to_position(*grid)


@map_grid_to_position.register
def _(grid_x: int, grid_y: int) -> tuple[int, int]:
    return IsometricMap.instance.iso_grid_to_position(grid_x, grid_y)


def adjacent_map_grids(x: Number, y: Number) -> List[GridPosition]:
    """Return list of map-normalised grid-positions adjacent to (x, y)."""
    grid = position_to_map_grid(x, y)
    return [(grid[0] + p[0], grid[1] + p[1]) for p in ADJACENT_OFFSETS]


def adjacent_distance(this: GridPosition, adjacent: GridPosition) -> int:
    return DIAGONAL_DIST if diagonal(this, adjacent) else VERTICAL_DIST


def diagonal(first_grid: GridPosition, second_grid: GridPosition) -> bool:
    return first_grid[0] != second_grid[0] and first_grid[1] != second_grid[1]


def random_terrain_texture() -> Texture:
    texture = random.choice(MAP_TEXTURES['mud'])
    texture.image.transpose(random.randint(0, 5))
    return texture


def set_terrain_texture(terrain_type: str,
                        index: int = None,
                        rotation: int = None) -> Tuple[Texture, int, int]:
    index = index or random.randint(0, len(MAP_TEXTURES[terrain_type]) - 1)
    texture: Texture = MAP_TEXTURES[terrain_type][index]

    rotation = rotation or random.randint(0, 5)
    texture.image.transpose(rotation)
    return texture, index, rotation

#
# @timer(level=2, global_profiling_level=PROFILING_LEVEL, forced=False)
# def a_star(current_map: Map,
#            start: GridPosition,
#            end: GridPosition,
#            pathable: bool = False) -> Union[MapPath, None]:
#     """
#     Find the shortest path from <start> to <end> position using A* algorithm.
#
#     :param current_map: Map
#     :param start: GridPosition -- (int, int) path-start point.
#     :param end: GridPosition -- (int, int) path-destination point.
#     :param pathable: bool -- should pathfinder check only walkable tiles
#     (default) or all pathable map area? Use it to get into 'blocked'
#     areas, e.g. places enclosed by units.
#     :return: Union[MapPath, bool] -- list of points or False if no path
#     found
#     """
#     map_nodes = current_map.nodes
#     unexplored = PriorityQueue(start, heuristic(start, end))
#     explored = set()
#     previous: Dict[GridPosition, GridPosition] = {}
#
#     get_best_unexplored = unexplored.get
#     put_to_unexplored = unexplored.put
#
#     cost_so_far = defaultdict(lambda: math.inf)
#     cost_so_far[start] = 0
#
#     while unexplored:
#         if (current := get_best_unexplored()[1]) == end:
#             return reconstruct_path(map_nodes, previous, current)
#         node = map_nodes[current]
#         walkable = node.pathable_adjacent if pathable else node.walkable_adjacent
#         for adjacent in (a for a in walkable if a.grid not in explored):
#             adj_grid = adjacent.grid
#             total = cost_so_far[current] + adjacent_distance(current, adj_grid)
#             if total < cost_so_far[adj_grid]:
#                 previous[adj_grid] = current
#                 cost_so_far[adj_grid] = total
#                 priority = total + heuristic(adj_grid, end)
#                 put_to_unexplored(adj_grid, priority)
#             explored.add(current)
#     # if path was not found searching by walkable tiles, we call second
#     # pass and search for pathable nodes this time
#     if not pathable:
#         return a_star(current_map, start, end, pathable=True)
#     return None  # no third pass, if there is no possible path!
#
#
# def heuristic(start: GridPosition, end: GridPosition) -> int:
#     dx = abs(start[0] - end[0])
#     dy = abs(start[1] - end[1])
#     return DIAGONAL_DIST * min(dx, dy) + VERTICAL_DIST * max(dx, dy)
#
#
# def reconstruct_path(map_nodes: Dict[GridPosition, MapNode],
#                      previous_nodes: Dict[GridPosition, GridPosition],
#                      current_node: GridPosition) -> MapPath:
#     path = [map_nodes[current_node]]
#     while current_node in previous_nodes.keys():
#         current_node = previous_nodes[current_node]
#         path.append(map_nodes[current_node])
#     return [node.position for node in path[::-1]]
#


def invert_matrix(a, b, c, d):
    det = (1 / (a * d - b * c))
    return det * d, det * -b, det * -c, det * a


def pos_to_iso_grid(pos_x: int, pos_y: int) -> Tuple[int, int] | None:
    """Use this, function from other scripts to convert positions to iso grid coordinates."""
    return IsometricMap.instance.pos_to_iso_grid(pos_x, pos_y)


# @timer(level=2, global_profiling_level=PROFILING_LEVEL, forced=False)
def a_star(current_map: IsometricMap,
           start: Tuple[int, int],
           end: Tuple[int, int],
           pathable: bool = False) -> Union[Union[List[Tuple[int, int]], List[Tuple[int, int]]], None]:
    """
    Find the shortest path from <start> to <end> position using A* algorithm.

    :param current_map: Map
    :param start: GridPosition -- (int, int) path-start point.
    :param end: GridPosition -- (int, int) path-destination point.
    :param pathable: bool -- should pathfinder check only walkable tiles
    (default) or all pathable map area? Use it to get into 'blocked'
    areas, e.g. places enclosed by units.
    :return: Union[MapPath, bool] -- list of points or False if no path
    found
    """
    map_nodes = current_map.tiles
    unexplored = PriorityQueue(start, heuristic(start, end))
    explored = set()
    previous: Dict[Tuple[int, int], Tuple[int, int]] = {}

    get_best_unexplored = unexplored.get
    put_to_unexplored = unexplored.put

    cost_so_far = defaultdict(lambda: math.inf)
    cost_so_far[start] = 0

    while unexplored:
        if (current := get_best_unexplored()[1]) == end:
            return reconstruct_path(map_nodes, previous, current)
        node = map_nodes[current]
        walkable = node.pathable_adjacent if pathable else node.walkable_adjacent
        for adjacent in (a for a in walkable if a.grid not in explored):
            adj_grid = adjacent.grid
            total = cost_so_far[current] + adjacent_distance(current, adj_grid)
            if total < cost_so_far[adj_grid]:
                previous[adj_grid] = current
                cost_so_far[adj_grid] = total
                priority = total + heuristic(adj_grid, end)
                put_to_unexplored(adj_grid, priority)
            explored.add(current)
    # if path was not found searching by walkable tiles, we call second
    # pass and search for pathable nodes this time
    if not pathable:
        return a_star(current_map, start, end, pathable=True)
    return None  # no third pass, if there is no possible path!


def heuristic(start: Tuple[int, int], end: Tuple[int, int]) -> int:
    dx = abs(start[0] - end[0])
    dy = abs(start[1] - end[1])
    return DIAGONAL_DIST * min(dx, dy) + VERTICAL_DIST * max(dx, dy)


def reconstruct_path(map_nodes: Dict[Tuple[int, int], IsometricTile],
                     previous_nodes: Dict[Tuple[int, int], Tuple[int, int]],
                     current_node: Tuple[int, int]) -> Union[List[Tuple[int, int]], List[Tuple[int, int,]]]:
    path = [map_nodes[current_node]]
    while current_node in previous_nodes.keys():
        current_node = previous_nodes[current_node]
        path.append(map_nodes[current_node])
    return [node.grid for node in path[::-1]]  # TODO: change GridPosition used by Unit.path to IsometricTile


@dataclass
class Coordinate:
    __slots__ = ['position', ]
    position: Tuple[float, float]


class IsometricMap:
    """
    The IsometricMap class represents a map in an isometric game. It generates and manages isometric tiles, handles
    conversions between isometric grid coordinates and cartesian coordinates, and provides methods for querying and
    manipulating the map.
    """
    game = None
    instance = None

    def __init__(self, map_settings: Dict[str, Any] = None):
        self.window = self.game.window
        self.tiles = {}
        self.grids_to_positions: Dict[Tuple[int, int], Tuple[int, int]] = {}
        self.tile_width = map_settings['tile_width']
        self.tile_height = self.tile_width // 2
        self.rows = map_settings['rows']
        self.columns = map_settings['columns']
        self.width = self.columns * self.tile_width
        self.height = self.rows * self.tile_height
        self.origin_tile = self.width // 2, self.height - self.tile_height // 2
        self.grid_gizmo = ShapeElementList()
        self.terrains = self.find_terrains()
        self.tiles: Dict[Tuple[int, int], IsometricTile] = self.generate_tiles()
        self.quadtree = self.generate_quadtree()
        IsometricMap.instance = IsometricTile.map = self

    def find_terrains(self) -> Dict[str, Texture]:
        return {
            name: load_texture(f'{name}.png', 0, 0, self.tile_width, self.tile_height)
            for name in ('grass', 'sand', 'water')
        }

    def generate_quadtree(self) -> IsometricQuadTree:
        quad_iso_x, quad_iso_y = self.iso_grid_to_position(self.rows // 2, self.columns // 2)
        quad_width, quad_height = self.columns * self.tile_width, self.rows * self.tile_height
        return IsometricQuadTree(quad_iso_x, quad_iso_y + self.tile_height // 2, quad_width, quad_height)

    def adjacent_grids(self, gx: int, gy: int) -> List[Tuple[int, int]]:
        return [adj for adj in [(gx + x, gy + y) for (x, y) in ADJACENCY_MATRIX] if adj in self.tiles]

    def generate_tiles(self) -> Dict[Tuple[int, int], IsometricTile]:
        tiles = {}
        for row in range(self.rows):
            for col in range(self.columns):
                idx = row * self.columns + col + 1
                tile_x, tile_y = self.iso_grid_to_position(col, row)
                sprite = Sprite(center_x=tile_x, center_y=tile_y, hit_box_algorithm='None')
                terrain, sprite.texture = random.choice(list(self.terrains.items()))
                tile = IsometricTile(idx, col, row, tile_x, tile_y, 0, self.tile_width, terrain, sprite=sprite)
                tile.texture = random.choice(list(self.terrains.values()))
                gizmo = create_line_strip(tile.points, WHITE)
                tiles[(col, row)] = tile
                self.grid_gizmo.append(gizmo)
                self.game.terrain_tiles.append(sprite)
                self.grids_to_positions[(col, row)] = tile_x, tile_y
        return tiles

    def iso_grid_to_position(self, gx: int, gy: int, gz: int = 0) -> Tuple[int, int]:
        """Convert isometric grid coordinates (gx, gy) to cartesian coordinates (e.g. mouse cursor position)."""
        x, y = self.origin_tile
        pos_x = int(x + (gx - gy) * (self.tile_width * 0.5))
        pos_y = int(y - (gx + gy) * (self.tile_height * 0.5) + gz)
        return pos_x, pos_y

    def pos_to_iso_grid(self, pos_x: int, pos_y: int) -> Tuple[int, int] | None:
        """Convert (x, y) position (e.g. mouse cursor position) to isometric grid coordinates."""
        left, _, bottom, _ = self.game.viewport
        iso_x = pos_x - (self.width * 0.5)
        iso_y = -pos_y + self.height
        width = self.tile_width * 0.5
        a, b, c, d = invert_matrix(width, -width, width * 0.5, width * 0.5)
        grid = int(iso_x * a + iso_y * b), int(iso_x * c + iso_y * d)
        return grid if grid in self.tiles else None

    def position_to_node(self, x: Number, y: Number) -> IsometricTile:
        return self.grid_to_node(self.pos_to_iso_grid(x, y))

    def grid_to_node(self, grid: Tuple[int, int]) -> IsometricTile:
        return self.tiles.get(grid, self.nonexistent_node)

    @property
    def random_walkable_tile(self) -> IsometricTile:
        return random.choice(tuple(self.all_walkable_tiles))

    @property
    def all_walkable_tiles(self) -> Generator[IsometricTile]:
        return (tile for tile in self.tiles.values() if tile.is_walkable)

    def get_tile(self, row: int, column: int) -> IsometricTile:
        return self.tiles[row][column]  # TODO: implement 2D array instead of Dictionary for self.tiles]

    def on_map_area(self, x: float, y: float) -> bool:
        return self.quadtree.in_bounds(Coordinate((x, y)))

    def __contains__(self, item: Tuple[int, int]):
        return item in self.tiles

    def is_inside_map_grid(self, grid: Collection[Tuple[int, int]]) -> Set[Tuple[int, int]]:
        return {g for g in grid if g in self.tiles}

    def walkable(self, grid: Tuple[int, int]) -> bool:
        try:
            return self.tiles[grid].is_walkable
        except KeyError:
            return False

    def walkable_adjacent(self, x, y) -> Set[IsometricTile]:
        if (x, y) not in self.tiles:
            x, y = self.pos_to_iso_grid(x, y)
        pointed_tile = self.tiles[self.pos_to_iso_grid(x, y)]
        return {tile for tile in pointed_tile.adjacent_tiles if tile.is_walkable}

    def pathable_adjacent(self, x, y) -> Set[IsometricTile]:
        if (x, y) not in self.tiles:
            x, y = self.pos_to_iso_grid(x, y)
        pointed_tile = self.tiles[x, y]
        return {tile for tile in pointed_tile.adjacent_tiles if tile.is_pathable}

    @cached_property
    def nonexistent_node(self) -> IsometricTile:
        tile = IsometricTile(-1, -1, -1, -TILE_WIDTH, -TILE_WIDTH, 0, TILE_WIDTH, 'grass', None)
        tile.is_pathable = tile._walkable = False
        return tile

    def get_random_position(self) -> NormalizedPoint:
        return random.choice([n.position for n in self.all_walkable_tiles])

    def get_valid_position(self, position: Optional[NormalizedPoint] = None) -> NormalizedPoint:
        """

        :param position: Optional[NormalizedPoint] -- if left to default None, returns random, valid position
        :return: NormalizedPoint
        """
        return position or self.get_random_position()

    def draw(self, editor_mode: bool = False):
        if editor_mode:
            self.grid_gizmo.draw()
            self.quadtree.draw()
        else:
            ...
            # self.tiles_sprites.draw()
        for tile in list(self.tiles.values())[:]:
            tile.draw()


class IsometricTile:
    map: Optional[IsometricMap] = None

    def __init__(self, idx: int, gx: int, gy: int, x: int, y: int, z: int, width: int, terrain: str,
                 sprite: Sprite = None):
        self.idx = idx
        self.gx = gx
        self.gy = gy
        self.x = x
        self.y = y
        self.z = z
        self.width = width
        self._position = x, y = self.x, self.y
        hh, hw = self.width // 4, self.width // 2
        self.points = ((x - hw, y + z), (x, y + hh + z), (x + hw, y + z), (x, y - hh + z), (x - hw, y + z))
        self.width = width
        self.pointed = False
        self._sprite = sprite

        self.grid = gx, gy
        self.terrain_type: TerrainType = TerrainType.GROUND if terrain in ('grass', 'sand') else TerrainType.WATER
        self.map_region: Optional[int] = None
        self.costs = None

        self._walkable = self.terrain_type != TerrainType.WATER
        self._pathable = self.terrain_type > -1
        self._adjacent_ids: Optional[List[Tuple[int, int]]] = None
        self._adjacent_tiles: Optional[List[IsometricTile]] = None

        self._is_pathable = True  # terrain_type > -1

        self._tree: Optional[int] = None
        self._unit: Optional['Unit'] = None
        self._building: Optional['Building'] = None
        self._static_gameobject: Optional['GameObject', int] = None

    def __repr__(self) -> str:
        return f'MapTile({self.idx},{self.gx},{self.gy},{self.x},{self.y},{self.z},{self.width})'

    def __str__(self) -> str:
        return f'IsometricTile(idx:{self.idx}, grid:{self.gx},{self.gy}, position:{self.x},{self.y}, type:{self.terrain_type})'

    @property
    def position(self) -> Tuple[int, int]:
        return self.x, self.y

    @position.setter
    def position(self, new_position: Tuple[int, int]):
        self.x, self.y = new_position

    @property
    def adjacent_ids(self) -> List[Tuple[int, int]]:
        if self._adjacent_ids is None:
            self._adjacent_ids = self.map.adjacent_grids(self.gx, self.gy)
        return self._adjacent_ids

    @property
    def adjacent_tiles(self) -> List[IsometricTile]:
        if self._adjacent_tiles is None:
            self._adjacent_tiles = [self.map.tiles[gx, gy] for (gx, gy) in self.adjacent_ids]
        return self._adjacent_tiles

    @property
    def walkable_adjacent(self):
        return {tile for tile in self.adjacent_tiles if tile.is_walkable}

    @property
    def pathable_adjacent(self):
        return {tile for tile in self.adjacent_tiles if tile.is_pathable}

    def diagonal_to_other(self, other: IsometricTile):
        return self.gx == other.gx or self.gy == other.gy

    @property
    def tree(self) -> Optional[int]:
        return self._tree

    @tree.setter
    def tree(self, value: Optional[int]):
        self._static_gameobject = self._tree = value

    def remove_tree(self):
        if self._tree is not None:
            for obj in self.map.game.static_objects:
                if obj.map_node is self:
                    obj.kill()

    @property
    def unit(self) -> Optional['Unit']:
        return self._unit

    @unit.setter
    def unit(self, value: Optional['Unit']):
        self._unit = value

    @property
    def building(self) -> Optional['Building']:
        return self._building

    @building.setter
    def building(self, value: Optional['Building']):
        self._static_gameobject = self._building = value

    @property
    def unit_or_building(self) -> Optional[Union['Unit', 'Building']]:
        return self._unit or self._building

    @property
    def static_gameobject(self) -> Optional['GameObject', int]:
        return self._static_gameobject

    @static_gameobject.setter
    def static_gameobject(self, value: Optional['GameObject', int]):
        self._static_gameobject = value

    @property
    def is_water(self) -> bool:
        return self.terrain_type is TerrainType.WATER

    @property
    def is_navigable(self):
        return self.is_water and self._unit is None

    @property
    def is_walkable(self) -> bool:
        """
        Use it to find if node is not blocked at the moment by units or
        buildings.
        """
        return self.terrain_type is TerrainType.GROUND and self.is_pathable and self._unit is None

    @property
    def is_pathable(self) -> bool:
        """Call it to find if this node is available for pathfinding at all."""
        return self._pathable and self._static_gameobject is None

    @is_pathable.setter
    def is_pathable(self, value: bool):
        self._pathable = value

    @property
    def available_for_construction(self) -> bool:
        return self.is_walkable and self.is_explored()  # and not self.are_buildings_nearby()

    def is_explored(self):
        return self.map.game.editor_mode or self.grid in self.map.game.fog_of_war.explored

    def are_buildings_nearby(self):
        return any(n.building for n in self.adjacent_tiles)

    def draw(self):
        color = rgb_to_rgba(GREEN, 125) if self.pointed else WHITE
        if self.pointed:
            draw_polygon_filled(self.points, color)
            draw_text(f'{self.gx},{self.gy}', self.x, self.y, WHITE, anchor_x='center', anchor_y='center')


class TerrainType(IntEnum):
    """
    Enum representing different types of terrain.
    """
    GROUND = 0
    WATER = 1
    VOID = 2

    def is_ground(self) -> bool:
        return self == TerrainType.GROUND

    def is_water(self) -> bool:
        return self == TerrainType.WATER

    def is_void(self) -> bool:
        return self == TerrainType.VOID

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'TerrainType.{self.name}'

    @staticmethod
    def is_valid_terrain(value: int) -> bool:
        return value in TerrainType.__members__.values()

#
# class Map:
#     game = None
#     instance = None
#
#     def __init__(self, map_settings: Dict):
#         MapNode.map = Map.instance = self
#         self.rows = map_settings['rows']
#         self.columns = map_settings['columns']
#         self.grid_width = map_settings['tile_width']
#         self.grid_height = map_settings['tile_height']
#         self.width = self.columns * self.grid_width
#         self.height = self.rows * self.grid_height
#
#         self.nodes_data = map_settings.get('nodes', {})
#
#         self.nodes: Dict[GridPosition, MapNode] = {}
#         self.distances = {}
#
#         self.quadtree = CartesianQuadTree(self.width // 2, self.height // 2, self.width, self.height)
#         log_here(f'Generated QuadTree of depth: {self.quadtree.total_depth()}', console=True)
#
#         self.generate_map_nodes_and_tiles()
#         #  TODO: find efficient way to use these costs in pathfinding
#         # self.calculate_distances_between_nodes()
#
#         self.prepare_planting_trees(map_settings)
#
#         log_here('Map was initialized successfully...', console=True)
#
#     def prepare_planting_trees(self, map_settings):
#         trees = map_settings.get('trees') or self.generate_random_trees()
#         self.game.after_load_functions.append(partial(self.plant_trees, trees))
#
#     @log_this_call()
#     def plant_trees(self, trees):
#         for node in self.nodes.values():
#             if (tree_type := trees.get(node.grid)) is not None:
#                 self.game.spawn(f'tree_leaf_{tree_type}', position=node.position)
#
#     def generate_random_trees(self) -> Dict[GridPosition, int]:
#         trees = len(all_files_of_type_named('.png', 'resources', 'tree_')) + 1
#         return {grid: random.randrange(1, trees) for grid in self.nodes.keys()
#                 if random.random() < self.game.settings.percent_chance_for_spawning_tree}
#
#     def save(self) -> Dict:
#         return {
#             'rows': self.rows,
#             'columns': self.columns,
#             'grid_width': self.grid_width,
#             'grid_height': self.grid_height,
#             'nodes_data': self.nodes_data,
#             'trees': {g: n.tree.save() for (g, n) in self.nodes.items() if n.tree is not None}
#         }
#
#     def __str__(self) -> str:
#         return f'Map(height: {self.height}, width: {self.width}, nodes: {len(self.nodes)})'
#
#     def __len__(self) -> int:
#         return len(self.nodes)
#
#     def __getitem__(self, item):
#         return self.nodes.get(item, self.nonexistent_node)
#
#     def __contains__(self, item: GridPosition):
#         return item in self.nodes
#
#     def is_inside_map_grid(self, grid: Collection[GridPosition]) -> Set[GridPosition]:
#         return {g for g in grid if g in self.nodes}
#
#     def on_map_area(self, x: Number, y: Number) -> bool:
#         return 0 <= x < self.width and 0 <= y < self.height
#
#     def walkable(self, grid) -> bool:
#         try:
#             return self.nodes[grid].is_walkable
#         except KeyError:
#             return False
#
#     def walkable_adjacent(self, x, y) -> Set[MapNode]:
#         if (x, y) not in self.nodes:
#             x, y = position_to_map_grid(x, y)
#         pointed_tile = self.nodes[x, y]
#         return {tile for tile in pointed_tile.adjacent_nodes if tile.is_walkable}
#
#     def pathable_adjacent(self, x, y) -> Set[MapNode]:
#         if (x, y) not in self.nodes:
#             x, y = position_to_map_grid(x, y)
#         pointed_node = self.nodes[x, y]
#         return {node for node in pointed_node.adjacent_nodes if node.is_pathable}
#
#     def adjacent_nodes(self, x: Number, y: Number) -> Set[MapNode]:
#         return {
#             self.nodes[adj] for adj in self.is_inside_map_grid(adjacent_map_grids(x, y))
#         }
#
#     def position_to_node(self, x: Number, y: Number) -> MapNode:
#         return self.grid_to_node(position_to_map_grid(x, y))
#
#     def grid_to_node(self, grid: GridPosition) -> MapNode:
#         return self.nodes.get(grid)
#
#     @property
#     def random_walkable_node(self) -> MapNode:
#         return random.choice(tuple(self.all_walkable_nodes))
#
#     @property
#     def all_walkable_nodes(self) -> Generator[MapNode]:
#         return (node for node in self.nodes.values() if node.is_walkable)
#
#     @timer(1, global_profiling_level=PROFILING_LEVEL)
#     @log_this_call(console=True)
#     def generate_map_nodes_and_tiles(self):
#         for x in range(self.columns):
#             for y in range(self.rows):
#                 terrain = TerrainType.VOID if x in (0, self.columns) or y in (0, self.rows) else TerrainType.GROUND
#                 self.nodes[(x, y)] = node = MapNode(x, y, terrain)
#                 self.create_map_sprite(*node.position, node.terrain_type)
#         log_here(f'Generated {len(self.nodes)} map nodes.', console=True)
#
#     def create_map_sprite(self, x: int, y: int, terrain_type: TerrainType):
#         sprite = Sprite(center_x=x, center_y=y, hit_box_algorithm='None')
#         sprite.texture = {
#             terrain_type.GROUND: MAP_TILE_TEXTURE_GROUND,
#             terrain_type.VOID: MAP_TILE_TEXTURE_VOID,
#             terrain_type.WATER: MAP_TILE_TEXTURE_WATER
#         }[terrain_type]
#         # try:
#         #     terrain_type, index, rotation = self.nodes_data[(x, y)]
#         #     t, i, r = set_terrain_texture(terrain_type, index, rotation)
#         # except KeyError:
#         #     terrain_type = 'mud'
#         #     t, i, r = set_terrain_texture(terrain_type)
#         #     self.nodes_data[(x, y)] = terrain_type, i, r
#         # sprite.texture = t
#         self.game.terrain_tiles.append(sprite)
#
#     def find_map_regions(self):
#         """
#         All MapNodes which are intermediary connected or there is possible path connecting them, belong to the same map
#         region, which allows for fast excluding impossible pathfinding calls - if start and destination belong to the
#         different regions, we do not need call A-star algorithm.
#         """
#         ...
#
#     def calculate_distances_between_nodes(self):
#         for node in self.nodes.values():
#             node.costs = costs_dict = {}
#             for grid in self.is_inside_map_grid(adjacent_map_grids(*node.position)):
#                 adjacent_node = self.nodes[grid]
#                 distance = adjacent_distance(grid, adjacent_node.grid)
#                 # terrain_cost = node.terrain_cost + adjacent_node.terrain_cost
#                 node.costs[grid] = distance #  * terrain_cost
#             self.distances[node.grid] = costs_dict
#
#     def get_nodes_by_row(self, row: int) -> List[MapNode]:
#         return [n for n in self.nodes.values() if n.grid[1] == row]
#
#     def get_nodes_by_column(self, column: int) -> List[MapNode]:
#         return [n for n in self.nodes.values() if n.grid[0] == column]
#
#     def get_all_nodes(self) -> Generator[MapNode]:
#         return (n for n in self.nodes.values())
#
#     def get_random_position(self) -> NormalizedPoint:
#         return random.choice([n.position for n in self.all_walkable_nodes])
#
#     def get_valid_position(self, position: Optional[NormalizedPoint] = None) -> NormalizedPoint:
#         """
#
#         :param position: Optional[NormalizedPoint] -- if left to default None, returns random, valid position
#         :return: NormalizedPoint
#         """
#         return position or self.get_random_position()
#
#     def node(self, grid: GridPosition) -> MapNode:
#         return self.nodes.get(grid, self.nonexistent_node)
#
#     @cached_property
#     def nonexistent_node(self) -> MapNode:
#         node = MapNode(-1, -1, TerrainType.VOID)
#         node.is_pathable = node._walkable = False
#         return node
#

class WaypointsQueue:
    """
    When human player gives his Units movement orders with left CTRL key
    pressed, he can plan multiple consecutive moves ahead, which would be
    executed when LCTRL is released, or when player points back to the first
    waypoint of the queue. The second scenario would produce a looped path to
    patrol.
    """

    def __init__(self, units: List[Unit]):
        self.map = IsometricMap.instance
        self.units = [u for u in units]
        self.waypoints = []
        self.units_waypoints = {unit: [] for unit in units}
        self.active = False
        self.loop = False

    def __contains__(self, unit: Unit) -> bool:
        return unit in self.units

    def __bool__(self):
        return bool(self.units)

    def add_waypoint(self, x: int, y: int):
        x, y = normalize_position(x, y)
        if len(self.waypoints) > 1 and (x, y) == self.waypoints[0]:
            self.loop = True
            Pathfinder.instance.finish_waypoints_queue()
        else:
            self.waypoints.append((x, y))
            self.add_waypoints_for_each_unit(len(self.units), x, y)

    def add_waypoints_for_each_unit(self, amount: int, x: int, y: int):
        waypoints = Pathfinder.instance.get_group_of_waypoints(x, y, amount)
        for i, unit in enumerate(self.units):
            self.units_waypoints[unit].append(waypoints[i])

    def update(self):
        for unit in self.units:
            if waypoints := self.units_waypoints[unit]:
                self.evaluate_unit_waypoints(unit, waypoints)
            else:
                self.units.remove(unit)

    def evaluate_unit_waypoints(self, unit, waypoints):
        destination = waypoints[-1]
        if unit.reached_destination(destination):
            removed = waypoints.pop()
            if self.loop:
                waypoints.insert(0, removed)
        elif not (unit.has_destination or unit.heading_to(destination)):
            unit.move_to(destination)

    def start(self):
        self.active = True
        for unit, waypoints in self.units_waypoints.items():
            waypoints.reverse()


class NavigatingUnitsGroup:
    """
    To avoid calling Pathfinde.a_star A* algorithm for very long paths for
    many Units at once, we use this class. NavigatingUnitsGroup call a_star
    method for the full path only once, and then divides this path for shorter
    ones and call a_star for particular units for those shorter distances.
    """

    def __init__(self, units: List[Unit], x: Number, y: Number):
        self.map = IsometricMap.instance
        self.leader = units[0]
        self.destination = position_to_map_grid(x, y)
        self.units_paths: Dict[Unit, List] = {unit: [] for unit in units}
        self.reset_units_navigating_groups(units)
        destinations = self.create_units_group_paths(units)
        self.reverse_units_paths()
        if self.leader.is_controlled_by_local_human_player:
            self.add_visible_indicators_of_destinations(destinations, units)

    def __str__(self) -> str:
        return f'NavigatingUnitsGroup(units:{len(self.units_paths)})'

    def __contains__(self, unit: Unit) -> bool:
        return unit in self.units_paths.keys()

    def __bool__(self):
        return bool(self.units_paths)

    def discard(self, unit: Unit):
        try:
            del self.units_paths[unit]
        except KeyError:
            log_here(f'Failed to discard {unit} from {self}', True)

    def reset_units_navigating_groups(self, units: List[Unit]):
        for unit in units:
            unit.stop_completely()
            unit.set_navigating_group(navigating_group=self)

    def create_units_group_paths(self, units: List[Unit]) -> List[GridPosition]:
        start = self.leader.current_node.grid
        path = a_star(self.map, start, self.destination, True)
        destinations = Pathfinder.instance.get_group_of_waypoints(*path[-1], len(units))
        if len(path) > OPTIMAL_PATH_LENGTH:
            self.slice_paths(units, path)
        self.add_destinations_to_units_paths(destinations, units)
        return destinations

    def slice_paths(self, units, path):
        for i in range(1, len(path) // OPTIMAL_PATH_LENGTH, OPTIMAL_PATH_LENGTH):
            step = path[i * OPTIMAL_PATH_LENGTH]
            units_steps = Pathfinder.instance.get_group_of_waypoints(*step, len(units))
            self.add_destinations_to_units_paths(units_steps, units)

    def add_destinations_to_units_paths(self, destinations, units):
        for unit, grid in zip(units, destinations):
            self.units_paths[unit].append(grid)

    def reverse_units_paths(self):
        """
        Reverse waypoints list of each Unit, to allow consuming it from the
        end using cheaply pop() method.
        """
        for unit, steps in self.units_paths.items():
            steps.reverse()
            if len(steps) > 1:
                steps.pop()

    def add_visible_indicators_of_destinations(self, destinations, units):
        positions = [map_grid_to_position(g) for g in destinations]
        self.map.game.units_ordered_destinations.new_destinations(positions, units)

    def update(self):
        to_remove = []
        for unit, steps in self.units_paths.items():
            if steps:
                self.find_next_path_for_unit(unit, steps)
            else:
                to_remove.append(unit)
        self.remove_finished_paths(to_remove)

    @staticmethod
    def find_next_path_for_unit(unit, steps):
        destination = steps[-1]
        if unit.reached_destination(destination):
            steps.pop()
        # elif len(steps) > 1 and unit.nearby(destination):
        #     steps.pop()
        elif not (unit.has_destination or unit.heading_to(destination)):
            unit.move_to(destination)

    @staticmethod
    def remove_finished_paths(finished_units: List[Unit]):
        for unit in finished_units:
            unit.set_navigating_group(navigating_group=None)


class Pathfinder(EventsCreator):
    """
    This class manages finding and assigning paths for Units in game. It also
    creates, updates and removes WaypointsQueues and NavigatingUnitsGroups.
    """
    instance: Optional[Pathfinder] = None

    def __init__(self, map: IsometricMap):
        """
        :param map: Map -- actual instance of game Map is_loaded.
        """
        EventsCreator.__init__(self)
        self.map = map
        self.created_waypoints_queue: Optional[WaypointsQueue] = None
        self.waypoints_queues: List[WaypointsQueue] = []
        self.navigating_groups: List[NavigatingUnitsGroup] = []
        self.requests_for_paths: Deque[PathRequest] = deque()
        Pathfinder.instance = self

    def __bool__(self) -> bool:
        return len(self.requests_for_paths) > 0

    def __len__(self) -> int:
        return len(self.requests_for_paths)

    def __contains__(self, unit: Unit) -> bool:
        return any(request[0] == unit for request in self.requests_for_paths)

    def enqueue_waypoint(self, units: List[Unit], x: int, y: int):
        if self.created_waypoints_queue is None:
            self.created_waypoints_queue = WaypointsQueue(units)
        self.created_waypoints_queue.add_waypoint(x, y)

    def finish_waypoints_queue(self):
        if (queue := self.created_waypoints_queue) is not None:
            self.waypoints_queues.append(queue)
            queue.start()
        self.created_waypoints_queue = None

    def navigate_units_to_destination(self, units: List[Unit], x: int, y: int):
        if not self.map.position_to_node(x, y).is_walkable:
            x, y = self.get_closest_walkable_position(x, y)
        self.navigating_groups.append(NavigatingUnitsGroup(units, x, y))

    def update(self):
        self.update_waypoints_queues()
        self.update_navigating_groups()
        if self.requests_for_paths:
            self.process_next_path_request()

    def process_next_path_request(self):
        """
        Each frame get first request from queue and try to find path for it,
        if successful, return the path, else enqueue the request again.
        """
        unit, start, destination = self.requests_for_paths.pop()
        # to avoid infinite attempts to find path to the Node blocked by
        # other Unit from the same navigating groups pathfinding to the
        # same place TODO: find a better way to not mutually-block nodes
        if self.map.grid_to_node(destination).is_walkable:
            if (path := a_star(self.map, start, destination)) is not None:
                return unit.follow_new_path(path)
        self.request_path(unit, start, destination)

    def update_waypoints_queues(self):
        for queue in (q for q in self.waypoints_queues if q.active):
            queue.update() if queue else self.waypoints_queues.remove(queue)

    def update_navigating_groups(self):
        for group in self.navigating_groups:
            group.update() if group else self.navigating_groups.remove(group)

    def request_path(self, unit: Unit, start: GridPosition, destination: GridPosition):
        """Enqueue new path-request. It will be resolved when possible."""
        self.requests_for_paths.appendleft((unit, start, destination))

    def cancel_unit_path_requests(self, unit: Unit):
        for request in (r for r in self.requests_for_paths.copy() if r[0] is unit):
            self.requests_for_paths.remove(request)

    def remove_unit_from_waypoint_queue(self, unit: Unit):
        for queue in (q for q in self.waypoints_queues if unit in q):
            del queue.units_waypoints[unit]
            return queue.units.remove(unit)

    def get_group_of_waypoints(self,
                               x: int,
                               y: int,
                               required_waypoints: int) -> List[GridPosition]:
        """
        Find requested number of valid waypoints around requested position.
        """
        center = self.map.pos_to_iso_grid(x, y)
        if required_waypoints == 1:
            return [center, ]
        radius = 1
        waypoints = []
        nodes = self.map.tiles
        while len(waypoints) < required_waypoints:
            waypoints = [w for w in calculate_circular_area(*center, radius) if
                         w in nodes and nodes[w].is_walkable]
            radius += 1
        waypoints.sort(key=lambda w: dist(w, center))
        return [d[0] for d in zip(waypoints, range(required_waypoints))]

    def get_closest_walkable_position(self, x, y) -> NormalizedPoint:
        if (node := self.map.position_to_node(x, y)).is_walkable:
            return node.position
        nearest_walkable = None
        while nearest_walkable is None:
            adjacent = node.adjacent_nodes
            for adjacent_node in (n for n in adjacent if n.is_walkable):
                return adjacent_node.position
            node = random.choice([n for n in adjacent])
            # TODO: potential infinite loop

    def get_closest_walkable_node(self, x, y) -> IsometricTile:
        nx, ny = self.get_closest_walkable_position(x, y)
        return self.map.position_to_node(nx, ny)


if __name__:
    # these imports are placed here to avoid circular-imports issue:
    from players_and_factions.player import PlayerEntity
    from units.units import Unit
    from buildings.buildings import Building
