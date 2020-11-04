#!/usr/bin/env python
from __future__ import annotations

from typing import Set, Deque, Optional, Sequence
from collections import deque
from arcade.arcade_types import Point
from statemachine import State, StateMachine

from utils.functions import (
    average_position_of_points_group, log, calculate_angle, close_enough,
    calculate_vector_2d
)
from map import Pathfinder, GridPosition, PATH, MapPath
from player import PlayerEntity, Player
from enums import UnitWeight
from data_types import Number, Vector2D
from game import Game


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


class Unit(PlayerEntity, Pathfinder):
    """Unit is a PlayerEntity which can move on map."""

    # # finite-state-machine states:
    # idle = State('idle', 0, initial=True)
    # moving = State('move', 1)
    # patrolling = State('patrolling', 2)
    #
    # # transitions:
    # start_patrol = idle.to(patrolling) | moving.to(patrolling)
    # move = idle.to(moving) | patrolling.to(moving) | moving.to(moving)
    # stop = patrolling.to(idle) | moving.to(idle)

    def __init__(self,
                 unit_name: str,
                 player: Player,
                 weight: UnitWeight,
                 position: Point):
        PlayerEntity.__init__(self, unit_name, player=player, position=position)
        Pathfinder.__init__(self)
        # StateMachine.__init__(self)

        self.weight: UnitWeight = weight
        self.visibility_radius = 100

        # cache frequently called methods with many 'dots':
        self.normalize_position = self.map.normalize_position
        self.position_to_node = self.map.position_to_node
        self.position_to_grid = self.map.position_to_grid

        self.position = self.normalize_position(*self.position)
        self.current_node = self.position_to_node(*self.position)
        self.current_node.walkable = False

        self.path: Deque[GridPosition] = deque()
        self.speed = 4
        self.current_speed = 0

    @property
    def selectable(self) -> bool:
        return self.player is self.game.local_human_player

    def update(self):
        if self.path:
            self.follow_path()
        else:
            self.stop()
        super().update()

    def follow_path(self):
        destination = self.path[0]
        if not close_enough(self.position, destination, self.speed):
            self.move_to_current_waypoint(destination)
        else:
            self.get_next_waypoint(destination)

    def get_next_waypoint(self, destination):
        self.position = destination
        self.path.popleft()

    def move_to_current_waypoint(self, destination):
        desired_angle = calculate_angle(*self.position, *destination)
        self.angle = desired_angle
        self.change_x, self.change_y = self.vector_2d(desired_angle)

    def vector_2d(self, angle: float, speed: Optional[float] = 0) -> Vector2D:
        return calculate_vector_2d(angle, speed or self.speed)

    def move_to(self, x: Number, y: Number):
        destination = self.position_to_grid(x, y)
        start = self.position_to_grid(*self.position)
        if self.map.node(destination).walkable:
            if path := self.find_path(start, destination):
                self.create_new_path(destination, path)

    def create_new_path(self, destination: GridPosition, path: MapPath):
        if self.game.debug:
            self.debug_found_path(path, destination)
        self.path = deque(path)

    def debug_found_path(self, path: MapPath, destination: GridPosition):
        self.game.debugged.clear()
        self.game.debugged.append([PATH, path])
        log(f'{self} found path to {destination}, path: {path}')
