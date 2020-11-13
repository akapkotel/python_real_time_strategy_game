#!/usr/bin/env python
from __future__ import annotations

from typing import List, Dict, Optional
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
    register_to: ObjectsOwner
    _owners = None

    def __post_init__(self):
        self.register_to_objectsowners(self.register_to)
        for element in self.elements:
            element.bundle = self

    def add(self, element: UiElement):
        self.elements.append(element)
        element.bundle = self

    def remove(self, element: UiElement):
        self.elements.remove(element)
        element.bundle = None


class UiBundlesHandler(ObjectsOwner):
    """
    This class keeps track of currently loaded and displayed UiElements,
    allowing switching between different groups of buttons, checkboxes etc.
    and dynamically compose content of the screen eg. in game menu or player
    interface.
    """

    def __init__(self):
        """
        To add UiElementsBundle to this handler you need only to initialize
        this bundle inside of the class inheriting from the handler and it
        will automatically add itself to the list of bundles and it's all
        elements will .
        """
        ObjectsOwner.__init__(self)
        self.ui_elements_bundles: Dict[str, UiElementsBundle] = {}
        self.submenu_index = 0
        self.ui_elements_spritelist = UiSpriteList()

    def register(self, acquired: OwnedObject):
        acquired: UiElementsBundle
        self.ui_elements_bundles[acquired.name] = acquired
        self.ui_elements_spritelist.extend(acquired.elements)
        self.bind_ui_elements_with_ui_spritelist(acquired.elements)

    def unregister(self, owned: OwnedObject):
        owned: UiElementsBundle
        del self.ui_elements_bundles[owned.name]

    def get_notified(self, *args, **kwargs):
        pass

    def switch_submenu_of_index(self, index: int = 0):
        for submenu in self.ui_elements_bundles.values():
            if submenu.index == index:
                return self._switch_to_submenu(submenu)

    def switch_to_submenu_of_name(self, name: str):
        self._switch_to_submenu(self.ui_elements_bundles[name])

    def _switch_to_submenu(self, submenu: UiElementsBundle):
        log(f'Switched to submenu {submenu.name} of index: {submenu.index}')
        self._unload_all()
        self._load_bundle(submenu)
        self.submenu_index = submenu.index

    def bind_ui_elements_with_ui_spritelist(self, elements):
        for ui_element in elements:
            ui_element.ui_spritelist = self.ui_elements_spritelist

    def load_bundle(self,
                    name: Optional[str] = None,
                    index: Optional[int] = None):
        """
        Only add UiElementsBundle elements to the current list, without
        removing anything from it.
        """
        if name is not None:
            bundle = self.ui_elements_bundles.get(name, None)
        elif index is not None:
            bundle = self.get_bundle_of_index(index)
        else:
            return
        if bundle is not None:
            self._load_bundle(bundle)

    def unload_bundle(self,
                      name: Optional[str] = None,
                      index: Optional[int] = None):
        if name is not None:
            bundle = self.ui_elements_bundles.get(name, None)
        elif index is not None:
            bundle = self.get_bundle_of_index(index)
        else:
            return
        if bundle is not None:
            self._unload_bundle(bundle)

    def get_bundle_of_index(self, index: int) -> Optional[UiElementsBundle]:
        try:
            return next(filter(lambda b: b.index == index,
                               self.ui_elements_bundles.values()))
        except StopIteration:
            return

    def _load_bundle(self, bundle: UiElementsBundle):
        self.ui_elements_spritelist.extend(bundle.elements)
        self.bind_ui_elements_with_ui_spritelist(bundle.elements)

    def _unload_bundle(self, bundle: UiElementsBundle):
        for element in self.ui_elements_spritelist[::-1]:
            if element.bundle == bundle:
                self.ui_elements_spritelist.remove(element)

    def _unload_all(self):
        self.ui_elements_spritelist.clear()


class Menu(WindowView, UiBundlesHandler):

    def __init__(self):
        super().__init__()
        UiBundlesHandler.__init__(self)
        self.set_updated_and_drawn_lists()

    def on_show_view(self):
        super().on_show_view()
        self.window.toggle_mouse_and_keyboard(True)
        self.switch_submenu_of_index(0)
