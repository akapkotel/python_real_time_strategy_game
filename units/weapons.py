#!/usr/bin/env python
from __future__ import annotations

import random
from time import time as get_time

from typing import List

from arcade.texture import Texture

from effects.sound import SOUNDS_EXTENSION
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
        self.explosion_name = 'SHOTBLAST'
        self.owner.game.explosions_pool.add(self.explosion_name, 75)

    def reload(self) -> bool:
        if (now := get_time()) >= self.last_firing_time + self.rate_of_fire:
            self.last_firing_time = now
            return True
        return False

    def shoot(self, target: PlayerEntity) -> bool:
        self.create_shot_audio_visual_effects()
        hit_chance = self.calculate_hit_chance(target)
        if not random.gauss(hit_chance, hit_chance // 10) < hit_chance:
            return False
        return target.on_being_hit(random.gauss(self.damage, self.damage // 4))

    def calculate_hit_chance(self, target):
        cover = target.cover
        experience = self.owner.experience // 20
        movement = 25 if self.owner.moving else 0
        target_movement = 15 if target.moving else 0
        hit_chance = sum(
            (self.accuracy, experience, -movement, -target_movement, -cover)
        )
        return hit_chance

    def create_shot_audio_visual_effects(self):
        self.owner.game.window.sound_player.play_sound(self.shot_sound)
        barrel_angle = 45 * self.owner.barrel_end
        x, y = self.owner.center_x, self.owner.center_y + 10
        blast_position = move_along_vector((x, y), 35, angle=barrel_angle)
        self.owner.game.create_effect(Explosion, 'SHOTBLAST', *blast_position)

    def effective_against(self, enemy: PlayerEntity) -> bool:
        """
        Units and Buildings can have armour, so they can be invulnerable to
        attack. Tanks have problem to hit

        :param enemy: PlayerEntity
        :return: bool -- if this Weapon can damage targeted enemy
        """
        return self.penetration >= enemy.armour
