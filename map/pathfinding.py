#!/usr/bin/env python
from __future__ import annotations

import math

from collections import defaultdict
from typing import Dict, Union

from utils.data_types import GridPosition
from utils.timing import timer
from utils.priority_queue import PriorityQueue
from game import PROFILING_LEVEL
from map.map import (MapNode, MapPath, Map, VERTICAL_DIST, adjacent_distance)


@timer(level=2, global_profiling_level=PROFILING_LEVEL, forced=False)
def a_star(map: Map,
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
    map_nodes = map.nodes
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
        explored.add(current)
        node = map_nodes[current]
        walkable = node.pathable_adjacent if pathable else node.walkable_adjacent
        for adjacent in (a for a in walkable if a.grid not in explored):
            adj_grid = adjacent.grid
            total = cost_so_far[current] + adjacent_distance(current, adj_grid)
            # TODO: implement Jump Point Search, for now, we resign from
            #  using real terrain costs and calculate fast heuristic for
            #  each waypoints pair, because it efficiently finds best
            #  path, but it ignores tiles-moving-costs:
            if total < cost_so_far[adj_grid]:
                previous[adj_grid] = current
                cost_so_far[adj_grid] = total
                priority = total + heuristic(adj_grid, end)
                put_to_unexplored(adj_grid, priority)
    # if path was not found searching by walkable tiles, we call second
    # pass and search for pathable nodes this time
    if not pathable:
        return a_star(map, start, end, pathable=True)
    return False  # no third pass, if there is no possible path!


def heuristic(start: GridPosition, end: GridPosition) -> int:
    return (abs(end[0] - start[0]) + abs(end[1] - start[1])) * VERTICAL_DIST


def reconstruct_path(map_nodes: Dict[GridPosition, MapNode],
                     previous_nodes: Dict[GridPosition, GridPosition],
                     current_node: GridPosition) -> MapPath:
    path = [map_nodes[current_node]]
    while current_node in previous_nodes.keys():
        current_node = previous_nodes[current_node]
        path.append(map_nodes[current_node])
    return [node.position for node in path[::-1]]
