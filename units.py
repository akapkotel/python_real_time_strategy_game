#!/usr/bin/env python
from __future__ import annotations

from typing import Set, Optional, Sequence
from arcade.arcade_types import Point
from statemachine import State, StateMachine

from game import Game

from functions import average_position_of_points_group
from map import Pathfinder, GridPosition, PATH
from player import PlayerEntity, Player
from enums import UnitWeight
from scheduling import log


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


class Unit(PlayerEntity, Pathfinder, StateMachine):
    """Unit is a PlayerEntity which can move on map."""

    # finite-state-machine states:
    idle = State('idle', 0, initial=True)
    moving = State('move', 1)
    patrolling = State('patrolling', 2)

    # transitions:
    start_patrol = idle.to(patrolling) | moving.to(patrolling)
    move = idle.to(moving) | patrolling.to(moving)
    stop = patrolling.to(idle) | moving.to(idle)

    def __init__(self,
                 unit_name: str,
                 player: Player,
                 weight: UnitWeight,
                 position: Point):
        PlayerEntity.__init__(self, unit_name, player=player, position=position)
        Pathfinder.__init__(self)
        StateMachine.__init__(self)

        self.weight: UnitWeight = weight
        self.visibility_radius = 100

        self.position = self.game.map.normalize_position(*self.position)
        self.current_node = self.game.map.position_to_node(*self.position)

    def move_to(self, destination: GridPosition):
        log(f'move_to')
        if (start := self.current_node.grid) == destination:
            return
        else:
            path = self.find_path(start, destination)
            self.game.debugged.clear()
            self.game.debugged.append([PATH, path])
            log(f'Found path: {path}')


if __name__:
    pass
