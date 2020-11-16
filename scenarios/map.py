#!/usr/bin/env python
from __future__ import annotations

import heapq
import math
import random

from abc import ABC, abstractmethod
from collections import defaultdict, deque

from math import hypot
from typing import Deque, Dict, List, Optional, Set, Tuple, Union

from arcade import Sprite, Texture, load_spritesheet

from utils.data_types import BuildingId, GridPosition, Number, SectorId, UnitId
from gameobjects.gameobject import TerrainObject
from game import Game, PROFILING_LEVEL, TILE_WIDTH, TILE_HEIGHT, SECTOR_SIZE
from utils.scheduling import EventsCreator, ScheduledEvent
from utils.classes import Singleton
from utils.functions import get_path_to_file, log, timer
from utils.enums import TerrainCost

# CIRCULAR IMPORTS MOVED TO THE BOTTOM OF FILE!


PATH = 'PATH'

# typing aliases:
NormalizedPoint = Tuple[int, int]
MapPath = List[NormalizedPoint]

MAP_TEXTURES = {
    'mud': load_spritesheet(
        get_path_to_file('mud_tileset_6x6.png'), 60, 60, 4, 16, 0)
}


class GridHandler:
    adjacent_offsets = [
        (-1, -1), (-1, 0), (-1, +1), (0, +1), (0, -1), (+1, -1), (+1, 0),
        (+1, +1)
    ]

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
        return [(grid[0] + p[0], grid[1] + p[1]) for p in cls.adjacent_offsets]

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

    def __init__(self, width=0, height=0, grid_width=0, grid_height=0):
        MapNode.map = Sector.map = self
        self.width = width
        self.height = height
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.rows = self.height // self.grid_height
        self.columns = self.width // self.grid_width

        # map is divided for sectors containing 10x10 Nodes each to split
        # space for smaller chunks in order to make enemies-detection
        # faster: since each Unit could only scan it's current Sector and
        # adjacent ones instead of whole map for enemies:
        self.sectors: Dict[SectorId, Sector] = {}
        self.nodes: Dict[GridPosition, MapNode] = {}
        self.units: Dict[GridPosition, UnitId] = {}
        self.buildings: Dict[GridPosition, BuildingId] = {}

        self.generate_sectors()
        self.generate_nodes()
        self.calculate_distances_between_nodes()

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
        for x in range(self.columns):
            sector_x = x // SECTOR_SIZE
            for y in range(self.rows):
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
        for node in self.nodes.values():
            for grid in self.in_bounds(self.adjacent_grids(*node.position)):
                adjacent_node = self.nodes[grid]
                distance = 1.4 if self.diagonal(node.grid, grid) else 1
                distance *= (node.terrain + adjacent_node.terrain)
                node.costs[grid] = distance

    def get_nodes_row(self, row: int) -> List[MapNode]:
        return [n for n in self.nodes.values() if n.grid[1] == row]

    def get_nodes_column(self, column: int) -> List[MapNode]:
        return [n for n in self.nodes.values() if n.grid[0] == column]

    def get_all_nodes(self) -> List[MapNode]:
        return list(self.nodes.values())

    def node(self, grid: GridPosition) -> MapNode:
        return self.nodes[grid]


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
        self.units_and_buildings: Set[PlayerEntity] = set()
        self.map.sectors[grid] = self

    def adjacent_sectors(self) -> List[Sector]:
        raw_grids = self.adjacent_grids(*self.grid)
        return [self.map.sectors[g] for g in self.in_bounds(raw_grids)]

    def in_bounds(self, grids: List[GridPosition]):
        # TODO: fix setting correct bounds for sectors
        return [p for p in grids if 0 <= p[0] < 13 and 0 <= p[1] < 7]

    def adjacent_grids(cls, x: Number, y: Number) -> List[GridPosition]:
        return [(x + p[0], y + p[1]) for p in cls.adjacent_offsets]


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
        self._walkable = True

        self._terrain_object_id: Optional[int] = None
        self._unit_id: Optional[UnitId] = None
        self._building_id: Optional[BuildingId] = None

        self.terrain: TerrainCost = TerrainCost.GROUND

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
    def unit_id(self, value: Optional[int]):
        self._terrain_object_id = value

    @property
    def unit_id(self) -> UnitId:
        return self._unit_id

    @unit_id.setter
    def unit_id(self, value: Optional[UnitId]):
        self.map.units[self.grid] = value
        self._unit_id = value

    @property
    def building_id(self) -> Optional[BuildingId]:
        return self._unit_id

    @building_id.setter
    def building_id(self, value: Optional[BuildingId]):
        self.map.buildings[self.grid] = value
        self._building_id = value

    @property
    def walkable(self) -> bool:
        """
        Use it to find if node is not blocked at the moment by units or
        buildings.
        """
        return self.pathable and self._unit_id is None

    @property
    def pathable(self) -> bool:
        """Call it to find if this node is available for pathfinding at all."""
        return self._terrain_object_id is None and self._building_id is None

    @property
    def walkable_adjacent(self) -> List[MapNode]:
        return self.map.walkable_adjacent(*self.position)

    @property
    def pathable_adjacent(self) -> List[MapNode]:
        return self.map.pathable_adjacent(*self.position)

    @property
    def adjacent_nodes(self) -> List[MapNode]:
        return self.map.adjacent_nodes(*self.position)


class PriorityQueue:
    # much faster than sorting list each frame
    def __init__(self, first_element=None, priority=None):
        self.elements = []
        self._contains = set()  # my improvement, faster lookups
        if first_element is not None:
            self.put(first_element, priority)

    def __bool__(self) -> bool:
        return len(self.elements) > 0

    def __len__(self) -> int:
        return len(self.elements)

    def __contains__(self, item) -> bool:
        return item in self._contains

    def not_empty(self) -> bool:
        return len(self.elements) > 0

    def put(self, item, priority):
        self._contains.add(item)
        heapq.heappush(self.elements, (priority, item))

    def get(self):
        return heapq.heappop(self.elements)[1]  # (priority, item)


PathRequest = Tuple['Unit', GridPosition, GridPosition]


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
        self.requests_for_paths: Deque[PathRequest] = deque()
        Pathfinder.instance = self

    def __bool__(self) -> bool:
        return len(self.requests_for_paths) > 0

    def __len__(self) -> int:
        return len(self.requests_for_paths)

    def __contains__(self, unit: Unit) -> bool:
        return any(request[0] == unit for request in self.requests_for_paths)

    def request_path(self,
                     unit: Unit,
                     start: GridPosition,
                     destination: GridPosition):
        self.requests_for_paths.appendleft((unit, start, destination))

    def cancel_path_requests(self, unit: Unit):
        for request in self.requests_for_paths.copy():
            if request[0] == unit:
                self.requests_for_paths.remove(request)

    def group_of_waypoints(self,
                    x: int,
                    y: int,
                    required_waypoints: int) -> List[GridPosition]:
        node = self.map.position_to_node(x, y)
        waypoints = {node.grid}
        while len(waypoints) < required_waypoints:
            adjacent = node.walkable_adjacent
            waypoints.update(n.grid for n in node.walkable_adjacent)
            node = adjacent[0]
        return [w for w in waypoints]

    @timer(level=2, global_profiling_level=PROFILING_LEVEL)
    def find_path(self,
                  start: GridPosition,
                  end: GridPosition,
                  pathable: bool = False) -> Union[MapPath, bool]:
        """
        Find shortest path from <start> to <end> position using A* algorithm.
        """
        log(f'Searching for path from {start} to {end}...')
        heuristic = self.heuristic

        map_nodes = self.map.nodes
        unexplored = PriorityQueue(start, heuristic(start, end) * 1.001)
        previous: Dict[GridPosition, GridPosition] = {}

        get_best_unexploed = unexplored.get
        put_to_unexplored = unexplored.put

        cost_so_far = defaultdict(lambda: math.inf)
        cost_so_far[start] = 0

        while unexplored:
            if (current := get_best_unexploed()) == end:
                return self.reconstruct_path(map_nodes, previous, current)
            node = map_nodes[current]
            walkable = node.pathable_adjacent if pathable else node.walkable_adjacent
            for adjacent in (a for a in walkable if a.grid not in unexplored):
                total = cost_so_far[current] + node.costs[adjacent.grid]
                if total < cost_so_far[adjacent.grid]:
                    previous[adjacent.grid] = current
                    cost_so_far[adjacent.grid] = total
                    priority = total + heuristic(adjacent.grid, end) * 1.001
                    put_to_unexplored(adjacent.grid, priority)
        # if path was not found searching by walkable tiles, we call second
        # pass and search for pathable nodes this time
        if not pathable:
            return self.find_path(start, end, pathable=True)
        return False  # no third pass, if there is no possible path!

    @staticmethod
    def heuristic(start, end):
        return hypot(start[0] - end[0], start[1] - end[1])

    def reconstruct_path(self,
                         map_nodes: Dict[GridPosition, MapNode],
                         previous_nodes: Dict[GridPosition, GridPosition],
                         current_node: GridPosition) -> MapPath:
        path = [map_nodes[current_node]]
        while current_node in previous_nodes.keys():
            current_node = previous_nodes[current_node]
            path.append(map_nodes[current_node])
        return self.nodes_list_to_path(path[::-1])

    @staticmethod
    def nodes_list_to_path(nodes_list: List[MapNode]) -> MapPath:
        return [node.position for node in nodes_list]

    def update(self) -> Optional[MapPath]:
        """
        Each frame get first request from queue and try to find path for it,
        if successful, return the path, else enqueue the request again.
        """
        if self.requests_for_paths:
            unit, start, destination = self.requests_for_paths.pop()
            if self.map.grid_to_node(destination).walkable:
                if path := self.find_path(start, destination):
                    return unit.create_new_path(path)
            self.request_path(unit, start, destination)

    def schedule_pathfinding_for_later(self,
                                       unit: Unit,
                                       start: GridPosition,
                                       destination: GridPosition,
                                       delay: int = 30):
        """
        Rather costly way to delay pathfinding execution. It is used only
        when Unit already have not found correct path to the destination
        because it is blocked for a longer while.
        """
        self.schedule_event(
            ScheduledEvent(
                creator=self,
                delay=1,
                function=self.request_path,
                args=(unit, start, destination),
                frames_left=delay,
            )
        )


if __name__:
    # these imports are placed here to avoid circular-imports issue:
    from players_and_factions.player import PlayerEntity
    from units.units import Unit
