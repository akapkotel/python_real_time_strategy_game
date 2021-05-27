#!/usr/bin/env python
from __future__ import annotations

import math

from functools import lru_cache
from collections import defaultdict
from typing import Dict, Union

from utils.data_types import GridPosition
from utils.functions import log, timer
from utils.classes import PriorityQueue
from game import PROFILING_LEVEL
from map.map import MapNode, MapPath


@timer(level=2, global_profiling_level=PROFILING_LEVEL, forced=True)
def a_star(map_nodes: Dict[GridPosition, MapNode],
           start: GridPosition,
           end: GridPosition,
           pathable: bool = False) -> Union[MapPath, bool]:
    """
    Find shortest path from <start> to <end> position using A* algorithm.

    :param map_nodes: Dict[GridPosition, MapNode] -- all nodes on the map
    :param start: GridPosition -- (int, int) path-start point.
    :param end: GridPosition -- (int, int) path-destination point.
    :param pathable: bool -- should pathfinder check only walkable tiles
    (default) or all pathable map area? Use it to get into 'blocked'
    areas, e.g. places enclosed by units.
    :return: Union[MapPath, bool] -- list of points or False if no path
    found
    """
    log(f'Searching for path from {start} to {end}...')
    unexplored = PriorityQueue(start, heuristic(start, end) * 1.001)
    explored = set()
    previous: Dict[GridPosition, GridPosition] = {}

    get_best_unexplored = unexplored.get
    put_to_unexplored = unexplored.put

    cost_so_far = defaultdict(lambda: math.inf)
    cost_so_far[start] = 0

    while unexplored:
        if (current := get_best_unexplored()) == end:
            return reconstruct_path(map_nodes, previous, current)
        explored.add(current)
        node = map_nodes[current]
        walkable = node.pathable_adjacent if pathable else node.walkable_adjacent
        for adjacent in (a for a in walkable if a.grid not in explored):
            if (adjacent_grid := adjacent.grid) in unexplored:
                continue
            # TODO: implement Jump Point Search, for now, we resign from
            #  using real terrain costs and calculate fast heuristic for
            #  each waypoints pair, because it efficiently finds best
            #  path, but it ignores tiles-moving-costs:
            total = cost_so_far[current] + heuristic(adjacent_grid, current)
            if total < cost_so_far[adjacent_grid]:
                previous[adjacent_grid] = current
                cost_so_far[adjacent_grid] = total
                priority = total + heuristic(adjacent_grid, end) * 1.001
                put_to_unexplored(adjacent_grid, priority)
        explored.update(walkable)
    # if path was not found searching by walkable tiles, we call second
    # pass and search for pathable nodes this time
    if not pathable:
        return a_star(map_nodes, start, end, pathable=True)
    return False  # no third pass, if there is no possible path!


def heuristic(start: GridPosition, end: GridPosition) -> float:
    return abs(end[0] - start[0]) + abs(end[1] - start[1])
    # distances = (end[0] - start[0]), (end[1] - start[1])
    # x_dist, y_dist = sorted(distances)  # to avoid duplicating keys
    # return self.euclidean_distances(x_dist, y_dist)

@lru_cache
def euclidean_distances(self, x_dist, y_dist):
    """
    Calculate heuristic distance between two GridPositions using built-in
    math.hypot function and lru_cache to store already calculated distances
    (since we have a finite number of possible distances on the map grid).
    """
    return math.hypot(x_dist, y_dist)


def reconstruct_path(map_nodes: Dict[GridPosition, MapNode],
                     previous_nodes: Dict[GridPosition, GridPosition],
                     current_node: GridPosition) -> MapPath:
    path = [map_nodes[current_node]]
    while current_node in previous_nodes.keys():
        current_node = previous_nodes[current_node]
        path.append(map_nodes[current_node])
    return [node.position for node in path[::-1]]