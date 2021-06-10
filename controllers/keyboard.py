#!/usr/bin/env python

from typing import Set

from arcade import Window
from arcade.key import *

from user_interface.user_interface import ToggledElement
from utils.functions import ignore_in_menu
from utils.logging import log, logger


class KeyboardHandler(ToggledElement):
    keys_pressed: Set[int] = set()

    def __init__(self, window: Window):
        super().__init__()
        self.window = window

    @logger(console=True)
    def on_key_press(self, symbol: int):
        self.keys_pressed.add(symbol)
        log(f'Pressed key: {symbol}, all pressed keys: {self.keys_pressed}')
        self.evaluate_pressed_key(symbol)

    def on_key_release(self, symbol: int):
        if symbol == LCTRL:
            self.window.game_view.pathfinder.finish_waypoints_queue()
        self.keys_pressed.discard(symbol)

    def evaluate_pressed_key(self, symbol: int):
        if symbol == P and self.window.is_game_running:
            self.window.game_view.toggle_pause()
        elif symbol == ESCAPE:
            self.on_escape_pressed()
        elif (digit := chr(symbol)).isdigit():
            self.on_numeric_key_press(int(digit))

    def on_escape_pressed(self):
        game = self.window.game_view
        if game is None or not game.is_running:
            self.window.close()
        elif game.current_mission.ended:
            game.current_mission.quit_mission()
        else:
            self.window.show_view(self.window.menu_view)

    def on_numeric_key_press(self, digit: int):
        manager = self.window.cursor.units_manager
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
        dx = (RIGHT in keys or D in keys) - (LEFT in keys or A in keys)
        dy = (UP in keys or W in keys) - (DOWN in keys or S in keys)
        if dx != 0 or dy != 0:
            self.window.change_viewport(- dx * 50, - dy * 50)
