#!/usr/bin/env python
from __future__ import annotations

from functools import partial

from user_interface.user_interface import (
    UiElementsBundle, UiBundlesHandler, Button, Tab, Checkbox
)
from utils.views import LoadableWindowView


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
            functions=partial(switch_menu, 'main menu')
        )

        x, y = SCREEN_X, (i for i in range(150, SCREEN_HEIGHT, 125))
        main_menu = UiElementsBundle(
            index=0,
            name='main menu',
            elements=[
                Button('menu_button_exit.png', x, next(y),
                       functions=window.close),
                Button('menu_button_credits.png', x, next(y),
                       functions=partial(switch_menu, 'credits')),
                Button('menu_button_options.png', x, next(y),
                       functions=partial(switch_menu, 'options')),
                Button('menu_button_loadgame.png', x, next(y),
                       functions=partial(switch_menu, 'saving menu')),
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
            name='options',
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
                         functions=window.toggle_fullscreen, subgroup=1),
            ],
            register_to=self
        )
        # sound:
        y = (i for i in range(300, SCREEN_HEIGHT, 75))
        options_menu.extend(
            [
                Checkbox('menu_checkbox.png', x, next(y),
                    'Sound:', 20, ticked=window.sound_player.sound_on,
                    variable=(window.sound_player, 'sound_on'), subgroup=2
                ),
                Checkbox('menu_checkbox.png', x, next(y),
                    'Music:', 20, ticked=window.sound_player.sound_on,
                    variable=(window.sound_player, 'music_on'), subgroup=2
                ),
                Checkbox('menu_checkbox.png', x, next(y),
                    'Sound effects:', 20, ticked=window.sound_player.sound_on,
                    variable=(window.sound_player, '_sound_effects_on'),
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
        self.window.sound_player.play_playlist('menu')

    def toggle_game_related_buttons(self):
        bundle = self.ui_elements_bundles['main menu']
        buttons = ('continue button', 'quit game button')
        if self.window.game_view is not None:
            for button in buttons:
                bundle.show_element(button)
                bundle.activate_element(button)
        else:
            for button in buttons:
                bundle.hide_element(button)
                bundle.deactivate_element(button)


if __name__:
    from game import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_X, SCREEN_Y
