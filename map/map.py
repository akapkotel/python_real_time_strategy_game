#!/usr/bin/env python
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import IntEnum

from math import dist
from collections import deque, defaultdict
from functools import cached_property, lru_cache, singledispatch
from typing import (
    Deque, Dict, List, Optional, Set, Tuple, Union, Generator, Collection, Any, Callable,
)

from arcade import Sprite, Texture, ShapeElementList, load_texture, create_line_strip, draw_polygon_filled, draw_text

from utils.constants import TILE_WIDTH, TILE_HEIGHT, VERTICAL_DIST, DIAGONAL_DIST, ADJACENT_OFFSETS, \
    OPTIMAL_PATH_LENGTH, NormalizedPoint, PathRequest, MAX_COLS_TO_ROWS_RATIO, MAXIMUM_MAP_SIZE
from gameobjects.gameobject import GameObject
from utils.colors import WHITE, rgb_to_rgba, GREEN
from utils.data_types import GridPosition, Number
from utils.priority_queue import PriorityQueue
from utils.scheduling import EventsCreator

from map.quadtree import IsometricQuadTree
from utils.game_logging import log_here

from utils.geometry import calculate_circular_area, clamp

# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!


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
    return [node.position for node in path[::-1]]  # TODO: change GridPosition used by Unit.path to IsometricTile


def max_distance_between_tiles(tile: IsometricTile, min_distance: int, max_distance: int) -> Callable[[IsometricTile], bool]:
    def internal(other_tile: IsometricTile):
        return min_distance <= dist(tile.grid, other_tile.grid) <= max_distance
    return internal


def resizer(bigger, smaller):
    smaller_at_start = smaller
    while not bigger // smaller == MAX_COLS_TO_ROWS_RATIO:
        if smaller_at_start * MAX_COLS_TO_ROWS_RATIO <= MAXIMUM_MAP_SIZE:
            bigger += 1
        else:
            smaller = bigger
            break
    return bigger, smaller


def resize_quadtree_outside_map(columns: int, rows: int, tile_height: int) -> Tuple[int, int, int]:
    if columns == rows:
        raise ValueError('columns and rows must not be equal!')
    if columns > rows:
        columns, rows = resizer(columns, rows)
    else:
        rows, columns = resizer(rows, columns)
    print(columns, rows)
    return (columns + rows) * tile_height, columns, rows


@dataclass
class Coordinate:
    __slots__ = ['position', ]
    position: Tuple[float, float]


class TerrainType(IntEnum):
    """
    Enum representing different types of terrain.
    """
    GROUND = 0
    WATER = 1
    VOID = 2

    @property
    def is_ground(self) -> bool:
        return self == TerrainType.GROUND

    @property
    def is_water(self) -> bool:
        return self == TerrainType.WATER

    @property
    def is_void(self) -> bool:
        return self == TerrainType.VOID

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'TerrainType.{self.name}'

    @staticmethod
    def is_valid_terrain(value: int) -> bool:
        return value in TerrainType.__members__.values()


class IsometricMap:
    """
    The IsometricMap class represents a map in an isometric game. It generates and manages isometric tiles, handles
    conversions between isometric grid coordinates and cartesian coordinates, and provides methods for querying and
    manipulating the map.
    """
    game = None
    instance = None

    def __init__(self, map_settings: Dict[str, Any] = None):
        IsometricMap.instance = None
        self.window = self.game.window
        self.tile_width = tile_width = map_settings['tile_width']
        self.tile_height = tile_height = self.tile_width // 2
        self.rows = rows = map_settings['rows']
        self.columns = columns = map_settings['columns']
        self.width = width = columns * tile_width
        self.height = height = rows * tile_height
        self.origin_tile_xy = width // 2, height - tile_height // 2
        self.grid_gizmo = ShapeElementList()
        self._grids_to_positions: List[List[Optional[Tuple[int, int]]]] = [
            [None for _ in range(self.columns)] for _ in range(self.rows)
        ]
        print(len(self._grids_to_positions))
        self.tiles: Dict[Tuple[int, int], IsometricTile] = self.generate_tiles()
        self.quadtree = self.generate_quadtree(columns, rows, tile_height)
        IsometricMap.instance = IsometricTile.map = self

    def find_terrains(self) -> Dict[str, Texture]:
        return {
            name: load_texture(f'{name}.png', 0, 0, self.tile_width, self.tile_height)
            for name in ('grass', 'sand', 'water')
        }

    def generate_tiles(self) -> Dict[Tuple[int, int], IsometricTile]:
        tiles = {}
        columns, rows, tile_width = self.columns, self.rows, self.tile_width
        terrains = list(self.find_terrains().items())
        find_iso_grid = self.iso_grid_to_position
        append_to_grid_gizmo = self.grid_gizmo.append
        append_to_terrain_tiles = self.game.terrain_tiles.append
        grids_to_positions_2d_array = self._grids_to_positions
        for row in range(rows):
            for col in range(columns):
                idx = row * columns + col + 1
                tile_x, tile_y = find_iso_grid(col, row)
                sprite = Sprite(center_x=tile_x, center_y=tile_y, hit_box_algorithm='None')
                terrain, sprite.texture = random.choice(terrains)   # terrains[idx % len(terrains)] - makes checked area
                tile = IsometricTile(idx, col, row, tile_x, tile_y, 0, tile_width, terrain, sprite=sprite)
                gizmo = create_line_strip(tile.points, WHITE)
                tiles[(col, row)] = tile
                append_to_grid_gizmo(gizmo)
                append_to_terrain_tiles(sprite)
                grids_to_positions_2d_array[row][col] = tile_x, tile_y
        return tiles

    def generate_quadtree(self, columns, rows, tile_height) -> IsometricQuadTree:
        if rows == columns or MAX_COLS_TO_ROWS_RATIO in (rows // columns, columns // rows):
            quad_size = (columns + rows) * tile_height
        else:
            quad_size, columns, rows = resize_quadtree_outside_map(columns, rows, tile_height)

        w_ratio = columns / (columns + rows)
        h_ratio = rows / (rows + columns)

        quad_x, y = self.iso_grid_to_position(columns // 2, rows // 2)
        quad_y = y + tile_height // 2
        return IsometricQuadTree(quad_x, quad_y, quad_size, quad_size, w_ratio, h_ratio)

    def grids_to_positions(self, grid: Tuple[int, int]) -> Tuple[int, int]:
        return self._grids_to_positions[grid[1]][grid[0]]

    def iso_grid_to_position(self, gx: int, gy: int, gz: int = 0) -> Tuple[int, int]:
        """Convert isometric grid coordinates (gx, gy) to cartesian coordinates (e.g. mouse cursor position)."""
        if IsometricMap.instance is not None:
            return self._grids_to_positions[clamp(gy, self.rows - 1)][clamp(gx, self.columns - 1)]
            # return self._grids_to_positions[gy][gx]
        x, y = self.origin_tile_xy
        pos_x = (x + (gx - gy) * (self.tile_width * 0.5)) // 1
        pos_y = (y - (gx + gy) * (self.tile_height * 0.5) + gz) // 1
        return pos_x, pos_y

    def pos_to_iso_grid(self, pos_x: int, pos_y: int) -> Tuple[int, int] | None:
        """Convert (x, y) position (e.g. mouse cursor position) to isometric grid coordinates."""
        iso_x = pos_x - (self.width * 0.5)
        iso_y = -pos_y + self.height
        width = self.tile_width * 0.5
        a, b, c, d = invert_matrix(width, -width, width * 0.5, width * 0.5)
        grid = int(iso_x * a + iso_y * b), int(iso_x * c + iso_y * d)
        return grid if grid in self.tiles else None

    def position_to_node(self, x: Number, y: Number) -> Optional[IsometricTile]:
        return self.grid_to_tile(self.pos_to_iso_grid(x, y))

    def grid_to_tile(self, grid: Tuple[int, int]) -> Optional[IsometricTile]:
        return self.tiles.get(grid, self.nonexistent_node)

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

    def adjacent_grids(self, gx: int, gy: int) -> List[Tuple[int, int]]:
        return [adj for adj in [(gx + x, gy + y) for (x, y) in ADJACENCY_MATRIX] if adj in self.tiles]

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

    def get_valid_position(self, position: Optional[NormalizedPoint] = None) -> NormalizedPoint:
        """
        Get new, existing position on the isometric map, or return the same position provided as parameter, if it is a
        valid position on the isometric map.

        :param position: Optional[NormalizedPoint] -- if left to default None, returns random, valid position
        :return: Tuple[int, int]
        """
        return position if self.quadtree.in_bounds(Coordinate(position)) else self.get_random_position()

    def get_random_position(self, near: Optional[Tuple[int, int]] = None, min_distance: int = 0, max_distance: int = 0) -> NormalizedPoint:
        """
        returns a random position on the isometric map. It can either return a completely random position or a position
        near a specified tile, within a specified minimum and maximum distance.
        """
        if near is not None:
            near = self.position_to_node(*near)
            if near is None:
                raise ValueError("Position is invalid.")
        return self.get_random_tile(near, min_distance, max_distance).position

    def get_random_tile(self, near_tile: Optional[IsometricTile] = None, min_distance: int = 0, max_distance: int = 0) -> Optional[IsometricTile]:
        if near_tile is not None:
            if not (0 < min_distance < max_distance):
                raise ValueError('min_distance must be greater than 0 and less than max_distance!')
            predicate = max_distance_between_tiles(near_tile, min_distance, max_distance) if max_distance else None
            return self.get_random_walkable_tile(predicate=predicate)
        else:
            return self.get_random_walkable_tile()

    def get_random_walkable_tile(self, predicate: Optional[Callable[[IsometricTile], bool]] = None) -> Optional[IsometricTile]:
        if predicate is not None:
            filtered_tiles = [tile for tile in self.tiles.values() if tile.is_walkable and predicate(tile)]
        else:
            filtered_tiles = [tile for tile in self.tiles.values() if tile.is_walkable]
        return random.choice(filtered_tiles)

    def get_all_walkable_tiles(self, predicate: Optional[Callable[[IsometricTile], bool]] = None) -> Generator[IsometricTile]:
        if predicate is not None:
            return (tile for tile in self.tiles.values() if tile.is_walkable and predicate(tile))
        else:
            return (tile for tile in self.tiles.values() if tile.is_walkable)

    def draw(self, editor_mode: bool = False):
        if editor_mode:
            self.grid_gizmo.draw()
            self.quadtree.draw()
        for tile in list(self.tiles.values())[:]:
            tile.draw()
            
    def save(self):
        # TODO: reimplement this method to allow saving Game!
        raise NotImplementedError


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

        self.quad_id = None

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
    def left(self) -> Tuple[int, int]:
        return self.points[0]

    @property
    def top(self) -> Tuple[int, int]:
        return self.points[1]

    @property
    def right(self) -> Tuple[int, int]:
        return self.points[2]

    @property
    def bottom(self) -> Tuple[int, int]:
        return self.points[3]

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
        return self.terrain_type.is_water

    @property
    def is_navigable(self):
        return self.is_water and self._unit is None

    @property
    def is_walkable(self) -> bool:
        """
        Use it to find if node is not blocked at the moment by units or
        buildings.
        """
        return self.terrain_type.is_ground and self.is_pathable and self._unit is None

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

    def __del__(self):
        IsometricTile.instance = None


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
        self.leader_waypoints = []
        self.units_waypoints = {unit: [] for unit in units}
        self.active = False
        self.loop = False

    def __contains__(self, unit: Unit) -> bool:
        return unit in self.units

    def __bool__(self):
        return bool(self.units)

    def add_waypoint(self, x: int, y: int):
        x, y = normalize_position(x, y)
        if len(self.leader_waypoints) > 1 and (x, y) == self.leader_waypoints[0]:
            self.loop = True
            Pathfinder.instance.finish_waypoints_queue()
        else:
            self.leader_waypoints.append((x, y))
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
        self.map: IsometricMap = IsometricMap.instance
        self.leader = units[0]
        self.destination = position_to_map_grid(x, y)
        self.units_paths: Dict[Unit, List] = {unit: [] for unit in units}
        self.reset_units_navigating_groups(units)
        self.reverse_units_paths()
        if self.leader.is_controlled_by_local_human_player:
            self.add_visible_indicators_of_destinations(units)

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
        start = self.leader.current_tile.grid
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

    def add_visible_indicators_of_destinations(self, units: List[Unit]):
        if not units:
            return
        destinations = self.create_units_group_paths(units)
        tiles = [self.map.grid_to_tile(g) for g in destinations]
        positions = [tile.position for tile in tiles]
        self.map.game.units_ordered_destinations.new_destinations(positions, tiles, units)

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
        if self.map.grid_to_tile(destination).is_walkable:
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
                               required_waypoints: int) -> List[Tuple[int, int]]:
        """
        Find requested number of valid waypoints around requested position.
        """
        center = self.map.pos_to_iso_grid(x, y)
        if required_waypoints == 1:
            return [center, ]
        radius = 1
        waypoints = []
        tiles = self.map.tiles
        while len(waypoints) < required_waypoints:
            waypoints = [w for w in calculate_circular_area(*center, radius) if
                         w in tiles and tiles[w].is_walkable]
            radius += 1
        waypoints.sort(key=lambda w: dist(w, center))
        return [w[0] for w in zip(waypoints, range(required_waypoints))]

    def get_closest_walkable_position(self, x, y) -> NormalizedPoint:
        if (node := self.map.position_to_node(x, y)).is_walkable:
            return node.position
        nearest_walkable = None
        while nearest_walkable is None:
            adjacent = node.adjacent_tiles
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
