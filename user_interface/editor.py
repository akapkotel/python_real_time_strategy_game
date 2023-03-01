#!/usr/bin/env python
from functools import partial
from typing import List, Tuple

from arcade import Color

from gameobjects.gameobject import PlaceableGameobject
from gameobjects.constants import UNITS, BUILDINGS
from user_interface.constants import EDITOR
from user_interface.user_interface import (
    UiElementsBundle, Button, ScrollableContainer, EditorPlaceableObject,
    SelectableGroup
)
from utils.colors import RED, GREEN, YELLOW, BLUE, colors_names
from utils.data_types import GridPosition
from utils.functions import get_path_to_file, add_player_color_to_name


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
        buttton_name = 'small_button_none.png'
        self.game.selectable_groups['colors'] = group = SelectableGroup()
        for i, (color_name, color) in enumerate(self.available_colors.items()):
            self.ui_elements.add(
                Button(buttton_name,
                       (ui_x - 100) + 60 * i,
                       ui_y * 1.5,
                       color_name,
                       functions=partial(
                           self.toggle_edited_color, color_name, color),
                       color=color,
                       selectable_group=group)
            )

    def toggle_edited_color(self, color_name: str, color: Color):
        self.current_color = color
        for element in (e for e in self.ui_elements if hasattr(e, 'gameobject_name')):
            element.toggle(color_name in element.gameobject_name)

    def find_all_gameobjects(self) -> List[str]:
        gameobjects = []
        colors = RED, GREEN, YELLOW, BLUE
        # for category in (UNITS, BUILDINGS):
            # objects = self.game.configs[category].keys()
        objects = (o for o in self.game.configs.keys() if self.game.configs[o]['game_id'].startswith(('U', 'B')))
        for color in colors:
            gameobjects.extend(
                [add_player_color_to_name(name, color) for name in objects]
            )
        # since some textures may be not existent yet:
        gameobjects = [
            o for o in gameobjects if get_path_to_file(o) is not None
        ]
        return gameobjects

    def create_editor_ui_panel(self) -> UiElementsBundle:
        ui_x, ui_y = self.position
        editor_ui_elements = UiElementsBundle(
            name=EDITOR,
            elements=[
                ScrollableContainer('ui_scrollable_frame.png', ui_x, ui_y,
                                    'scrollable'),
            ],
            register_to=self.game,
        )
        editor_ui_elements.extend(
            [
                EditorPlaceableObject(
                    name, ui_x, 100 * i,
                    parent=editor_ui_elements.elements[0],
                    functions=partial(self.attach_gameobject_to_cursor, name)
                ) for i, name in enumerate(self.find_all_gameobjects())
            ]
        )
        return editor_ui_elements

    def attach_gameobject_to_cursor(self, gameobject_name: str):
        placeable = PlaceableGameobject(gameobject_name)
        self.game.window.cursor.placeable_gameobject = placeable
