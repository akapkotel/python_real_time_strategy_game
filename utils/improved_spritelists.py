#!/usr/bin/env python
from __future__ import annotations

from typing import Dict, Optional, Union

from arcade import SpriteList, Sprite

from utils.game_logging import log


class SpriteListWithSwitch(SpriteList):
    """
    This is a arcade Spritelist improved with parameters: update_on, draw_on
    and method toggle_update() and toggle_draw() which controls if this
    SpriteList is updated and drawn each frame or not.
    """

    def __init__(self, use_spatial_hash=False,
                 spatial_hash_cell_size: int = 128,
                 is_static=False,
                 update_on=True,
                 draw_on=True):
        super().__init__(use_spatial_hash, spatial_hash_cell_size, is_static)
        self.update_on = update_on
        self.draw_on = draw_on

    def get_by_id(self, sprite_id: int) -> Optional[Sprite]:
        for sprite in self:
            if sprite.id == sprite_id:
                return sprite

    def on_update(self, delta_time: float = 1/60):
        if self.update_on:
            super().on_update(delta_time)

    def update(self):
        if self.update_on:
            super().update()

    def draw(self, **kwargs):
        if self.draw_on:
            super().draw(**kwargs)

    def toggle_update(self):
        self.update_on = not self.update_on

    def toggle_draw(self):
        self.draw_on = not self.draw_on


# noinspection PyUnresolvedReferences
class LayeredSpriteList(SpriteList):
    """
    This SpriteList works with Sprites having attributes: 'id', 'updated' and
    'rendered'. It is possible to switch updating and drawing of single
    sprites by changing their 'updated' and 'rendered' attributes inside
    their own logic, or by calling 'start_updating', 'start_rendering',
    'stop_updating' and 'stop_rendering' methods of SelectableSpriteList with
    the chosen Sprite as parameter.
    LayeredSpritelist also maintains hashmap of all Sprites which allows for
    fast lookups by their 'id' attribute.
    """
    game = None

    def __init__(self,
                 use_spatial_hash=False,
                 spatial_hash_cell_size=128,
                 is_static=False,
                 update_on=True,
                 draw_on=True):
        super().__init__(use_spatial_hash, spatial_hash_cell_size, is_static)
        # to keep track of triggers in spritelist, fast lookups:
        self.registry: Dict[int, Sprite] = {}

        # layers are ordering Sprites spatially from top of the map to bottom
        # what allows rendering them in reversed way to avoid Sprites being
        # 'closer' to the player'spoint of view being obstructed by those which
        # are more distant
        self.rendering_layers = self.create_rendering_layers()
        self.update_on = update_on
        self.draw_on = draw_on

    def create_rendering_layers(self) -> List[List]:
        return [[] for _ in range(self.game.settings.map_height)]

    def get_by_id(self, sprite_id: int) -> Optional[Sprite]:
        """Return element with particular 'id' attribute value or None."""
        try:
            return self.registry[sprite_id]
        except KeyError:
            return None

    def __len__(self) -> int:
        return len(self.registry)

    def __contains__(self, sprite) -> bool:
        return sprite.id in self.registry

    def append(self, entity):
        entity.layered_spritelist = self
        if entity.id not in self.registry:
            self.registry[entity.id] = entity
            super().append(entity)
            self.add_to_rendering_layer(entity)

    def add_to_rendering_layer(self, sprite):
        pass
        # try:
        #     self.rendering_layers[sprite.current_node.grid[1]].append(sprite)
        # except (AttributeError, ValueError):
        #     pass

    def swap_rendering_layers(self, sprite, old_layer: int, new_layer: int):
        pass
        # try:
        #     self.rendering_layers[old_layer].remove(sprite)
        # except ValueError:
        #     pass
        # finally:
        #     self.rendering_layers[new_layer].append(sprite)

    def remove(self, sprite):
        try:
            del self.registry[sprite.id]
            super().remove(sprite)
            sprite.layered_spritelist = None
            self.remove_from_rendering_layer(sprite)
        except KeyError:
            pass

    def remove_from_rendering_layer(self, sprite):
        pass
        # try:
        #     self.rendering_layers[sprite.current_node.grid[1]].remove(sprite)
        # except (AttributeError, ValueError):
        #     if sprite.is_building:
        #         for layer in (l for l in self.rendering_layers if sprite in l):
        #             layer.remove(sprite)

    def extend(self, iterable):
        for sprite in iterable:
            self.append(sprite)

    def on_update(self, delta_time: float = 1/60):
        if self.update_on:
            for sprite in (s for s in self if s.is_updated):
                sprite.on_update(delta_time)

    def draw(self):
        if self.draw_on:
            super().draw()
        if any(s.is_building for s in self.registry.values()):
            for building in self:
                building.draw()

            # for layer in self.rendering_layers[::-1]:  # from bottom to top
            #     for sprite in (s for s in layer if s.is_rendered):
            #         sprite.draw()

    def pop(self, index: int = -1) -> Sprite:
        sprite = super().pop(index)
        del self.registry[sprite.id]
        self.remove_from_rendering_layer(sprite)
        return sprite

    def clear(self):
        """Safe clearing of the whole SpriteList using reversed order."""
        for _ in range(len(self)):
            self.pop()


class UiSpriteList(SpriteList):
    """
    Wrapper for spritelists containing UiElements for quick identifying the
    spritelists which should be collided with the MouseCursor.
    """

    def __init__(self, use_spatial_hash=False, spatial_hash_cell_size=128,
                 is_static=False):
        super().__init__(use_spatial_hash, spatial_hash_cell_size, is_static)

    def append(self, item):
        if hasattr(item, 'visible') and hasattr(item, 'active'):
            super().append(item)

    def extend(self, items: Union[list, 'SpriteList']):
        for item in (i for i in items if hasattr(i, 'visible') and hasattr(i, 'active')):
            super().append(item)

    def clear(self):
        for i in range(len(self)):
            self.pop()

    def draw(self, **kwargs):
        # noinspection PyUnresolvedReferences
        for ui_element in (u for u in self if u.visible):
            ui_element.draw()

    def on_update(self, delta_time: float = 1/60):
        # noinspection PyUnresolvedReferences
        for ui_element in (u for u in self if u.active):
            ui_element.on_update()
