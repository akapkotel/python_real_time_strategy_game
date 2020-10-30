#!/usr/bin/env python
from __future__ import annotations

import logging
import arcade

from typing import (
    List, Dict, Set, Any, Optional, Union
)

from scheduling import EventsCreator, ScheduledEvent, EventsScheduler
from data_containers import DividedSpriteList
from functions import get_path_to_file
from colors import GREEN, WHITE
from observers import ObjectsOwner, OwnedObject
from views import WindowView

SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
UPDATE_RATE = 1 / 30

SpriteList = arcade.SpriteList


logging.basicConfig(
    filename='resources/logfile.txt',
    filemode='w',
    level=logging.INFO,
    format='%(levelname)s: %(asctime)s %(message)s',
    datefmt='%m/%d/%Y %I:%M:%S %p'
)


def spawn_test_unit() -> Unit:
    unit_name = get_path_to_file('medic_truck_red.png')
    position = 500, 500
    return Unit(unit_name, Player((0, 0, 0), None, False), UnitWeight.LIGHT, position)


def test_scheduling_with_function():
    print("Executed test unbound function")


def test_scheduling_with_with_args(x):
    print(f'Executed unbound function with argument: {x}')


class Window(arcade.Window, EventsCreator):

    def __init__(self, width: int, height: int, update_rate: float):
        arcade.Window.__init__(self, width, height, update_rate=update_rate)
        self.center_window()
        self.events_scheduler = EventsScheduler(update_rate=update_rate)

        self.updated: List = []
        self.drawn: List = []

        self.menu_view = Menu()
        self.game_view = None

        self.show_view(LoadingScreen(loaded_view=self.menu_view))

        self.cursor = MouseCursor(self, get_path_to_file('normal.png'))
        self.keyboard = KeyboardHandler()

    def create_new_game(self):
        self.game_view = Game()

    def start_new_game(self):
        if self.game_view is not None:
            self.show_view(self.game_view)

    def on_update(self, delta_time: float):
        self.current_view.on_update(delta_time)
        if (cursor := self.cursor).active:
            cursor.update()

    def on_draw(self):
        self.clear()
        self.current_view.on_draw()
        if (cursor := self.cursor).visible:
            cursor.draw()

    def on_mouse_motion(self, x: float, y: float, dx: float, dy: float):
        if self.cursor.active:
            self.cursor.on_mouse_motion(x, y, dx, dy)

    def on_mouse_press(self, x: float, y: float, button: int, modifiers: int):
        if self.cursor.active:
            self.cursor.on_mouse_press(x, y, button, modifiers)
            self.toggle_view()  # TODO: replace with interface interaction

    def on_mouse_release(self, x: float, y: float, button: int,
                         modifiers: int):
        if self.cursor.active:
            self.cursor.on_mouse_release(x, y, button, modifiers)

    def on_mouse_drag(self, x: float, y: float, dx: float, dy: float,
                      buttons: int, modifiers: int):
        if self.cursor.active:
            self.cursor.on_mouse_drag(x, y, dx, dy, buttons, modifiers)

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int):
        if self.cursor.active:
            self.cursor.on_mouse_scroll(x, y, scroll_x, scroll_y)

    def on_key_press(self, symbol: int, modifiers: int):
        if self.keyboard.active:
            self.keyboard.on_key_press(symbol, modifiers)

    def on_key_release(self, symbol: int, modifiers: int):
        self.keyboard.on_key_release(symbol, modifiers)

    def show_view(self, new_view: WindowView):
        if new_view.requires_loading:
            self.show_view(LoadingScreen(loaded_view=new_view))
        else:
            super().show_view(new_view)

    def toggle_view(self):
        if self.current_view is self.menu_view:
            self.create_new_game()
            self.start_new_game()
        else:
            self.show_view(self.menu_view)

    def toggle_mouse_and_keyboard(self, value: bool):
        try:
            self.cursor.active = value
            self.cursor.visible = value
            self.keyboard.active = value
        except AttributeError:
            pass

    def save_game(self):
        # TODO: save GameObject.total_objects_count (?)
        raise NotImplementedError

    def load_game(self):
        raise NotImplementedError


class Menu(WindowView, ObjectsOwner):

    def __init__(self):
        super().__init__()
        ObjectsOwner.__init__(self)
        self.set_updated_and_drawn_lists()
        self.submenus: Set[WindowView] = set()
        self.current_submenu = None

    def on_show_view(self):
        super().on_show_view()
        self.window.toggle_mouse_and_keyboard(True)
        self.window.background_color = (75, 0, 25)

    def on_update(self, delta_time: float):
        super().on_update(delta_time)

    def on_draw(self):
        super().on_draw()

    def register(self, acquired: OwnedObject):
        acquired: WindowView
        self.submenus.add(acquired)

    def unregister(self, owned: OwnedObject):
        owned: WindowView
        self.submenus.discard(owned)

    def get_notified(self, *args, **kwargs):
        pass


class Game(WindowView, EventsCreator, ObjectsOwner):
    instance: Optional[Game] = None

    def __init__(self):
        WindowView.__init__(self, requires_loading=True)
        EventsCreator.__init__(self)
        self.assign_reference_to_self_for_all_classes()

        # SpriteLists:
        self.interface = arcade.SpriteList()
        self.units = DividedSpriteList()
        self.buildings = DividedSpriteList()

        self.fog_of_war = FogOfWar()

        # Settings, game-progress data, etc.
        self.player_configs: Dict[str, Any] = self.load_player_configs()

        self.players: Dict[int, Player] = {}
        self.local_human_player: Optional[Player] = None

        self.players: Dict[int, Player] = {}
        self.factions: Dict[int, Faction] = {}

        self.set_updated_and_drawn_lists()

        self.test_methods()

    def assign_reference_to_self_for_all_classes(self):
        name = self.__class__.__name__.lower()
        for _class in (c for c in globals().values() if hasattr(c, name)):
            setattr(_class, name, self)
        Game.instance = self

    def on_show_view(self):
        super().on_show_view()
        self.window.toggle_mouse_and_keyboard(True)
        self.window.background_color = (0, 0, 120)

    def test_methods(self):
        self.test_scheduling_events()
        self.test_units_spawning()

    def test_scheduling_events(self):
        event = ScheduledEvent(self, 1, self.scheduling_test, repeat=True)
        self.schedule_event(event)

    def test_units_spawning(self):
        unit = spawn_test_unit()
        self.units.append(unit)

    def load_player_configs(self) -> Dict[str, Any]:
        configs: Dict[str, Any] = {}
        # TODO
        return configs

    def register(self, acquired: OwnedObject):
        acquired: Union[Unit, Building, Player, Faction]
        if isinstance(acquired, (Unit, Building)):
            self.register_player_entity(acquired)
        else:
            self.register_player_or_faction(acquired)

    def register_player_entity(self, registered: Union[Unit, Building]):
        if isinstance(registered, Unit):
            self.units.append(registered)
        else:
            self.buildings.append(registered)

    def register_player_or_faction(self, registered: Union[Player, Faction]):
        if isinstance(registered, Player):
            self.players[len(self.players)] = registered
        else:
            self.factions[len(self.factions)] = registered

    def unregister(self, owned: OwnedObject):
        owned: Union[PlayerEntity, Player, Faction]
        if isinstance(owned, PlayerEntity):
            self.unregister_player_entity(owned)
        else:
            self.unregister_player_or_faction(owned)

    def unregister_player_entity(self, owned: Union[PlayerEntity]):
        owned: Union[Unit, Building]
        if isinstance(owned, Unit):
            self.units.remove(owned)
        else:
            self.buildings.remove(owned)

    def unregister_player_or_faction(self, owned: Union[Player, Faction]):
        if isinstance(owned, Player):
            del self.players[owned.id]
        else:
            del self.factions[owned.id]

    def get_notified(self, *args, **kwargs):
        pass


class LoadingScreen(WindowView):

    def __init__(self,
                 loaded_view: WindowView,
                 loading_text: str = 'Loading',
                 background_name: Optional[str] = None):
        super().__init__()
        self.sprite_list = SpriteList(is_static=True)
        self.loading_text = loading_text
        self.progress = 0
        self.progress_bar = self.create_progress_bar()
        self.loading_background = arcade.Sprite(background_name) if background_name else None
        self.sprite_list.extend(
            [e for e in (self.progress_bar, self.loading_background) if e]
        )
        self.set_updated_and_drawn_lists()
        self.loaded_view = loaded_view

    def create_progress_bar(self) -> arcade.SpriteSolidColor:
        bar_width = 1
        bar_height = int(SCREEN_HEIGHT * 0.025)
        bar = arcade.SpriteSolidColor(bar_width, bar_height, GREEN)
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
        arcade.draw_text(text, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 10, WHITE, 20)

    def update_progress(self, delta_time: float):
        self.progress += 50 * delta_time
        if self.progress >= 100:
            self.loaded_view.loaded = True
            self.window.show_view(self.loaded_view)

    def update_progress_bar(self):
        progress = self.progress
        self.progress_bar.center_x = center = progress * (SCREEN_WIDTH / 200)
        self.progress_bar.width = center * 2


if __name__ == '__main__':
    from mouse_handling import MouseCursor
    from keyboard_handling import KeyboardHandler
    from player import Faction, Player, PlayerEntity
    from buildings import Building
    from units import Unit, UnitWeight
    from fog_of_war import FogOfWar

    window = Window(SCREEN_WIDTH, SCREEN_HEIGHT, UPDATE_RATE)
    arcade.run()
