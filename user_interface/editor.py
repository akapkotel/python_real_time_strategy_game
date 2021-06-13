#!/usr/bin/env python
from typing import List, Tuple

from user_interface.user_interface import (
    UiElementsBundle, Button, ScrollableContainer, EditorPlaceableObject
)
from utils.colors import RED, GREEN, YELLOW, BLUE, colors_names
from utils.data_types import GridPosition
from utils.functions import get_path_to_file, add_player_color_to_name

EDITOR = 'editor'


class ScenarioEditor:
    game = None

    def __init__(self, ui_center_x, ui_center_y):
        self.position = ui_center_x, ui_center_y
        self.history: List[Tuple[GridPosition, str]] = []  # to undo changes
        self.available_colors = {}
        self.current_color = None

        self.ui_elements = self.create_editor_ui_panel()
        self.set_colors_palette(self.game.players)
        self.game.unload_bundle(EDITOR)

    def do_edit(self, change: Tuple[GridPosition, str]):
        self.history.append(change)

    def undo_edit(self):
        self.history.pop()

    def set_colors_palette(self, players):
        self.available_colors = {
            colors_names[p.color]: p.color for p in players.values()
        }
        self.current_color = colors_names[self.game.local_human_player.color]
        self.create_colors_buttons()

    def create_colors_buttons(self):
        ui_x, ui_y = self.position
        self.ui_elements.extend(
            Button('small_button_none.png', (ui_x - 100) + 60 * i, ui_y)
            for i, (color_name, color) in
            enumerate(self.available_colors.items())
        )

    def find_all_gameobjects(self) -> List[str]:
        gameobjects = []
        colors = RED, GREEN, YELLOW, BLUE
        for category in ('units', 'buildings'):
            for color in colors:
                gameobjects.extend(
                    [add_player_color_to_name(name, color)
                     for name in self.game.configs[category].keys()]
                )
        gameobjects = [o for o in gameobjects if get_path_to_file(o) is not None]
        return gameobjects

    def create_editor_ui_panel(self) -> UiElementsBundle:
        ui_x, ui_y = self.position
        editor_ui_elements = UiElementsBundle(
            name=EDITOR,
            index=3,
            elements=[
                ScrollableContainer('ui_scrollable_frame.png', ui_x, ui_y,
                                    'scrollable'),
            ],
            register_to=self.game,
        )
        editor_ui_elements.extend(
            [
                EditorPlaceableObject(object_name, ui_x, 100 * i,
                       parent=editor_ui_elements.elements[0])
                for i, object_name in enumerate(self.find_all_gameobjects())
            ]
        )
        return editor_ui_elements
