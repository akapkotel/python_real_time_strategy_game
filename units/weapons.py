#!/usr/bin/env python
from __future__ import annotations

import random

from typing import List, Optional

from arcade.texture import Texture

from game import UPDATE_RATE
from players_and_factions.player import PlayerEntity
from audio.sound import SoundPlayer


class Weapon:
    sound_player = SoundPlayer('')
    name: str = 'gun'
    damage: float = 10.0
    penetration: float = 2.0
    accuracy: float = 75.0
    range: float = 200.0
    rate_of_fire: int = 6 / UPDATE_RATE  # frames
    reloading_time_left: int = 6 / UPDATE_RATE
    shot_sound: Optional[str] = 'tank_light_gun.wav'
    projectile_sprites: List[Texture] = []

    def reload(self) -> bool:
        self.reloading_time_left -= 1
        if self.reloading_time_left == 0:
            self.reloading_time_left = self.rate_of_fire
            return True
        return False

    def shoot(self, target: PlayerEntity) -> bool:
        self.sound_player.play_sound(self.shot_sound)
        return target.on_being_hit(random.gauss(self.damage, 0.25))

    def effective_against(self, enemy: PlayerEntity) -> bool:
        return self.penetration >= enemy.armour
