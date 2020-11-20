#!/usr/bin/env python
from __future__ import annotations

import random
from time import time as get_time

from typing import List

from arcade.texture import Texture

from game import UPDATE_RATE
from audio.sound import SOUNDS_EXTENSION
from utils.functions import move_along_vector
from effects.explosions import Explosion
from players_and_factions.player import PlayerEntity


class Weapon:
    """Spawn a Weapon instance for each Unit you want to be able to fight."""

    def __init__(self, name: str, owner: PlayerEntity):
        self.effective_against_infantry = False
        self.owner = owner
        self.name: str = name
        self.damage: float = 10.0
        self.penetration: float = 2.0
        self.accuracy: float = 75.0
        self.range: float = 200.0
        self.rate_of_fire: float = 2.0  # seconds
        self.last_firing_time = 0
        self.shot_sound = '.'.join((name, SOUNDS_EXTENSION))
        self.projectile_sprites: List[Texture] = []

    def reload(self) -> bool:
        if (now := get_time()) >= self.last_firing_time + self.rate_of_fire:
            self.last_firing_time = now
            return True
        return False

    def shoot(self, target: PlayerEntity) -> bool:
        # TODO: infantry difficult to hit [ ]
        self.create_shot_audio_visual_effects()
        self_movement = -25 if self.owner.moving else 0
        target_movement = -15 if target.moving else 0
        accuracy = self.accuracy + self_movement + target_movement
        if not random.gauss(accuracy, accuracy // 10) < accuracy:
            return False
        return target.on_being_hit(random.gauss(self.damage, self.damage // 4))

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
        if enemy.is_infantry:
            return self.effective_against_infantry
        return self.penetration >= enemy.armour
