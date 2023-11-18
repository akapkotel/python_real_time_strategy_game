#!/usr/bin/env python
from __future__ import annotations

from random import uniform

from typing import List

from arcade.texture import Texture

from effects.sound import SOUNDS_EXTENSION
from players_and_factions.player import PlayerEntity
from utils.constants import (
    MAGAZINE_RELOAD_MULTIPLIER, EXPERIENCE_HIT_CHANCE_BONUS, INFANTRY_HIT_CHANCE_PENALTY, TARGET_MOVEMENT_HIT_PENALTY,
    MOVEMENT_HIT_PENALTY, BUILDING_HIT_CHANCE_BONUS
)


class Weapon:
    """Spawn a Weapon instance for each Unit you want to be able to fight."""

    def __init__(self, name: str, owner: PlayerEntity):
        self.max_ammunition: int = 0
        self.magazine_size = 0
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

        for attr_name, value in self.owner.game.configs[name].items():
            setattr(self, attr_name, value)

        self.ammunition: int = self.max_ammunition
        self.ammo_left_in_magazine = self.magazine_size

    @property
    def reloaded(self) -> bool:
        return self.owner.timer.total_game_time >= self.next_firing_time and self.ammunition

    def shoot(self, target: PlayerEntity):
        self.next_firing_time = self.owner.timer.total_game_time + self.rate_of_fire
        self.consume_ammunition()
        if self.check_if_target_was_hit(target):
            target.on_being_hit(self.damage, self.penetration)
        self.create_shot_audio_visual_effects()

    def consume_ammunition(self, burst_size: int = 1):
        if self.magazine_size:
            self.ammo_left_in_magazine -= burst_size
            if not self.ammo_left_in_magazine:
                self.ammo_left_in_magazine = self.magazine_size
                self.next_firing_time += (self.rate_of_fire * MAGAZINE_RELOAD_MULTIPLIER)
        self.ammunition = max(0, self.ammunition - burst_size)

    def check_if_target_was_hit(self, target: PlayerEntity) -> bool:
        # we use that booleans are integers we can multiply by other values to avoid if statements
        hit_chance = sum(
            (
                self.accuracy,
                -target.cover,
                self.owner.experience * EXPERIENCE_HIT_CHANCE_BONUS,
                -target.experience * EXPERIENCE_HIT_CHANCE_BONUS,
                BUILDING_HIT_CHANCE_BONUS * target.is_building,
                MOVEMENT_HIT_PENALTY * self.owner.is_moving,
                TARGET_MOVEMENT_HIT_PENALTY * target.is_moving,
                INFANTRY_HIT_CHANCE_PENALTY * (target.is_infantry - self.owner.is_infantry)
            )
        )
        return uniform(0, 100) < hit_chance

    def create_shot_audio_visual_effects(self):
        x, y = self.owner.center_x, self.owner.center_y + 10
        self.owner.game.sound_player.play_sound(self.shot_sound, sound_position=(x, y))
