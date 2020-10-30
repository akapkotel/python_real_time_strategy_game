#!/usr/bin/env python
from __future__ import annotations

from arcade.arcade_types import Point

from player import PlayerEntity, Player


class Building(PlayerEntity):

    def __init__(self, building_name: str, player: Player, position: Point):
        PlayerEntity.__init__(self, building_name, player, position, 4)

