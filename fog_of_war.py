#!/usr/bin/env python

from typing import Set, Optional, Dict
from functools import lru_cache
from numba import njit

from arcade import Sprite, SpriteList, make_circle_texture

from data_types import GridPosition
from colors import BLACK, FOG
from map import TILE_WIDTH, TILE_HEIGHT, MapNode
from game import Game


OFFSET_X = TILE_WIDTH // 2
OFFSET_Y = TILE_HEIGHT // 2


DARK_TEXTURE = make_circle_texture(2 * TILE_WIDTH, BLACK)
FOG_TEXTURE = make_circle_texture(2 * TILE_WIDTH, FOG)


class FogSprite(Sprite):

    def __init__(self, position, texture):
        px, py = position
        super().__init__(center_x=px, center_y=py)
        self.texture = texture


class FogOfWar:
    game: Optional[Game] = None

    def __init__(self):
        """
        Create hashset of map tiles (corresponding with Map nodes) which on
        the beginning are all colored BLACK - hidden from player. Second
        hashset keeps track of currently 'revealed' tiles - seen by
        player's units. By comparing these sets of tiles we determine, Where
        should be FoW displayed and where map is visible.
        """
        # this Set contains id's of Tiles which are currently visible:
        self.revealed: Set[GridPosition] = set()
        # this contains id's of fog-hidden Tiles:
        self.fog_tiles: Set[GridPosition] = set()
        # static set used to compare dark map tiles with currently revealed:
        tiles = self.game.map.nodes
        self.dark_tiles: Set[GridPosition] = set([k for k in tiles.keys()])
        # to check if all map is revealed (no dark tiles):
        self.unexplored: Set[GridPosition] = self.dark_tiles.copy()
        # this dict keeps track of Sprites - if they should be drawn or not:
        self.tiles_to_sprites: Dict[GridPosition, FogSprite] = {}
        # sprites lists - this SpriteList is drawn in game:
        self.fog_sprites: Optional[SpriteList] = self.create_dark_sprites(tiles)

    def create_dark_sprites(self, map_tiles: Dict[GridPosition, MapNode]):
        """
        Fill whole map with black tiles representing unexplored, hidden area.
        """
        fog_sprites = SpriteList(is_static=True)
        append_to_sprites = fog_sprites.append
        fog_tiles = self.fog_tiles
        self.tiles_to_sprites = {tile: i for i, tile in enumerate(map_tiles)}
        for tile in map_tiles:
            x, y = self.tile_position(*tile)
            texture = FOG_TEXTURE if tile in fog_tiles else DARK_TEXTURE
            dark_sprite = FogSprite((x, y), texture)
            self.tiles_to_sprites[tile] = dark_sprite
            append_to_sprites(dark_sprite)
        return fog_sprites

    def explore_map(self, tiles: Set[GridPosition]):
        self.revealed.update(tiles)
        self.fog_tiles.update(tiles)

    def update(self):
        """
        Each frame check which map-tiles are visible for player units,
        and which are not, then remove visible from SpriteList and add
        Sprite representing FoW to tiles which were revealed once but are
        no longer visible.
        """
        # set local variables for speed:
        tiles_to_sprites = self.tiles_to_sprites
        revealed = self.revealed
        fog_sprites = self.fog_sprites
        # revealing visible tiles (removing 'dark' tiles):
        self.unexplored.difference_update(revealed)
        remove_from_sprites = fog_sprites.remove
        for tile in revealed.intersection(tiles_to_sprites):
            remove_from_sprites(tiles_to_sprites[tile])
            del tiles_to_sprites[tile]
        # covering tiles with semi-transparent 'fog' sprites:
        dark_tiles = self.dark_tiles - revealed
        append_to_sprites = fog_sprites.append
        for tile in dark_tiles.difference(tiles_to_sprites):
            x, y = self.tile_position(*tile)
            tiles_to_sprites[tile] = sprite = FogSprite((x, y), FOG_TEXTURE)
            append_to_sprites(sprite)
        self.fog_sprites = fog_sprites
        self.revealed.clear()

    @staticmethod
    @lru_cache()
    @njit(["int64, int64"], nogil=True, fastmath=True)
    def tile_position(x, y):
        return x * TILE_WIDTH + OFFSET_X, y * TILE_WIDTH + OFFSET_Y

    def draw(self):
        self.fog_sprites.draw()
