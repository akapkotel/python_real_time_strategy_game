#!/usr/bin/env python

from typing import List, Union
from arcade import Window, View, SpriteList, Sprite

from functions import get_attributes_with_attribute
from data_containers import DividedSpriteList


Updateable = Drawable = Union[SpriteList, DividedSpriteList, Sprite]


class WindowView(View):

    def __init__(self, requires_loading: bool = False):
        super().__init__()
        self.loaded = False
        self._requires_loading = requires_loading
        self.updated: List[Updateable] = []
        self.drawn: List[Drawable] = []

    @property
    def requires_loading(self):
        return self._requires_loading and not self.loaded

    @property
    def is_running(self):
        return self.window.current_view is self

    def set_updated_and_drawn_lists(self):
        # to draw and update everything with one instruction in on_draw()
        # and on_update() methods:
        ignored = (Window, )
        self.drawn = get_attributes_with_attribute(self, 'draw', ignored)
        self.updated = get_attributes_with_attribute(self, 'update', ignored)

    def on_show_view(self):
        self.window.updated = self.updated
        self.window.drawn = self.drawn

    def on_update(self, delta_time: float):
        for obj in self.updated:
            obj.update()

    def on_draw(self):
        for obj in self.drawn:
            obj.draw()
