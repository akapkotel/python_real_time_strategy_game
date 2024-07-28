#!/usr/bin/env python
from __future__ import annotations

import math
import random
from enum import IntEnum

from math import dist
from collections import deque, defaultdict
from functools import partial, cached_property, lru_cache, singledispatch
from typing import (
    Deque, Dict, List, Optional, Set, Tuple, Union, Generator, Collection, Any,
)

from arcade import Sprite, Texture, load_spritesheet, make_soft_square_texture

from game import PROFILING_LEVEL
from utils.constants import TILE_WIDTH, TILE_HEIGHT, VERTICAL_DIST, DIAGONAL_DIST, ADJACENT_OFFSETS, \
    OPTIMAL_PATH_LENGTH, NormalizedPoint, MapPath, PathRequest, TreeID
from gameobjects.gameobject import GameObject
from utils.colors import SAND, WATER_SHALLOW, BLACK
from utils.data_types import GridPosition, Number
from utils.priority_queue import PriorityQueue
from utils.scheduling import EventsCreator
from utils.functions import (
    get_path_to_file, all_files_of_type_named
)
from map.quadtree import CartesianQuadTree
from utils.game_logging import log_here, log_this_call
from utils.timing import timer
from utils.geometry import calculate_circular_area

# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!


MAP_TEXTURES = {
    'mud': load_spritesheet(
        get_path_to_file('mud_tileset_6x6.png'), 60, 50, 4, 16, 0)
}

random_value = random.random

MAP_TILE_TEXTURE_GROUND = make_soft_square_texture(TILE_WIDTH, SAND, 255, 255)
MAP_TILE_TEXTURE_WATER = make_soft_square_texture(TILE_WIDTH, WATER_SHALLOW, 255, 255)
MAP_TILE_TEXTURE_VOID = make_soft_square_texture(TILE_WIDTH, BLACK, 255, 0)


def position_to_map_grid(x: Number, y: Number) -> GridPosition:
    """Return map-grid-normalised position."""
    return int(x // TILE_WIDTH), int(y // TILE_HEIGHT)


def normalize_position(x: Number, y: Number) -> NormalizedPoint:
    return map_grid_to_position((int(x // TILE_WIDTH), int(y // TILE_HEIGHT)))


@lru_cache(maxsize=62500)
@singledispatch
def map_grid_to_position(grid: Any, *args) -> tuple[int, int]:
    """Return (x, y) position of the map-grid-normalised Node."""
    raise NotImplementedError


@map_grid_to_position.register
def _(grid: tuple) -> tuple[int, int]:
    return (
        int(grid[0] * TILE_WIDTH + (TILE_WIDTH // 2)),
        int(grid[1] * TILE_HEIGHT + (TILE_HEIGHT // 2))
    )


@map_grid_to_position.register
def _(grid_x: int, grid_y: int) -> tuple[int, int]:
    return (
        int(grid_x * TILE_WIDTH + (TILE_WIDTH // 2)),
        int(grid_y * TILE_HEIGHT + (TILE_HEIGHT // 2))
    )


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
    texture.image.transpose(random.randint(0, 6))
    return texture


def set_terrain_texture(terrain_type: str,
                        index: int = None,
                        rotation: int = None) -> Tuple[Texture, int, int]:
    index = index or random.randint(0, len(MAP_TEXTURES[terrain_type]) - 1)
    texture: Texture = MAP_TEXTURES[terrain_type][index]
    rotation = rotation or random.randint(0, 6)
    texture.image.transpose(rotation)
    return texture, index, rotation


@timer(level=2, global_profiling_level=PROFILING_LEVEL, forced=False)
def a_star(current_map: Map,
           start: GridPosition,
           end: GridPosition,
           pathable: bool = False) -> Union[MapPath, bool]:
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
    map_nodes = current_map.nodes
    unexplored = PriorityQueue(start, heuristic(start, end))
    explored = set()
    previous: Dict[GridPosition, GridPosition] = {}

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
    return False  # no third pass, if there is no possible path!


def heuristic(start: GridPosition, end: GridPosition) -> int:
    dx = abs(start[0] - end[0])
    dy = abs(start[1] - end[1])
    return DIAGONAL_DIST * min(dx, dy) + VERTICAL_DIST * max(dx, dy)


def reconstruct_path(map_nodes: Dict[GridPosition, MapNode],
                     previous_nodes: Dict[GridPosition, GridPosition],
                     current_node: GridPosition) -> MapPath:
    path = [map_nodes[current_node]]
    while current_node in previous_nodes.keys():
        current_node = previous_nodes[current_node]
        path.append(map_nodes[current_node])
    return [node.position for node in path[::-1]]


class TerrainType(IntEnum):
    GROUND = 0
    WATER = 1
    VOID = 2


class Map:
    game = None
    instance = None

    def __init__(self, map_settings: Dict):
        MapNode.map = Map.instance = self
        self.rows = map_settings['rows']
        self.columns = map_settings['columns']
        self.grid_width = map_settings['grid_width']
        self.grid_height = map_settings['grid_height']
        self.width = self.columns * self.grid_width
        self.height = self.rows * self.grid_height

        self.nodes_data = map_settings.get('nodes', {})

        self.nodes: Dict[GridPosition, MapNode] = {}
        self.distances = {}

        self.quadtree = CartesianQuadTree(self.width // 2, self.height // 2, self.width, self.height)
        log_here(f'Generated QuadTree of depth: {self.quadtree.total_depth()}', console=True)

        self.generate_map_nodes_and_tiles()
        #  TODO: find efficient way to use these costs in pathfinding
        # self.calculate_distances_between_nodes()

        self.prepare_planting_trees(map_settings)

        log_here('Map was initialized successfully...', console=True)

    def prepare_planting_trees(self, map_settings):
        trees = map_settings.get('trees') or self.generate_random_trees()
        self.game.after_load_functions.append(partial(self.plant_trees, trees))

    @log_this_call()
    def plant_trees(self, trees: Dict[GridPosition, int]):
        for node in self.nodes.values():
            if (tree_type := trees.get(node.grid)) is not None:
                self.game.spawn(f'tree_leaf_{tree_type}', position=node.position)

    def generate_random_trees(self) -> Dict[GridPosition, int]:
        trees = len(all_files_of_type_named('.png', 'resources', 'tree_')) + 1
        forbidden = set(self.get_nodes_by_row(self.rows) + self.get_nodes_by_row(0) + self.get_nodes_by_column(self.columns) + self.get_nodes_by_column(0))
        return {grid: random.randrange(1, trees) for grid, node in self.nodes.items()
                if random.random() < self.game.settings.percent_chance_for_spawning_tree and node not in forbidden}

    def save(self) -> Dict:
        return {
            'rows': self.rows,
            'columns': self.columns,
            'grid_width': self.grid_width,
            'grid_height': self.grid_height,
            'nodes_data': self.nodes_data,
            'trees': {g: n.tree.save() for (g, n) in self.nodes.items() if n.tree is not None}
        }

    def __str__(self) -> str:
        return f'Map(height: {self.height}, width: {self.width}, nodes: {len(self.nodes)})'

    def __len__(self) -> int:
        return len(self.nodes)

    def __getitem__(self, item):
        return self.nodes.get(item, self.nonexistent_node)

    def __contains__(self, item: GridPosition):
        return item in self.nodes

    def is_inside_map_grid(self, grid: Collection[GridPosition]) -> Set[GridPosition]:
        return {g for g in grid if g in self.nodes}

    def on_map_area(self, x: Number, y: Number) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def walkable(self, grid) -> bool:
        try:
            return self.nodes[grid].is_walkable
        except KeyError:
            return False

    def walkable_adjacent(self, x, y) -> Set[MapNode]:
        return {n for n in self.adjacent_nodes(x, y) if n.is_walkable}

    def pathable_adjacent(self, x, y) -> Set[MapNode]:
        return {n for n in self.adjacent_nodes(x, y) if n.is_pathable}

    def adjacent_nodes(self, x: Number, y: Number) -> Set[MapNode]:
        return {
            self.nodes[adj] for adj in self.is_inside_map_grid(adjacent_map_grids(x, y))
        }

    def position_to_node(self, x: Number, y: Number) -> MapNode:
        return self.grid_to_node(position_to_map_grid(x, y))

    def grid_to_node(self, grid: GridPosition) -> MapNode:
        return self.nodes.get(grid)

    @property
    def random_walkable_node(self) -> MapNode:
        return random.choice(tuple(self.all_walkable_nodes))

    @property
    def all_walkable_nodes(self) -> Generator[MapNode, Any, None]:
        return (node for node in self.nodes.values() if node.is_walkable)

    @timer(1, global_profiling_level=PROFILING_LEVEL)
    @log_this_call(console=True)
    def generate_map_nodes_and_tiles(self):
        columns, rows = self.columns, self.rows
        for x in range(columns):
            for y in range(rows):
                terrain = TerrainType.VOID if x in(0, columns) or y in (0, rows) else TerrainType.GROUND
                self.nodes[(x, y)] = node = MapNode(x, y, terrain)
                self.create_map_sprite(*node.position, node.terrain_type)
        log_here(f'Generated {len(self.nodes)} map nodes.', console=True)

    def create_map_sprite(self, x: int, y: int, terrain_type: TerrainType):
        sprite = Sprite(center_x=x, center_y=y, hit_box_algorithm='None')
        sprite.texture = {
            # terrain_type.GROUND: MAP_TILE_TEXTURE_GROUND,
            terrain_type.GROUND: random_terrain_texture(),
            terrain_type.VOID: MAP_TILE_TEXTURE_VOID,
            terrain_type.WATER: MAP_TILE_TEXTURE_WATER
        }[terrain_type]
        # try:
        #     terrain_type, index, rotation = self.nodes_data[(x, y)]
        #     t, i, r = set_terrain_texture(terrain_type, index, rotation)
        # except KeyError:
        #     terrain_type = 'mud'
        #     t, i, r = set_terrain_texture(terrain_type)
        #     self.nodes_data[(x, y)] = terrain_type, i, r
        # sprite.texture = t
        self.game.terrain_tiles.append(sprite)

    def find_map_regions(self):
        """
        All MapNodes which are intermediary connected or there is possible path connecting them, belong to the same map
        region, which allows for fast excluding impossible pathfinding calls - if start and destination belong to the
        different regions, we do not need call A-star algorithm.
        """
        ...

    def calculate_distances_between_nodes(self):
        for node in self.nodes.values():
            node.costs = costs_dict = {}
            for grid in self.is_inside_map_grid(adjacent_map_grids(*node.position)):
                adjacent_node = self.nodes[grid]
                distance = adjacent_distance(grid, adjacent_node.grid)
                # terrain_cost = node.terrain_cost + adjacent_node.terrain_cost
                node.costs[grid] = distance #  * terrain_cost
            self.distances[node.grid] = costs_dict

    def get_nodes_by_row(self, row: int) -> List[MapNode]:
        return [n for n in self.nodes.values() if n.grid[1] == row]

    def get_nodes_by_column(self, column: int) -> List[MapNode]:
        return [n for n in self.nodes.values() if n.grid[0] == column]

    def get_all_nodes(self) -> Generator[MapNode]:
        return (n for n in self.nodes.values())

    def get_random_position(self) -> NormalizedPoint:
        return random.choice([n.position for n in self.all_walkable_nodes])

    def get_valid_position(self, position: Optional[NormalizedPoint] = None) -> NormalizedPoint:
        """

        :param position: Optional[NormalizedPoint] -- if left to default None, returns random, valid position
        :return: NormalizedPoint
        """
        return position or self.get_random_position()

    def node(self, grid: GridPosition) -> MapNode:
        return self.nodes.get(grid, self.nonexistent_node)

    @cached_property
    def nonexistent_node(self) -> MapNode:
        node = MapNode(-1, -1, TerrainType.VOID)
        node.is_pathable = node._walkable = False
        return node


class MapNode:
    """
    Class representing a single point on Map which can be Units pathfinding
    destination and is associated with graphic-map-tiles displayed on the
    screen.
    """
    map: Optional[Map] = None

    def __init__(self, x: Number, y: Number, terrain_type: TerrainType):
        self.grid = int(x), int(y)
        self.position = self.x, self.y = map_grid_to_position(self.grid)
        self.terrain_type: TerrainType = terrain_type
        self.map_region: Optional[int] = None
        self.costs = None

        self._pathable = terrain_type > -1

        self._tree: Optional[TreeID] = None
        self._unit: Optional[Unit] = None
        self._building: Optional[Building] = None
        self._static_gameobject: Optional[GameObject, TreeID] = None

    def __str__(self) -> str:
        return f'MapNode(position: {self.position})'

    def __repr__(self) -> str:
        return f'MapNode(x={self.x}, y={self.y}, terrain_type={self.terrain_type})'

    def in_bounds(self, *args, **kwargs):
        return self.map.is_inside_map_grid(*args, **kwargs)

    def diagonal_to_other(self, other: GridPosition):
        return self.grid[0] != other[0] and self.grid[1] != other[1]

    @property
    def tree(self) -> Optional[TreeID]:
        return self._tree

    @tree.setter
    def tree(self, value: Optional[TreeID]):
        self._static_gameobject = self._tree = value

    def remove_tree(self):
        if self._tree is not None:
            for obj in self.map.game.static_objects:
                if obj.map_node is self:
                    obj.kill()

    @property
    def unit(self) -> Optional[Unit]:
        return self._unit

    @unit.setter
    def unit(self, value: Optional[Unit]):
        self._unit = value

    @property
    def building(self) -> Optional[Building]:
        return self._building

    @building.setter
    def building(self, value: Optional[Building]):
        self._static_gameobject = self._building = value

    @property
    def unit_or_building(self) -> Optional[Union[Unit, Building]]:
        return self._unit or self._building

    @property
    def static_gameobject(self) -> Optional[GameObject, TreeID]:
        return self._static_gameobject

    @static_gameobject.setter
    def static_gameobject(self, value: Optional[GameObject, TreeID]):
        self._static_gameobject = value

    @property
    def is_water(self) -> bool:
        return self.terrain_type is TerrainType.WATER

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
        return any(n.building for n in self.adjacent_nodes)

    @property
    def walkable_adjacent(self) -> Set[MapNode]:
        return {n for n in self.adjacent_nodes if n.is_walkable}

    @property
    def pathable_adjacent(self) -> Set[MapNode]:
        return {n for n in self.adjacent_nodes if n.is_pathable}

    @cached_property
    def adjacent_nodes(self) -> Set[MapNode]:
        return self.map.adjacent_nodes(*self.position)

    def __getstate__(self) -> Dict:
        saved_node = self.__dict__.copy()
        for key in ('_unit', '_building'):
            saved_node[key] = None
        return saved_node

    def __setstate__(self, state):
        self.__dict__.update(state)


class WaypointsQueue:
    """
    When human player gives his Units movement orders with left CTRL key
    pressed, he can plan multiple consecutive moves ahead, which would be
    executed when LCTRL is released, or when player points back to the first
    waypoint of the queue. The second scenario would produce a looped path to
    patrol.
    """

    def __init__(self, units: List[Unit]):
        self.map = Map.instance
        self.units = [u for u in units]
        self.waypoints = []
        self.units_waypoints = {unit: [] for unit in units}
        self.active = False
        self.visible = True
        self.loop = False
        self.map.game.units_ordered_destinations.new_waypoints_queue(self)

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
        for unit in (u for u in self.units):
            if waypoints := self.units_waypoints[unit]:
                self.evaluate_unit_waypoints(unit, waypoints)
            else:
                unit.waypoints_queue = None
                self.units.remove(unit)

    def evaluate_unit_waypoints(self, unit, waypoints):
        destination = waypoints[-1]
        if unit.reached_destination(destination):
            removed = waypoints.pop()
            if self.loop:
                waypoints.insert(0, removed)
        elif not (unit.has_destination or unit.is_heading_to(destination)):
            unit.move_to(destination, forced=True)

    def start(self):
        self.active = True
        for unit, waypoints in self.units_waypoints.items():
            waypoints.reverse()


class NavigatingUnitsGroup:
    """
    To avoid calling Pathfinder A* algorithm for very long paths for
    many Units at once, we use this class. NavigatingUnitsGroup call a_star
    method for the full path only once, and then divides this path for shorter
    ones and call a_star for particular units for those shorter distances.
    """

    def __init__(self, units: List[Unit], x: Number, y: Number, forced: bool = False):
        self.map = Map.instance
        self.leader = max(units, key=lambda u: u.experience, default=units[0])
        self.destination = position_to_map_grid(x, y)
        self.forced_destination = forced
        self.units_paths: Dict[Unit, List] = {unit: [] for unit in units}
        self.reset_units_navigating_groups(units)
        destinations = self.create_units_group_paths(units)
        self.reverse_units_paths()
        if self.leader.is_controlled_by_human_player:
            self.add_visible_indicators_of_destinations(destinations, units)

    def __str__(self) -> str:
        return f'NavigatingUnitsGroup(units:{len(self.units_paths)})'

    def __contains__(self, unit: Unit) -> bool:
        return unit in self.units_paths.keys()

    def __bool__(self) -> bool:
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
        leader_path: List[GridPosition] = a_star(self.map, start, self.destination, True)
        if len(leader_path) > OPTIMAL_PATH_LENGTH:
            self.slice_paths(units, leader_path)
        x, y = leader_path[-1]
        destinations = Pathfinder.instance.get_group_of_waypoints(x, y, len(units))
        self.add_waypoints_to_units_paths(units, destinations)
        return destinations

    def slice_paths(self, units: List[Unit], leader_path: List[GridPosition]):
        for i in range(1, len(leader_path) // OPTIMAL_PATH_LENGTH, OPTIMAL_PATH_LENGTH):
            step = leader_path[i * OPTIMAL_PATH_LENGTH]
            units_steps = Pathfinder.instance.get_group_of_waypoints(*step, len(units))
            self.add_waypoints_to_units_paths(units, units_steps)

    def add_waypoints_to_units_paths(self, units: List[Unit], waypoints: List[GridPosition]):
        for unit, grid in zip(units, waypoints):
            self.units_paths[unit].append(grid)

    def reverse_units_paths(self):
        """
        Reverse waypoints list of each Unit, to allow consuming it from the
        end using cheaply pop() method.
        """
        for unit, steps in self.units_paths.items():
            steps.reverse()

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

    def find_next_path_for_unit(self, unit, steps):
        destination = steps[-1]
        if unit.reached_destination(destination):
            steps.pop()
        elif not (unit.has_destination or unit.is_heading_to(destination)):
            unit.move_to(destination, self.forced_destination)

    @staticmethod
    def remove_finished_paths(finished_units: List[Unit]):
        for unit in finished_units:
            unit.forced_destination = False
            unit.set_navigating_group(navigating_group=None)


class Pathfinder(EventsCreator):
    """
    This class manages finding and assigning paths for Units in game. It also
    creates, updates and removes WaypointsQueues and NavigatingUnitsGroups.
    """
    instance: Optional[Pathfinder] = None

    def __init__(self, map: Map):
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
            queue.visible = False
            queue.start()
        self.created_waypoints_queue = None
        self.map.game.units_manager.waypoints_mode = False

    def navigate_units_to_destination(self, units: List[Unit], x: int, y: int, forced: bool = False):
        if not self.map.position_to_node(x, y).is_walkable:
            x, y = self.get_closest_walkable_position(x, y)
        self.navigating_groups.append(NavigatingUnitsGroup(units, x, y, forced))

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
            if path := a_star(self.map, start, destination):
                return unit.follow_new_path(path)
        self.request_path(unit, start, destination)

    def update_waypoints_queues(self):
        for queue in (q for q in self.waypoints_queues if q.active):
            if queue:
                queue.update()
            else:
                self.waypoints_queues.remove(queue)
                self.map.game.units_ordered_destinations.remove_queue(queue)

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
        center = position_to_map_grid(x, y)
        if required_waypoints is 1:
            return [center, ]
        waypoints: List[Tuple[int, int]] = []
        nodes = self.map.nodes
        radius = 1
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

    def get_closest_walkable_node(self, x, y) -> MapNode:
        nx, ny = self.get_closest_walkable_position(x, y)
        return self.map.position_to_node(nx, ny)


if __name__:
    # these imports are placed here to avoid circular-imports issue:
    from players_and_factions.player import PlayerEntity
    from units.units import Unit
    from buildings.buildings import Building
