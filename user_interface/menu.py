#!/usr/bin/env python
from __future__ import annotations

from user_interface.user_interface import (UiBundlesHandler)
from utils.views import WindowView


class Menu(WindowView, UiBundlesHandler):

    def __init__(self):
        super().__init__()
        UiBundlesHandler.__init__(self)
        self.set_updated_and_drawn_lists()

    def on_show_view(self):
        super().on_show_view()
        self.window.toggle_mouse_and_keyboard(True)
        self.switch_to_bundle_of_index(0)
        self.toggle_game_related_buttons()
        self.window.sound_player.play_music('menu_theme.wav')

    def toggle_game_related_buttons(self):
        bundle = self.ui_elements_bundles['main menu']
        if self.window.game_view is not None:
            bundle.activate_element('continue button')
            bundle.activate_element('quit game button')
        else:
            bundle.deactivate_element('continue button')
            bundle.deactivate_element('quit game button')
