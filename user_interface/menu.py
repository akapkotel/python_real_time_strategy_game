#!/usr/bin/env python
from __future__ import annotations

from functools import partial

from utils.constants import MULTIPLAYER_MENU, SCENARIOS, PROJECTS, SAVED_GAMES, SCENARIO_EDITOR_MENU, NEW_GAME_MENU, \
    SKIRMISH_MENU, CAMPAIGN_MENU, LOADING_MENU, SAVING_MENU, MAIN_MENU, OPTIONS_SUBMENU, GRAPHICS_TAB, SOUND_TAB, \
    GAME_TAB, CREDITS_SUBMENU, NOT_AVAILABLE_NOTIFICATION, QUIT_GAME_BUTTON, CONTINUE_BUTTON, SAVE_GAME_BUTTON
from user_interface.user_interface import (
    UiElementsBundle, UiBundlesHandler, Button, Checkbox, TextInputField, UiTextLabel, Slider, SelectableGroup,
    GenericTextButton, ScrollableContainer, ImageSlot
)
from utils.geometry import generate_2d_grid
from utils.views import LoadableWindowView

LOADER = 'loader'


class Menu(LoadableWindowView, UiBundlesHandler):

    def __init__(self):
        super().__init__()
        UiBundlesHandler.__init__(self)
        self.set_updated_and_drawn_lists()
        self.create_submenus()

    def create_back_to_menu_button(self) -> Button:
        return Button('menu_button_back.png', SCREEN_X, 150, functions=partial(self.switch_to_bundle, MAIN_MENU))

    def create_submenus(self):
        window = self.window
        switch_menu = self.switch_to_bundle

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
                       name=CONTINUE_BUTTON, active=False,
                       functions=window.continue_game),
                Button('menu_button_quit.png', x, next(y),
                       name=QUIT_GAME_BUTTON, active=False,
                       functions=window.quit_current_game),
                Button('menu_button_savegame.png', x, next(y),
                       name=SAVE_GAME_BUTTON, functions=window.open_saving_menu,
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
        rows = 18
        col_width = SCREEN_WIDTH // (columns + 1)
        row_height = SCREEN_HEIGHT // (rows + 1) * 0.75

        options_menu = UiElementsBundle(
            name=OPTIONS_SUBMENU,
            elements=[
                self.create_back_to_menu_button(),
                Button('menu_tab_graphics.png', 960, SCREEN_HEIGHT - 34,
                    functions=(partial(switch_menu, GRAPHICS_TAB, (OPTIONS_SUBMENU,)))),
                Button('menu_tab_sound.png', 320, SCREEN_HEIGHT - 34,
                    functions=(partial(switch_menu, SOUND_TAB, (OPTIONS_SUBMENU,)))),
                Button('menu_tab_game.png', 1600, SCREEN_HEIGHT - 34,
                    functions=(partial(switch_menu, GAME_TAB, (OPTIONS_SUBMENU,))))
            ],
            register_to=self
        )

        positions = (p for p in generate_2d_grid(col_width, SCREEN_HEIGHT * 0.8, rows, columns, col_width, row_height))
        graphics_tab = UiElementsBundle(
            name=GRAPHICS_TAB,
            elements=[
                Checkbox('menu_checkbox.png', *next(positions), 'Vehicles threads:',
                         20, ticked=window.settings.vehicles_threads,
                         variable=(window.settings, 'vehicles_threads')),
                Checkbox('menu_checkbox.png', *next(positions), 'Full screen:',
                         20, ticked=window.fullscreen,
                         functions=window.toggle_full_screen),
                Checkbox('menu_checkbox.png', *next(positions), 'Simplified health bars:',
                         20, ticked=window.settings.simplified_health_bars,
                         variable=(window.settings, 'simplified_health_bars')),
            ],
            register_to=self
        )

        positions = (p for p in generate_2d_grid(col_width, SCREEN_HEIGHT * 0.8, rows, columns, col_width, row_height))
        sound_tab = UiElementsBundle(
            name=SOUND_TAB,
            elements=[
                Checkbox('menu_checkbox.png', *next(positions),
                         text='Sound:', font_size=20, ticked=window.settings.sound_on,
                         variable=(window.sound_player, 'sound_on')),
                Slider('slider.png', *next(positions), 'Sound volume:', 200,
                       variable=(window.sound_player, 'sound_volume')),
                Checkbox('menu_checkbox.png', *next(positions),
                         text='Music:', font_size=20, ticked=window.settings.music_on,
                         variable=(window.sound_player, 'music_on')),
                Slider('slider.png', *next(positions), 'Music volume:', 200,
                       variable=(window.sound_player, 'music_volume')),
                Checkbox('menu_checkbox.png', *next(positions), text='Sound effects:', font_size=20,
                         ticked=window.settings.sound_effects_on,
                         variable=(window.sound_player, 'sound_effects_on')),
                Slider('slider.png', *next(positions), 'Effects volume:', 200,
                       variable=(window.sound_player, 'effects_volume')),
            ],
            register_to=self
        )

        positions = (p for p in generate_2d_grid(col_width, SCREEN_HEIGHT * 0.8, rows, columns, col_width, row_height))
        game_tab = UiElementsBundle(
            name=GAME_TAB,
            elements=[],
            register_to=self
        )

        if self.window.settings.developer_mode or self.window.settings.cheats == 889267:  # cheats!
            game_tab.extend(
                [
                    UiTextLabel(*next(positions), text='Cheats:', font_size=20, align_x='right'),
                    Checkbox('menu_checkbox.png', *next(positions), 'Immortal player units:',
                             20, ticked=window.settings.immortal_player_units,
                             functions=partial(window.switch_immortality, True),
                             variable=(window.settings, 'immortal_player_units')),
                    Checkbox('menu_checkbox.png', *next(positions), 'Immortal AI units:',
                             20, ticked=window.settings.immortal_cpu_units,
                             functions=partial(window.switch_immortality, False),
                             variable=(window.settings, 'immortal_cpu_units')),
                    Checkbox('menu_checkbox.png', *next(positions), 'AI Sleep:',
                             20, ticked=window.settings.ai_sleep,
                             variable=(window.settings, 'ai_sleep')),
                    Checkbox('menu_checkbox.png', *next(positions), 'Unlimited player resources:',
                              20, ticked=window.settings.unlimited_player_resources,
                              variable=(window.settings, 'unlimited_player_resources')),
                    Checkbox('menu_checkbox.png', *next(positions), 'Unlimited AI resources',
                              20, ticked=window.settings.unlimited_cpu_resources,
                              variable=(window.settings, 'unlimited_cpu_resources')),
                    Checkbox('menu_checkbox.png', *next(positions), 'Instant production time',
                              20, ticked=window.settings.instant_production_time,
                              variable=(window.settings, 'instant_production_time')),
                    Checkbox('menu_checkbox.png', *next(positions), 'Fog of war',
                             20, ticked=window.settings.fog_of_war,
                             variable=(window.settings, 'fog_of_war')),
                ]
            )

        x, y = SCREEN_X, (i for i in range(300, SCREEN_HEIGHT, 125))
        loading_menu = UiElementsBundle(
            name=LOADING_MENU,
            elements=[
                self.create_back_to_menu_button(),
                Button('menu_button_loadgame.png', x, next(y),
                       functions=window.load_game),
                Button('menu_button_deletesave.png', x, next(y),
                       functions=window.delete_saved_game),
                ImageSlot('image_slot.png', x, next(y) + 100, 'miniature_slot', None),
                ScrollableContainer('ui_scrollable_frame.png', SCREEN_WIDTH * 0.2, SCREEN_Y, 'scrollable')
            ],
            register_to=self,
            _on_load=partial(self.refresh_files_list_in_bundle, LOADING_MENU, SAVED_GAMES)
        )

        y = (i for i in range(300, SCREEN_HEIGHT, 125))
        text_input = TextInputField('text_input_field.png', x, next(y), 'input_field', forbidden_symbols='.,/\\')
        saving_menu = UiElementsBundle(
            name=SAVING_MENU,
            elements=[
                self.create_back_to_menu_button(),
                Button('menu_button_savegame.png', x, next(y),
                       functions=partial(window.save_game, text_input)),
                text_input,
                ImageSlot('image_slot.png', x, next(y) + 100, 'miniature_slot', None),
                ScrollableContainer('ui_scrollable_frame.png', SCREEN_WIDTH * 0.2, SCREEN_Y, 'scrollable'),
                # TODO: add checkbox to set the 'finished' flag
            ],
            register_to=self,
            _on_load=partial(self.refresh_files_list_in_bundle, SAVING_MENU, SAVED_GAMES)
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
                ScrollableContainer('ui_scrollable_frame.png', SCREEN_WIDTH * 0.8, SCREEN_Y, 'scrollable'),
                ImageSlot('image_slot.png', SCREEN_X, 650, 'miniature_slot', None),
                # TODO: create and add ColorPicker using PlayerColor enum
            ],
            register_to=self,
            _on_load=partial(self.refresh_files_list_in_bundle, SKIRMISH_MENU, SCENARIOS)
        )

        campaign_menu = UiElementsBundle(
            name=CAMPAIGN_MENU,
            elements=[
                self.create_back_to_menu_button(),
                UiTextLabel(SCREEN_X, SCREEN_Y, NOT_AVAILABLE_NOTIFICATION, 20),
                ScrollableContainer('ui_scrollable_frame.png', SCREEN_WIDTH * 0.2, SCREEN_Y, 'scrollable')
            ],
            register_to=self,
            _on_load=partial(self.refresh_files_list_in_bundle, CAMPAIGN_MENU, SCENARIOS)
        )

        multiplayer_menu = UiElementsBundle(
            name=MULTIPLAYER_MENU,
            elements=[
                self.create_back_to_menu_button(),
                UiTextLabel(SCREEN_X, SCREEN_Y, NOT_AVAILABLE_NOTIFICATION, 20)
            ],
            register_to=self
        )

        positions = (p for p in generate_2d_grid(col_width, SCREEN_HEIGHT * 0.8, rows, columns, col_width, row_height))
        y = (i for i in range(300, 675, 75))

        text_input = TextInputField('text_input_field.png', SCREEN_X, 650, 'input_field', forbidden_symbols='.,/\\')
        scenario_editor_menu = UiElementsBundle(
            name=SCENARIO_EDITOR_MENU,
            elements=[
                self.create_back_to_menu_button(),
                # UiTextLabel(SCREEN_X, SCREEN_Y, NOT_AVAILABLE_NOTIFICATION, 20),
                Button('menu_button_create.png', SCREEN_X * 0.4, 150,
                       functions=window.open_scenario_editor),
                Button('menu_button_delete_project.png', SCREEN_X, 300,
                       functions=window.delete_scenario),
                Button('menu_button_load_project.png', SCREEN_X, 425,
                       functions=window.load_scenario),
                Button('menu_button_save_project.png', SCREEN_X, 550,
                       functions=partial(window.save_game, text_input)),
                text_input,
                Slider('slider.png', *next(positions), 'Map width:', 200,
                       variable=(window.settings, 'map_width'),
                       min_value=60, max_value=260, step=20),
                Slider('slider.png', *next(positions), 'Map height:', 200,
                       variable=(window.settings, 'map_height'),
                       min_value=60, max_value=260, step=20),
                ScrollableContainer('ui_scrollable_frame.png', SCREEN_WIDTH * 0.8, SCREEN_Y, 'scrollable'),
                ImageSlot('image_slot.png', SCREEN_X, 850, 'miniature_slot', None),
            ],
            register_to=self,
            _on_load=partial(self.refresh_files_list_in_bundle, SCENARIO_EDITOR_MENU, PROJECTS)
        )

    def refresh_files_list_in_bundle(self, bundle_name: str, files_type: str):
        """
        Populate the list of scenarios or saved games to display in the screen.
        """
        self.window.mouse.select_ui_element(None)
        bundle: UiElementsBundle = self.window.menu_view.get_bundle(bundle_name)
        bundle.remove_subgroup(1)
        file_selection_buttons = self.create_files_selection_buttons(bundle, files_type, bundle_name)
        self.populate_scrollable_container_with_selection_buttons(bundle, file_selection_buttons)

    def create_files_selection_buttons(self, bundle, files_type, bundle_name):
        x, y = SCREEN_X // 2, (i for i in range(0, SCREEN_HEIGHT, 1))
        files = self.get_saved_files(bundle_name, files_type)
        return [
            GenericTextButton('generic_text_button.png', x, next(y), file,
                              functions=(partial(self.select_button, bundle, file),), subgroup=1) for file in files
        ]

    def get_saved_files(self, bundle_name: str, files_type: str):
        manager = self.window.save_manager
        if bundle_name == SCENARIO_EDITOR_MENU:
            return manager.projects
        if files_type == SCENARIOS:
            return manager.projects if self.window.settings.editor_mode else manager.scenarios
        return manager.projects if self.window.settings.editor_mode else manager.saved_games

    def select_button(self, bundle, file):
        if (input_field := bundle.find_by_name('input_field')) is not None:
            input_field.set_text(file)
        self.window.mouse.select_ui_element(self.window.mouse.pointed_ui_element)
        self.set_scenario_miniature(bundle, file)

    def set_scenario_miniature(self, bundle: UiElementsBundle, save_file_name: str):
        if (image_slot := bundle.find_by_name('miniature_slot')) is None:
            return
        image_slot: ImageSlot
        if (image := self.window.save_manager.extract_miniature_from_save(save_file_name)) is not None:
            image_slot.image = image

    def populate_scrollable_container_with_selection_buttons(self, bundle, file_selection_buttons):
        scrollable = bundle.find_by_name('scrollable')
        scrollable.clear_children()
        scrollable.extend_children(file_selection_buttons)

    def on_show_view(self):
        super().on_show_view()
        if (game := self.window.game_view) is not None:
            game.save_timer()
            game.mouse.placeable_gameobject = None
        self.window.toggle_mouse_and_keyboard(True)
        self.switch_to_bundle(MAIN_MENU)
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
