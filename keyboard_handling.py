#!/usr/bin/env python

from typing import Set

from user_interface import ToggledElement
from scheduling import log


class KeyboardHandler(ToggledElement):
    keys_pressed: Set[int] = set()

    def on_key_press(self, symbol: int, modifiers: int):
        self.keys_pressed.add(symbol)
        log(f'Pressed key: {symbol}, all pressed keys: {self.keys_pressed}')

    def on_key_release(self, symbol: int, modifiers: int):
        self.keys_pressed.discard(symbol)

    def key_to_letter(self, symbol: int) -> str:
        return chr(symbol)
