#!/usr/bin/env python
from __future__ import annotations

from collections import deque
from typing import Dict, Deque

from arcade import Sprite, load_spritesheet

from effects.constants import (
    EXPLOSION_SMALL_5, HIT_BLAST, SHOT_BLAST, EXPLOSION
)
from utils.classes import Singleton
from utils.functions import get_path_to_file

path = get_path_to_file
explosions = {
    EXPLOSION: load_spritesheet(path('explosion.png'), 256, 256, 15, 75),
    SHOT_BLAST: load_spritesheet(path('shot_blast.png'), 256, 256, 4, 16),
    HIT_BLAST: load_spritesheet(path('hit_blast.png'), 256, 256, 8, 48),
    EXPLOSION_SMALL_5: load_spritesheet(path('explosion_small_5.png'), 256, 256, 15, 60)
}


class ExplosionsPool(Singleton):
    """
    Pooling allows to avoid initializing many, often-used objects lowering
    CPU load. Number of pooled Explosions is dynamically adjusted to number of
    Units in game.
    """

    def __init__(self):
        super().__init__()
        self.explosions: Dict[str, Deque] = {
            name: deque([Explosion(name, self, EXPLOSION in name)
                         for _ in range(20)]) for name in explosions
        }

    def get(self, explosion_name, x, y) -> Explosion:
        try:
            explosion = self.explosions[explosion_name].popleft()
        except IndexError:
            explosion = Explosion(explosion_name, self)
        explosion.position = x, y
        return explosion

    def put(self, explosion: Explosion):
        self.explosions[explosion.name].append(explosion)

    def add(self, explosion_name: str, required: int):
        explosions_count = len(self.explosions[explosion_name])
        if explosions_count < required:
            self.put(Explosion(explosion_name, self))
        elif explosions_count > required:
            self.explosions[explosion_name].popleft()


class Explosion(Sprite):
    """ This class creates an explosion animation."""
    game = None

    def __init__(self, sprite_sheet_name: str, pool, sound=True):
        super().__init__()
        self.name = sprite_sheet_name
        self.pool = pool
        self.sound = '.'.join((self.name.lower(), 'wav')) if sound else None
        self.textures = [t for t in explosions[sprite_sheet_name]]
        self.set_texture(0)
        self.exploding = False

    def play(self):
        self.set_texture(0)
        self.cur_texture_index = 0  # Start at the first frame
        self.exploding = True
        if self.sound is not None:
            self.game.window.sound_player.play_sound(self.sound)

    def on_update(self, delta_time: float = 1/60):
        # Update to the next frame of the animation. If we are at the end
        # of our frames, then put it back to the pool.
        if self.exploding:
            self.update_animation(delta_time)
            self.cur_texture_index += 1
            if self.cur_texture_index < len(self.textures):
                self.set_texture(self.cur_texture_index)
            else:
                self.return_to_pool()

    def return_to_pool(self):
        self.exploding = False
        self.remove_from_sprite_lists()
        self.pool.put(self)
