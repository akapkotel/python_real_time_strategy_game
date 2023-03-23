#!/usr/bin/env python
from __future__ import annotations

from random import uniform

from typing import List

from arcade.texture import Texture

from effects.constants import SHOT_BLAST
from effects.sound import SOUNDS_EXTENSION
from players_and_factions.player import PlayerEntity

EXPERIENCE_HIT_CHANCE_BONUS = 0.05

INFANTRY_HIT_CHANCE_PENALTY = -25

TARGET_MOVEMENT_HIT_PENALTY = -15

MOVEMENT_HIT_PENALTY = -25

BUILDING_HIT_CHANCE_BONUS = 25


class Weapon:
    """Spawn a Weapon instance for each Unit you want to be able to fight."""

    def __init__(self, name: str, owner: PlayerEntity):
        self.max_ammunition: int = 0
        self.magazine_size = 0
        self.effective_against_infantry = False
        self.owner = owner
        self.name: str = name
        self.damage: float = 0
        self.penetration: float = 0
        self.accuracy: float = 0
        self.range: float = 0
        self.rate_of_fire: float = 4  # 4 seconds
        self.ammo_per_shot = 1
        self.next_firing_time = 0
        self.shot_sound = '.'.join((name, SOUNDS_EXTENSION))
        self.projectile_sprites: List[Texture] = []
        self.explosion_name = SHOT_BLAST
        self.owner.game.explosions_pool.add(self.explosion_name, 75)

        for attr_name, value in self.owner.game.configs[name].items():
            setattr(self, attr_name, value)

        self.ammunition: int = self.max_ammunition
        self.ammo_left_in_magazine = self.magazine_size

    def reloaded(self) -> bool:
        return self.owner.timer.total >= self.next_firing_time and self.ammunition

    def shoot(self, target: PlayerEntity):
        self.next_firing_time = self.owner.timer.total + self.rate_of_fire
        self.consume_ammunition()
        if self.check_if_target_was_hit(target):
            target.on_being_damaged(self.damage, self.penetration)
        self.create_shot_audio_visual_effects()

    def consume_ammunition(self):
        if self.magazine_size:
            self.ammo_left_in_magazine -= 1
            if not self.ammo_left_in_magazine:
                self.ammo_left_in_magazine = self.magazine_size
                self.next_firing_time += (self.rate_of_fire * 4)
        self.ammunition = max(0, self.ammunition - 1)

    def check_if_target_was_hit(self, target: PlayerEntity) -> bool:
        # we use that booleans are integers we can multiply by other values to avoid if statements
        hit_chance = sum(
            (
                self.accuracy,
                -target.cover,
                self.owner.experience * EXPERIENCE_HIT_CHANCE_BONUS,
                -target.experience * EXPERIENCE_HIT_CHANCE_BONUS,
                BUILDING_HIT_CHANCE_BONUS * target.is_building,
                MOVEMENT_HIT_PENALTY * self.owner.moving,
                TARGET_MOVEMENT_HIT_PENALTY * target.moving,
                INFANTRY_HIT_CHANCE_PENALTY * (target.is_infantry -self.owner.is_infantry)
            )
        )
        return uniform(0, 100) < hit_chance

    def create_shot_audio_visual_effects(self):
        x, y = self.owner.center_x, self.owner.center_y + 10
        self.owner.game.sound_player.play_sound(self.shot_sound, sound_position=(x, y))
