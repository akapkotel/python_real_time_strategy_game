#!/usr/bin/env python
from __future__ import annotations

import PIL

from dataclasses import dataclass
from functools import partial
from typing import Dict, List, Optional, Callable, Set, Tuple, Union

from arcade import (
    Sprite, SpriteList, load_texture, draw_rectangle_outline, draw_text,
    draw_rectangle_filled
)
from arcade.arcade_types import Color

from utils.observers import ObjectsOwner, OwnedObject

from utils.functions import log, make_texture

from utils.colors import GREEN, RED, WHITE, BLACK, FOG


class UiSpriteList(SpriteList):
    """
    Wrapper for spritelists containing UiElements for quick identifying the
    spritelists which should be collided with the MouseCursor.
    """

    def __init__(self, use_spatial_hash=False, spatial_hash_cell_size=128,
                 is_static=False):
        super().__init__(use_spatial_hash, spatial_hash_cell_size, is_static)

    def clear(self):
        for i in range(len(self)):
            self.pop()

    def draw(self, **kwargs):
        # noinspection PyUnresolvedReferences
        for ui_element in (u for u in self if u.visible):
            ui_element.draw()


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

    def remove(self, name: str):
        if (element := self._find_by_name(name)) is not None:
            self._remove(element)
            element.bundle = None

    def __getitem__(self, name: str):
        return self._find_by_name(name)

    def show_element(self, name: str):
        if (element := self._find_by_name(name)) is not None:
            element.show()

    def hide_element(self, name: str):
        if (element := self._find_by_name(name)) is not None:
            element.hide()

    def activate_element(self, name: str):
        if (element := self._find_by_name(name)) is not None:
            element.activate()

    def deactivate_element(self, name: str):
        if (element := self._find_by_name(name)) is not None:
            element.deactivate()

    def switch_to_subgroup(self, subgroup: int):
        for element in self.elements:
            if element.subgroup == subgroup:
                element.show()
                element.activate()
            else:
                element.hide()
                element.deactivate()

    def _find_by_name(self, name: str) -> Optional[UiElement]:
        try:
            return next(e for e in self.elements if e.name == name)
        except StopIteration:
            return

    def _remove(self, element: UiElement):
        self.elements.remove(element)
        element.bundle = None


class UiBundlesHandler(ObjectsOwner):
    """
    This class keeps track of currently loaded and displayed UiElements,
    allowing switching between different groups of buttons, checkboxes etc.
    and dynamically compose content of the screen eg. in game menu or player
    interface.
    """

    def __init__(self, use_spatial_hash=False):
        """
        To add UiElementsBundle to this handler you need only to initialize
        this bundle inside of the class inheriting from the handler and it
        will automatically add itself to the list of bundles and it's all
        elements will .
        """
        ObjectsOwner.__init__(self)
        # all bundles available to load and display:
        self.ui_elements_bundles: Dict[str, UiElementsBundle] = {}
        # currently displayed UiElements of the chosen bundle/s:
        self.ui_elements_spritelist = UiSpriteList(use_spatial_hash)

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

    def switch_to_bundle_of_index(self, index: int = 0):
        for bundle in self.ui_elements_bundles.values():
            if bundle.index == index:
                return self._switch_to_bundle(bundle)

    def switch_to_bundle_of_name(self, name: str):
        if name in self.ui_elements_bundles:
            self._switch_to_bundle(self.ui_elements_bundles[name])

    def _switch_to_bundle(self, bundle: UiElementsBundle):
        log(f'Switched to submenu {bundle.name} of index: {bundle.index}')
        self._unload_all()
        self._load_bundle(bundle)

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

    def __getitem__(self, name: Union[str, int]) -> Optional[UiElementsBundle]:
        return self.ui_elements_bundles.get(name, self.get_bundle_of_index(name))

    def get_bundle_of_index(self, index: int) -> Optional[UiElementsBundle]:
        try:
            return next(b for b in self.ui_elements_bundles.values() if b.index == index)
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


class Hierarchical:
    """
    Interface offering hierarchical order of elements, e.g. one element can
    have 'children' and/or 'parent' object. Hierarchy allows user to work
    with an objects and theirs children-objects simultaneously.
    """

    def __init__(self, parent: Optional[Hierarchical] = None):
        self._parent = parent
        self._children: Optional[Set] = None

        if parent is not None:
            parent.add_child(self)

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, parent: Optional[Hierarchical]):
        if parent is None:
            self._parent.discard_child(self)
        else:
            parent.add_child(self)
        self._parent = parent

    @property
    def children(self):
        return self._children

    def add_child(self, child: Hierarchical):
        print(f'Added new child: {child}')
        if self._children is None:
            self._children = set()
        self._children.add(child)

    def discard_child(self, child: Hierarchical):
        self._children.discard(child)

    @property
    def level(self):
        return 0 if not self._parent else self._parent.level + 1


class CursorInteractive(Hierarchical):
    """Interface for all objects which are clickable etc."""

    def __init__(self,
                 can_be_dragged: bool = False,
                 function_on_left_click: Optional[Callable] = None,
                 function_on_right_click: Optional[Callable] = None,
                 parent: Optional[Hierarchical] = None):
        Hierarchical.__init__(self, parent)
        self.pointed = False
        self.dragged = False
        self.can_be_dragged = can_be_dragged
        self.function_on_left_click = function_on_left_click
        self.function_on_right_click = function_on_right_click
        self.cursor = None

    def __repr__(self):
        return f'{self.__class__.__name__} id: {id(self)}'

    def on_mouse_enter(self, cursor: Optional['MouseCursor'] = None):
        if not self.pointed:
            log(f'Mouse over {self}')
            self.pointed = True
            self.cursor = cursor
            self._func_on_mouse_enter(cursor)

    def _func_on_mouse_enter(self, cursor):
        pass

    def on_mouse_exit(self):
        if self.pointed:
            log(f'Mouse left {self}')
            self.pointed = False
            self.cursor = None
            self._func_on_mouse_exit()

    def _func_on_mouse_exit(self):
        pass

    def on_mouse_press(self, button: int):
        log(f'Mouse button {button} clicked on {self}')
        if self.function_on_left_click is not None:
            self.function_on_left_click()
        self.dragged = self.can_be_dragged

    def on_mouse_release(self, button: int):
        log(f'Released button {button} on {self}')
        self.dragged = False

    def on_mouse_drag(self, x: float = None, y: float = None):
        if x is not None:
            setattr(self, 'center_x', x)
        if y is not None:
            setattr(self, 'center_y', y)


class ToggledElement:
    """Interface for toggling objects state of being active and visible."""

    def __init__(self, active: bool = True, visible: bool = True):
        self._visible = visible
        self._active = active

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, value: bool):
        self._active = value
        log(f'{self.__class__.__name__} state = {value}')

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        self._visible = value

    def activate(self):
        self._active = True

    def deactivate(self):
        self._active = False

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False


class UiElement(Sprite, ToggledElement, CursorInteractive, OwnedObject):
    """
    Basic class for all user-interface and menu objects, like buttons,
    scrollbars, mouse-cursors etc.
    UiElement interacts with other UiElements through Hierarchical interface,
    and with other objects in game through OwnedObject interface.
    To add an UiElement to the WindowView register it with OwnedObject method
    register_to_objectsowners.
    To create relation with other UiElement set this UiElement as parent with
    add_child method ot as child of another object by setting it as parent with
    parent property.
    """
    sound_on_mouse_enter = None
    sound_on_mouse_click = None

    def __init__(self, texture_name: str, x: int, y: int,
                 name: Optional[str] = None, active: bool = True,
                 visible: bool = True, parent: Optional[Hierarchical] = None,
                 function_on_right_click: Optional[Callable] = None,
                 function_on_left_click: Optional[Callable] = None,
                 can_be_dragged: bool = False, subgroup: Optional[int] = None):
        super().__init__(texture_name, center_x=x, center_y=y)
        ToggledElement.__init__(self, active, visible)
        CursorInteractive.__init__(self,
                                   can_be_dragged,
                                   function_on_right_click,
                                   function_on_left_click,
                                   parent=parent)
        OwnedObject.__init__(self, owners=True)
        self.name = name
        self.bundle = None
        self.subgroup = subgroup
        self.ui_spritelist = None

    def on_mouse_press(self, button: int):
        super().on_mouse_press(button)
        if (sound := self.sound_on_mouse_click) is not None and self._active:
            self.cursor.window.sound_player.play_sound(sound)

    def on_mouse_enter(self, cursor: Optional['MouseCursor'] = None):
        super().on_mouse_enter(cursor)
        if (sound := self.sound_on_mouse_enter) is not None and self._active:
            cursor.window.sound_player.play_sound(sound)

    def _func_on_mouse_enter(self, cursor):
        if self._active:
            self.set_texture(-1)

    def _func_on_mouse_exit(self):
        if self._active:
            self.set_texture(0)

    def draw(self):
        super().draw()
        if self._active and self.pointed:
            self.draw_highlight_around_element()

    def draw_highlight_around_element(self):
        color = RED if 'exit' in self.textures[-1].name else GREEN
        draw_rectangle_outline(*self.position, self.width + 4, self.height + 4, color, 2)


class Frame(UiElement):

    def __init__(self,
                 texture_name: str,
                 x: int,
                 y: int,
                 width: int,
                 height: int,
                 name: Optional[str] = None,
                 color: Optional[Color] = None,
                 active: bool = False,
                 visible: bool = True,
                 parent: Optional[Hierarchical] = None,
                 subgroup: Optional[int] = None
                 ):
        super().__init__(texture_name, x, y, name, active, visible, parent, subgroup)
        if not texture_name:
            self.textures = [make_texture(width, height, color or WHITE)]
            self.set_texture(0)

    def draw_highlight_around_element(self):
        pass


class Button(UiElement):
    sound_on_mouse_enter = 'cursor_over_ui_element.wav'
    sound_on_mouse_click = 'click_on_ui_element.wav'

    def __init__(self, texture_name: str,
                 x: int,
                 y: int,
                 name: Optional[str] = None,
                 active: bool = True,
                 visible: bool = True,
                 parent: Optional[Hierarchical] = None,
                 function_on_right_click: Optional[Callable] = None,
                 function_on_left_click: Optional[Callable] = None,
                 subgroup: Optional[int] = None
                 ):
        super().__init__('', x, y, name, active, visible, parent,
                         function_on_left_click, function_on_right_click,
                         subgroup=subgroup)
        # we load 2 textures for button: normal and for 'highlighted' button:
        image = PIL.Image.open(texture_name)
        width, height = image.size[0] // 2, image.size[1]
        self.textures = [
            load_texture(texture_name, 0, 0, width, height),
            load_texture(texture_name, width, 0, width, height)
        ]
        self.set_texture(0)

    def draw(self):
        super().draw()
        if not self._active:
            draw_rectangle_filled(*self.position, self.width, self.height, FOG)


class Checkbox(UiElement):
    """
    Checkbox is a UiElement which function is to allow user toggling the
    boolean value of some variable - if Checkbox is 'ticked' the value is
    set to True, else it is considered False.
    """

    def __init__(self, texture_name: str, x: int, y: int, text: str,
                 font_size: int = 10, text_color: Color = WHITE,
                 name: Optional[str] = None, active: bool = True,
                 visible: bool = True, parent: Optional[Hierarchical] = None,
                 function_on_right_click: Optional[Callable] = None,
                 function_on_left_click: Optional[Callable] = None,
                 ticked: bool = False, variable: Tuple[object, str] = None,
                 subgroup: Optional[int] = None):
        """

        :param texture_name:
        :param x:
        :param y:
        :param name:
        :param active:
        :param visible:
        :param parent:
        :param function_on_right_click:
        :param function_on_left_click:
        :param ticked:
        :param variable: Tuple[object, str] -- to bind a variable to this
        Checkbox you must pass a tuple which first element is an reference
        to the python object and second is a string name of this object
        attribute, e.g. (self, 'name_of_my_attribute').
        """
        super().__init__(texture_name, x, y, name, active, visible,
                         parent, function_on_left_click,
                         function_on_right_click, subgroup=subgroup)
        self.ticked = ticked
        self.variable = variable
        self.textures = [
            load_texture(texture_name, 0, 0, 30, 30),
            load_texture(texture_name, 30, 0, 30, 30)
        ]
        self.set_texture(int(self.ticked))
        self.text_label = UiTextLabel(
            x - int(len(text) * font_size * 0.45), y, text, font_size,
            text_color
        )
        self.add_child(self.text_label)

    def _func_on_mouse_enter(self, cursor):
        pass

    def _func_on_mouse_exit(self):
        pass

    def on_mouse_press(self, button: int):
        super().on_mouse_press(button)
        self.ticked = not self.ticked
        self.set_texture(int(self.ticked))
        if self.variable is not None:
            self.toggle_variable()

    def toggle_variable(self):
        setattr(self.variable[0], self.variable[1], self.ticked)

    def draw(self):
        self.text_label.draw()
        super().draw()


class UiTextLabel(UiElement):

    def __init__(self, x: int, y: int, text: str,
                 font_size: int = 10, text_color: Color = WHITE,
                 name: Optional[str] = None, active: bool = False,
                 visible: bool = True, parent: Optional[Hierarchical] = None,
                 subgroup: Optional[int] = None):
        super().__init__('', x, y, name, active, visible, parent, subgroup)
        self.text = text
        self.size = font_size
        self.text_color = text_color
        self.textures = [
            make_texture(int(len(text) * font_size * 0.725), font_size * 2, (1, 1, 1, 1))
        ]
        self.set_texture(0)

    def draw(self):
        super().draw()
        draw_text(
            self.text, self.left, self.bottom + self.size // 2,
            self.text_color, self.size)

    def draw_highlight_around_element(self):
        pass


class ListBox(UiElement):
    ...


class TextInputField(UiElement):
    ...


class ScrollBar(UiElement):
    ...
