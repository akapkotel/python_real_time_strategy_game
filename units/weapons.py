#!/usr/bin/env python
from __future__ import annotations

import random

from typing import List

from arcade.texture import Texture

from game import UPDATE_RATE
from audio.sound import SOUNDS_EXTENSION
from utils.functions import move_along_vector
from effects.explosions import Explosion
from players_and_factions.player import PlayerEntity


class Weapon:

    def __init__(self, name: str, owner: PlayerEntity):
        self.owner = owner
        self.name: str = name
        self.damage: float = 10.0
        self.penetration: float = 2.0
        self.accuracy: float = 75.0
        self.range: float = 200.0
        self.rate_of_fire: int = 6 / UPDATE_RATE  # frames
        self.reloading_time_left: int = 6 / UPDATE_RATE
        self.shot_sound = '.'.join((name, SOUNDS_EXTENSION))
        self.projectile_sprites: List[Texture] = []

    def reload(self) -> bool:
        self.reloading_time_left -= 1
        if self.reloading_time_left == 0:
            self.reloading_time_left = self.rate_of_fire
            return True
        return False

    def shoot(self, target: PlayerEntity) -> bool:
        # TODO: check accuracy [ ], infantry difficult to hit [ ]
        self.create_shot_audio_visual_effects()
        return target.on_being_hit(random.gauss(self.damage, 0.25))

    def create_shot_audio_visual_effects(self):
        self.owner.game.window.sound_player.play_sound(self.shot_sound)
        barrel_angle = 45 * self.owner.barrel_end
        start = self.owner.position
        blast_position = move_along_vector(start, 35, angle=barrel_angle)
        self.owner.game.create_effect(Explosion(*blast_position, 'SHOTBLAST'))

    def effective_against(self, enemy: PlayerEntity) -> bool:
        """
        Units and Buildings can have armour, so they can be invulnerable to
        attack. Tanks have problem to hit

        :param enemy: PlayerEntity
        :return: bool -- if this Weapon can damage targeted enemy
        """
        return self.penetration >= enemy.armour
