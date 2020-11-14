#!/usr/bin/env python
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import deque
from typing import Deque, List, Set, Optional, Union, cast

from arcade import AnimatedTimeBasedSprite
from arcade.arcade_types import Point

from buildings.buildings import Building
from utils.enums import UnitWeight
from game import UPDATE_RATE
from scenarios.map import GridPosition, MapNode, MapPath, PATH, Sector, Pathfinder
from players_and_factions.player import Player, PlayerEntity
from units.units_tasking import TasksExecutor, UnitTask
from utils.functions import (
    calculate_angle, distance_2d, log, vector_2d
)


class Unit(PlayerEntity, TasksExecutor):
    """Unit is a PlayerEntity which can move on map."""

    def __init__(self,
                 unit_name: str,
                 player: Player,
                 weight: UnitWeight,
                 position: Point,
                 tasks_on_start: Optional[List[UnitTask]] = None):
        PlayerEntity.__init__(self, unit_name, player, position)
        TasksExecutor.__init__(self, tasks_on_start)

        self.weight: UnitWeight = weight
        self.visibility_radius = 100

        # pathfinding-related:
        self.angle = random.random() * 360
        self.position = self.map.normalize_position(*self.position)
        self.reserved_node = None
        self.current_node = node = self.map.position_to_node(*self.position)
        self.current_sector: Optional[Sector] = None
        self.update_current_sector()

        self.block_map_node(node)

        self.path: Deque[GridPosition] = deque()
        self.waiting_for_path: List[int, MapPath] = [0, []]
        self.speed = 4
        self.current_speed = 0

        self.permanent_units_group: int = 0

    @property
    def current_task(self) -> Optional[UnitTask]:
        try:
            return self.tasks[0]
        except IndexError:
            return None

    @abstractmethod
    def needs_repair(self) -> bool:
        raise NotImplementedError

    def on_update(self, delta_time: float = 1/60):
        super().on_update(delta_time)
        self.evaluate_tasks()

        new_current_node = self.map.position_to_node(*self.position)
        if self in self.game.local_human_player.faction.units:
            self.update_observed_area(new_current_node)

        self.update_blocked_map_nodes(new_current_node)
        self.update_current_sector()
        self.update_pathfinding()

    def update_observed_area(self, new_current_node: MapNode):
        if self.observed_nodes and new_current_node == self.current_node:
            self.game.fog_of_war.explore_map(self.observed_nodes)
        else:
            self.observed_nodes = self.calculate_observed_area()
            self.game.fog_of_war.explore_map(self.observed_nodes)

    def update_blocked_map_nodes(self, new_current_node):
        """
        Units are blocking MapNodes they are occupying to enable other units
        avoid collisions by navigating around blocked nodes.
        """
        self.scan_next_nodes_for_collisions()
        self.update_current_blocked_node(new_current_node)
        if len(self.path) > 1:
            self.update_reserved_node()

    def update_current_blocked_node(self, new_current_node: MapNode):
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

    def scan_next_nodes_for_collisions(self):
        if self.path:
            next_node = self.map.position_to_node(*self.path[0])
            if not next_node.walkable and next_node.unit_id != self.id:
                blocker = self.game.units.get_id(next_node.unit_id)
                self.find_best_way_to_avoid_collision(blocker)

    def find_best_way_to_avoid_collision(self, blocker):
        if (blocker.path or blocker.waiting_for_path[0] or
                self.is_enemy(blocker) or blocker in Pathfinder.instance):
            self.wait_for_free_path()
        elif self.find_alternative_path() is not None:
            pass
        else:
            self.ask_for_pass(blocker)

    def wait_for_free_path(self):
        """
        Waiting for free path is useful when next node is only temporarily
        blocked (blocking Unit is moving) and allows to avoid pathfinding
        the path with A* algorthm. Instead, Unit 'shelves' currently found
        path and after 1 second 'unshelves' it in countdown_waiting method.
        """
        self.waiting_for_path = [1 // UPDATE_RATE, self.path.copy()]
        self.path.clear()
        self.stop()

    def find_alternative_path(self) -> Optional[Deque]:
        if len(path := self.path) > 1:
            destination = self.map.position_to_node(*path[1])
            adjacent = self.current_node.walkable_adjacent
            for node in (n for n in adjacent if n in destination.walkable_adjacent):
                self.path[0] = node.position
                return self.path

    def ask_for_pass(self, blocker: Unit):
        if blocker.find_free_tile_to_unblock_way(self.path):
            self.wait_for_free_path()
        else:
            destination = self.map.position_to_grid(*self.path[-1])
            self.move_to(destination)

    def find_free_tile_to_unblock_way(self, path) -> bool:
        adjacent = self.current_node.walkable_adjacent
        possible = [n for n in adjacent if n.position not in path]
        try:
            free_tile = random.choice(possible)
            self.move_to(self.map.position_to_grid(*free_tile.position))
            return True
        except IndexError:
            return False

    def update_current_sector(self):
        if (sector := self.current_node.sector) != self.current_sector:
            if self.current_sector is not None:
                self.current_sector.units_and_buildings.discard(self)
            self.current_sector = sector
            sector.units_and_buildings.add(self)

    def update_pathfinding(self):
        if self.waiting_for_path[0]:
            self.countdown_waiting()
        if self.path:
            self.follow_path()
        else:
            self.stop()

    def countdown_waiting(self):
        self.waiting_for_path[0] -= 1
        if self.waiting_for_path[0] == 0:
            destination_position = self.waiting_for_path[1][-1]
            self.move_to(self.map.position_to_grid(*destination_position))

    def follow_path(self):
        destination = self.path[0]
        speed = self.current_speed
        if (distance_left := distance_2d(self.position, destination)) <= speed:
            self.move_to_next_waypoint()
        else:
            self.move_to_current_waypoint(destination, distance_left)

    def move_to_next_waypoint(self):
        self.path.popleft()

    def move_to_current_waypoint(self, destination, distance_left):
        self.angle = angle = calculate_angle(*self.position, *destination)
        self.current_speed = speed = min(distance_left, self.speed)
        self.change_x, self.change_y = vector_2d(angle, speed)

    def move_to(self, destination: GridPosition):
        self.path.clear()
        self.cancel_path_requests()
        start = self.map.position_to_grid(*self.position)
        Pathfinder.instance.request_path(self, start, destination)

    def create_new_path(self, path: MapPath):
        self.path = deque(path[1:])
        self.waiting_for_path[0] = 0
        self.unschedule_earlier_move_orders()

    def unschedule_earlier_move_orders(self):
        for event in (e for e in self.scheduled_events if e.function == self.move_to):
            self.unschedule_event(event)

    def debug_found_path(self, path: MapPath, destination: GridPosition):
        self.game.debugged.clear()
        self.game.debugged.append([PATH, path])
        log(f'{self} found path to {destination}, path: {path}')

    def kill(self):
        self.current_sector.units_and_buildings.discard(self)

        self.cancel_path_requests()

        for node in (self.current_node, self.reserved_node):
            if node is not None:
                self.unblock_map_node(node)

        super().kill()

    def cancel_path_requests(self):
        self.game.pathfinder.cancel_path_requests(self)

    def get_sectors_to_scan_for_enemies(self) -> List[Sector]:
        return [self.current_sector] + self.current_sector.adjacent_sectors()

    def visible_for(self, other: PlayerEntity) -> bool:
        other: Union[Unit, Building]
        if self.player is self.game.local_human_player and not other.is_building:
            if other.current_node not in self.observed_nodes:
                return False
        return super().visible_for(other)

    def get_nearby_friends(self) -> Set[PlayerEntity]:
        return {
            u for u in self.current_sector.units_and_buildings if not
            u.is_enemy(self)
        }

    def set_permanent_units_group(self, index: int = 0):
        if group := self.permanent_units_group:
            self.game.permanent_units_groups[group].discard(self)
        self.permanent_units_group = index


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
        return cast(int, self._health) < 25 * len(self.soldiers)

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


if __name__:
    from units.unit_management import PermanentUnitsGroup
