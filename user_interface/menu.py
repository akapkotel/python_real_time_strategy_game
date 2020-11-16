#!/usr/bin/env python
from __future__ import annotations

from functools import partial

from user_interface.user_interface import (
    UiElementsBundle, UiBundlesHandler, Button, Checkbox
)
from utils.functions import get_path_to_file
from utils.views import WindowView


class Menu(WindowView, UiBundlesHandler):

    def __init__(self):
        super().__init__()
        UiBundlesHandler.__init__(self)
        self.set_updated_and_drawn_lists()
        self.create_submenus()

    def create_submenus(self):
        window = self.window
        switch_menu = self.switch_to_bundle_of_name
        back_to_menu_button = Button(
            get_path_to_file('menu_button_back.png'), SCREEN_X, 150,
            function_on_left_click=partial(switch_menu, 'main menu')
        )

        x, y = SCREEN_X, (i for i in range(150, SCREEN_HEIGHT, 125))
        main_menu = UiElementsBundle(
            index=0,
            name='main menu',
            elements=[
                Button(get_path_to_file('menu_button_exit.png'), x, next(y),
                       function_on_left_click=window.close),
                Button(get_path_to_file('menu_button_credits.png'), x, next(y),
                       function_on_left_click=partial(switch_menu, 'credits')),
                Button(get_path_to_file('menu_button_options.png'), x, next(y),
                       function_on_left_click=partial(switch_menu, 'options')),
                Button(get_path_to_file('menu_button_loadgame.png'), x, next(y),
                       function_on_left_click=partial(switch_menu, 'saving menu')),
                Button(get_path_to_file('menu_button_newgame.png'), x, next(y),
                       function_on_left_click=partial(switch_menu, 'new game menu')),
                Button(get_path_to_file('menu_button_continue.png'), x, next(y),
                       name='continue button', active=False,
                       function_on_left_click=window.start_new_game),
                Button(get_path_to_file('menu_button_quit.png'), x, next(y),
                       name='quit game button', active=False,
                       function_on_left_click=window.quit_current_game),
            ],
            register_to=self
        )

        y = (i for i in range(300, SCREEN_HEIGHT, 75))
        options_menu = UiElementsBundle(
            index=1,
            name='options',
            elements=[
                back_to_menu_button,
                # UiTextLabel(SCREEN_X - 100, 600, 'Draw debug:', 20),
                Checkbox(
                    get_path_to_file('menu_checkbox.png'), x, next(y),
                    'Draw debug:', 20, ticked=window.debug,
                    variable=(window, 'debug'), subgroup=1
                ),
                Checkbox(
                    get_path_to_file('menu_checkbox.png'), x, next(y),
                    'Sound:', 20, ticked=window.sound_player.sound_on,
                    variable=(window.sound_player, 'sound_on'), subgroup=2
                ),
                Checkbox(
                    get_path_to_file('menu_checkbox.png'), x, next(y),
                    'Music:', 20, ticked=window.sound_player.sound_on,
                    variable=(window.sound_player, 'music_on'), subgroup=2
                ),
                Checkbox(
                    get_path_to_file('menu_checkbox.png'), x, next(y),
                    'Sound effects:', 20, ticked=window.sound_player.sound_on,
                    variable=(window.sound_player, '_sound_effects_on'), subgroup=2
                ),
                Checkbox(
                    get_path_to_file('menu_checkbox.png'), x, next(y),
                    'Full screen:', 20, ticked=window.fullscreen,
                    function_on_left_click=window.toggle_fullscreen, subgroup=1
                ),
            ],
            register_to=self
        )

        saving_menu = UiElementsBundle(
            index=2,
            name='saving menu',
            elements=[
                back_to_menu_button,
            ],
            register_to=self
        )

        x, y = SCREEN_WIDTH // 4, SCREEN_Y
        new_game_menu = UiElementsBundle(
            index=3,
            name='new game menu',
            elements=[
                back_to_menu_button,
                Button(get_path_to_file('menu_button_skirmish.png'), x, y,
                       function_on_left_click=partial(switch_menu, 'skirmish menu')),
                Button(get_path_to_file('menu_button_campaign.png'), 2 * x, y,
                       function_on_left_click=partial(switch_menu, 'campaign menu')),
                Button(get_path_to_file('menu_button_multiplayer.png'), 3 * x, y,
                       function_on_left_click=partial(switch_menu, 'multiplayer menu')),
            ],
            register_to=self
        )

        credits = UiElementsBundle(
            index=4,
            name='credits',
            elements=[
                back_to_menu_button,
            ],
            register_to=self
        )

        skirmish_menu = UiElementsBundle(
            index=5,
            name='skirmish menu',
            elements=[
                back_to_menu_button,
                Button(get_path_to_file('menu_button_play.png'), SCREEN_X, 300,
                       function_on_left_click=window.start_new_game)
            ],
            register_to=self
        )

        campaign_menu = UiElementsBundle(
            index=6,
            name='campaign menu',
            elements=[
                back_to_menu_button,
            ],
            register_to=self
        )

        multiplayer_menu = UiElementsBundle(
            index=7,
            name='multiplayer menu',
            elements=[
                back_to_menu_button,
            ],
            register_to=self
        )

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


if __name__:
    from game import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_X, SCREEN_Y
