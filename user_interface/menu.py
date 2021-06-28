#!/usr/bin/env python
from __future__ import annotations

from functools import partial

from user_interface.user_interface import (
    UiElementsBundle, UiBundlesHandler, Button, Tab, Checkbox, TextInputField,
    UiTextLabel
)
from utils.views import LoadableWindowView

LOADING_MENU = 'loading menu'
SAVING_MENU = 'saving_menu'
MAIN_MENU = 'main menu'

OPTIONS_SUBMENU = 'options'
CREDITS_SUBMENU = 'credits'


class Menu(LoadableWindowView, UiBundlesHandler):

    def __init__(self):
        super().__init__()
        UiBundlesHandler.__init__(self)
        self.set_updated_and_drawn_lists()
        self.create_submenus()

    def create_submenus(self):
        window = self.window
        switch_menu = self.switch_to_bundle_of_name
        back_to_menu_button = Button('menu_button_back.png', SCREEN_X, 150,
            functions=partial(switch_menu, MAIN_MENU)
        )

        x, y = SCREEN_X, (i for i in range(150, SCREEN_HEIGHT, 125))
        main_menu = UiElementsBundle(
            index=0,
            name=MAIN_MENU,
            elements=[
                Button('menu_button_exit.png', x, next(y),
                       functions=window.close),
                Button('menu_button_credits.png', x, next(y),
                       functions=partial(switch_menu, CREDITS_SUBMENU)),
                Button('menu_button_options.png', x, next(y),
                       functions=partial(switch_menu, OPTIONS_SUBMENU)),
                Button('menu_button_loadgame.png', x, next(y),
                       functions=partial(switch_menu, LOADING_MENU)),
                Button('menu_button_newgame.png', x, next(y),
                       functions=partial(switch_menu, 'new game menu')),
                Button('menu_button_continue.png', x, next(y),
                       name='continue button', active=False,
                       functions=window.start_new_game),
                Button('menu_button_quit.png', x, next(y),
                       name='quit game button', active=False,
                       functions=window.quit_current_game),
            ],
            register_to=self
        )

        y = (i for i in range(300, SCREEN_HEIGHT, 75))
        options_menu = UiElementsBundle(
            index=1,
            name=OPTIONS_SUBMENU,
            elements=[
                back_to_menu_button,
                # set 'subgroup' index for each element to assign it to the
                # proper tab in options sub-menu:
                Checkbox('menu_checkbox.png', x, next(y), 'Draw debug:', 20,
                         ticked=window.settings.debug,
                         variable=(window.settings, 'debug'), subgroup=1),
                Checkbox('menu_checkbox.png', x, next(y), 'Vehicles threads:',
                         20, ticked=window.settings.vehicles_threads,
                         variable=(window.settings, 'vehicles_threads'),
                         subgroup=1),
                Checkbox('menu_checkbox.png', x, next(y), 'Full screen:',
                         20, ticked=window.fullscreen,
                         functions=window.toggle_full_screen, subgroup=1),
            ],
            register_to=self
        )
        # sound:
        y = (i for i in range(300, SCREEN_HEIGHT, 75))
        options_menu.extend(
            [
                Checkbox('menu_checkbox.png', x, next(y),
                    'Music:', 20, ticked=window.sound_player.music_on,
                    variable=(window.sound_player, 'music_on'), subgroup=2
                ),
                Checkbox('menu_checkbox.png', x, next(y),
                    'Sound effects:', 20, ticked=window.sound_player.sound_effects_on,
                    variable=(window.sound_player, 'sound_effects_on'),
                    subgroup=2
                )
            ]
        )

        # tabs switching what groups of elements are visible by
        # switching between subgroups:
        graphics_tab = Tab('menu_tab_graphics.png', 960,
                           SCREEN_HEIGHT - 34, functions=partial(
                           options_menu.switch_to_subgroup, 1))
        sound_tab = Tab('menu_tab_sound.png', 320,
                        SCREEN_HEIGHT - 34, functions=partial(
                        options_menu.switch_to_subgroup, 2),
                        other_tabs=(graphics_tab, ))
        game_tab = Tab('menu_tab_blank.png', 1600,
                        SCREEN_HEIGHT - 34, functions=partial(
                        options_menu.switch_to_subgroup, 3),
                        other_tabs=(graphics_tab, sound_tab))
        options_menu.extend((sound_tab, graphics_tab, game_tab))
        sound_tab.on_mouse_press(1)

        x, y = SCREEN_X * 1.5, (i for i in range(300, SCREEN_HEIGHT, 125))

        loading_menu = UiElementsBundle(
            index=2,
            name=LOADING_MENU,
            elements=[
                back_to_menu_button,
                # left column - ui-buttons:
                Button('menu_button_loadgame.png', x, next(y),
                       functions=window.load_game),
                Button('menu_button_deletesave.png', x, next(y),
                       functions=window.delete_saved_game)
            ],
            register_to=self,
            _on_load=window.update_saved_games_list
        )

        y = (i for i in range(675, 300, -125))
        text_input = TextInputField('text_input_field.png', x, next(y), 'input')
        saving_menu = UiElementsBundle(
            index=2,
            name=SAVING_MENU,
            elements=[
                back_to_menu_button,
                # left column - ui-buttons:
                Button('menu_button_savegame.png', x, next(y),
                       functions=partial(window.save_game, text_input)),
                text_input
            ],
            register_to=self,
            _on_load=window.update_saved_games_list
        )

        x, y = SCREEN_WIDTH // 4, SCREEN_Y
        new_game_menu = UiElementsBundle(
            index=3,
            name='new game menu',
            elements=[
                back_to_menu_button,
                Button('menu_button_skirmish.png', x, y,
                       functions=partial(switch_menu, 'skirmish menu')),
                Button('menu_button_campaign.png', 2 * x, y,
                       functions=partial(switch_menu, 'campaign menu')),
                Button('menu_button_multiplayer.png', 3 * x, y,
                       functions=partial(switch_menu, 'multiplayer menu')),
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
                Button('menu_button_play.png', SCREEN_X, 300,
                       functions=window.start_new_game)
            ],
            register_to=self
        )

        campaign_menu = UiElementsBundle(
            index=6,
            name='campaign menu',
            elements=[
                back_to_menu_button,
                UiTextLabel(SCREEN_X, SCREEN_Y, 'Not available yet...', 20)
            ],
            register_to=self
        )

        multiplayer_menu = UiElementsBundle(
            index=7,
            name='multiplayer menu',
            elements=[
                back_to_menu_button,
                UiTextLabel(SCREEN_X, SCREEN_Y, 'Not available yet...', 20)
            ],
            register_to=self
        )

    def on_show_view(self):
        super().on_show_view()
        if (game := self.window.game_view) is not None:
            game.save_timer()
        self.window.toggle_mouse_and_keyboard(True)
        self.switch_to_bundle_of_name(MAIN_MENU)
        self.toggle_game_related_buttons()
        self.window.sound_player.play_playlist('menu')

    def toggle_game_related_buttons(self):
        bundle = self.ui_elements_bundles['main menu']
        buttons = ('continue button', 'quit game button')
        for button in buttons:
            bundle.toggle_element(button, self.window.game_view is not None)


if __name__:
    from game import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_X, SCREEN_Y
