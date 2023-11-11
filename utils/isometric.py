from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache, singledispatch
from typing import Tuple, List, Dict, Optional, Collection, Set, Union, Any

from arcade import (
    Window,
    Sprite,
    SpriteList,
    ShapeElementList,
    run,
    load_texture,
    draw_polygon_filled,
    create_line_strip, Texture, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_LEFT, draw_text
)

# from buildings.buildings import Building
# from gameobjects.gameobject import GameObject
from map.quadtree import IsometricQuadTree
# from units.units import Unit
from utils.colors import WHITE, GREEN, rgb_to_rgba
from utils.constants import DIAGONAL_DIST, VERTICAL_DIST
from utils.priority_queue import PriorityQueue
from utils.singleton import SingletonMeta

ADJACENCY_MATRIX = ((-1, -1), (-1, 0), (0, -1), (0, 1), (1, 1), (1, 0), (1, -1), (-1, 1))


def invert_matrix(a, b, c, d):
    det = (1 / (a * d - b * c))
    return det * d, det * -b, det * -c, det * a


@lru_cache(maxsize=62500)
@singledispatch
def map_grid_to_position(grid: Any, *args) -> tuple[int, int]:
    """Return (x, y) position of the map-grid-normalised Node."""
    raise NotImplementedError


@map_grid_to_position.register
def _(grid: tuple) -> tuple[int, int]:
    x, y = IsometricMap().grids_to_positions[grid]
    return pos_to_iso_grid(x, y)


@map_grid_to_position.register
def _(grid_x: int, grid_y: int) -> tuple[int, int]:
    x, y = IsometricMap().grids_to_positions[(grid_x, grid_y)]
    return pos_to_iso_grid(x, y)


def pos_to_iso_grid(pos_x: int, pos_y: int) -> Tuple[int, int] | None:
    """Use this, function from other scripts to convert positions to iso grid coordinates."""
    return IsometricMap().pos_to_iso_grid(pos_x, pos_y)


def adjacent_distance(this: Tuple[int, int], adjacent: Tuple[int, int]) -> int:
    return DIAGONAL_DIST if diagonal(this, adjacent) else VERTICAL_DIST


def diagonal(first_grid: Tuple[int, int], second_grid: Tuple[int, int]) -> bool:
    return first_grid[0] == second_grid[0] and first_grid[1] == second_grid[1]


@dataclass
class Coordinate:
    __slots__ = ['position', 'faction']
    id = 1
    position: Tuple[float, float]
    faction: Faction

    def __hash__(self):
        return hash(id(self))



class Faction:
    id = 1


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


class IsometricMap(metaclass=SingletonMeta):
    """
    The IsometricMap class represents a map in an isometric game. It generates and manages isometric tiles, handles
    conversions between isometric grid coordinates and cartesian coordinates, and provides methods for querying and
    manipulating the map.
    """
    game = None

    def __init__(self, window: Window = None, settings: Dict[str, Any] = None):
        self.window = window
        self.tiles = {}
        self.grids_to_positions: Dict[Tuple[int, int], Tuple[int, int]] = {}
        self.tile_width = settings['tile_width']
        self.tile_height = self.tile_width // 2
        self.rows = settings['rows']
        self.columns = settings['columns']
        self.width = self.columns * self.tile_width
        self.height = self.rows * self.tile_height
        self.origin_tile_xy = self.width // 2, self.height - self.tile_height // 2
        self.grid_gizmo = ShapeElementList()
        self.tiles_sprites = SpriteList(use_spatial_hash=True, is_static=True)
        self.terrains = self.find_terrains()
        self.tiles: Dict[Tuple[int, int], IsometricTile] = self.generate_tiles()
        self.quadtree = self.generate_quadtree()
        IsometricTile.map = self

    def find_terrains(self) -> Dict[str, Texture]:
        return {
            name: load_texture(f'{name}.png', 0, 0, self.tile_width, self.tile_height)
            for name in ('grass', 'sand', 'water')
        }

    # rows 10 * 50
    # columns 20 * 100
    # width 100

    def generate_quadtree(self) -> IsometricQuadTree:
        # bounding box
        w_ratio = self.columns / (self.columns + self.rows)
        h_ratio = self.rows / (self.rows + self.columns)
        print(w_ratio, h_ratio)

        quad_x, y = self.iso_grid_to_position(self.columns // 2, self.rows // 2)
        quad_y = y + self.tile_height // 2

        quad_width = (self.columns + self.rows) * self.tile_height
        quad_height = (self.columns + self.rows) * self.tile_height

        return IsometricQuadTree(quad_x, quad_y, quad_width, quad_height, w_ratio, h_ratio)

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
                self.tiles_sprites.append(sprite)
                self.grids_to_positions[(col, row)] = tile_x, tile_y
        return tiles

    def iso_grid_to_position(self, gx: int, gy: int, gz: int = 0) -> Tuple[int, int]:
        """Convert isometric grid coordinates (gx, gy) to cartesian coordinates (e.g. mouse cursor position)."""
        x, y = self.origin_tile_xy
        pos_x = int(x + (gx - gy) * (self.tile_width * 0.5))
        pos_y = int(y - (gx + gy) * (self.tile_height * 0.5) + gz)
        return pos_x, pos_y

    def pos_to_iso_grid(self, pos_x: int, pos_y: int) -> Tuple[int, int] | None:
        """Convert (x, y) position (e.g. mouse cursor position) to isometric grid coordinates."""
        left, _, bottom, _ = self.window.get_viewport()
        iso_x = pos_x - (self.width * 0.5 - left)
        iso_y = -pos_y - bottom + self.height
        width = self.tile_width * 0.5
        a, b, c, d = invert_matrix(width, -width, width * 0.5, width * 0.5)
        grid = int(iso_x * a + iso_y * b), int(iso_x * c + iso_y * d)
        return grid if grid in self.tiles else None

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

    def position_to_node(self, x: int, y: int) -> IsometricTile:
        iso_grid = self.pos_to_iso_grid(x, y)
        return self.tiles.get(iso_grid)

    def draw(self, editor_mode: bool = False):
        if editor_mode:
            self.grid_gizmo.draw()
            self.quadtree.draw()
        else:
            self.tiles_sprites.draw()
        for tile in list(self.tiles.values())[:]:
            tile.draw()


class IsometricTile:
    map: Optional[IsometricMap] = None

    def __init__(self, idx: int, gx: int, gy: int, x: int, y: int, z: int, width: int, terrain: str, sprite: Sprite = None):
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


class IsometricWindow(Window):
    # 20 : 60, 30 : 90, 10 : 30, (1:1, 1:3)
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        map_settings = {
            'rows': 30,
            'columns': 30,
            'tile_width': 100,
        }
        self.map = IsometricMap(self, map_settings)

        # debugging stuff
        self.cursor = 0, 0
        self.world_cursor = 0, 0
        self.current_tile = None
        self.start_point = None
        self.end_point = None
        self.path = None
        self.quadtree = None
        self.faction = Faction()

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)

    def on_draw(self):
        self.clear()
        self.map.draw(editor_mode=True)
        left, *_, top = self.get_viewport()
        # debug cursor
        draw_text(f'screen:{self.cursor}', left + 30, top - 30, WHITE)
        draw_text(f'world: {self.world_cursor}', left + 30, top - 60, WHITE)
        # debug pathfinding
        if self.path:
            for (gx, gy) in self.path:
                points = self.map.tiles[(gx, gy)].points
                draw_polygon_filled(points, rgb_to_rgba(GREEN, 125))

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        self.cursor = x, y, self.quadtree.id if self.quadtree is not None else '...'
        self.highlight_pointed_tile(x, y)

    def highlight_pointed_tile(self, x, y):
        if (tile := self.map.position_to_node(x, y)) is not None:
            if self.current_tile not in (tile, None):
                self.current_tile.pointed = False
            self.current_tile = tile
            tile.pointed = True
        else:
            self.current_tile = None

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        left, _, bottom, _ = self.get_viewport()
        try:
            ix, iy = self.map.position_to_node(x, y).position
        except AttributeError:
            raise AttributeError(f'Position {x, y} yielded no Tile!')
        self.quadtree = self.map.quadtree.insert(entity=Coordinate((ix, iy), self.faction),)
        # debugging stuff
        if button == MOUSE_BUTTON_RIGHT:
            self.clear_pathfinding_debug()
        elif self.current_tile is not None:
            self.highlight_adjacent_tiles()
            self.debug_pathfinding()
            print(self.current_tile)

    def circular_area(self):
        area = calculate_circular_area(*self.current_tile.grid, 2)
        area = [self.map.tiles.get(g) for g in area if g is not None]
        for tile in area:
            tile.pointed = True

    def debug_pathfinding(self):
        if self.start_point is None:
            self.start_point = self.current_tile.grid
        elif self.end_point is None and self.end_point != self.start_point:
            self.end_point = self.current_tile.grid
            self.path = a_star(self.map, self.start_point, self.end_point)

    def clear_pathfinding_debug(self):
        self.start_point = self.end_point = None
        if self.path:
            self.path.clear()

    def on_mouse_release(self, x: float, y: float, button: int, modifiers: int):
        if button == MOUSE_BUTTON_LEFT and self.current_tile is not None:
            self.highlight_adjacent_tiles()

    def highlight_adjacent_tiles(self):
        for adjacent in self.current_tile.adjacent_tiles:
            adjacent.pointed = not adjacent.pointed

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float, buttons: int, modifiers: int):
        old_left, _, old_bottom, _ = self.get_viewport()
        new_left = old_left - dx
        new_right = new_left + self.width
        new_bottom = old_bottom - dy
        new_top = new_bottom + self.height
        self.set_viewport(new_left, new_right, new_bottom, new_top)


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


@lru_cache(maxsize=None)
def calculate_circular_area(grid_x, grid_y, max_distance):
    radius = max_distance * 1.6
    observable_area = []
    for x in range(-max_distance, max_distance + 1):
        dist_x = abs(x)
        for y in range(-max_distance, max_distance + 1):
            dist_y = abs(y)
            total_distance = dist_x + dist_y
            if total_distance < radius:
                grid = (grid_x + x, grid_y + y)
                observable_area.append(grid)
    return observable_area


if __name__ == '__main__':
    window = IsometricWindow(2000, 1200, "Isometric map")
    run()
