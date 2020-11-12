#!/usr/bin/env python
from __future__ import annotations

from typing import List, Dict, Union
from dataclasses import dataclass

from observers import ObjectsOwner, OwnedObject
from user_interface import UiElement, UiSpriteList
from views import WindowView
from utils.functions import log


@dataclass
class UiElementsBundle(OwnedObject):
    """
    A bundle of UiElement objects kept together to easy swithc between Menu
    submenus.

    Initialize with params:\n
    index: int \n
    name: str \n
    elements: List[UiElement]
    """
    index: int
    name: str
    elements: List[UiElement]


class Menu(WindowView, ObjectsOwner):

    def __init__(self):
        super().__init__()
        ObjectsOwner.__init__(self)
        self.submenus: Dict[str, UiElementsBundle] = {}
        self.submenu_index = 1
        self.ui_elements_spritelist = UiSpriteList()
        self.set_updated_and_drawn_lists()

    def on_show_view(self):
        super().on_show_view()
        self.window.toggle_mouse_and_keyboard(True)

    def register(self, acquired: OwnedObject):
        acquired: UiElementsBundle
        self.submenus[acquired.name] = acquired
        self.bind_ui_elements_with_ui_spritelist(acquired.elements)

    def unregister(self, owned: OwnedObject):
        owned: UiElementsBundle
        del self.submenus[owned.name]

    def get_notified(self, *args, **kwargs):
        pass

    def on_update(self, delta_time: float):
        super().on_update(delta_time)

    def switch_submenu_of_index(self, index: int = 0):
        for submenu in self.submenus.values():
            if submenu.index == index:
                return self._switch_to_submenu(submenu)

    def switch_to_submenu_of_name(self, name: str):
        self._switch_to_submenu(self.submenus[name])

    def _switch_to_submenu(self, submenu: UiElementsBundle):
        log(f'Switched to submenu {submenu.name} of index: {submenu.index}')
        self.ui_elements_spritelist.clear()
        self.ui_elements_spritelist.extend(submenu.elements)
        self.bind_ui_elements_with_ui_spritelist(submenu.elements)
        self.submenu_index = submenu.index

    def bind_ui_elements_with_ui_spritelist(self, elements):
        for ui_element in elements:
            ui_element.ui_spritelist = self.ui_elements_spritelist
