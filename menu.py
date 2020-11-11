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
        self.ui_elements: UiSpriteList[UiElement] = UiSpriteList()
        self.set_updated_and_drawn_lists()

    def on_show_view(self):
        super().on_show_view()
        self.window.toggle_mouse_and_keyboard(True)

    def register(self, acquired: OwnedObject):
        acquired: Union[WindowView, UiElement]
        if isinstance(acquired, UiElementsBundle):
            self.submenus[acquired.name] = acquired
        else:
            self.ui_elements.append(acquired)

    def unregister(self, owned: OwnedObject):
        owned: Union[WindowView, UiElement]
        if isinstance(owned, UiElementsBundle):
            del self.submenus[owned.name]
        else:
            self.ui_elements.remove(owned)

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
        self.ui_elements.clear()
        self.ui_elements.extend(submenu.elements)
        self.submenu_index = submenu.index
