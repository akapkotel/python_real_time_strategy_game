#!/usr/bin/env python
from __future__ import annotations


from arcade import Sprite, load_spritesheet

from utils.functions import get_path_to_file


class Explosion(Sprite):
    """ This class creates an explosion animation """

    file_name = get_path_to_file('explosion.png')
    print(file_name)
    explosion_texture_list = load_spritesheet(file_name, 256, 256, 16, 60)

    def __init__(self, x, y):
        super().__init__()
        self.center_x = x
        self.center_y = y
        # Start at the first frame
        self.current_texture = 0
        self.textures = self.explosion_texture_list
        self.set_texture(0)

    def on_update(self, delta_time: float = 1/60):
        # Update to the next frame of the animation. If we are at the end
        # of our frames, then delete this sprite.
        self.current_texture += 1
        if self.current_texture < len(self.textures):
            self.set_texture(self.current_texture)
        else:
            self.remove_from_sprite_lists()


class ShootBlast:
    ...
