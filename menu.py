#!/usr/bin/env python
from __future__ import annotations

from typing import List, Union, Optional

from arcade import SpriteList
from arcade.arcade_types import Color

from observers import ObjectsOwner, OwnedObject
from user_interface import UiElement, Hierarchical
from views import WindowView
from colors import WHITE


class Menu(WindowView, ObjectsOwner):

    def __init__(self):
        super().__init__()
        ObjectsOwner.__init__(self)
        self.set_updated_and_drawn_lists()
        self.submenus: List[WindowView] = []
        self.current_submenu: Optional[SubMenu] = None
        self.ui_elements: SpriteList[UiElement] = SpriteList()
        self.current_submenu = None

    def on_show_view(self):
        super().on_show_view()
        self.window.toggle_mouse_and_keyboard(True)

    def on_update(self, delta_time: float):
        if self.current_submenu is None:
            super().on_update(delta_time)
        else:
            self.current_submenu.on_update()

    def on_draw(self):
        if self.current_submenu is None:
            super().on_draw()
        else:
            self.current_submenu.on_draw()

    def register(self, acquired: OwnedObject):
        acquired: Union[WindowView, UiElement]
        if isinstance(acquired, WindowView):
            self.submenus.append(acquired)
        else:
            self.ui_elements.append(acquired)

    def unregister(self, owned: OwnedObject):
        owned: Union[WindowView, UiElement]
        if isinstance(owned, WindowView):
            self.submenus.remove(owned)
        else:
            self.ui_elements.remove(owned)

    def get_notified(self, *args, **kwargs):
        pass

    def toggle_submenu(self, submenu: Optional[SubMenu] = None):
        self.current_submenu = submenu
        self.window.show_view(self.current_submenu)


class SubMenu(WindowView, ObjectsOwner, OwnedObject, Hierarchical):

    def __init__(self,
                 name: str,
                 background_color: Color = WHITE):
        WindowView.__init__(self)
        ObjectsOwner.__init__(self)
        OwnedObject.__init__(self, owners=True)
        Hierarchical.__init__(self)

        self.name = name
        self.background_color = background_color
        self.ui_elements: SpriteList[UiElement] = SpriteList()

        self.register_to_objectsowners(self.window.menu_view)

    def on_show_view(self):
        super().on_show_view()
        self.window.background_color = self.background_color

    def register(self, acquired: OwnedObject):
        acquired: UiElement
        self.ui_elements.append(acquired)

    def unregister(self, owned: OwnedObject):
        owned: UiElement
        self.ui_elements.remove(owned)

    def get_notified(self, *args, **kwargs):
        pass
