#!/usr/bin/env python

from functools import lru_cache
from typing import Dict, KeysView, Optional, Set, List, Tuple
from shapely.geometry import Polygon

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
        # Black or semi-transparent grey sprites are drawn_area on the screen width
        # normal SpriteLists. We divide map for smaller areas with distinct
        # spritelists to avoid updating too large sets each frame:
        self.fog_sprite_lists = self.create_dark_sprites()

        self.viewport = None

    def create_dark_sprites(self):
        """
        Fill whole map with black tiles representing unexplored, hidden area.
        """
        cols, rows = self.game.map.columns // 50, self.game.map.rows // 50

        sprite_lists = {}
        for col in range(rows + 1):
            for row in range(cols + 1):
                sprite_lists[(row, col)] = SpriteList(is_static=True)

        get_tile_position = self.get_tile_position
        for x, y in self.map_grids:
            sprite_list = sprite_lists[(x // 50, y // 50)]
            sprite = FogSprite(get_tile_position(x, y), DARK_TEXTURE)
            self.grids_to_sprites[(x, y)] = sprite
            sprite_list.append(sprite)
        return sprite_lists

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
        for grid in visible.intersection(grids_to_sprites):
            sprite_list = self.fog_sprite_lists[(grid[0] // 50, grid[1] // 50)]
            sprite_list.remove(grids_to_sprites[grid])
            del grids_to_sprites[grid]
        # add grey-semi-transparent fog to the tiles which are no longer seen:
        fog = self.explored - visible
        get_tile_position = self.get_tile_position
        for grid_x, grid_y in fog.difference(grids_to_sprites):
            x, y = get_tile_position(grid_x, grid_y)
            grids_to_sprites[(grid_x, grid_y)] = sprite = FogSprite((x, y), FOG_TEXTURE)
            sprite_list = self.fog_sprite_lists[(grid_x // 50, grid_y // 50)]
            sprite_list.append(sprite)
        self.explored.update(visible)
        visible.clear()

    @staticmethod
    @lru_cache()
    @njit(["int64, int64"], nogil=True, fastmath=True)
    def get_tile_position(x, y):
        return x * TILE_WIDTH + OFFSET_X, y * TILE_HEIGHT + OFFSET_Y

    def draw(self):
        left, right, bottom, top = self.game.viewport
        for key, sprite_list in self.fog_sprite_lists.items():
            s_left, s_right = key[0] * 3000, (key[0] + 1) * 3000
            s_bottom, s_top = key[1] * 2000, (key[1] +1) * 3000
            if left < s_right and right > s_left and bottom < s_top and top > s_bottom:
                sprite_list.draw()
