#!/usr/bin/env python
from typing import List, Tuple

from user_interface.user_interface import (
    UiElementsBundle, Button, ScrollableContainer, EditorPlaceableObject
)
from utils.data_types import GridPosition

EDITOR = 'editor'


class ScenarioEditor:
    game = None

    def __init__(self, ui_center_x, ui_center_y):
        self.position = ui_center_x, ui_center_y
        self.history: List[Tuple[GridPosition, str]] = []  # to undo changes
        self.game.register(self.create_editor_ui_panel())

    def do_edit(self, change: Tuple[GridPosition, str]):
        self.history.append(change)

    def undo_edit(self):
        self.history.pop()

    def find_all_gameobjects(self):
        raise NotImplementedError

    def create_editor_ui_panel(self) -> UiElementsBundle:
        ui_x, ui_y = self.position
        editor_panel = UiElementsBundle(
            name=EDITOR,
            index=3,
            elements=[
                ScrollableContainer('ui_scrollable_frame.png', ui_x, ui_y,
                                    'scrollable'),
            ],
            register_to=self.game,
        )
        editor_panel.extend(
            [
                EditorPlaceableObject('tank_medium_red.png', ui_x, 100 * i,
                       parent=editor_panel.elements[0]) for i in range(5)
            ]
        )
        return editor_panel
