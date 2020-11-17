#!/usr/bin/env python
from __future__ import annotations

from typing import List, Optional

from arcade.texture import Texture

from players_and_factions.player import PlayerEntity


class Weapon:
    name: str
    damage: float
    penetration: float
    accuracy: float
    range: float
    rate_of_fire: int
    reloading_time_left: int = 0
    target: Optional[PlayerEntity] = None
    shot_sound: Optional[str] = None
    projectile_sprites: List[Texture] = []

    def reload(self):
        if self.reloading_time_left:
            self.reloading_time_left -= 1
        else:
            self.reloading_time_left = self.rate_of_fire
            self.shoot()

    def shoot(self):
        raise NotImplementedError
