#!/usr/bin/env python
from __future__ import annotations

import random
import time

from abc import ABC, abstractmethod
from collections import deque
from typing import Deque, Dict, List, Optional, Set, Tuple, Union

from arcade import Sprite, Texture, load_spritesheet

from game import (
    Game, PROFILING_LEVEL, SECTOR_SIZE, TILE_HEIGHT, TILE_WIDTH
)
from gameobjects.gameobject import TerrainObject
from utils.classes import Singleton
from utils.data_types import (
    GridPosition, Number, PlayerId, SectorId, UnitId
)
from utils.enums import TerrainCost
from utils.scheduling import EventsCreator
from utils.functions import (
    get_path_to_file
)
from utils.logging import log, logger, timer
from utils.geometry import distance_2d, calculate_circular_area

# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!


PATH = 'PATH'
DIAGONAL = 1.4142  # approx square root of 2
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


class GridHandler:

    @abstractmethod
    def position_to_node(self, x: Number, y: Number) -> MapNode:
        raise NotImplementedError

    @classmethod
    def position_to_grid(cls, x: Number, y: Number) -> GridPosition:
        """Return map-grid-normalised position."""
        return x // TILE_WIDTH, y // TILE_HEIGHT

    @classmethod
    def normalize_position(cls, x: Number, y: Number) -> NormalizedPoint:
        grid = cls.position_to_grid(x, y)
        return cls.grid_to_position(grid)

    @classmethod
    def grid_to_position(cls, grid: GridPosition) -> NormalizedPoint:
        """Return (x, y) position of the map-grid-normalised Node."""
        return (
            int(grid[0] * TILE_WIDTH + TILE_WIDTH // 2),
            int(grid[1] * TILE_HEIGHT + TILE_HEIGHT // 2)
        )

    @classmethod
    def adjacent_grids(cls, x: Number, y: Number) -> List[GridPosition]:
        """Return list of map-normalised grid-positions adjacent to (x, y)."""
        grid = cls.position_to_grid(x, y)
        return [(grid[0] + p[0], grid[1] + p[1]) for p in ADJACENT_OFFSETS]

    @abstractmethod
    def in_bounds(self, *args, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def adjacent_nodes(self, *args, **kwargs) -> List[MapNode]:
        raise NotImplementedError

    @abstractmethod
    def walkable_adjacent(self, *args, **kwargs) -> List[MapNode]:
        """Useful for pathfinding."""
        raise NotImplementedError

    @classmethod
    def diagonal(cls, first_id: GridPosition, second_id: GridPosition) -> bool:
        return first_id[0] != second_id[0] and first_id[1] != second_id[1]


class Map(GridHandler):
    """

    """
    game: Optional[Game] = None
    instance = None

    def __init__(self, map_settings: Dict):
        start_time = time.time()
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

        self.generate_sectors()
        self.generate_nodes()
        self.calculate_distances_between_nodes()

        self.game.after_load_functions.append(self.plant_random_trees)

        log(f'Created map in: {time.time() - start_time}', console=True)

    def save(self) -> Dict:
        return {
            'rows': self.rows,
            'columns': self.columns,
            'grid_width': self.grid_width,
            'grid_height': self.grid_height,
            'nodes_data': self.nodes_data
        }

    def __str__(self) -> str:
        return f'Map(height: {self.height}, width: {self.width}, nodes: {len(self.nodes)})'

    def __len__(self) -> int:
        return len(self.nodes)

    def in_bounds(self, grids) -> List[GridPosition]:
        return [
            p for p in grids if 0 <= p[0] < self.columns and 0 <= p[1] < self.rows
        ]

    def on_map_area(self, x: Number, y: Number) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def walkable_adjacent(self, x, y) -> List[MapNode]:
        return [n for n in self.adjacent_nodes(x, y) if n.walkable]

    def pathable_adjacent(self, x, y) -> List[MapNode]:
        return [n for n in self.adjacent_nodes(x, y) if n.pathable]

    def adjacent_nodes(self, x: Number, y: Number) -> List[MapNode]:
        return [
            self.nodes[adj] for adj in self.in_bounds(self.adjacent_grids(x, y))
        ]

    def position_to_node(self, x: Number, y: Number) -> MapNode:
        return self.grid_to_node(self.position_to_grid(x, y))

    def grid_to_node(self, grid: GridPosition) -> MapNode:
        return self.nodes[grid]

    def generate_sectors(self):
        for x in range(self.columns // SECTOR_SIZE + 1):
            for y in range(self.rows // SECTOR_SIZE + 1):
                self.sectors[(x, y)] = Sector((x, y))
        log(f'Created {len(self.sectors)} map sectors.')

    @timer(1, global_profiling_level=PROFILING_LEVEL)
    @logger(console=True)
    def generate_nodes(self):
        for x in range(self.columns + 1):
            sector_x = x // SECTOR_SIZE
            for y in range(self.rows + 1):
                sector_y = y // SECTOR_SIZE
                sector = self.sectors[sector_x, sector_y]
                self.nodes[(x, y)] = node = MapNode(x, y, sector)
                self.create_map_sprite(*node.position)
        log(f'Generated {len(self.nodes)} map nodes', console=True)

    def create_map_sprite(self, x, y):
        sprite = Sprite(center_x=x, center_y=y)
        try:
            terrain_type, index, rotation = self.nodes_data[(x, y)]
            t, i, r = self.set_terrain_texture(terrain_type, index, rotation)
        except KeyError:
            terrain_type = 'mud'
            t, i, r = self.set_terrain_texture(terrain_type)
            self.nodes_data[(x, y)] = terrain_type, i, r
        sprite.texture = t
        self.game.terrain_tiles.append(sprite)

    @staticmethod
    def set_terrain_texture(terrain_type: str,
                            index: int = None,
                            rotation: int = None) -> Tuple[Texture, int, int]:
        index = index or random.randint(0, len(MAP_TEXTURES[terrain_type]) - 1)
        texture = MAP_TEXTURES[terrain_type][index]

        rotation = rotation or random.randint(0, 5)
        texture.image.transpose(rotation)
        return texture, index, rotation

    @staticmethod
    def random_terrain_texture() -> Texture:
        texture = random.choice(MAP_TEXTURES['mud'])
        texture.image.transpose(random.randint(0, 5))
        return texture

    def calculate_distances_between_nodes(self):
        distances: Dict[(GridPosition, GridPosition), float] = {}
        for node in self.nodes.values():
            for grid in self.in_bounds(self.adjacent_grids(*node.position)):
                adjacent_node = self.nodes[grid]
                distance = DIAGONAL if self.diagonal(node.grid, grid) else 1
                distance *= (node.terrain_cost + adjacent_node.terrain_cost)
                node.costs[grid] = distance
        return distances

    @logger()
    def plant_random_trees(self):
        self.game.static_objects.extend(
            TerrainObject(f'tree_leaf_{random.choice((1, 2))}.png', 4, node.position) for
            node in self.nodes.values() if random.random() > 0.95
        )

    def get_nodes_row(self, row: int) -> List[MapNode]:
        return [n for n in self.nodes.values() if n.grid[1] == row]

    def get_nodes_column(self, column: int) -> List[MapNode]:
        return [n for n in self.nodes.values() if n.grid[0] == column]

    def get_all_nodes(self) -> List[MapNode]:
        return list(self.nodes.values())

    def node(self, grid: GridPosition) -> MapNode:
        try:
            return self.nodes[grid]
        except KeyError:
            node = MapNode(-1, -1, None)
            node._allowed_for_pathfinding = False
            return node


class Sector(GridHandler, ABC):
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

        :param id: SectorId is a Tuple[int, int] which are boundaries of
        this Sector: first column and first row of MapNodes, this Sector owns
        """
        self.grid = grid
        self.units_and_buildings: Dict[PlayerId, Set[PlayerEntity]] = {}
        self.map.sectors[grid] = self

    def get_entities(self, player_id: PlayerId) -> Optional[Set[PlayerEntity]]:
        return self.units_and_buildings.get(player_id)

    def discard_entity(self, entity: PlayerEntity):
        try:
            self.units_and_buildings[entity.player.id].discard(entity)
        except KeyError:
            pass

    def add_entity(self, entity: PlayerEntity):
        try:
            self.units_and_buildings[entity.player.id].add(entity)
        except KeyError:
            self.units_and_buildings[entity.player.id] = {entity}

    def adjacent_sectors(self) -> List[Sector]:
        raw_grids = self.adjacent_grids(*self.grid)
        return [self.map.sectors[g] for g in self.in_bounds(raw_grids)]

    def in_bounds(self, grids: List[GridPosition]):
        # TODO: fix setting correct bounds for sectors
        c, r = self.map.columns // SECTOR_SIZE, self.map.rows // SECTOR_SIZE
        return [p for p in grids if 0 <= p[0] < c and 0 <= p[1] < r]

    def adjacent_grids(cls, x: Number, y: Number) -> List[GridPosition]:
        return [(x + p[0], y + p[1]) for p in ADJACENT_OFFSETS]

    def __getstate__(self) -> Dict:
        saved_sector = self.__dict__.copy()
        saved_sector['map'] = None
        saved_sector['units_and_buildings'] = {}
        return saved_sector

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.map = Sector.map


class MapNode(GridHandler, ABC):
    """
    Class representing a single point on Map which can be Units pathfinding
    destination and is associated with graphic-map-tiles displayed on the
    screen.
    """
    map: Optional[Map] = None

    def __init__(self, x, y, sector):
        self.grid = x, y
        self.sector = sector
        self.position = self.x, self.y = self.grid_to_position(self.grid)
        self.costs: Dict[GridPosition, float] = {}

        self._allowed_for_pathfinding = True

        self._terrain_object_id: Optional[int] = None
        self._unit: Optional[Unit] = None
        self._building: Optional[Building] = None

        self.terrain_cost: TerrainCost = TerrainCost.GROUND

    def __repr__(self) -> str:
        return f'MapNode(grid position: {self.grid}, position: {self.position})'

    def in_bounds(self, *args, **kwargs):
        return self.map.in_bounds(*args, **kwargs)

    def diagonal_to_other(self, other: GridPosition):
        return self.grid[0] != other[0] and self.grid[1] != other[1]

    @property
    def obstacle_id(self) -> UnitId:
        return self._terrain_object_id

    @obstacle_id.setter
    def obstacle_id(self, value: Optional[int]):
        self._terrain_object_id = value

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
        self._building = value

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
        return self._allowed_for_pathfinding and self._building is None

    def set_pathable(self, value: bool):
        self._allowed_for_pathfinding = value

    @property
    def walkable_adjacent(self) -> List[MapNode]:
        return self.map.walkable_adjacent(*self.position)

    @property
    def pathable_adjacent(self) -> List[MapNode]:
        return self.map.pathable_adjacent(*self.position)

    @property
    def adjacent_nodes(self) -> List[MapNode]:
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
    When human player gives hist Units movement orders with left CTRL key
    pressed, he can plan multiple consecutive moves ahead, which would be
    executed when LCTRL is released, or when player points back to the first
    waypoint of the queue. The second scenario would produce a looped path to
    patrol.
    """

    def __init__(self, units: List[Unit]):
        self.map = Map.instance
        self.units = units
        self.waypoints = []
        self.units_waypoints = {unit: [] for unit in units}
        self.active = False

    def add_waypoint(self, x: int, y: int):
        x, y = Map.normalize_position(x, y)
        if len(self.waypoints) > 1 and (x, y) == self.waypoints[0]:
            Pathfinder.instance.finish_waypoints_queue()
        else:
            self.waypoints.append((x, y))
            self.add_waypoints_for_each_unit(len(self.units), x, y)

    def add_waypoints_for_each_unit(self, amount: int, x: int, y: int):
        waypoints = Pathfinder.instance.get_group_of_waypoints(amount, x, y)
        for i, unit in enumerate(self.units):
            self.units_waypoints[unit].append(waypoints[i])

    def update(self):
        # TODO: execution of the waypoints queue
        for unit, waypoints in self.units_waypoints.items():
            destination = waypoints[-1]
            if unit.reached_destination(destination):
                waypoints.pop()
            elif not (unit.has_destination or unit.heading_to(destination)):
                unit.move_to(destination)
            if not waypoints:
                del self.units_waypoints[unit]

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
        self.destination = Map.position_to_grid(x, y)
        self.units_paths = {unit: [] for unit in units}
        self.reset_units_navigating_groups(units)
        destinations = self.create_units_group_paths(units)
        self.add_visible_indicators_of_destinations(destinations)
        self.reverse_units_paths()

    def __str__(self) -> str:
        return f"NavigatingUnitsGroup(units:{len(self.units_paths)})"

    def reset_units_navigating_groups(self, units: List[Unit]):
        for unit in units:
            unit.stop_completely()
            unit.set_navigating_group(navigating_group=self)

    def discard(self, unit: Unit):
        try:
            del self.units_paths[unit]
        except KeyError:
            pass

    def create_units_group_paths(self, units: List[Unit]) -> List[GridPosition]:
        start = units[0].current_node.grid
        path = a_star(self.map.nodes, start, self.destination, True)
        destinations = Pathfinder.instance.get_group_of_waypoints(*path[-1], len(units))
        if len(path) > OPTIMAL_PATH_LENGTH:
            self.slice_paths(units, destinations, path)
        else:
            self.navigate_straightly_to_destination(destinations, units)
        return destinations

    def slice_paths(self, units, destinations, path):
        for i in range(len(path) // OPTIMAL_PATH_LENGTH):
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

    def add_visible_indicators_of_destinations(self, destinations):
        positions = [self.map.grid_to_position(g) for g in destinations]
        self.map.game.units_ordered_destinations.new_destinations(positions)

    @staticmethod
    def get_next_units_steps(amount: int, step: GridPosition):
        destinations = Pathfinder.instance.get_group_of_waypoints(*step, amount)
        return [d[0] for d in zip(destinations, range(amount))]

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
        if unit.reached_destination(destination) or unit.nearby(destination):
            steps.pop()
        elif not (unit.has_destination or unit.heading_to(destination)):
            unit.move_to(destination)

    @staticmethod
    def remove_finished_paths(finished_units: List[Unit]):
        for unit in finished_units:
            unit.set_navigating_group(navigating_group=None)


class Pathfinder(EventsCreator):
    """
    A* algorithm implementation using PriorityQueue based on improved heapq.
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
        self.path_requests_count = 0
        self.paths_found = 0
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
        self.navigating_groups.append(NavigatingUnitsGroup(units, x, y))

    def update(self):
        """
        Each frame get first request from queue and try to find path for it,
        if successful, return the path, else enqueue the request again.
        """
        self.update_waypoints_queues()
        self.update_navigating_groups()
        if self.requests_for_paths:
            unit, start, destination = self.requests_for_paths.pop()
            if self.map.grid_to_node(destination).walkable:
                if path := a_star(self.map.nodes, start, destination):
                    self.paths_found += 1
                    return unit.create_new_path(path)
            self.request_path(unit, start, destination)

    def update_waypoints_queues(self):
        for queue in (q for q in self.waypoints_queues if q.active):
            if queue.units_waypoints:
                queue.update()
            else:
                self.waypoints_queues.remove(queue)

    def update_navigating_groups(self):
        for nav_group in self.navigating_groups:
            if nav_group.units_paths:
                nav_group.update()
            else:
                self.navigating_groups.remove(nav_group)

    def request_path(self, unit: Unit, start: GridPosition, destination: GridPosition):
        """Enqueue new path-request. It will be resolved when possible."""
        self.requests_for_paths.appendleft((unit, start, destination))
        self.path_requests_count += 1

    def cancel_unit_path_requests(self, unit: Unit):
        for request in self.requests_for_paths.copy():
            if request[0] is unit:
                self.requests_for_paths.remove(request)

    def get_group_of_waypoints(self,
                               x: int,
                               y: int,
                               required_waypoints: int) -> List[GridPosition]:
        """
        Find requested number of valid waypoints around requested position.
        """
        center = self.map.position_to_grid(x, y)
        if required_waypoints == 1: return [center, ]
        radius = 1
        waypoints = []
        nodes = self.map.nodes
        while len(waypoints) < required_waypoints:
            waypoints = [w for w in calculate_circular_area(*center, radius) if
                         w in nodes and nodes[w].walkable]
            radius += 1
        # return sorted(waypoints, key=lambda w: distance_2d(w, center))
        waypoints.sort(key=lambda w: distance_2d(w, center))
        return [d[0] for d in zip(waypoints, range(required_waypoints))]

    def get_closest_walkable_position(self,
                                      x: Number,
                                      y: Number) -> NormalizedPoint:
        nearest_walkable = None
        node = self.map.position_to_node(x, y)
        while nearest_walkable is None:
            adjacent = node.adjacent_nodes
            for node in adjacent:
                if node.walkable:
                    return node.position
                else:
                    continue
            node = random.choice(adjacent)


if __name__:
    # these imports are placed here to avoid circular-imports issue:
    from players_and_factions.player import PlayerEntity
    from units.units import Unit
    from map.pathfinding import a_star
    from buildings.buildings import Building

