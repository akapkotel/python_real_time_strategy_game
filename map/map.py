#!/usr/bin/env python
from __future__ import annotations

import random

from abc import ABC, abstractmethod
from collections import deque
from typing import Deque, Dict, List, Optional, Set, Tuple, Union

from arcade import Sprite, Texture, load_spritesheet

from game import (
    Game, PROFILING_LEVEL, SECTOR_SIZE, TILE_HEIGHT, TILE_WIDTH
)
from utils.classes import Singleton
from utils.data_types import (
    GridPosition, Number, PlayerId, SectorId, UnitId
)
from utils.enums import TerrainCost
from utils.scheduling import EventsCreator
from utils.functions import (
    get_path_to_file, calculate_circular_area, distance_2d, log, timer
)

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

# typing aliases:
NormalizedPoint = Tuple[int, int]
MapPath = List[NormalizedPoint]
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
            grid[0] * TILE_WIDTH + TILE_WIDTH // 2,
            grid[1] * TILE_HEIGHT + TILE_HEIGHT // 2
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

    def __init__(self, columns: int, rows: int, grid_width: int, grid_height: int):
        MapNode.map = Sector.map = self
        self.rows = rows
        self.columns = columns
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.width = columns * grid_width
        self.height = rows * grid_height

        # map is divided for sectors containing 10x10 Nodes each to split
        # space for smaller chunks in order to make enemies-detection
        # faster: since each Unit could only scan it's current Sector and
        # adjacent ones instead of whole map for enemies:
        self.sectors: Dict[SectorId, Sector] = {}
        self.nodes: Dict[GridPosition, MapNode] = {}

        self.generate_sectors()
        self.generate_nodes()
        self.calculate_distances_between_nodes()

        Map.instance = self

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
        log(f'Created {len(self.sectors)} sectors.', 1)

    @timer(1, global_profiling_level=PROFILING_LEVEL)
    def generate_nodes(self):
        print(f'map rows: {self.rows}, columns: {self.columns}')
        for x in range(self.columns + 1):
            sector_x = x // SECTOR_SIZE
            for y in range(self.rows + 1):
                sector_y = y // SECTOR_SIZE
                sector = self.sectors[sector_x, sector_y]
                self.nodes[(x, y)] = node = MapNode(x, y, sector)
                self.create_map_sprite(*node.position)
        log(f'Generated {len(self.nodes)} map nodes', 1)

    def create_map_sprite(self, x, y):
        sprite = Sprite(center_x=x, center_y=y)
        sprite.texture = self.random_terrain_texture()
        self.game.terrain_objects.append(sprite)

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
        self.active = False

    def add_waypoint(self, x: int, y: int):
        if len(self.waypoints) > 1 and (x, y) == self.waypoints[0]:
            Pathfinder.instance.finish_waypoints_queue()
        else:
            self.waypoints.append((x, y))

    def update(self):
        # TODO: execution of the waypoints queue
        pass

    def start(self):
        self.active = True

    def stop(self):
        self.active = False


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

    def reset_units_navigating_groups(self, units):
        for unit in (u for u in units if u.navigating_group is not None):
            unit.set_navigating_group(navigating_group=self)

    def create_units_group_paths(self, units: List[Unit]) -> List[GridPosition]:
        start = units[0].current_node.grid
        path = a_star(self.map.nodes, start, self.destination, True)
        destinations = self.get_next_units_steps(len(units), path[-1])
        if len(path) > OPTIMAL_PATH_LENGTH:
            self.slice_paths(units, destinations, path)
        else:
            self.navigate_straightly_to_destination(destinations, units)
        return destinations

    def slice_paths(self, units, destinations, path):
        path_steps = OPTIMAL_PATH_LENGTH // 2
        amount = len(units)
        for i in range(len(path) // path_steps):
            step = path[i * path_steps]
            units_steps = self.get_next_units_steps(amount, step)
            for unit, grid in zip(units, units_steps):
                self.units_paths[unit].append(grid)
        for i, unit in enumerate(units):
            self.units_paths[unit].append(destinations[units.index(unit)])

    def navigate_straightly_to_destination(self, destinations, units):
        self.units_paths = {
            unit: [destination] for unit, destination in
            zip(units, destinations)
        }

    def reverse_units_paths(self):
        # to cheaply use pop() to remove reached waypoints from paths
        for unit, steps in self.units_paths.items():
            steps.reverse()

    def add_visible_indicators_of_destinations(self, destinations):
        positions = [self.map.grid_to_position(g) for g in destinations]
        self.map.game.units_ordered_destinations.new_destinations(positions)

    @staticmethod
    def get_next_units_steps(amount: int, step: GridPosition):
        destinations = Pathfinder.instance.group_of_waypoints(*step, amount)
        return [d[0] for d in zip(destinations, range(amount))]

    def update(self):
        to_remove = []
        for unit, steps in self.units_paths.items():
            if steps:
                self.find_next_path_for_unit(steps, to_remove, unit)
            else:
                to_remove.append(unit)
        self.remove_finished_paths(to_remove)

    @staticmethod
    def find_next_path_for_unit(steps, to_remove, unit):
        destination = steps[-1]
        if unit.current_node.grid != destination:
            if not unit.path or unit.path[-1] != destination:
                unit.move_to(destination)
                to_remove.append(steps)

    def remove_finished_paths(self, to_remove: List[Union[Unit, GridPosition]]):
        for elem in to_remove:
            if isinstance(elem, List):
                elem.pop()
            else:
                elem.set_navigating_group(navigating_group=None)
                del self.units_paths[elem]


class Pathfinder(Singleton, EventsCreator):
    """
    A* algorithm implementation using PriorityQueue based on improved heapq.
    """
    instance: Optional[Pathfinder] = None

    def __init__(self, map: Map):
        """
        This class is a Singleton, so there is only one instance of
        Pathfinder in the game, and it will be returned each time the
        Pathfinder() is instantiated.
        :param map: Map -- actual instance of game Map loaded.
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
            queue.update()

    def update_navigating_groups(self):
        for nav_group in self.navigating_groups[::-1]:
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
            if request[0] == unit:
                self.requests_for_paths.remove(request)

    def group_of_waypoints(self,
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
        return sorted(waypoints, key=lambda w: distance_2d(w, center))

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

