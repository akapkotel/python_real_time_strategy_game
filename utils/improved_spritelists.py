#!/usr/bin/env python
from __future__ import annotations

from typing import Any, Iterable, List, Optional, Callable

from arcade import SpriteList, Sprite


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
        self._update_on = update_on
        self._draw_on = draw_on

    @property
    def update_on(self) -> bool:
        return self._update_on

    @property
    def draw_on(self) -> bool:
        return self._draw_on

    def on_update(self, delta_time: float = 1/60):
        if self._update_on:
            super().on_update(delta_time)

    def update(self):
        if self._update_on:
            super().update()

    def draw(self, **kwargs):
        if self._draw_on:
            super().draw(**kwargs)

    def toggle_update(self):
        self._update_on = not self._update_on

    def toggle_draw(self):
        self._draw_on = not self._draw_on


class DividedSpriteList(SpriteList):
    """
    Reasons for this wrapper: (1) speed. Adding additional set allows to
    store ID of each Sprite appended to this SpriteList for faster lookups.
    Hashed set provides lookup in O(1).
    (2) Separating SpriteLists for visible and drawn Sprites and invisible, so
    not drawn. Each Sprite can be stored in drawn, updated or both SpriteLists.
    Not-drawing all Sprites each frame, but only visible saves CPU-time.
    """

    def __init__(self, use_spatial_hash=False, is_static=False):
        super().__init__(use_spatial_hash, is_static)  # to comply with
        # SpriteList interface
        self.id_elements_dict = {}
        del self.sprite_list  # we replace it with two SpriteLists below:
        self.updated = SpriteList(use_spatial_hash, is_static)
        self.drawn = SpriteList(use_spatial_hash, is_static)

    def __repr__(self) -> str:
        return f'DividedSpriteList, contains: {self.id_elements_dict}'

    def __len__(self) -> int:
        return len(self.id_elements_dict)

    def __bool__(self) -> bool:
        return len(self.id_elements_dict) > 0

    def __getitem__(self, item):
        return self.updated[item]

    def __iter__(self) -> Iterable:
        return iter(self.updated)

    def __contains__(self, sprite) -> bool:
        return sprite.id in self.id_elements_dict

    def append(self, sprite, start_drawing=False):
        if (item_id := sprite.id) not in self.id_elements_dict:
            sprite.divided_spritelist = self
            self.id_elements_dict[item_id] = sprite
            self.start_updating(sprite)
            if start_drawing or sprite.visible:
                self.start_drawing(sprite)

    def remove(self, sprite):
        if (item_id := sprite.id) in self.id_elements_dict:
            self.stop_updating(sprite)
            self.stop_drawing(sprite)
            del self.id_elements_dict[item_id]

    def extend(self, iterable):
        for sprite in iterable:
            self.append(sprite)

    def start_updating(self, sprite):
        self.updated.append(sprite)

    def stop_updating(self, sprite):
        try:
            self.updated.remove(sprite)
        except ValueError:
            pass

    def start_drawing(self, sprite):
        self.drawn.append(sprite)

    def stop_drawing(self, sprite):
        try:
            self.drawn.remove(sprite)
        except ValueError:
            pass

    def update(self):
        self.updated.update()

    def on_update(self, delta_time: float = 1/60):
        for sprite in self.updated:
            sprite.on_update(delta_time)

    def draw(self):
        self.drawn.draw()

    def pop(self, index: int = -1):
        poped_item = self.updated.pop(index)
        self.remove(poped_item)
        return poped_item

    def get_id(self, sprite_id: int) -> Optional[Any]:
        try:
            return self.id_elements_dict[sprite_id]
        except KeyError:
            return None

    def where(self, condition: Callable) -> List[Sprite]:
        return [item for item in self.updated if condition(item)]
