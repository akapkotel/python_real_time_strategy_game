#!/usr/bin/env python
from __future__ import annotations

from typing import Optional, Callable, Set

from arcade import Sprite, SpriteList, load_texture

from observers import OwnedObject

from utils.functions import log, get_path_to_file


class UiSpriteList(SpriteList):
    """
    Wrapper for spritelists containing UiElements for quick identifying the
    spritelists which should be collided with the MouseCursor.
    """

    def clear(self):
        for i in range(len(self)):
            self.pop()


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

    @children.setter
    def children(self, *children: Hierarchical):
        self._children.update(children)

    def add_child(self, child: Hierarchical):
        print(f'Added new child: {child}')
        if self._children is None:
            self._children = set()
        self._children.add(child)

    def discard_child(self, child: Hierarchical):
        self._children.discard(child)


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
            self._func_on_mouse_enter(cursor)

    def _func_on_mouse_enter(self, cursor):
        pass

    def on_mouse_exit(self):
        if self.pointed:
            log(f'Mouse left {self}')
            self.pointed = False
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

    def __init__(self,
                 texture_name: str,
                 x: int,
                 y: int,
                 active: bool = True,
                 visible: bool = True,
                 parent: Optional[Hierarchical] = None,
                 function_on_right_click: Optional[Callable] = None,
                 function_on_left_click: Optional[Callable] = None,
                 can_be_dragged: bool = False):
        Sprite.__init__(self, texture_name, center_x=x, center_y=y)
        ToggledElement.__init__(self, active, visible)
        CursorInteractive.__init__(self,
                                   can_be_dragged,
                                   function_on_right_click,
                                   function_on_left_click,
                                   parent=parent)
        OwnedObject.__init__(self, owners=True)


class Frame(UiElement):

    def __init__(self,
                 texture_name: str,
                 active: bool = True,
                 visible: bool = True):
        super().__init__(texture_name, active, visible)


class TabsGroup(UiElement):
    ...


class Tab(UiElement):
    ...


class Button(UiElement):

    def __init__(self, texture_name: str,
                 x: int,
                 y: int,
                 active: bool = True,
                 visible: bool = True,
                 parent: Optional[Hierarchical] = None,
                 function_on_right_click: Optional[Callable] = None,
                 function_on_left_click: Optional[Callable] = None,
                 ):
        super().__init__(texture_name, x, y, active, visible, parent,
                         function_on_left_click, function_on_right_click)
        self.highlight = None
        self.ui_spritelist = None
        self.textures = [
            load_texture(texture_name, 0, 0, 300, 60),
            load_texture(texture_name, 300, 0, 300, 60)
        ]
        self.set_texture(0)

    def _func_on_mouse_enter(self, cursor):
        x, y = self.position
        self.highlight = sprite = Sprite(
            get_path_to_file('button_highlight_green.png'), center_x=x, center_y=y
        )
        self.ui_spritelist.append(sprite)
        self.set_texture(1)

    def _func_on_mouse_exit(self):
        self.highlight.kill()
        self.set_texture(0)


class CheckButton(UiElement):
    ...


class ListBox(UiElement):
    ...


class TextInputField(UiElement):
    ...


class ScrollBar(UiElement):
    ...
