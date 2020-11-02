#!/usr/bin/env python
from __future__ import annotations

import heapq
from math import inf as INFINITY, hypot
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Optional, Tuple, List, Set, Dict, Generator, Any

from scheduling import log
from utils.classes import Singleton
from data_types import Number, UnitId


PATH = 'PATH'
TILE_WIDTH = 50
TILE_HEIGHT = 50

# typing aliases:
GridPosition = SectorId = NormalizedPoint = Tuple[int, int]
MapPath = List[NormalizedPoint]


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
        grid = cls.position_to_grid(int(x), int(y))
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
    def adjacent_nodes(self, *args, **kwargs):
        raise NotImplementedError


class Map(GridHandler):
    """

    """

    def __init__(self, width=0, height=0, grid_width=0, grid_height=0):
        self.grid_width = grid_width or 50
        self.grid_height = grid_height or 40
        self.width = width or self.grid_width * 100
        self.height = height or self.grid_height * 50
        self.rows = self.height // self.grid_height if height else 50
        self.columns = self.width // self.grid_width if width else 100

        self.nodes: List[List[MapNode]] = []
        self.units: List[List[UnitId]] = []

        self.generate_nodes()
        MapNode.map = Pathfinder.map = self

    def __len__(self) -> int:
        return sum(len(row) for row in self.nodes)

    def in_bounds(self, grids) -> List[GridPosition]:
        return [
            p for p in grids if 0 <= p[0] < self.rows and 0 <= p[1] < self.columns
        ]

    def adjacent_nodes(self, x: Number, y: Number) -> List[MapNode]:
        adjacent_grids = self.in_bounds(self.adjacent_grids(x, y))
        return [
            self.nodes[adj[0]][adj[1]] for adj in adjacent_grids
        ]

    def position_to_node(self, x: Number, y: Number) -> MapNode:
        return self.grid_to_node(self.position_to_grid(x, y))

    def grid_to_node(self, grid: GridPosition) -> MapNode:
        return self.nodes[grid[0]][grid[1]]

    def generate_nodes(self):
        for row in range(self.rows):
            self.nodes.append([])
            for column in range(self.columns):
                node = MapNode(row, column)
                node.costs = {
                    grid: 1 for grid in self.in_bounds(self.adjacent_grids(*node.position))
                }
                self.nodes[row].append(node)
        log(f'Generated {len(self)} map nodes.')

    def get_nodes_row(self, row: int) -> List[MapNode]:
        return self.nodes[row]

    def get_nodes_column(self, column: int) -> List[MapNode]:
        return [row[column] for row in self.nodes]

    def get_all_nodes(self) -> List[MapNode]:
        nodes = []
        for row in self.nodes:
            for node in row:
                nodes.append(node)
        return nodes

    def node(self, grid: GridPosition) -> MapNode:
        return self.nodes[grid[0]][grid[1]]


class MapNode(GridHandler, ABC):
    """
    Class representing a single point on Map which can be Units pathfinding
    destination and is associated with graphic-map-tiles displayed on the
    screen.
    """
    map: Optional[Map] = None

    def __init__(self, x, y):
        self.grid = x, y
        self.position = self.x, self.y = self.grid_to_position(self.grid)
        self.costs: Dict[GridPosition, float] = {}
        self.walkable = True

    def __repr__(self) -> str:
        return f'MapNode(grid position: {self.grid}, position: {self.position})'

    def in_bounds(self, *args, **kwargs):
        return self.map.in_bounds(*args, **kwargs)

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

    def __contains__(self, item) -> bool:
        return item in self._contains

    def not_empty(self) -> bool:
        return len(self.elements) > 0

    def put(self, item, priority):
        self._contains.add(item)
        heapq.heappush(self.elements, (priority, item))

    def get(self):
        return heapq.heappop(self.elements)[1]


class Pathfinder(Singleton):
    """
    A* algorithm implementation using PriorityQueue based on heapq.
    """
    instance: Optional[Pathfinder] = None
    map: Optional[Map] = None

    @staticmethod
    def heuristic(start, end):
        return hypot(start[0] - end[0], start[1] - end[1])

    def find_path(self, start: GridPosition, end: GridPosition):
        log(f'Searching for path from {start} to {end}...')
        heuristic = self.heuristic

        map_nodes = self.map.node
        adjacent_grids = self.map.adjacent_grids
        unexplored = PriorityQueue(start, heuristic(start, end))
        explored: Set[GridPosition] = set()
        previous: Dict[GridPosition, GridPosition] = {}

        get_best_unexploed = unexplored.get
        put_to_unexplored = unexplored.put

        cost_so_far = defaultdict(lambda: INFINITY)
        cost_so_far[start] = 0

        while unexplored:
            current: GridPosition = get_best_unexploed()
            explored.add(current)
            if current == end:
                return self.reconstruct_path(map_nodes, previous, current)

            node = map_nodes(current)  # current[0]][current[1]
            for adj in adjacent_grids(*node.position):
                if not (adj_node := map_nodes(adj)).walkable and adj not in explored:
                    continue
                if (total := cost_so_far[current] + adj_node.costs[current]) < cost_so_far[adj]:
                    previous[adj] = current
                    cost_so_far[adj] = total
                    priority = total + heuristic(adj, end)
                    put_to_unexplored(adj, priority)
        return []

    def reconstruct_path(self, map_nodes, previous_nodes, current_node):
        path = [map_nodes(current_node)]
        while current_node in previous_nodes.keys():
            current_node = previous_nodes[current_node]
            path.append(map_nodes(current_node))
        return self.nodes_list_to_path(path[:-1])

    @staticmethod
    def nodes_list_to_path(nodes_list: List[MapNode]) -> MapPath:
        return [node.position for node in nodes_list]
