#!/usr/bin/env python
from __future__ import annotations

from random import gauss

from typing import List

from arcade.texture import Texture

from effects.constants import SHOT_BLAST
from effects.sound import SOUNDS_EXTENSION
from utils.geometry import move_along_vector
from effects.explosions import Explosion
from players_and_factions.player import PlayerEntity


class Weapon:
    """Spawn a Weapon instance for each Unit you want to be able to fight."""

    def __init__(self, name: str, owner: PlayerEntity):
        self.max_ammunition: int = 0
        self.magazine_size = 0
        self.effective_against_infantry = False
        self.owner = owner
        self.name: str = name
        self.damage: float = 10.0
        self.penetration: float = 2.0
        self.accuracy: float = 75.0
        self.range: float = 200.0
        self.rate_of_fire: float = 4  # 4 seconds
        self.ammo_per_shot = 1
        self.next_firing_time = 0
        self.shot_sound = '.'.join((name, SOUNDS_EXTENSION))
        self.projectile_sprites: List[Texture] = []
        self.explosion_name = SHOT_BLAST
        self.owner.game.explosions_pool.add(self.explosion_name, 75)

        for attr_name, value in self.owner.game.configs['weapons'][name].items():
            setattr(self, attr_name, value)

        self.ammunition: int = self.max_ammunition
        self.ammo_left_in_magazine = self.magazine_size

    def reloaded(self) -> bool:
        return self.owner.timer['total'] >= self.next_firing_time

    def shoot(self, target: PlayerEntity):
        self.next_firing_time = self.owner.timer['total'] + self.rate_of_fire
        self.create_shot_audio_visual_effects()
        self.consume_ammunition()
        if self.check_if_target_was_hit(target):
            target.on_being_damaged(self.damage, self.penetration)

    def consume_ammunition(self):
        if self.magazine_size:
            self.ammo_left_in_magazine -= 1
            if not self.ammo_left_in_magazine:
                self.ammo_left_in_magazine = self.magazine_size
                self.next_firing_time += (self.rate_of_fire * 4)
        self.ammunition = max(0, self.ammunition - 1)

    def check_if_target_was_hit(self, target: PlayerEntity) -> bool:
        hit_chance = sum(
            (
                self.accuracy,
                self.owner.experience * 0.05,
                -target.experience * 0.05,
                25 if target.is_building else 0,
                -target.cover,
                -25 if self.owner.moving else 0,
                -15 if target.moving else 0,
                -25 if target.is_infantry and not self.owner.is_infantry else 0
            )
        )
        return gauss(hit_chance, 0.1) < hit_chance

    def create_shot_audio_visual_effects(self):
        barrel_angle = 45 * self.owner.barrel_end
        x, y = self.owner.center_x, self.owner.center_y + 10
        blast_position = move_along_vector((x, y), 35.0, angle=barrel_angle)
        self.owner.game.create_effect(Explosion, SHOT_BLAST, *blast_position)
        self.owner.game.sound_player.play_sound(self.shot_sound, sound_position=(x, y))
