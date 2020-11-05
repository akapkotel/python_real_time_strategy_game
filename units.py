#!/usr/bin/env python
from __future__ import annotations

from typing import Set, Deque, Optional, Sequence, List
from collections import deque
from abc import ABC, abstractmethod
from arcade import AnimatedTimeBasedSprite
from arcade.arcade_types import Point

from utils.functions import (
    average_position_of_points_group, log, calculate_angle, close_enough,
    vector_2d, distance_2d
)
from map import Pathfinder, GridPosition, PATH, MapPath, MapNode
from units_tasking import UnitTask, TasksExecutor
from data_types import Number, Vector2D, UnitId
from player import PlayerEntity, Player
from scheduling import ScheduledEvent

from enums import UnitWeight
from game import Game, UPDATE_RATE


class PermanentUnitsGroup:
    """
    Player can group units by selecting them with mouse and pressing CTRL +
    numeric keys (1-9). Such groups could be then quickly selected by pressing
    their numbers.
    """
    game: Optional[Game] = None

    def __init__(self, group_id: int, units: Sequence[Unit]):
        self.group_id = group_id
        self.units: Set[Unit] = set(units)

    @property
    def position(self) -> Point:
        positions = [(u.center_x, u.center_y) for u in self.units]
        return average_position_of_points_group(positions)

    def discard(self, unit: Unit):
        self.units.discard(unit)


class Unit(PlayerEntity, TasksExecutor, Pathfinder):
    """Unit is a PlayerEntity which can move on map."""

    def __init__(self,
                 unit_name: str,
                 player: Player,
                 weight: UnitWeight,
                 position: Point,
                 tasks_on_start: Optional[List[UnitTask]] = None):
        PlayerEntity.__init__(self, unit_name, player=player, position=position)
        TasksExecutor.__init__(self, tasks_on_start)
        Pathfinder.__init__(self)

        self.weight: UnitWeight = weight
        self.visibility_radius = 100

        # pathfinding-related:
        self.position = self.map.normalize_position(*self.position)
        self.reserved_node = None
        self.current_node = node = self.map.position_to_node(*self.position)
        self.block_map_node(node)

        self.path: Deque[GridPosition] = deque()
        self.waiting_for_path: List[int, Deque] = [0, None]
        self.speed = 3
        self.current_speed = 0

    @property
    def current_task(self) -> Optional[UnitTask]:
        try:
            return self.tasks[0]
        except IndexError:
            return None

    @abstractmethod
    def needs_repair(self) -> bool:
        raise NotImplementedError

    def update(self):
        self.evaluate_tasks()
        self.update_blocked_map_nodes()
        self.update_pathfinding()
        super().update()

    def update_blocked_map_nodes(self):
        """
        Units are blocking MapNodes they are occupying to enable other units
        avoid collisions by navigating around blocked nodes.
        """
        self.scan_next_nodes_for_collisionss()
        self.update_current_blocked_node()
        if len(self.path) > 1:
            self.update_reserved_node()

    def update_current_blocked_node(self):
        new_current_node = self.map.position_to_node(*self.position)
        self.swap_blocked_nodes(self.current_node, new_current_node)
        self.current_node = new_current_node

    def update_reserved_node(self):
        new_reserved_node = self.map.position_to_node(*self.path[0])
        self.swap_blocked_nodes(self.reserved_node, new_reserved_node)
        self.reserved_node = new_reserved_node

    def swap_blocked_nodes(self, unblocked: MapNode, blocked: MapNode):
        if unblocked is not None:
            self.unblock_map_node(unblocked)
        self.block_map_node(blocked)

    @staticmethod
    def unblock_map_node(node: MapNode):
        node.unit_id = None

    def block_map_node(self, node: MapNode):
        node.unit_id = self.id

    def scan_next_nodes_for_collisionss(self):
        if not self.path:
            return
        if len(self.path) == 1:
            self.scan_node_for_collisions(0)
        else:
            self.scan_node_for_collisions(1)

    def scan_node_for_collisions(self, path_index: int):
        next_node = self.map.position_to_node(*self.path[path_index])
        if not next_node.walkable and next_node.unit_id != self.id:
            if self.game.units.id_elements_dict[next_node.unit_id].path:
                self.wait_for_free_path()
            else:
                self.schedule_pathfinding(self.map.position_to_grid(*self.path[-1]))

    def wait_for_free_path(self):
        """
        Waiting for free path is useful when next node is only temporarily
        blocked (blocking Unit is moving) and allows to avoid pathfinding
        the path with A* algorthm. Instead, Unit 'shelves' currently found
        path and after 1 second 'unshelves' it in countdown_waiting method.
        """
        self.waiting_for_path = [1 / UPDATE_RATE, self.path.copy()]
        self.path.clear()

    def update_pathfinding(self):
        if self.waiting_for_path[0]:
            self.countdown_waiting()
        if self.path:
            self.follow_path()
        else:
            self.stop()

    def countdown_waiting(self):
        self.waiting_for_path[0] -= 1
        if not self.waiting_for_path[0]:
            self.path = self.waiting_for_path[1]

    def follow_path(self):
        destination = self.path[0]
        if not close_enough(self.position, destination, self.current_speed):
            self.move_to_current_waypoint(destination)
        else:
            self.move_to_next_waypoint()

    def move_to_next_waypoint(self):
        self.path.popleft()

    def move_to_current_waypoint(self, destination):
        self.angle = angle = calculate_angle(*self.position, *destination)
        distance_left = distance_2d(self.position, destination)
        self.current_speed = speed = min(distance_left, self.speed)
        self.change_x, self.change_y = vector_2d(angle, speed)

    def move_to(self, destination: GridPosition):
        start = self.map.position_to_grid(*self.position)
        if self.map.grid_to_node(destination).walkable:
            if path := self.find_path(start, destination):
                self.create_new_path(destination, path)
            else:
                self.schedule_pathfinding(destination)

    def create_new_path(self, destination: GridPosition, path: MapPath):
        if self.game.debug:
            self.debug_found_path(path, destination)
        self.path = deque(path[1:])

    def schedule_pathfinding(self, destination: GridPosition):
        """
        Rather costly way to delay pathfinding execution. It is used only
        when Unit already have not found correct path to the destination
        because it is blocked for a longer while.
        """
        self.path.clear()
        self.schedule_event(
            ScheduledEvent(
                creator=self,
                delay=1,
                function=self.move_to,
                args=(destination,),
            )
        )

    def debug_found_path(self, path: MapPath, destination: GridPosition):
        self.game.debugged.clear()
        self.game.debugged.append([PATH, path])
        log(f'{self} found path to {destination}, path: {path}')


class Vehicle(Unit):

    @property
    def needs_repair(self) -> bool:
        return self._health < self._max_health


class Infantry(Unit, ABC):

    def __init__(self, unit_name: str, player: Player, weight: UnitWeight,
                 position: Point):
        super().__init__(unit_name, player, weight, position)

        self.max_soldiers = 4
        self.soldiers: List[Soldier] = []

        self.health_restoration = 0.003

    def __len__(self):
        return len(self.soldiers)

    @property
    def needs_medic(self) -> bool:
        return int(self._health) < 25 * len(self.soldiers)

    def update(self):
        super().update()
        self.restore_soldiers_health()

    def restore_soldiers_health(self):
        for soldier in self.soldiers:
            self._health += soldier.restore_health()


class Soldier(AnimatedTimeBasedSprite):
    _max_health = 25
    health = _max_health
    health_restoration = 0.003

    def restore_health(self) -> float:
        wounds = round(self._max_health - self.health, 3)
        health_gained = min(self.health_restoration, wounds)
        self.health += health_gained
        return health_gained
