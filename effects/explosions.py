#!/usr/bin/env python
from __future__ import annotations


from arcade import Sprite, load_spritesheet

from utils.functions import get_path_to_file

path = get_path_to_file
explosions = {
    'EXPLOSION': load_spritesheet(path('explosion.png'), 256, 256, 16, 96),
    'SHOTBLAST': load_spritesheet(path('shot_blast.png'), 256, 256, 4, 16),
    'HITBLAST': load_spritesheet(path('hit_blast.png'), 256, 256, 8, 48),
    'SMALL_EXPLOSION_5': load_spritesheet(path('explosion_small_5.png'), 256, 256, 15, 60)
}


class Explosion(Sprite):
    """ This class creates an explosion animation """

    def __init__(self, x, y, spritesheet_name: str):
        super().__init__()
        self.center_x = x
        self.center_y = y
        self.textures = explosions[spritesheet_name]
        self.set_texture(0)
        self.cur_texture_index = 0  # Start at the first frame

    def on_update(self, delta_time: float = 1/60):
        # Update to the next frame of the animation. If we are at the end
        # of our frames, then delete this sprite.
        self.cur_texture_index += 1
        if self.cur_texture_index < len(self.textures):
            self.set_texture(self.cur_texture_index)
        else:
            self.kill()
