#!/usr/bin/env python
from __future__ import annotations

import time

from random import gauss

from typing import List

from arcade.texture import Texture

from effects.sound import SOUNDS_EXTENSION
from utils.geometry import move_along_vector
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
        self.rate_of_fire: float = 4  # 4 seconds
        self.next_firing_time = 0
        self.shot_sound = '.'.join((name, SOUNDS_EXTENSION))
        self.projectile_sprites: List[Texture] = []
        self.explosion_name = 'SHOTBLAST'
        self.owner.game.explosions_pool.add(self.explosion_name, 75)
        for attr_name, value in self.owner.game.configs['weapons'][name].items():
            setattr(self, attr_name, value)

    def reloaded(self) -> bool:
        return time.time() >= self.next_firing_time

    def shoot(self, target: PlayerEntity):
        self.next_firing_time = time.time() + self.rate_of_fire
        self.create_shot_audio_visual_effects()
        if self.can_penetrate(target) and self.hit_target(target):
            target.on_being_damaged(damage=self.damage)

    def hit_target(self, target: PlayerEntity) -> bool:
        hit_chance = sum(
            (
                self.accuracy,
                self.owner.experience * 0.05,
                25 if target.is_building else 0,
                -target.cover,
                -25 if self.owner.moving else 0,
                -15 if target.moving else 0,
                -25 if target.is_infantry and not self.owner.is_infantry else 0
            )
        )
        return gauss(hit_chance, hit_chance * 0.20) < hit_chance

    def create_shot_audio_visual_effects(self):
        self.owner.game.window.sound_player.play_sound(self.shot_sound)
        barrel_angle = 45 * self.owner.barrel_end
        x, y = self.owner.center_x, self.owner.center_y + 10
        blast_position = move_along_vector((x, y), 35.0, angle=barrel_angle)
        self.owner.game.create_effect(Explosion, 'SHOTBLAST', *blast_position)

    def can_penetrate(self, enemy: PlayerEntity) -> bool:
        """
        Units and Buildings can have armour, so they can be invulnerable to
        attack.

        :param enemy: PlayerEntity
        :return: bool -- if this Weapon can damage targeted enemy
        """
        return self.penetration >= enemy.armour
