#!/usr/bin/env python

import time

from typing import List, Set, Dict, Union, Optional, Any, Callable
from arcade import (
    Window, View, SpriteList, Sprite, SpriteSolidColor, draw_text
)


from utils.functions import get_attributes_with_attribute, log, logger
from utils.improved_spritelists import SelectiveSpriteList
from utils.colors import WHITE, GREEN
from utils.data_types import Viewport


Updateable = Drawable = Union[SpriteList, SelectiveSpriteList, Sprite]


class LoadableWindowView(View):

    def __init__(self):
        super().__init__()
        self.loading_progress = 0.0
        self.things_to_load = []
        self.after_load_functions = []
        self.updated: List[Updateable] = []
        self.drawn: List[Drawable] = []
        self.paused = False

        # Since we can toggle views and some views has dynamic viewports and
        # other do not, we keep track of each View viewport to retrieve it
        # when we go back to the View from another, and each time we update
        # the viewport of the Window, we use current View viewport coordinates:
        self.viewport: Viewport = 0, SCREEN_WIDTH, 0, SCREEN_HEIGHT

    @property
    def is_running(self):
        return self.window.current_view is self

    def set_updated_and_drawn_lists(self,
                                    *ignore_update,
                                    ignored=(Window, Set, Dict)):
        """
        Call this method after you initialised all 'updateable' and 'drawable'
        attributes of application eg.: SpriteLists. They are identified by
        having 'on_update' and 'draw' methods. Collected all these objects
        you can later update and draw them at once with:

        for obj in self.updated:
            obj.update()

        or:

        for obj in self.drawn_area:
            obj.draw()

        :param ignore_update: put here all SpriteLists and other objects
        which have on_update method but you want them to be NOT updated
        :param ignored: instead you can declare types of objects, you do not
        want to be updated, nor drawn_area
        """
        updated = get_attributes_with_attribute(self, 'on_update', ignored)
        self.drawn = get_attributes_with_attribute(self, 'draw', ignored)
        self.updated = [u for u in updated if u not in ignore_update]

    def on_show_view(self):
        log(f'Switched to View: {self.__class__.__name__}')
        self.window.updated = self.updated
        self.window.set_viewport(*self.viewport)

    def on_update(self, delta_time: float):
        if not self.is_loaded:
            return self.update_loading()
        if not self.paused:
            self.update_view(delta_time)

    @property
    def is_loaded(self):
        return self.loading_progress >= 1.0

    @logger(console=True)
    def update_loading(self):
        if self.things_to_load:
            self.load(*self.things_to_load[0])
            self.things_to_load.pop(0)
        # elif self.functions_to_call:
        #     self.call_function()
        else:
            self.after_loading()

    def update_view(self, delta_time: float):
        for obj in self.updated:
            obj.on_update(delta_time)

    @logger(console=True)
    def load(self, loaded: str, value: Any, progress: float, *args, **kwargs):
        args = [a() if callable(a) else a for a in args]
        setattr(self, loaded, value(*args, **kwargs) if callable(value) else value)
        self.loading_progress += progress

    @property
    def requires_loading(self):
        return len(self.things_to_load) > 0

    def after_loading(self):
        self.call_after_load_functions()
        self.loading_progress = 1.01

    def call_after_load_functions(self):
        for function in self.after_load_functions:
            function()
        self.after_load_functions.clear()

    def on_draw(self):
        for obj in self.drawn:
            obj.draw()

    def toggle_pause(self):
        self.paused = not self.paused


class LoadingScreen(LoadableWindowView):

    def __init__(self,
                 loaded_view: Optional[LoadableWindowView] = None,
                 loading_text: str = 'Loading',
                 background_name: Optional[str] = None):
        super().__init__()
        self.sprite_list = SpriteList()
        self.loading_text = loading_text
        self.progress = 0
        self.progress_bar = self.create_progress_bar()
        self.loading_background = Sprite(background_name) if \
            background_name is not None else None
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

    def on_update(self, delta_time: float):
        super().on_update(delta_time)
        try:
            self.update_progress(getattr(self.loaded_view, 'loading_progress'))
            self.loaded_view.on_update(delta_time)
        except AttributeError:
            self.update_progress(delta_time)
        self.update_progress_bar()

    def on_draw(self):
        super().on_draw()
        self.draw_loading_text()

    def draw_loading_text(self):
        text = ' '.join([self.loading_text, str(int(self.progress))])
        draw_text(text, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 10, WHITE, 20)

    def update_progress(self, update: float):
        self.progress += (25 * update)
        if self.progress >= 100:
            self.window.show_view(self.loaded_view)

    def update_progress_bar(self):
        progress = self.progress
        self.progress_bar.center_x = center = progress * (SCREEN_WIDTH / 200)
        self.progress_bar.width = 0.01 + center * 2


if __name__:
    from game import SCREEN_WIDTH, SCREEN_HEIGHT
