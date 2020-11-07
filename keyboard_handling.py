#!/usr/bin/env python

from typing import Set, Optional

from arcade import Window
from arcade.key import *

from unit_management import PermanentUnitsGroup
from user_interface import ToggledElement
from utils.functions import log


class KeyboardHandler(ToggledElement):
    keys_pressed: Set[int] = set()
    window: Optional[Window] = None

    def __init__(self, window: Window):
        super().__init__()
        self.window = window

    def on_key_press(self, symbol: int, modifiers: int):
        self.keys_pressed.add(symbol)
        log(f'Pressed key: {symbol}, all pressed keys: {self.keys_pressed}')
        self.evaluate_pressed_key(symbol, modifiers)

    def on_key_release(self, symbol: int, modifiers: int):
        self.keys_pressed.discard(symbol)

    def evaluate_pressed_key(self, symbol: int, modifiers: int):
        if symbol == P and self.window.game_view is not None:
            self.window.game_view.toggle_pause()
        elif symbol == SPACE:
            self.window.toggle_view()
        elif symbol == ESCAPE:
            self.window.close()
        elif (digit := chr(symbol)).isdigit():
            self.on_numeric_key_press(int(digit))

    def on_numeric_key_press(self, digit: int):
        if LCTRL in self.keys_pressed and self.window.cursor.selected_units:
            self.create_new_permanent_units_group(digit)
        elif digit in self.window.game_view.permanent_units_groups:
            self.select_permanent_units_group(digit)

    def create_new_permanent_units_group(self, digit: int):
        units = self.window.cursor.selected_units
        new_group = PermanentUnitsGroup(group_id=digit, units=units)
        self.window.game_view.permanent_units_groups[digit] = new_group

    def select_permanent_units_group(self, group_id: int):
        group = self.window.game_view.permanent_units_groups[group_id]
        self.window.cursor.unselect_units()
        self.window.cursor.select_units(*group.units)

    def key_to_letter(self, symbol: int) -> str:
        return chr(symbol)
