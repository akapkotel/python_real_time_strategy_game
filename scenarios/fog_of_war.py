#!/usr/bin/env python

from functools import lru_cache
from typing import Dict, KeysView, Optional, Set

from arcade import Sprite, SpriteList, make_circle_texture
from numba import njit

from utils.colors import BLACK, FOG
from utils.data_types import GridPosition
from game import Game, TILE_HEIGHT, TILE_WIDTH

OFFSET_X = TILE_WIDTH // 2
OFFSET_Y = TILE_HEIGHT // 2


DARK_TEXTURE = make_circle_texture(2 * TILE_WIDTH, BLACK)
FOG_TEXTURE = make_circle_texture(2 * TILE_WIDTH, FOG)


class FogSprite(Sprite):

    def __init__(self, position, texture):
        super().__init__(center_x=position[0], center_y=position[1])
        self.texture = texture


class FogOfWar:
    game: Optional[Game] = None

    def __init__(self):
        """
        TO DO:
        """
        # grid-data of the game-map:
        self.map_grids: KeysView[GridPosition] = self.game.map.nodes.keys()
        # Tiles which have not been revealed yet:
        self.unexplored: Set[GridPosition] = set([k for k in self.map_grids])

        # Tiles revealed in this frame:
        self.visible: Set[GridPosition] = set()
        # All tiles revealed to this moment:
        self.explored: Set[GridPosition] = set()

        # Dict to find and manipulate Sprites in the spritelist:
        self.grids_to_sprites: Dict[GridPosition, FogSprite] = {}
        # Black or semi-transparent grey sprites are drawn on the screen:
        self.fog_sprite_list = self.create_dark_sprites()

    def create_dark_sprites(self):
        """
        Fill whole map with black tiles representing unexplored, hidden area.
        """
        fog_sprite_list = SpriteList(is_static=True)
        append_to_sprites = fog_sprite_list.append
        get_tile_position = self.get_tile_position
        for grid in self.map_grids:
            sprite = FogSprite(get_tile_position(*grid), DARK_TEXTURE)
            self.grids_to_sprites[grid] = sprite
            append_to_sprites(sprite)
        return fog_sprite_list

    def explore_map(self, explored: Set[GridPosition]):
        """
        Call this method from each PlayerEntity, which is observing map,
        sending as param a set of GridPositions seen by the entity.
        """
        self.visible.update(explored)

    def update(self):
        # remove currently visible tiles from the fog-of-war:
        visible = self.visible
        grids_to_sprites = self.grids_to_sprites
        fog_sprite_list = self.fog_sprite_list
        remove_from_sprites = fog_sprite_list.remove
        for grid in visible.intersection(grids_to_sprites):
            remove_from_sprites(grids_to_sprites[grid])
            del grids_to_sprites[grid]
        # add grey-semi-transparent fog to the tiles which are no longer seen:
        fog = self.explored - visible
        append_to_sprites = fog_sprite_list.append
        get_tile_position = self.get_tile_position
        for grid in fog.difference(grids_to_sprites):
            x, y = get_tile_position(*grid)
            grids_to_sprites[grid] = sprite = FogSprite((x, y), FOG_TEXTURE)
            append_to_sprites(sprite)
        self.explored.update(visible)
        visible.clear()

    @staticmethod
    @lru_cache()
    @njit(["int64, int64"], nogil=True, fastmath=True)
    def get_tile_position(x, y):
        return x * TILE_WIDTH + OFFSET_X, y * TILE_HEIGHT + OFFSET_Y

    def draw(self):
        self.fog_sprite_list.draw()
