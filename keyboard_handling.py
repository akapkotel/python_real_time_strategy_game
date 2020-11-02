#!/usr/bin/env python

from typing import Set, Optional

from arcade import Window
from arcade.key import *

from user_interface import ToggledElement
from scheduling import log


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

    def key_to_letter(self, symbol: int) -> str:
        return chr(symbol)


