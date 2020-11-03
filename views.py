#!/usr/bin/env python

from typing import List, Set, Dict, Union, Optional
from arcade import (
    Window, View, SpriteList, Sprite, SpriteSolidColor, draw_text
)


from utils.functions import get_attributes_with_attribute, log
from data_containers import DividedSpriteList
from colors import WHITE, GREEN


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

    def set_updated_and_drawn_lists(self, ignored=(Window, Set, Dict)):
        # to draw and update everything with one instruction in on_draw()
        # and on_update() methods:
        self.drawn = get_attributes_with_attribute(self, 'draw', ignored)
        self.updated = get_attributes_with_attribute(self, 'update', ignored)

    def on_show_view(self):
        log(f'Switched to WindowView: {self.__class__.__name__}')
        self.window.updated = self.updated
        self.window.drawn = self.drawn

    def on_update(self, delta_time: float):
        for obj in self.updated:
            obj.update()

    def on_draw(self):
        for obj in self.drawn:
            obj.draw()


class LoadingScreen(WindowView):

    def __init__(self,
                 loaded_view: WindowView,
                 loading_text: str = 'Loading',
                 background_name: Optional[str] = None):
        super().__init__()
        self.sprite_list = SpriteList()
        self.loading_text = loading_text
        self.progress = 0
        self.progress_bar = self.create_progress_bar()
        self.loading_background = Sprite(background_name) if \
            background_name else None
        self.sprite_list.extend(
            [e for e in (self.progress_bar, self.loading_background) if e]
        )
        self.set_updated_and_drawn_lists()
        self.loaded_view = loaded_view

    @staticmethod
    def create_progress_bar() -> SpriteSolidColor:
        bar_width = 1
        bar_height = int(SCREEN_HEIGHT * 0.025)
        bar = SpriteSolidColor(bar_width, bar_height, GREEN)
        bar.center_y = SCREEN_HEIGHT / 2
        return bar

    def on_show_view(self):
        super().on_show_view()
        self.window.toggle_mouse_and_keyboard(False)
        self.window.background_color = (0, 0, 0)

    def on_update(self, delta_time: float):
        super().on_update(delta_time)
        self.update_progress(delta_time)
        self.update_progress_bar()

    def on_draw(self):
        super().on_draw()
        self.draw_loading_text()

    def draw_loading_text(self):
        text = ' '.join([self.loading_text, str(int(self.progress))])
        draw_text(text, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 10, WHITE, 20)

    def update_progress(self, delta_time: float):
        self.progress += 50 * delta_time
        if self.progress >= 100:
            self.loaded_view.loaded = True
            self.window.show_view(self.loaded_view)

    def update_progress_bar(self):
        progress = self.progress
        self.progress_bar.center_x = center = progress * (SCREEN_WIDTH / 200)
        self.progress_bar.width = center * 2


if __name__:
    from game import SCREEN_WIDTH, SCREEN_HEIGHT
