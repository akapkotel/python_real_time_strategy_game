#!/usr/bin/env python

from typing import Set, Optional

from arcade import Window
from arcade.key import *

from utils.constants import UI_UNITS_CONSTRUCTION_PANEL, UI_BUILDINGS_CONSTRUCTION_PANEL
from user_interface.user_interface import (
    ToggledElement, TextInputField, UiBundlesHandler
)
from utils.functions import ignore_in_menu, ignore_in_game
from utils.game_logging import log_here

KEYBOARD_SCROLL_SPEED = 50


class KeyboardHandler(ToggledElement):
    keys_pressed: Set[int] = set()

    def __init__(self, window: Window, text_input_consumer: UiBundlesHandler):
        super().__init__()
        self.window = window
        self.keyboard_input_consumer: Optional[TextInputField] = None
        text_input_consumer.set_keyboard_handler(handler=self)

    def on_key_press(self, symbol: int):
        log_here(f'Pressed key: {symbol}, other pressed keys: {self.keys_pressed}')
        self.keys_pressed.add(symbol)
        self.evaluate_pressed_key(symbol)
        if self.keyboard_input_consumer is not None:
            self.send_key_to_input_consumer(symbol)

    def on_key_release(self, symbol: int):
        if symbol == LCTRL and self.window.is_game_running:
            self.window.game.units_manager.toggle_waypoint_mode(False)
        self.keys_pressed.discard(symbol)

    def evaluate_pressed_key(self, symbol: int):
        if symbol == P and self.window.is_game_running:
            self.window.game.toggle_pause()
        elif symbol == U and self.window.is_game_running:
            self.window.game.show_construction_options(UI_UNITS_CONSTRUCTION_PANEL)
        elif symbol == B and self.window.is_game_running:
            self.window.game.show_construction_options(UI_BUILDINGS_CONSTRUCTION_PANEL)
        elif symbol == D:
            ...
        elif symbol == ESCAPE:
            self.on_escape_pressed()
        elif symbol == LCTRL:
            self.window.game.units_manager.toggle_waypoint_mode()
        elif symbol == DELETE:
            if self.window.settings.editor_mode and self.window.game.units_manager.units_or_building_selected:
                self.window.game.units_manager.kill_selected()
        elif (digit := chr(symbol)).isdigit():
            self.on_numeric_key_press(int(digit))

    def on_escape_pressed(self):
        game = self.window.game_view
        if game is None:
            self.window.close()
        elif game.current_scenario.ended:
            game.current_scenario.quit_scenario()
        elif not game.is_running:
            self.window.show_view(game)
        else:
            self.window.show_view(self.window.menu_view)

    def on_numeric_key_press(self, digit: int):
        manager = self.window.mouse.units_manager
        if LCTRL in self.keys_pressed:
            manager.create_new_permanent_units_group(digit)
        else:
            manager.select_permanent_units_group(digit)

    @staticmethod
    def key_to_letter(symbol: int) -> str:
        return chr(symbol)

    def update(self):
        if self.keys_pressed:
            self.keyboard_map_scroll()

    @ignore_in_menu
    def keyboard_map_scroll(self):
        keys = self.keys_pressed
        dx = (RIGHT in keys) - (LEFT in keys)
        dy = (UP in keys) - (DOWN in keys)
        if dx or dy:
            self.window.change_viewport(- dx * KEYBOARD_SCROLL_SPEED, - dy * KEYBOARD_SCROLL_SPEED)

    @ignore_in_game
    def send_key_to_input_consumer(self, symbol: int):
        self.keyboard_input_consumer.receive(symbol, LSHIFT in self.keys_pressed)

    def bind_keyboard_input_consumer(self, consumer: TextInputField):
        self.keyboard_input_consumer = consumer

    def unbind_keyboard_input_consumer(self):
        self.keyboard_input_consumer = None
