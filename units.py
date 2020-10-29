#!/usr/bin/env python
from __future__ import annotations

from typing import Set, Union, Optional, Sequence
from arcade.arcade_types import Point
from arcade.sprite import get_distance_between_sprites

from game import Game
from buildings import Building

from functions import average_position_of_points_group
from player import PlayerEntity, Faction, Player
from scheduling import ScheduledEvent

from enums import UnitWeight


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


class Unit(PlayerEntity):
    """Unit is a PlayerEntity which can move on map."""

    def __init__(self,
                 unit_name: str,
                 player: Player,
                 weight: UnitWeight,
                 position: Point):
        super().__init__(unit_name, player=player, position=position)

        self.weight: UnitWeight = weight
        self.visbility_radius = 100
