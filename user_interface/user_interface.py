#!/usr/bin/env python
from __future__ import annotations

from typing import Optional, Callable, Set, Tuple

from arcade import (
    Sprite, SpriteList, load_texture, draw_rectangle_outline, draw_text
)
from arcade.arcade_types import Color

from utils.observers import OwnedObject

from utils.functions import log, make_texture

from utils.colors import GREEN, RED, WHITE, BLACK


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
        for ui_element in (u for u in self if u.visible):
            ui_element.draw()


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

    def __init__(self, texture_name: str, x: int, y: int,
                 name: Optional[str] = None, active: bool = True,
                 visible: bool = True, parent: Optional[Hierarchical] = None,
                 function_on_right_click: Optional[Callable] = None,
                 function_on_left_click: Optional[Callable] = None,
                 can_be_dragged: bool = False):
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
        self.ui_spritelist = None

    def draw(self):
        super().draw()
        if self.pointed:
            self.draw_highlight_around_element()

    def draw_highlight_around_element(self):
        color = RED if 'quit' in self.textures[-1].name else GREEN
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
                 parent: Optional[Hierarchical] = None
                 ):
        super().__init__(texture_name, x, y, name, active, visible, parent)
        if not texture_name:
            self.texture = make_texture(width, height, color or WHITE)

    def draw_highlight_around_element(self):
        pass


class TabsGroup(UiElement):
    ...


class Tab(UiElement):
    ...


class Button(UiElement):

    def __init__(self, texture_name: str,
                 x: int,
                 y: int,
                 name: Optional[str] = None,
                 active: bool = True,
                 visible: bool = True,
                 parent: Optional[Hierarchical] = None,
                 function_on_right_click: Optional[Callable] = None,
                 function_on_left_click: Optional[Callable] = None,
                 ):
        super().__init__(texture_name, x, y, name, active, visible, parent,
                         function_on_left_click, function_on_right_click)
        self.textures = [
            load_texture(texture_name, 0, 0, 300, 60),
            load_texture(texture_name, 300, 0, 300, 60)
        ]
        self.set_texture(0)

    def draw(self):
        super().draw()


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
                 ticked: bool = False, variable: Tuple[object, str] = None):
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
                         parent,
                         function_on_left_click, function_on_right_click)
        self.ticked = ticked
        self.variable = variable
        self.textures = [
            load_texture(texture_name, 0, 0, 40, 40),
            load_texture(texture_name, 40, 0, 40, 40)
        ]
        self.set_texture(int(self.ticked))
        self.text_label = UiTextLabel(
            x - int(len(text) * font_size * 0.45), y, text, font_size,
            text_color
        )
        self.add_child(self.text_label)

    def on_mouse_press(self, button: int):
        super().on_mouse_press(button)
        self.toggle_variable()

    def toggle_variable(self):
        self.ticked = not self.ticked
        setattr(self.variable[0], self.variable[1], self.ticked)
        self.set_texture(int(self.ticked))

    def draw(self):
        self.text_label.draw()
        super().draw()


class UiTextLabel(UiElement):

    def __init__(self, x: int, y: int, text: str,
                 font_size: int = 10, text_color: Color = WHITE,
                 name: Optional[str] = None, active: bool = False,
                 visible: bool = True, parent: Optional[Hierarchical] = None):
        super().__init__('', x, y, name, active, visible, parent)
        self.text = text
        self.size = font_size
        self.text_color = text_color
        self.textures = [
            make_texture(int(len(text) * font_size * 0.725), font_size * 2, BLACK)
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