#!/usr/bin/env python
from __future__ import annotations

import random

from collections import deque, defaultdict
from functools import partial, cached_property
from typing import (
    Deque, Dict, List, Optional, Set, Tuple, Union, Generator, Collection,
    DefaultDict
)

from arcade import Sprite, Texture, load_spritesheet

from game import PROFILING_LEVEL, SECTOR_SIZE, TILE_HEIGHT, TILE_WIDTH
from gameobjects.gameobject import GameObject
from utils.data_types import GridPosition, Number, SectorId
from utils.enums import TerrainCost
from utils.scheduling import EventsCreator
from utils.functions import (
    get_path_to_file, all_files_of_type_named
)
from utils.logging import log, logger
from utils.timing import timer
from utils.geometry import distance_2d, calculate_circular_area

# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!


PATH = 'PATH'
VERTICAL_DIST = 10
DIAGONAL_DIST = 14  # approx square root of 2
MAP_TEXTURES = {
    'mud': load_spritesheet(
        get_path_to_file('mud_tileset_6x6.png'), 60, 45, 4, 16, 0)
}
ADJACENT_OFFSETS = [
    (-1, -1), (-1, 0), (-1, +1), (0, +1), (0, -1), (+1, -1), (+1, 0), (+1, +1)
]
OPTIMAL_PATH_LENGTH = 50

random_value = random.random

# typing aliases:
NormalizedPoint = Tuple[int, int]
MapPath = Union[List[NormalizedPoint], List[GridPosition]]
PathRequest = Tuple['Unit', GridPosition, GridPosition]
TreeID = int


def position_to_map_grid(x: Number, y: Number) -> GridPosition:
    """Return map-grid-normalised position."""
    return int(x // TILE_WIDTH), int(y // TILE_HEIGHT)


def normalize_position(x: Number, y: Number) -> NormalizedPoint:
    return map_grid_to_position((int(x // TILE_WIDTH), int(y // TILE_HEIGHT)))


def map_grid_to_position(grid: GridPosition) -> NormalizedPoint:
    """Return (x, y) position of the map-grid-normalised Node."""
    return (
        int(grid[0] * TILE_WIDTH + TILE_WIDTH // 2),
        int(grid[1] * TILE_HEIGHT + TILE_HEIGHT // 2)
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
    texture.image.transpose(random.randint(0, 5))
    return texture


def set_terrain_texture(terrain_type: str,
                        index: int = None,
                        rotation: int = None) -> Tuple[Texture, int, int]:
    index = index or random.randint(0, len(MAP_TEXTURES[terrain_type]) - 1)
    texture = MAP_TEXTURES[terrain_type][index]

    rotation = rotation or random.randint(0, 5)
    texture.image.transpose(rotation)
    return texture, index, rotation


class Map:
    game = None
    instance = None

    def __init__(self, map_settings: Dict):
        MapNode.map = Sector.map = Map.instance = self
        self.rows = map_settings['rows']
        self.columns = map_settings['columns']
        self.grid_width = map_settings['grid_width']
        self.grid_height = map_settings['grid_height']
        self.width = self.columns * self.grid_width
        self.height = self.rows * self.grid_height

        try:
            self.nodes_data = map_settings['nodes']
        except KeyError:
            self.nodes_data = {}

        # map is divided for sectors containing 10x10 Nodes each to split
        # space for smaller chunks in order to make enemies-detection
        # faster: since each Unit could only scan it's current Sector and
        # adjacent ones instead of whole map for enemies:
        self.sectors: Dict[SectorId, Sector] = {}
        self.nodes: Dict[GridPosition, MapNode] = {}
        self.distances = {}

        self.generate_sectors()
        self.generate_nodes()
        # self.calculate_distances_between_nodes()
        # TODO: find efficient way to use these costs in pathfinding

        try:
            trees = map_settings['trees']
            self.game.after_load_functions.append(partial(self.plant_trees, trees))
        except KeyError:
            self.game.after_load_functions.append(self.plant_trees)

        log('Map was initialized successfully...', console=True)

    def save(self) -> Dict:
        return {
            'rows': self.rows,
            'columns': self.columns,
            'grid_width': self.grid_width,
            'grid_height': self.grid_height,
            'nodes_data': self.nodes_data,
            'trees': {g: n.tree for (g, n) in self.nodes.items() if n.tree is not None}
        }

    def __str__(self) -> str:
        return f'Map(height: {self.height}, width: {self.width}, nodes: {len(self.nodes)})'

    def __len__(self) -> int:
        return len(self.nodes)

    def __getitem__(self, item):
        return self.nodes.get(item, self.nonexistent_node)

    def __contains__(self, item: GridPosition):
        return item in self.nodes

    def in_bounds(self, grid: Collection[GridPosition]) -> Set[GridPosition]:
        return {g for g in grid if g in self.nodes}

    def on_map_area(self, x: Number, y: Number) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def walkable(self, grid) -> bool:
        try:
            return self.nodes[grid].walkable
        except KeyError:
            return False

    def walkable_adjacent(self, x, y) -> Set[MapNode]:
        return {n for n in self.adjacent_nodes(x, y) if n.walkable}

    def pathable_adjacent(self, x, y) -> Set[MapNode]:
        return {n for n in self.adjacent_nodes(x, y) if n.pathable}

    def adjacent_nodes(self, x: Number, y: Number) -> Set[MapNode]:
        return {
            self.nodes[adj] for adj in self.in_bounds(adjacent_map_grids(x, y))
        }

    def position_to_node(self, x: Number, y: Number) -> MapNode:
        return self.grid_to_node(position_to_map_grid(x, y))

    def grid_to_node(self, grid: GridPosition) -> MapNode:
        return self.nodes.get(grid)

    @property
    def random_walkable_node(self) -> MapNode:
        return random.choice(tuple(self.nodes.values()))

    @property
    def all_walkable_nodes(self) -> Generator[MapNode]:
        return (node for node in self.nodes.values() if node.walkable)

    def generate_sectors(self):
        for x in range(self.columns):
            sector_x = x // SECTOR_SIZE
            for y in range(self.rows):
                sector_y = y // SECTOR_SIZE
                self.sectors[(sector_x, sector_y)] = Sector((sector_x, sector_y))
        log(f'Created {len(self.sectors)} map sectors.', console=True)

    @timer(1, global_profiling_level=PROFILING_LEVEL)
    @logger(console=True)
    def generate_nodes(self):
        for x in range(self.columns):
            sector_x = x // SECTOR_SIZE
            for y in range(self.rows):
                sector_y = y // SECTOR_SIZE
                sector = self.sectors[(sector_x, sector_y)]
                self.nodes[(x, y)] = node = MapNode(x, y, sector)
                self.create_map_sprite(*node.position)
        log(f'Generated {len(self.nodes)} map nodes.', console=True)

    def create_map_sprite(self, x, y):
        sprite = Sprite(center_x=x, center_y=y)
        try:
            terrain_type, index, rotation = self.nodes_data[(x, y)]
            t, i, r = set_terrain_texture(terrain_type, index, rotation)
        except KeyError:
            terrain_type = 'mud'
            t, i, r = set_terrain_texture(terrain_type)
            self.nodes_data[(x, y)] = terrain_type, i, r
        sprite.texture = t
        self.game.terrain_tiles.append(sprite)

    def calculate_distances_between_nodes(self):
        distances = self.distances
        for node in self.nodes.values():
            costs_dict = {}
            for grid in self.in_bounds(adjacent_map_grids(*node.position)):
                adjacent_node = self.nodes[grid]
                distance = adjacent_distance(grid, adjacent_node.grid)
                terrain_cost = (node.terrain_cost + adjacent_node.terrain_cost)
                node.costs[grid] = distance * terrain_cost
            distances[node.grid] = costs_dict

    @logger()
    def plant_trees(self, trees: Optional[Dict[GridPosition, int]] = None):
        if trees is None:
            trees = self.generate_random_trees()
        for node in self.nodes.values():
            if (tree_type := trees.get(node.grid)) is not None:
                self.game.spawn(f'tree_leaf_{tree_type}', position=node.position)
                # TerrainObject(f'tree_leaf_{tree_type}', 4, node.position)
                node.tree = tree_type

    def generate_random_trees(self) -> Dict[GridPosition, int]:
        trees = len(all_files_of_type_named('.png', 'resources', 'tree_')) + 1
        return {grid: random.randrange(1, trees) for grid in self.nodes.keys()
                if random.random() < self.game.settings.trees_density}

    def get_nodes_row(self, row: int) -> List[MapNode]:
        return [n for n in self.nodes.values() if n.grid[1] == row]

    def get_nodes_column(self, column: int) -> List[MapNode]:
        return [n for n in self.nodes.values() if n.grid[0] == column]

    def get_all_nodes(self) -> Generator[MapNode]:
        return (n for n in self.nodes.values())

    def node(self, grid: GridPosition) -> MapNode:
        return self.nodes.get(grid, default=self.nonexistent_node)

    @cached_property
    def nonexistent_node(self) -> MapNode:
        print('NONEXISTENT NODE')
        node = MapNode(-1, -1, None)
        node.pathable = False
        return node


class Map2:

    def __init(self):
        self.sectors: Dict[GridPosition, SectorId] = {}
        self._pathable: Dict[GridPosition, bool] = {}
        self._walkable: Dict[GridPosition, bool] = {}
        self._adjacent: Dict[GridPosition, Set[GridPosition]] = {}
        self._units: Dict[GridPosition, Unit] = {}
        self._buildings: Dict[GridPosition, Building] = {}
        self._static: Dict[GridPosition, GameObject] = {}
        self._trees: Dict[GridPosition, TreeID] = {}

    def unit(self, grid) -> Optional[Unit]:
        try:
            return self._units[grid]
        except KeyError:
            return self._units.get(position_to_map_grid(*grid))

    def building(self, grid) -> Optional[Building]:
        try:
            return self._buildings[grid]
        except KeyError:
            return self._buildings.get(position_to_map_grid(*grid))

    def adjacent(self, grid) -> Optional[Set[GridPosition]]:
        try:
            return self._adjacent[grid]
        except KeyError:
            return self._adjacent.get(position_to_map_grid(*grid))

    def is_walkable(self, grid):
        try:
            return self._walkable[grid]
        except KeyError:
            return self._walkable.get(position_to_map_grid(*grid))

    def is_pathable(self, grid):
        try:
            return self._pathable[grid]
        except KeyError:
            return self._pathable.get(position_to_map_grid(*grid))

    def walkable_adjacent(self, grid):
        try:
            return {n for n in self._adjacent[grid] if self._walkable[n]}
        except KeyError:
            grid = position_to_map_grid(*grid)
            return {n for n in self._adjacent[grid] if self._walkable[n]}


class Sector:
    """
    Map is divided for sectors containing 10x10 Nodes each to split space for
    smaller chunks in order to make enemies-detection faster: since each Unit
    could only scan it's current Sector and adjacent ones instead of whole
    map for enemies.
    """
    map: Optional[Map] = None

    def __init__(self, grid: SectorId):
        """
        Each MapSector is a 10x10 square containing 100 MapNodes.
        """
        self.grid = grid
        self.map.sectors[grid] = self
        self.units_and_buildings: DefaultDict[int, Set[Union[Unit, Building]]] = defaultdict(set)

    def get_entities(self, player_id: int) -> Optional[Set[PlayerEntity]]:
        return self.units_and_buildings.get(player_id)

    def discard_entity(self, entity: PlayerEntity):
        try:
            self.units_and_buildings[entity.player.id].discard(entity)
        except KeyError:
            pass

    def add_player_entity(self, entity: PlayerEntity):
        self.units_and_buildings[entity.player.id].add(entity)

    @cached_property
    def adjacent_sectors(self) -> List[Sector]:
        x, y = self.grid
        raw_grids = {(x + p[0], y + p[1]) for p in ADJACENT_OFFSETS}
        return [self.map.sectors[g] for g in raw_grids if g in self.map.sectors]

    def in_bounds(self, grids: List[GridPosition]) -> Generator[GridPosition]:
        c, r = self.map.columns // SECTOR_SIZE, self.map.rows // SECTOR_SIZE
        return (p for p in grids if 0 <= p[0] <= c and 0 <= p[1] <= r)

    # def adjacent_grids(cls, x: Number, y: Number) -> Set[GridPosition]:
    #     return {(x + p[0], y + p[1]) for p in ADJACENT_OFFSETS}

    def __getstate__(self) -> Dict:
        saved_sector = self.__dict__.copy()
        saved_sector['map'] = None
        saved_sector['units_and_buildings'] = {}
        return saved_sector

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.units_and_buildings = defaultdict(set)
        self.map = Sector.map


class MapNode:
    """
    Class representing a single point on Map which can be Units pathfinding
    destination and is associated with graphic-map-tiles displayed on the
    screen.
    """
    map: Optional[Map] = None

    def __init__(self, x, y, sector):
        self.grid = int(x), int(y)
        self.sector = sector
        self.position = self.x, self.y = map_grid_to_position(self.grid)
        self.costs = None

        self._pathable = True

        self._tree: Optional[TreeID] = None
        self._unit: Optional[Unit] = None
        self._building: Optional[Building] = None
        self._static_gameobject: Optional[GameObject, TreeID] = None

        self.terrain_cost: TerrainCost = TerrainCost.GROUND

    def __repr__(self) -> str:
        return f'MapNode(grid: {self.grid}, position: {self.position})'

    def in_bounds(self, *args, **kwargs):
        return self.map.in_bounds(*args, **kwargs)

    def diagonal_to_other(self, other: GridPosition):
        return self.grid[0] != other[0] and self.grid[1] != other[1]

    @property
    def tree(self) -> Optional[TreeID]:
        return self._tree

    @tree.setter
    def tree(self, value: Optional[TreeID]):
        self._static_gameobject = self._tree = value

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
    def walkable(self) -> bool:
        """
        Use it to find if node is not blocked at the moment by units or
        buildings.
        """
        return self.pathable and self._unit is None

    @property
    def pathable(self) -> bool:
        """Call it to find if this node is available for pathfinding at all."""
        return self._pathable and self._static_gameobject is None

    @pathable.setter
    def pathable(self, value: bool):
        self._pathable = value

    @property
    def walkable_adjacent(self) -> Set[MapNode]:
        return {n for n in self.adjacent_nodes if n.walkable}

    @property
    def pathable_adjacent(self) -> Set[MapNode]:
        return {n for n in self.adjacent_nodes if n.pathable}

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
        self.map = Map.instance
        self.destination = position_to_map_grid(x, y)
        self.units_paths = {unit: [] for unit in units}
        self.reset_units_navigating_groups(units)
        destinations = self.create_units_group_paths(units)
        self.add_visible_indicators_of_destinations(destinations)
        self.reverse_units_paths()

    def __str__(self) -> str:
        return f"NavigatingUnitsGroup(units:{len(self.units_paths)})"

    def __contains__(self, unit: Unit) -> bool:
        return unit in self.units_paths.keys()

    def __bool__(self):
        return bool(self.units_paths)

    def discard(self, unit: Unit):
        try:
            del self.units_paths[unit]
        except KeyError:
            log(f'Failed to discard {unit} from {self}', True)

    def reset_units_navigating_groups(self, units: List[Unit]):
        for unit in units:
            unit.stop_completely()
            unit.set_navigating_group(navigating_group=self)

    def create_units_group_paths(self, units: List[Unit]) -> List[GridPosition]:
        start = units[0].current_node.grid
        path = a_star(self.map, start, self.destination, True)
        destinations = Pathfinder.instance.get_group_of_waypoints(*path[-1], len(units))
        if len(path) > OPTIMAL_PATH_LENGTH:
            self.slice_paths(units, destinations, path)
        else:
            self.navigate_straightly_to_destination(destinations, units)
        return destinations

    def slice_paths(self, units, destinations, path):
        for i in range(1, len(path) // OPTIMAL_PATH_LENGTH, OPTIMAL_PATH_LENGTH):
            step = path[i * OPTIMAL_PATH_LENGTH]
            units_steps = Pathfinder.instance.get_group_of_waypoints(*step, len(units))
            self.navigate_straightly_to_destination(units_steps, units)
        self.navigate_straightly_to_destination(destinations, units)

    def navigate_straightly_to_destination(self, destinations, units):
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

    def add_visible_indicators_of_destinations(self, destinations):
        positions = [map_grid_to_position(g) for g in destinations]
        self.map.game.units_ordered_destinations.new_destinations(positions)

    @staticmethod
    def get_next_units_steps(amount: int, step: GridPosition):
        destinations = Pathfinder.instance.get_group_of_waypoints(*step, amount)
        return [d[0] for d in zip(destinations, range(amount))]

    def update(self):
        to_remove = []
        remove = to_remove.append
        for unit, steps in self.units_paths.items():
            self.find_next_path_for_unit(unit, steps) if steps else remove(unit)
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
            queue.start()
        self.created_waypoints_queue = None

    def navigate_units_to_destination(self, units: List[Unit], x: int, y: int):
        if not self.map.position_to_node(x, y).walkable:
            x, y = self.get_closest_walkable_position(x, y)
        self.navigating_groups.append(NavigatingUnitsGroup(units, x, y))

    def update(self):
        self.update_waypoints_queues()
        self.update_navigating_groups()
        self.process_next_path_request()

    def process_next_path_request(self):
        """
        Each frame get first request from queue and try to find path for it,
        if successful, return the path, else enqueue the request again.
        """
        if self.requests_for_paths:
            unit, start, destination = self.requests_for_paths.pop()
            # to avoid infinite attempts to find path to the Node blocked by
            # other Unit from the same navigating groups pathfinding to the
            # same place TODO: find a better way to not mutually-block nodes
            if self.map.grid_to_node(destination).walkable:
                if path := a_star(self.map, start, destination):
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
        center = position_to_map_grid(x, y)
        if required_waypoints == 1: return [center, ]
        radius = 1
        waypoints = []
        nodes = self.map.nodes
        while len(waypoints) < required_waypoints:
            waypoints = [w for w in calculate_circular_area(*center, radius) if
                         w in nodes and nodes[w].walkable]
            radius += 1
        waypoints.sort(key=lambda w: distance_2d(w, center))
        return [d[0] for d in zip(waypoints, range(required_waypoints))]

    def get_closest_walkable_position(self,
                                      x: Number,
                                      y: Number) -> NormalizedPoint:
        nearest_walkable = None
        if (node := self.map.position_to_node(x, y)).walkable:
            return node.position
        while nearest_walkable is None:
            adjacent = node.adjacent_nodes
            for adjacent_node in (n for n in adjacent if n.walkable):
                return adjacent_node.position
            node = random.choice([n for n in adjacent])
            # TODO: potential infinite loop


if __name__:
    # these imports are placed here to avoid circular-imports issue:
    from players_and_factions.player import PlayerEntity
    from units.units import Unit
    from map.pathfinding import a_star
    from buildings.buildings import Building
