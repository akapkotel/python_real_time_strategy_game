#!/usr/bin/env python
from __future__ import annotations

from functools import partial
from typing import Union, Tuple, Optional

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
BTN_TXT_SIZE = 35


class Menu(LoadableWindowView, UiBundlesHandler):

    def __init__(self):
        super().__init__()
        UiBundlesHandler.__init__(self)
        self.previous = []
        self.current = None
        self.set_updated_and_drawn_lists()
        self.create_submenus()

    def create_back_to_menu_button(self, forced: Optional[str] = None) -> Button:
        return Button('menu_button_back.png', SCREEN_X, 150,
                      text=self.window.localization_manager.get('BACK'), text_size=BTN_TXT_SIZE,
                      functions=partial(self.switch_back, forced) if forced is not None else self.switch_back)

    def switch_to_bundle(self,
                         bundle: Union[str, UiElementsBundle],
                         exceptions: Union[Tuple[str], None] = None,
                         back: bool = False):
        if self.current is not None and not back:
            self.previous.append(self.current)
        self.current = bundle if isinstance(bundle, str) else bundle.name
        super().switch_to_bundle(bundle, exceptions)

    def switch_back(self, forced: Optional[str] = None):
        self.switch_to_bundle(forced or self.previous.pop(), back=True)

    def create_submenus(self):
        window = self.window
        switch = self.switch_to_bundle
        localize = self.window.localization_manager.get

        x, y = SCREEN_X * 0.25, (i for i in range(125, SCREEN_HEIGHT, 125))
        main_menu = UiElementsBundle(
            name=MAIN_MENU,
            elements=[
                # left row:
                Button('menu_button_exit.png', x, next(y), text=localize('EXIT'), text_size=BTN_TXT_SIZE,
                       functions=window.close),
                Button('menu_button_credits.png', x, next(y), text=localize('CREDITS'), text_size=BTN_TXT_SIZE,
                       functions=partial(switch, CREDITS_SUBMENU)),
                Button('menu_button_options.png', x, next(y), text=localize('OPTIONS'), text_size=BTN_TXT_SIZE,
                       functions=partial(switch, OPTIONS_SUBMENU)),
                Button('menu_button_loadgame.png', x, next(y), text=localize('LOAD_GAME'), text_size=BTN_TXT_SIZE,
                       functions=partial(switch, LOADING_MENU)),
                Button('menu_button_newgame.png', x, next(y), text=localize('NEW_GAME'), text_size=BTN_TXT_SIZE,
                       functions=partial(switch, NEW_GAME_MENU)),
                Button('menu_button_continue.png', x, next(y),
                       name=CONTINUE_BUTTON, active=False, text=localize('CONTINUE'), text_size=BTN_TXT_SIZE,
                       functions=window.continue_game),
                Button('menu_button_quit.png', x, next(y), text=localize('QUIT'), text_size=BTN_TXT_SIZE,
                       name=QUIT_GAME_BUTTON, active=False, functions=window.quit_current_game),
                Button('menu_button_savegame.png', x, next(y), text=localize('SAVE_GAME'), text_size=BTN_TXT_SIZE,
                       name=SAVE_GAME_BUTTON, functions=window.open_saving_menu, active=False),
                # buttons in center:
                Button('menu_button_skirmish.png', x * 4, SCREEN_HEIGHT * 0.75,
                       text=localize('SKIRMISH'), text_size=BTN_TXT_SIZE, functions=partial(switch, SKIRMISH_MENU)),
                Button('menu_button_campaign.png', x * 6, SCREEN_HEIGHT * 0.75,
                       text=localize('CAMPAIGN'), text_size=BTN_TXT_SIZE, functions=partial(switch, CAMPAIGN_MENU)),
                Button('menu_button_multiplayer.png', x * 4, SCREEN_HEIGHT * 0.25,
                       text=localize('MULTIPLAYER'), text_size=BTN_TXT_SIZE, functions=partial(switch, MULTIPLAYER_MENU)),
                Button('menu_button_editor.png', x * 6, SCREEN_HEIGHT * 0.25,
                       text=localize('SCENARIO_EDITOR'), text_size=BTN_TXT_SIZE, functions=partial(switch, SCENARIO_EDITOR_MENU))
            ],
            register_to=self,
        )

        columns = 4
        rows = 18
        col_width = SCREEN_WIDTH // (columns + 1)
        row_height = SCREEN_HEIGHT // (rows + 1) * 0.75

        options_menu = UiElementsBundle(
            name=OPTIONS_SUBMENU,
            elements=[
                self.create_back_to_menu_button(forced=MAIN_MENU),
                Button('menu_tab_blank.png', 960, SCREEN_HEIGHT - 34,
                       text=localize('GRAPHICS'), text_size=BTN_TXT_SIZE,
                       functions=(partial(switch, GRAPHICS_TAB, (OPTIONS_SUBMENU,)))),
                Button('menu_tab_blank.png', 320, SCREEN_HEIGHT - 34,
                       text=localize('SOUND'), text_size=BTN_TXT_SIZE,
                       functions=(partial(switch, SOUND_TAB, (OPTIONS_SUBMENU,)))),
                Button('menu_tab_blank.png', 1600, SCREEN_HEIGHT - 34,
                       text=localize('GAME'), text_size=BTN_TXT_SIZE,
                       functions=(partial(switch, GAME_TAB, (OPTIONS_SUBMENU,))))
            ],
            register_to=self,
        )

        positions = (p for p in generate_2d_grid(col_width, SCREEN_HEIGHT * 0.8, rows, columns, col_width, row_height))
        graphics_tab = UiElementsBundle(
            name=GRAPHICS_TAB,
            elements=[
                Checkbox('menu_checkbox.png', *next(positions), localize('VEHICLES_THREADS'),
                         20, ticked=window.settings.vehicles_threads,
                         variable=(window.settings, 'vehicles_threads')),
                Checkbox('menu_checkbox.png', *next(positions), localize('FULL_SCREEN'),
                         20, ticked=window.fullscreen, functions=window.toggle_full_screen),
                Checkbox('menu_checkbox.png', *next(positions), localize('SIMPLIFIED_HEALTH_BARS'),
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
                         text=localize('SOUND'), font_size=20, ticked=window.settings.sound_on,
                         variable=(window.sound_player, 'sound_on')),
                Slider('slider.png', *next(positions), localize('SOUND_VOLUME'), 200,
                       variable=(window.sound_player, 'sound_volume')),
                Checkbox('menu_checkbox.png', *next(positions),
                         text=localize('MUSIC'), font_size=20, ticked=window.settings.music_on,
                         variable=(window.sound_player, 'music_on')),
                Slider('slider.png', *next(positions), localize('MUSIC_VOLUME'), 200,
                       variable=(window.sound_player, 'music_volume')),
                Checkbox('menu_checkbox.png', *next(positions), text=localize('SOUND_EFFECTS'), font_size=20,
                         ticked=window.settings.sound_effects_on,
                         variable=(window.sound_player, 'sound_effects_on')),
                Slider('slider.png', *next(positions), localize('SOUND_EFFECTS_VOLUME'), 200,
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
                Button('menu_button_loadsave.png', x, next(y), text=localize('LOAD'), text_size=BTN_TXT_SIZE,
                       functions=window.load_game),
                Button('menu_button_deletesave.png', x, next(y), text=localize('DELETE'), text_size=BTN_TXT_SIZE,
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
                Button('menu_button_savegame.png', x, next(y), text=localize('SAVE'), text_size=BTN_TXT_SIZE,
                       functions=partial(window.save_game, text_input)),
                text_input,
                ImageSlot('image_slot.png', x, next(y) + 100, 'miniature_slot', None),
                ScrollableContainer('ui_scrollable_frame.png', SCREEN_WIDTH * 0.2, SCREEN_Y, 'scrollable'),
            ],
            register_to=self,
            _on_load=partial(self.refresh_files_list_in_bundle, SAVING_MENU, SAVED_GAMES)
        )

        x, y = SCREEN_WIDTH * 0.25, SCREEN_Y
        new_game_menu = UiElementsBundle(
            name=NEW_GAME_MENU,
            elements=[
                self.create_back_to_menu_button(),
                Button('menu_button_skirmish.png', x, y, text=localize('SKIRMISH'), text_size=BTN_TXT_SIZE,
                       functions=partial(switch, 'skirmish menu')),
                Button('menu_button_campaign.png', 2 * x, y, text=localize('CAMPAIGN'), text_size=BTN_TXT_SIZE,
                       functions=partial(switch, 'campaign menu')),
                Button('menu_button_multiplayer.png', 3 * x, y, text=localize('MULTIPLAYER'), text_size=BTN_TXT_SIZE,
                       functions=partial(switch, 'multiplayer menu')),
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

            elements=[          # TODO: create background image
                # Background('background.png', SCREEN_X, SCREEN_Y),
                self.create_back_to_menu_button(),
                Button('menu_button_continue.png', SCREEN_X, 300, text=localize('BEGIN'),
                       text_size=BTN_TXT_SIZE, functions=window.start_new_game),
                Slider('slider.png',  *next(positions), localize('TREES_DENSITY'), 200,
                       variable=(window.settings, 'percent_chance_for_spawning_tree'),
                       min_value=0.01, max_value=0.1),
                Slider('slider.png',  *next(positions), localize('START_RESOURCES'), 200,
                       variable=(window.settings, 'starting_resources'),
                       min_value=0.25, max_value=1.0),
                Slider('slider.png',  *next(positions), localize('MAP_WIDTH'), 200,
                       variable=(window.settings, 'map_width'),
                       min_value=60, max_value=260, step=20),
                Slider('slider.png',  *next(positions), localize('MAP_HEIGHT'), 200,
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
                UiTextLabel(SCREEN_X, SCREEN_Y, localize('WIP'), 20),
                ScrollableContainer('ui_scrollable_frame.png', SCREEN_WIDTH * 0.2, SCREEN_Y, 'scrollable')
            ],
            register_to=self,
            _on_load=partial(self.refresh_files_list_in_bundle, CAMPAIGN_MENU, SCENARIOS)
        )

        multiplayer_menu = UiElementsBundle(
            name=MULTIPLAYER_MENU,
            elements=[
                self.create_back_to_menu_button(),
                UiTextLabel(SCREEN_X, SCREEN_Y, localize('WIP'), 20)
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
                Button('menu_button_create.png', SCREEN_X * 0.4, 130,
                       text=localize('CREATE_NEW_SCENARIO'), text_size=BTN_TXT_SIZE, functions=window.open_scenario_editor),
                Button('menu_button_delete_project.png', SCREEN_X, 280,
                       text=localize('DELETE_SCENARIO'), text_size=BTN_TXT_SIZE, functions=window.delete_scenario),
                Button('menu_button_load_project.png', SCREEN_X, 405,
                       text=localize('LOAD_SCENARIO'), text_size=BTN_TXT_SIZE, functions=window.load_scenario),
                Button('menu_button_load_project.png', SCREEN_X, 530,
                       text=localize('SAVE_SCENARIO'), text_size=BTN_TXT_SIZE, functions=partial(window.save_game, text_input)),
                text_input,
                Checkbox('menu_checkbox.png', SCREEN_X + 100, 595, localize('FINISHED'),
                         20, name='finished', ticked=False, variable=(window.save_manager, 'finished')),
                Slider('slider.png', *next(positions), localize('MAP_WIDTH'),  200,
                       variable=(window.settings, 'map_width'),
                       min_value=60, max_value=260, step=20),
                Slider('slider.png', *next(positions), localize('MAP_HEIGHT'), 200,
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
                bundle.show_element(button)
            else:
                bundle.deactivate_element(button)
                bundle.hide_element(button)


if __name__:
    from game import SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_X, SCREEN_Y
