#!/usr/bin/env python

from typing import List, Tuple, Set, Dict, Union, Optional, Any, Generator
from arcade import (
    Window, View, SpriteList, Sprite, SpriteSolidColor, draw_text, draw_rectangle_outline, draw_lrtb_rectangle_filled
)


# from utils.functions import get_objects_with_attribute
from utils.game_logging import log, logger
from utils.improved_spritelists import LayeredSpriteList
from utils.colors import WHITE, GREEN, BLACK
from utils.data_types import Viewport


Updateable = Drawable = Union[SpriteList, LayeredSpriteList, Sprite]


def get_objects_with_attribute(instance: object,
                               name: str,
                               ignore: Tuple = ()) -> List[Any]:
    """
    Search all attributes of <instance> to find all objects which have their
    own attribute of <name> and return these objects as List. You can also add
    a Tuple of class names to be ignored during query.
    """
    attributes = instance.__dict__.values()
    return [
        attr for attr in attributes if
        hasattr(attr, name) and not isinstance(attr, ignore)
    ]


class LoadableWindowView(View):

    def __init__(self, loader: Optional[Generator] = None):
        """
        This View subclass works with LoadingScreen class to allow displaying
        the loading-progress bar and load content behind the scenes.

        :param loader: Generator -- function yielding None but on each yield
        calling another function to retrieve from save-file next chunk of data
        associated with loaded Game instance. Use it only for loading Game!
        """
        super().__init__()
        self.loading_progress = 0.0
        self.loader = loader
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
        want to be updated, nor drawn
        """
        updated = get_objects_with_attribute(self, 'on_update', ignored)
        self.drawn = get_objects_with_attribute(self, 'draw', ignored)
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

    @logger(console=False)
    def update_loading(self):
        if self.things_to_load:
            self.load(*self.things_to_load[0])
            self.things_to_load.pop(0)
        elif self.loader is not None:
            self.load_from_loader()
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

    @logger()
    def load_from_loader(self):
        try:
            progress = next(self.loader)
            self.loading_progress += progress
        except StopIteration:
            self.loader = None
            self.after_loading()

    @property
    def requires_loading(self):
        return len(self.things_to_load) > 0 or self.loader is not None

    def after_loading(self):
        self.call_after_load_functions()
        self.loading_progress = 1.01

    def call_after_load_functions(self):
        for function in self.after_load_functions:
            function()
        self.after_load_functions.clear()

    def on_draw(self):
        for obj in (o for o in self.drawn if o is not None):
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
        self.progress_bar = ProgressBar(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, SCREEN_WIDTH, SCREEN_HEIGHT / 30)
        self.loading_background = Sprite(background_name) if \
            background_name is not None else None
        self.set_updated_and_drawn_lists()
        self.loaded_view = loaded_view

    def on_show_view(self):
        super().on_show_view()
        self.window.toggle_mouse_and_keyboard(False)

    def on_update(self, delta_time: float):
        super().on_update(delta_time)
        try:
            progress = getattr(self.loaded_view, 'loading_progress') * 15
            self.update_progress(progress)
            self.loaded_view.on_update(delta_time)
        except AttributeError:
            progress = delta_time
            self.update_progress(progress)
        self.progress_bar.update(progress=progress)

    def on_draw(self):
        super().on_draw()
        self.progress_bar.draw()
        self.draw_loading_text()

    def draw_loading_text(self):
        text = ' '.join([self.loading_text, str(int(self.progress))])
        draw_text(text, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 10, WHITE, 20)

    def update_progress(self, update: float):
        self.progress += update
        if self.progress >= 100:
            self.window.show_view(self.loaded_view)

class ProgressBar:

    def __init__(self, x, y, width, height, start_progres=0, max_progress=100, progress_step=1, outline_color=BLACK, color=GREEN):
        self.total_progress = start_progres
        self.max_progress = max_progress
        self.progress_step = progress_step
        self.left_margin = x - (width / 2)
        self.width = width

        self.outline_data = [x, y, width, height, outline_color]
        self.progress_bar_data = [
            self.left_margin + 1,
            self.left_margin + 1.01 + (width / max_progress) * start_progres,
            y + (height / 2) - 1,
            y - (height / 2) + 1,
            color
        ]

    def draw(self):
        draw_rectangle_outline(*self.outline_data)
        draw_lrtb_rectangle_filled(*self.progress_bar_data)

    def update(self, progress: Optional[float] = None):
        if progress is None:
            self.total_progress += self.progress_step
        else:
            self.total_progress += progress
        self.progress_bar_data[1] = self.left_margin + (self.width / self.max_progress) * self.total_progress


if __name__:
    from game import SCREEN_WIDTH, SCREEN_HEIGHT
