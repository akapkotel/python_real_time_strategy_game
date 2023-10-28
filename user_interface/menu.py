#!/usr/bin/env python
from __future__ import annotations

from functools import partial

from controllers.constants import MULTIPLAYER_MENU
from user_interface.constants import (
    LOADING_MENU, SAVING_MENU, MAIN_MENU, OPTIONS_SUBMENU, CREDITS_SUBMENU,
    CAMPAIGN_MENU, SKIRMISH_MENU, NEW_GAME_MENU, SCENARIO_EDITOR_MENU,
    QUIT_GAME_BUTTON, CONTINUE_BUTTON, SAVE_GAME_BUTTON, NOT_AVAILABLE_NOTIFICATION
)
from user_interface.user_interface import (
    UiElementsBundle, UiBundlesHandler, Button, Tab, Checkbox, TextInputField,
    UiTextLabel, Slider, Background, Frame
)
from utils.geometry import generate_2d_grid
from utils.views import LoadableWindowView


class Menu(LoadableWindowView, UiBundlesHandler):

    def __init__(self):
        super().__init__()
        UiBundlesHandler.__init__(self)
        self.set_updated_and_drawn_lists()
        self.create_submenus()

    def create_back_to_menu_button(self) -> Button:
        return Button('menu_button_back.png', SCREEN_X, 150, functions=partial(self.switch_to_bundle_of_name, MAIN_MENU))

    def create_submenus(self):
        window = self.window
        switch_menu = self.switch_to_bundle_of_name

        x, y = SCREEN_X * 0.25, (i for i in range(125, SCREEN_HEIGHT, 125))
        main_menu = UiElementsBundle(
            name=MAIN_MENU,
            elements=[
                # left row:
                Button('menu_button_exit.png', x, next(y),
                       functions=window.close),
                Button('menu_button_credits.png', x, next(y),
                       functions=partial(switch_menu, CREDITS_SUBMENU)),
                Button('menu_button_options.png', x, next(y),
                       functions=partial(switch_menu, OPTIONS_SUBMENU)),
                Button('menu_button_loadgame.png', x, next(y),
                       functions=partial(switch_menu, LOADING_MENU)),
                Button('menu_button_newgame.png', x, next(y),
                       functions=partial(switch_menu, NEW_GAME_MENU)),
                Button('menu_button_continue.png', x, next(y),
                       name=('%s' % CONTINUE_BUTTON), active=False,
                       functions=window.continue_game),
                Button('menu_button_quit.png', x, next(y),
                       name=('%s' % QUIT_GAME_BUTTON), active=False,
                       functions=window.quit_current_game),
                Button('menu_button_savegame.png', x, next(y),
                       name=('%s' % SAVE_GAME_BUTTON),
                       functions=partial(switch_menu, SAVING_MENU),
                       active=False),
                # buttons in center:
                Button('menu_button_skirmish.png', x * 4, SCREEN_HEIGHT * 0.75,
                       functions=partial(switch_menu, SKIRMISH_MENU)),
                Button('menu_button_campaign.png', x * 6, SCREEN_HEIGHT * 0.75,
                       functions=partial(switch_menu, CAMPAIGN_MENU)),
                Button('menu_button_multiplayer.png', x * 4, SCREEN_HEIGHT * 0.25,
                       functions=partial(switch_menu, MULTIPLAYER_MENU)),
                Button('menu_button_editor.png', x * 6, SCREEN_HEIGHT * 0.25,
                       functions=partial(switch_menu, SCENARIO_EDITOR_MENU))
            ],
            register_to=self
        )

        columns = 4
        rows = 10
        col_width = SCREEN_WIDTH // (columns + 1)
        row_height = SCREEN_HEIGHT // (rows + 1)

        positions = (p for p in generate_2d_grid(col_width, SCREEN_HEIGHT * 0.8, rows, columns, col_width, row_height))

        x, y = SCREEN_X, (i for i in range(300, SCREEN_HEIGHT, 75))
        options_menu = UiElementsBundle(
            name=OPTIONS_SUBMENU,
            elements=[
                self.create_back_to_menu_button(),
                # set 'subgroup' index for each element to assign it to the
                # proper tab in options sub-menu:
                Checkbox('menu_checkbox.png', *next(positions), 'Vehicles threads:',
                         20, ticked=window.settings.vehicles_threads,
                         variable=(window.settings, 'vehicles_threads'),
                         subgroup=1),
                Checkbox('menu_checkbox.png', *next(positions), 'Full screen:',
                         20, ticked=window.fullscreen,
                         functions=window.toggle_full_screen, subgroup=1),
            ],
            register_to=self
        )

        positions = (p for p in generate_2d_grid(col_width, SCREEN_HEIGHT * 0.8, rows, columns, col_width, row_height))
        # sound:
        options_menu.extend(
            [
                Checkbox('menu_checkbox.png', *next(positions),  # x, next(y)
                    'Music:', 20, ticked=window.sound_player.music_on,
                    variable=(window.sound_player, 'music_on'), subgroup=2
                ),
                Checkbox('menu_checkbox.png', *next(positions),  # x, next(y)
                    'Sound effects:', 20, ticked=window.sound_player.sound_effects_on,
                    variable=(window.sound_player, 'sound_effects_on'),
                    subgroup=2
                ),
                Slider('slider.png', *next(positions), 'Sound volume:', 200,
                       variable=(window.settings, 'volume'), subgroup=2),
                Slider('slider.png', *next(positions), 'Effects volume:', 200,
                       variable=(window.settings, 'effects_volume'), subgroup=2),
                Slider('slider.png', *next(positions), 'Music volume:', 200,
                       variable=(window.settings, 'music_volume'),
                       subgroup=2),
            ]
        )

        positions = (p for p in generate_2d_grid(col_width, SCREEN_HEIGHT * 0.8, rows, columns, col_width, row_height))

        if self.window.settings.developer_mode:  # cheats!
            options_menu.extend(
                (Checkbox('menu_checkbox.png', *next(positions), 'Immortal player units:',
                         20, ticked=window.settings.immortal_player_units,
                         variable=(window.settings, 'immortal_player_units'),
                         subgroup=3),
                Checkbox('menu_checkbox.png', *next(positions), 'AI Sleep:',
                         20, ticked=window.settings.ai_sleep,
                         variable=(window.settings, 'ai_sleep'),
                         subgroup=3),
                 Checkbox('menu_checkbox.png', *next(positions), 'Unlimited player resources:',
                          20, ticked=window.settings.unlimited_player_resources,
                          variable=(window.settings, 'unlimited_player_resources'),
                          subgroup=3),
                 Checkbox('menu_checkbox.png', *next(positions), 'Unlimited AI resources',
                          20, ticked=window.settings.unlimited_cpu_resources,
                          variable=(window.settings, 'unlimited_cpu_resources'),
                          subgroup=3),
                 Checkbox('menu_checkbox.png', *next(positions), 'Instant production time',
                          20, ticked=window.settings.instant_production_time,
                          variable=(window.settings, 'instant_production_time'),
                          subgroup=3),
                )
            )

        # tabs switching what groups of elements are visible by
        # switching between subgroups:
        graphics_tab = Tab('menu_tab_graphics.png', 960,
                           SCREEN_HEIGHT - 34, functions=partial(
                           options_menu.switch_to_subgroup, 1))
        sound_tab = Tab('menu_tab_sound.png', 320,
                        SCREEN_HEIGHT - 34, functions=partial(
                        options_menu.switch_to_subgroup, 2),
                        other_tabs=(graphics_tab,))
        game_tab = Tab('menu_tab_game.png', 1600,
                        SCREEN_HEIGHT - 34, functions=partial(
                        options_menu.switch_to_subgroup, 3),
                        other_tabs=(graphics_tab, sound_tab))
        options_menu.extend((sound_tab, graphics_tab, game_tab))
        sound_tab.on_mouse_press(1)

        x, y = SCREEN_X * 1.5, (i for i in range(300, SCREEN_HEIGHT, 125))

        loading_menu = UiElementsBundle(
            name=LOADING_MENU,
            elements=[
                self.create_back_to_menu_button(),
                # left column - ui-buttons:
                Button('menu_button_loadgame.png', x, next(y),
                       functions=window.load_saved_game_or_scenario),
                Button('menu_button_deletesave.png', x, next(y),
                       functions=window.delete_saved_game)
            ],
            register_to=self,
            _on_load=partial(window.update_saved_games_list, LOADING_MENU)
        )

        y = (i for i in range(675, 300, -125))
        text_input = TextInputField('text_input_field.png', x, next(y), 'input_field')
        saving_menu = UiElementsBundle(
            name=SAVING_MENU,
            elements=[
                self.create_back_to_menu_button(),
                Button('menu_button_savegame.png', x, next(y),
                       functions=partial(window.save_game, text_input)),
                text_input
            ],
            register_to=self,
            _on_load=partial(window.update_saved_games_list, SAVING_MENU)
        )

        x, y = SCREEN_WIDTH * 0.25, SCREEN_Y
        new_game_menu = UiElementsBundle(
            name=NEW_GAME_MENU,
            elements=[
                self.create_back_to_menu_button(),
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
            name='credits',
            elements=[
                self.create_back_to_menu_button(),
            ],
            register_to=self
        )

        positions = (p for p in generate_2d_grid(col_width, SCREEN_HEIGHT * 0.8, rows, columns, col_width, row_height))
        y = (i for i in range(300, 675, 75))
        skirmish_menu = UiElementsBundle(
            name=SKIRMISH_MENU,
            elements=[
                # TODO: create background image
                # Background('background.png', SCREEN_X, SCREEN_Y),
                self.create_back_to_menu_button(),
                Button('menu_button_play.png', SCREEN_X, 300, functions=window.start_new_game),
                Slider('slider.png',  *next(positions), 'Trees density:', 200,
                       variable=(window.settings, 'percent_chance_for_spawning_tree'),
                       min_value=0.01, max_value=0.1),
                Slider('slider.png',  *next(positions), 'Start resources:', 200,
                       variable=(window.settings, 'starting_resources'),
                       min_value=0.25, max_value=1.0),
                Slider('slider.png',  *next(positions), 'Map width:', 200,
                       variable=(window.settings, 'map_width'),
                       min_value=60, max_value=260, step=20),
                Slider('slider.png',  *next(positions), 'Map height:', 200,
                       variable=(window.settings, 'map_height'),
                       min_value=60, max_value=260, step=20),
            ],
            register_to=self,
            _on_load=partial(window.update_scenarios_list, SKIRMISH_MENU)
        )

        campaign_menu = UiElementsBundle(
            name=CAMPAIGN_MENU,
            elements=[
                self.create_back_to_menu_button(),
                UiTextLabel(SCREEN_X, SCREEN_Y, NOT_AVAILABLE_NOTIFICATION, 20)
            ],
            register_to=self,
            _on_load=partial(window.update_scenarios_list, CAMPAIGN_MENU)
        )

        multiplayer_menu = UiElementsBundle(
            name=MULTIPLAYER_MENU,
            elements=[
                self.create_back_to_menu_button(),
                UiTextLabel(SCREEN_X, SCREEN_Y, NOT_AVAILABLE_NOTIFICATION, 20)
            ],
            register_to=self
        )

        scenario_editor_menu = UiElementsBundle(
            name=SCENARIO_EDITOR_MENU,
            elements=[
                self.create_back_to_menu_button(),
                UiTextLabel(SCREEN_X, SCREEN_Y, NOT_AVAILABLE_NOTIFICATION, 20)
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
        bundle = self.ui_elements_bundles[MAIN_MENU]
        for button in (CONTINUE_BUTTON, QUIT_GAME_BUTTON, SAVE_GAME_BUTTON):
            if self.window.game_view is not None:
                bundle.activate_element(button)
            else:
                bundle.deactivate_element(button)


if __name__:
    from game import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_X, SCREEN_Y
