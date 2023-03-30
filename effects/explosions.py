#!/usr/bin/env python
from __future__ import annotations

from arcade import Sprite, load_spritesheet, SpriteList


class ExplosionsPool:
    game = None
    explosions_names = ('explosion.png', 'shot_blast.png')  # 'hit_blast.png'
    explosions_spritesheets_paths = {}
    explosions_sounds_files_paths = {}

    def __init__(self, game):
        self.game = game
        self.explosions = SpriteList()
        for explosion_name in self.explosions_names:
            self.explosions_spritesheets_paths[explosion_name] = self.game.resources_manager.get(explosion_name)
            self.explosions_sounds_files_paths[explosion_name] = explosion_name.replace('png', 'wav')

    def create_explosion(self, explosion_name: str, x, y):
        explosion_spritesheet_path = self.explosions_spritesheets_paths[explosion_name]
        sound_file_path = self.explosions_sounds_files_paths[explosion_name]
        self.explosions.append(
            Explosion(explosion_spritesheet_path, sound_file_path, x, y)
        )

    def on_update(self, delta_time):
        self.explosions.on_update(delta_time)

    def draw(self):
        self.explosions.draw()


class Explosion(Sprite):
    """ This class creates an explosion animation."""
    game = None

    def __init__(self, explosion_spritesheet_path: str, sound_file_path: str, x, y):
        super().__init__(center_x=x, center_y=y)
        self.textures = load_spritesheet(explosion_spritesheet_path, 256, 256, 15, 60)
        self.set_texture(0)
        self.game.sound_player.play_sound(sound_file_path)

    def on_update(self, delta_time: float = 1/60):
        if self.cur_texture_index < len(self.textures) - 1:
            self.update_animation(delta_time)
        else:
            self.kill()

    def update_animation(self, delta_time: float = 1/60):
        self.cur_texture_index += 1
        self.set_texture(self.cur_texture_index)
