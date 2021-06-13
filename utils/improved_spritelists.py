#!/usr/bin/env python
from __future__ import annotations

from typing import Dict, Optional, Union

from arcade import SpriteList, Sprite

from utils.logging import log


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


class SelectiveSpriteList(SpriteList):
    """
    This SpriteList works with Sprites having attributes: 'id', 'updated' and
    'rendered'. It is possible to switch updating and drawing of single
    sprites by changing their 'updated' and 'rendered' attributes inside
    their own logic, or by calling 'start_updating', 'start_drawing',
    'stop_updating' and 'stop_drawing' methods of SelectableSpriteList with
    the chosen Sprite as parameter.
    SelectableSpriteList also maintains hashmap of all Sprites which allows for
    fast lookups by their 'id' attribute.
    """

    def __init__(self, use_spatial_hash=False, spatial_hash_cell_size=128, is_static=False):
        super().__init__(use_spatial_hash, spatial_hash_cell_size, is_static)
        # to keep track of items in spritelist, fast lookups:
        self.registry: Dict[int, Sprite] = {}

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

    def append(self, sprite):
        sprite.selective_spritelist = self
        if sprite.id not in self.registry:
            self.registry[sprite.id] = sprite
            super().append(sprite)

    def remove(self, sprite):
        try:
            del self.registry[sprite.id]
            super().remove(sprite)
        except KeyError:
            pass

    def extend(self, iterable):
        for sprite in iterable:
            self.append(sprite)

    @staticmethod
    def start_updating(sprite):
        try:
            sprite.is_updated = True
        except AttributeError:
            log(f'Tried to draw Sprite instance without "updated" attribute')

    @staticmethod
    def stop_updating(sprite):
        try:
            sprite.is_updated = False
        except AttributeError:
            log(f'Tried stop drawing Sprite instance without "updated" attribute')

    @staticmethod
    def start_drawing(sprite):
        try:
            sprite.is_rendered = True
        except AttributeError:
            log(f'Tried to draw Sprite instance without "drawn_area" attribute')

    @staticmethod
    def stop_drawing(sprite):
        try:
            sprite.is_rendered = False
        except AttributeError:
            log(f'Tried stop drawing Sprite instance without "drawn_area" attribute')

    def on_update(self, delta_time: float = 1/60):
        for sprite in (s for s in self if s.is_updated):
            sprite.on_update(delta_time)

    def draw(self):
        for sprite in (s for s in self if s.is_rendered):
            sprite.draw()

    def pop(self, index: int = -1) -> Sprite:
        sprite = super().pop(index)
        del self.registry[sprite.id]
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
