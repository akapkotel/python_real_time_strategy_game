#!/usr/bin/env python
from __future__ import annotations

import time
from collections import defaultdict
from functools import partial, singledispatchmethod

import PIL

from dataclasses import dataclass
from typing import (
    Dict, List, Optional, Callable, Set, Tuple, Union, Type, Any
)

from arcade import (
    Sprite, Texture, load_texture, draw_rectangle_outline, draw_text,
    draw_rectangle_filled, draw_scaled_texture_rectangle, check_for_collision,
    draw_lrtb_rectangle_filled, MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT
)
from arcade.arcade_types import Color
from arcade.key import BACKSPACE, ENTER

from controllers.constants import HORIZONTAL, VERTICAL
from user_interface.constants import CONFIRMATION_DIALOG, PADDING_X, PADDING_Y
from utils.observer import Observed, Observer
from utils.geometry import clamp
from utils.colors import rgb_to_rgba
from utils.improved_spritelists import UiSpriteList
from utils.functions import get_path_to_file, get_texture_size
from utils.game_logging import log
from utils.colors import GREEN, RED, WHITE, BLACK, FOG


PLACEHOLDER_TEXTURE = 'placeholder.png'
NO_TEXTURE = 'no_texture'


def make_texture(width: int, height: int, color: Color) -> Texture:
    """
    Return a :class:`Texture` of a square with the given diameter and color,
    fading out at its edges.

    :param int size: Diameter of the square and dimensions of the square
    Texture returned.
    :param Color color: Color of the square.
    :param int center_alpha: Alpha value of the square at its center.
    :param int outer_alpha: Alpha value of the square at its edges.

    :returns: New :class:`Texture` object.
    """
    img = PIL.Image.new("RGBA", (width, height), color)
    name = "{}:{}:{}:{}".format("texture_rect", width, height, color)
    return Texture(name, img)


class Hierarchical:
    """
    Interface offering hierarchical order of elements, e.g. one element can
    have 'children' and/or 'parent' object. Hierarchy allows user to work
    with an objects and theirs children-objects simultaneously.
    """
    __slots__ = ['_parent', '_children']

    def __init__(self, parent: Optional[Hierarchical | str] = None):
        self._parent = parent
        self._children: Optional[Set] = None

        try:
            parent.add_child(self)
        except AttributeError:
            log(f'UiElement {id(self)} was unable to register its parent of type {type(parent)}')

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

    def __init__(self, can_be_dragged: bool = False,
                 functions: Optional[Union[Callable, Tuple[Callable, ...]]] = None,
                 parent: Optional[Hierarchical | str] = None):
        """
        :param can_be_dragged: bool -- default: False
        :param functions: None or Callable or Tuple[Callable]
        :param parent: Hierarchical object
        """
        Hierarchical.__init__(self, parent)
        self.pointed = False
        self.dragged = False
        self.can_be_dragged = can_be_dragged

        self.functions = {MOUSE_BUTTON_LEFT: [], MOUSE_BUTTON_RIGHT: []}

        if functions is None:
            pass
        elif isinstance(functions, Callable):
            self.functions[MOUSE_BUTTON_LEFT] = [functions, ]
        else:
            self.functions[MOUSE_BUTTON_LEFT] = [f for f in functions]

        self.cursor: Optional['MouseCursor'] = None

    def __repr__(self):
        return f'{self.__class__.__name__} id: {id(self)}'

    def on_mouse_enter(self, cursor: Optional['MouseCursor'] = None):
        if not self.pointed:
            self.pointed = True
            self.cursor = cursor
            self._func_on_mouse_enter(cursor)

    def _func_on_mouse_enter(self, cursor):
        pass

    def on_mouse_exit(self):
        if self.pointed:
            self._func_on_mouse_exit()
            self.pointed = False
            self.cursor = None

    def _func_on_mouse_exit(self):
        pass

    def on_mouse_press(self, button: int):
        log(f'Mouse button {button} clicked on {self}')
        if self.functions[button]:
            self._call_bound_functions(button)
        self.dragged = self.can_be_dragged
        if self.can_be_dragged:
            self.cursor.dragged_ui_element = self

    def _call_bound_functions(self, button: int):
        for function in self.functions[button]:
            function()

    def bind_function(self, function: Callable, button: int = MOUSE_BUTTON_LEFT):
        self.functions[button].append(function)

    def unbind_function(self, function=None):
        for functions in (f for f in self.functions.values() if function in f):
            functions.remove(function)

    def on_mouse_release(self, button: int):
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

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        self._visible = value

    def toggle(self, state: bool):
        self._active = self._visible = state

    def activate(self):
        self._active = True

    def deactivate(self):
        self._active = False

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False


class Selectable:
    """
    Selectable works with SelectableGroup class and should be grouped with other Selectable instances inside the group.
    When one Selectable is toggled as 'selected', the rest of the group members are automatically unselected.
    """

    def __init__(self, selectable_group: Optional[SelectableGroup] = None):
        self.selectable_group = selectable_group
        self.selected = False
        if selectable_group is not None:
            selectable_group.bind_selectable(self)
            self.functions[MOUSE_BUTTON_LEFT].append(self.toggle_selection)

    def toggle_selection(self):
        self.select() if not self.selected else self.unselect()

    def select(self):
        self.selected = True
        self.selectable_group.unselect_all_except_selected(self)

    def unselect(self):
        self.selected = False


class SelectableGroup:
    """
    This class maintains Selectable elements, which are UiElements having 'selected' and 'selectable_group' attributes.
    When one Selectable is toggled as 'selected', the rest of the group members are automatically unselected by this
    class.
    """
    __slots__ = ['selectable_elements']

    def __init__(self):
        self.selectable_elements: List[Selectable] = []

    @property
    def currently_selected(self) -> Optional[Selectable]:
        for element in (s for s in self.selectable_elements if s.selected):
            return element

    def bind_selectable(self, selectable: Selectable):
        self.selectable_elements.append(selectable)
        selectable.selectable_group = self

    def unselect_all_except_selected(self, excepted: Selectable):
        for element in (e for e in self.selectable_elements if e is not excepted):
            element.unselect()


class UiElement(Sprite, ToggledElement, CursorInteractive, Selectable):
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
    sound_on_mouse_enter = 'cursor_over_ui_element.wav'
    sound_on_mouse_click = 'click_on_ui_element.wav'
    game = None

    def __init__(self, texture_name: str, x: int, y: int,
                 name: Optional[str] = None, active: bool = True,
                 visible: bool = True, parent: Optional[Hierarchical | str] = None,
                 functions: Optional[Union[Callable, Tuple[Callable]]] = None,
                 can_be_dragged: bool = False, subgroup: Optional[int] = None,
                 selectable_group: Optional[SelectableGroup] = None,
                 scale: float = 1.0,
                 hint: Optional[Hint] = None):

        full_texture_name = get_path_to_file(texture_name)

        super().__init__(full_texture_name, scale=scale, center_x=x, center_y=y)
        ToggledElement.__init__(self, active, visible)
        CursorInteractive.__init__(self, can_be_dragged, functions=functions, parent=parent)
        Selectable.__init__(self, selectable_group=selectable_group)
        self.name = name
        self._bundle = None
        self.hint = hint
        self.subgroup = subgroup
        self.ui_spritelist = None

    @property
    def bundle(self):
        return self._bundle

    @bundle.setter
    def bundle(self, bundle: UiElementsBundle):
        self._bundle = bundle
        if isinstance(self.parent, str) and (parent := bundle.find_by_name(self.parent)) is not None:
            self.parent = parent

    def add_hint(self, hint: Hint) -> UiElement:
        self.hint = hint
        return self

    def remove_hint(self) -> UiElement:
        self.hint = None
        return self

    def this_or_child(self, cursor) -> UiElement:
        """
        If UiElement has children UiElements, first iterate through them, to
        check if any child is pointed by cursor instead, otherwise, this
        UiElement is pointed.
        """
        if self.children is not None:
            for child in self.children:
                if check_for_collision(cursor, child):
                    return child
        return self

    def update_position(self, dx, dy):
        self.center_x += dx
        self.center_y += dy

    def on_mouse_press(self, button: int):
        super().on_mouse_press(button)
        if (sound := self.sound_on_mouse_click) is not None and self._active:
            self.cursor.window.sound_player.play_sound(sound)

    def on_mouse_enter(self, cursor: Optional['MouseCursor'] = None):
        super().on_mouse_enter(cursor)
        if self.hint is not None:
            self.hint.set_position(self.left - self.hint.width // 2, self.center_y)
            self.hint.show()
        if (sound := self.sound_on_mouse_enter) is not None and self._active:
            cursor.window.sound_player.play_sound(sound)

    def on_mouse_exit(self):
        super().on_mouse_exit()
        if self.hint is not None and self.hint.active:
            self.hint.hide()

    def _func_on_mouse_enter(self, cursor):
        if self._active:
            self.set_texture(-1)

    def _func_on_mouse_exit(self):
        if self._active:
            self.set_texture(0)

    def draw(self):
        if self._active and (self.pointed or self.selected):
            self.draw_highlight_around_element()

        super().draw()

        if self.hint is not None and self.hint.should_show:
            self.hint.draw()

    def draw_highlight_around_element(self):
        color = RED if 'exit' in self.textures[-1].name else GREEN
        draw_rectangle_outline(*self.position, self.width + 4, self.height + 4, color, 2)

    def deactivate(self):
        self._func_on_mouse_exit()
        super().deactivate()


class Background(UiElement):
    """Use this to put a static background wherever You need it."""

    def __init__(self, texture_name: str, x: int, y: int, name: str = None):
        super().__init__(texture_name, x, y, name, active=False)


class Frame(UiElement):
    sound_on_mouse_enter = None
    sound_on_mouse_click = None

    def __init__(self,
                 texture_name: str,
                 x: int,
                 y: int,
                 width: int,
                 height: int,
                 name: Optional[str] = None,
                 color: Optional[Color] = None,
                 active: bool = True,
                 visible: bool = True,
                 parent: Optional[Hierarchical] = None,
                 subgroup: Optional[int] = None,
                 hint: Optional[Hint] = None
                 ):
        super().__init__(texture_name, x, y, name, active, visible, parent,
                         subgroup=subgroup, hint=hint)
        if not texture_name:
            self.textures = [make_texture(width, height, color or WHITE)]
            self.set_texture(0)

    def draw_highlight_around_element(self):
        pass


class Button(UiElement):

    def __init__(self, texture_name: str,
                 x: int,
                 y: int,
                 name: Optional[str] = None,
                 active: bool = True,
                 visible: bool = True,
                 parent: Optional[Hierarchical | str] = None,
                 functions: Optional[Union[Callable, Tuple[Callable]]] = None,
                 subgroup: Optional[int] = None,
                 selectable_group: Optional[SelectableGroup] = None,
                 color: Optional[Color] = None,
                 scale: float = 1.0,
                 hint: Optional[Hint] = None):
        super().__init__(NO_TEXTURE, x, y, name, active, visible, parent, functions, subgroup=subgroup,
                         selectable_group=selectable_group, scale=scale, hint=hint)
        # we load 2 textures for button: normal and for 'highlighted' button:
        full_texture_name = get_path_to_file(texture_name) or get_path_to_file('placeholder_icon.png')
        image = PIL.Image.open(full_texture_name)
        width, height = image.size[0] // 2, image.size[1]
        self.textures = [
            load_texture(full_texture_name, 0, 0, width, height),
            load_texture(full_texture_name, width, 0, width, height)
        ]
        self.set_texture(0)
        self.button_color = color

    def draw(self):
        super().draw()
        if self.button_color is not None:
            width, height = self.width * 0.8, self.height * 0.8
            draw_rectangle_filled(*self.position, width, height, self.button_color)
        if not self._active:
            draw_rectangle_filled(*self.position, self.width, self.height, FOG)


class ProgressButton(Button):
    """
    This button displays the progress of some process it is attached to. Updating
    and tracking of this progress is up to user.
    """

    def __init__(self, texture_name: str,
                 x: int,
                 y: int,
                 name: Optional[str] = None,
                 active: bool = True,
                 visible: bool = True,
                 parent: Optional[Hierarchical] = None,
                 functions: Optional[Union[Callable, Tuple[Callable]]] = None,
                 subgroup: Optional[int] = None,
                 selectable_group: Optional[SelectableGroup] = None,
                 color: Optional[Color] = None,
                 counter: Optional[int] = None,
                 hint: Optional[Hint] = None):
        super().__init__(texture_name, x, y, name, active, visible, parent, functions, subgroup, selectable_group, color, hint=hint)
        self._counter = counter
        self._progress = 0

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = clamp(value, 100, 0)

    @property
    def counter(self):
        return self._counter

    @counter.setter
    def counter(self, value: int):
        self._counter = value

    def draw(self):
        super().draw()
        if self._progress:
            top = self.bottom + (self.height * 0.01) * self._progress
            color = rgb_to_rgba(GREEN, alpha=150)
            draw_lrtb_rectangle_filled(self.left, self.right, top, self.bottom, color)
        if self._counter:
            draw_text(str(self._counter), self.left + 5, self.top - 20, RED, 15)


class GenericTextButton(Button):

    def __init__(self, texture_name: str, x: int, y: int, name: str, functions,
                 subgroup, selectable_group: Optional[SelectableGroup] = None):
        super().__init__(texture_name, x, y, name, functions=functions, subgroup=subgroup,
                         selectable_group=selectable_group)

    def draw(self):
        super().draw()
        x, y = self.position
        draw_text(self.name, x, y, BLACK, 15, anchor_x='center', anchor_y='center')


class Tab(Button):
    """
    Tab is a subclass of Button which can be grouped with other Tabs to work
    unison. When one tab is activated, all other, connected Tabs are
    deactivated and vice versa. When used simultaneously with subgroups,
    Tab can be easily used to switch between 'pages' or 'tabs' of menus and
    submenus.
    """

    def __init__(self, texture_name: str, x: int, y: int,
                 name: Optional[str] = None, active: bool = True,
                 visible: bool = True, parent: Optional[Hierarchical] = None,
                 functions: Optional[Union[Callable, Tuple[Callable]]] = None,
                 subgroup: Optional[int] = None,
                 other_tabs: Tuple[Tab, ...] = (),
                 hint: Optional[Hint] = None):
        super().__init__(texture_name, x, y, name, active, visible, parent,
                         functions, subgroup, hint=hint)
        self.other_tabs = [tab for tab in other_tabs]
        for tab in other_tabs:
            if self not in tab.other_tabs:
                tab.other_tabs.append(self)

    def switch_to(self):
        self.bundle.switch_to_subgroup(self.subgroup)
        self.deactivate()

    def _call_bound_functions(self, button: int):
        super()._call_bound_functions(button)
        self.deactivate()

    def activate(self):
        super().activate()
        for tab in (t for t in self.other_tabs if t.active):
            tab.active = False

    def deactivate(self):
        super().deactivate()
        for tab in (t for t in self.other_tabs if not t.active):
            tab.active = True


class Checkbox(UiElement):
    """
    Checkbox is a UiElement which functions is to allow user toggling the
    boolean value of some variable - if Checkbox is 'ticked' the value is
    set to True, else it is considered False.
    """

    def __init__(self, texture_name: str, x: int, y: int, text: str,
                 font_size: int = 10, text_color: Color = WHITE,
                 name: Optional[str] = None, active: bool = True,
                 visible: bool = True, parent: Optional[Hierarchical] = None,
                 functions: Optional[Callable] = None,
                 ticked: bool = False, variable: Tuple[object, str] = None,
                 subgroup: Optional[int] = None,
                 selectable_group: Optional[SelectableGroup] = None,
                 hint: Optional[Hint] = None):
        """

        :param texture_name:
        :param x:
        :param y:
        :param name:
        :param active:
        :param visible:
        :param parent:
        :param functions:
        :param ticked:
        :param variable: Tuple[object, str] -- to bind a variable to this
        Checkbox you must pass a tuple which first element is an reference
        to the python object and second is a string name of this object
        attribute, e.g. (self, 'name_of_my_attribute').
        """
        super().__init__(texture_name, x, y, name, active, visible,
                         parent, functions, subgroup=subgroup,
                         selectable_group=selectable_group, hint=hint)
        self.ticked = ticked
        self.variable = variable
        full_texture_name = get_path_to_file(texture_name)
        self.textures = [
            load_texture(full_texture_name, 0, 0, 30, 30),
            load_texture(full_texture_name, 30, 0, 30, 30)
        ]
        self.set_texture(int(self.ticked))
        self.text = text
        self.font_size = font_size
        self.text_color = text_color
        self.text_label = UiTextLabel(
            x - int(len(text) * font_size * 0.45), y, text, font_size,
            text_color
        )

    def _func_on_mouse_enter(self, cursor):
        pass

    def _func_on_mouse_exit(self):
        pass

    def update_from_variable(self):
        self.ticked = getattr(self.variable[0], self.variable[1])
        self.set_texture(int(self.ticked))

    def on_mouse_press(self, button: int):
        super().on_mouse_press(button)
        self.ticked = not self.ticked
        self.set_texture(int(self.ticked))
        if self.variable is not None:
            self.toggle_variable()

    def toggle_variable(self):
        log(f'Changing {self.variable[0]}{self.variable[1]} to {self.ticked}')
        setattr(self.variable[0], self.variable[1], self.ticked)

    def draw(self):
        # self.text_label.draw()
        self.draw_text()
        super().draw()

    def draw_text(self):
        x = self.left - PADDING_X
        y = self.center_y
        draw_text(self.text, x, y, self.text_color, self.font_size, anchor_x='right', anchor_y='center')


class UiTextLabel(UiElement):
    sound_on_mouse_enter = None
    sound_on_mouse_click = None

    def __init__(self, x: int, y: int, text: str, font_size: int = 10, text_color: Color = WHITE,
                 name: Optional[str] = None, active: bool = False, align_x: str = 'center', align_y: str = 'center',
                 visible: bool = True, parent: Optional[Hierarchical] = None, subgroup: Optional[int] = None,
                 hint: Optional[Hint] = None):
        super().__init__('', x, y, name, active, visible, parent, subgroup=subgroup, hint=hint)
        self.text = text
        self.size = font_size
        self.text_color = text_color
        self.align_text_x = align_x
        self.align_text_y = align_y
        self.textures = [make_texture(1, 1, (1, 1, 1, 1))]
        self.set_texture(0)

    def draw(self):
        draw_text(
            self.text, *self.position, self.text_color, self.size,
            anchor_x=self.align_text_x, anchor_y=self.align_text_y
        )

    def draw_highlight_around_element(self):
        pass


class ScrollableContainer(UiElement):
    """
    Container organizes other UiElements and allows user to use mouse-scroll to
    navigate among elements changing position of all objects at once.
    """

    def __init__(self, texture_name: str, x: int, y: int,
                 name: Optional[str] = None, active: bool = True,
                 visible: bool = True, parent: Optional[Hierarchical] = None,
                 functions: Optional[Union[Callable, Tuple[Callable]]] = None,
                 can_be_dragged: bool = False, subgroup: Optional[int] = None,
                 max_scroll_x=None, min_scroll_x=None, max_scroll_y=None,
                 min_scroll_y=None):
        super().__init__(texture_name, x, y, name, active, visible, parent,
                         functions, can_be_dragged, subgroup)
        self.max_scroll_x = max_scroll_x or self.right
        self.min_scroll_x = min_scroll_x or self.left
        self.max_scroll_y = max_scroll_y or self.top
        self.min_scroll_y = min_scroll_y or self.bottom
        self.invisible_children = []

    def add_child(self, child: UiElement):
        super().add_child(child)
        self._manage_child_visibility(child)

    def _func_on_mouse_enter(self, cursor):
        super()._func_on_mouse_enter(cursor)
        cursor.pointed_scrollable = self

    def _func_on_mouse_exit(self):
        super()._func_on_mouse_exit()
        self.cursor.pointed_scrollable = None

    def on_mouse_scroll(self, scroll_x: int, scroll_y: int):
        for child in self._children:
            child.center_y -= scroll_y * 15
            self._manage_child_visibility(child)

    def draw(self):
        super().draw()
        draw_rectangle_outline(*self.position, self.width, self.height, WHITE)

    def inside_scrollable_area(self, child) -> bool:
        return self.top > child.top and self.bottom < child.bottom

    def _manage_child_visibility(self, child):
        try:
            child.toggle(self.top > child.top and self.bottom < child.bottom)
        except ValueError:
            child.toggle(False)


class EditorPlaceableObject(Button):
    """
    Used to pick objects from ScenarioEditor panel in the UI in editor mode and
    place them on the map.
    """

    def __init__(self, gameobject_name: str, x: int, y: int, parent, functions=None):
        super().__init__('small_button_none.png', x, y, parent=parent, functions=functions)
        self.gameobject_name = get_path_to_file(gameobject_name)
        width, height = get_texture_size(self.gameobject_name)
        w, h = min(self.width, width), min(self.height, height)
        self.gameobject_texture = load_texture(self.gameobject_name, 0, 0, w, h)

    def draw(self):
        super().draw()
        x, y = self.position
        draw_scaled_texture_rectangle(x, y, self.gameobject_texture)


class ListBox(UiElement):
    ...


class TextInputField(UiElement):
    """
    TextInputField is a keyboard-interactive UiElement, which listen to the
    bound KeyboardHandler instance and stores pressed keys into the internal
    list of characters, to be displayed as string.
    """

    def __init__(self, texture_name: str, x: int, y: int, name: str,
                 keyboard_handler: KeyboardHandler = None):
        super().__init__(texture_name, x, y)
        self.name = name
        self.input_characters = []
        self.keyboard_handler = keyboard_handler

    def set_keyboard_handler(self, handler: KeyboardHandler):
        self.keyboard_handler = handler

    def on_mouse_press(self, button: int):
        self.bind_to_mouse_and_keyboard_handlers()

    def bind_to_mouse_and_keyboard_handlers(self):
        self.cursor.bind_text_input_field(self)
        self.keyboard_handler.bind_keyboard_input_consumer(self)

    def unbind_keyboard_handler(self):
        self.keyboard_handler.unbind_keyboard_input_consumer()

    def receive(self, symbol: int, shift_pressed=False):
        if symbol == BACKSPACE:
            self.erase_last_character()
        elif symbol == ENTER:
            self.on_enter_pressed()
        elif self.not_too_long and (key := chr(symbol)).isascii():
            self.input_characters.append(key.upper() if shift_pressed else key)

    @property
    def not_too_long(self) -> bool:
        return len(self.input_characters) < 26

    def erase_last_character(self):
        try:
            self.input_characters.pop()
        except IndexError:
            pass

    def on_enter_pressed(self):
        for function in self.functions:
            function()

    def _raw_text(self) -> str:
        return ''.join(self.input_characters)

    def get_text(self) -> str:
        return self._raw_text().strip()

    def draw(self):
        super().draw()
        if self.input_characters:
            self.draw_inner_text()

    def draw_inner_text(self):
        x, y = self.position
        c = 'center'
        text = self._raw_text()
        draw_text(text, x, y, WHITE, 15, bold=True, anchor_x=c, anchor_y=c)


class ScrollBar(UiElement):
    sound_on_mouse_enter = None
    sound_on_mouse_click = None
    ...


class Slider(UiElement):
    """
    Slider allows user to manipulate some assigned value by increasing and
    decreasing it with a slide-able handle in predefined range.
    """

    def __init__(self, texture_name: str, x: int, y: int, text: str, size: int,
                 axis: str = HORIZONTAL, variable: Tuple[object, str] = None,
                 min_value=None, max_value=None, step=None, show_value=True,
                 subgroup: Optional[int] = None):
        super().__init__(texture_name, x, y, subgroup=subgroup)
        self.axis = axis
        self.angle = 0 if axis == HORIZONTAL else 90
        self.width = size if axis == HORIZONTAL else self.width
        self.height = size if axis == VERTICAL else self.height

        self.text = text

        self.min_value = min_value
        self.max_value = max_value
        self.step = step
        self.variable = variable
        if variable is not None:
            _object, attribute = variable
            self._value = getattr(_object, attribute)
        else:
            self.value = 0.5

        self.show_value = show_value

        self.handle = _SliderHandle('slider_handle.png', x, y, axis, parent=self)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = self.convert_value(value)
        if self.variable is not None:
            setattr(self.variable[0], self.variable[1], self._value)

    def convert_value(self, value):
        max_value, min_value, step = self.max_value, self.min_value, self.step
        if min_value is not None and max_value is not None:
            value = min_value + (max_value - min_value) * value
            if step is not None:
                value = int((value // step) * step)
        return round(value, 2)

    def update_from_variable(self):
        self.handle.value_to_position(self.value)

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, value: bool):
        self.handle.active = self._active = value

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        self.handle.visible = self._visible = value

    def toggle(self, state: bool):
        self._active = self._visible = state
        self.handle.toggle(state)

    def activate(self):
        self.handle.active = self._active = True

    def deactivate(self):
        self.handle.active = self._active = False

    def show(self):
        self.handle.visible = self._visible = True

    def hide(self):
        self.handle.visible = self._visible = False

    def draw(self):
        super().draw()
        self.handle.draw()
        self.draw_text()
        if self.show_value:
            self.draw_value()

    def draw_text(self):
        x = self.center_x
        y = self.top + PADDING_Y
        draw_text(str(self.text), x, y, WHITE, 20, anchor_x='right', anchor_y='center')

    def draw_value(self):
        x = self.right + PADDING_Y
        draw_text(str(self._value), x, self.center_y, WHITE, 20, anchor_y='center')


class _SliderHandle(UiElement):
    """Used internally by the Slider class."""

    def __init__(self, texture_name: str, x: int, y: int, axis, parent: Slider):
        super().__init__(texture_name, x, y, parent=parent, can_be_dragged=True)
        self.min_x = self.parent.left if axis == HORIZONTAL else self.parent.center_x
        self.max_x = self.parent.right if axis == HORIZONTAL else self.parent.center_x
        self.min_y = self.parent.bottom if axis == VERTICAL else self.parent.center_y
        self.max_y = self.parent.top if axis == VERTICAL else self.parent.center_y
        self.range_x = self.max_x - self.min_x
        self.range_y = self.max_y - self.min_y
        self.value_to_position(self.parent.value)

    def on_mouse_drag(self, x: float = None, y: float = None):
        self.center_x = clamp(x, self.max_x, self.min_x)
        self.center_y = clamp(y, self.max_y, self.min_y)
        self.update_value()

    def update_value(self):
        if self.range_x:
            self.parent.value = (self.center_x - self.min_x) / self.range_x
        else:
            self.parent.value = (self.center_y - self.min_y) / self.range_y
        if self.parent.step:
            self.value_to_position(self.parent.value)

    @singledispatchmethod
    def value_to_position(self, value):
        pass

    @value_to_position.register
    def _(self, value: float):
        if self.range_x:
            self.center_x = self.min_x + self.range_x * value
        else:
            self.center_y = self.min_y + self.range_y * value

    @value_to_position.register
    def _(self, value: int):
        value_range = (self.parent.max_value - self.parent.min_value)
        if self.range_x:
            unit = self.range_x / value_range
            self.center_x = clamp(self.min_x + unit * (value - self.parent.min_value), self.max_x, self.min_x)
        else:
            unit = self.range_y / value_range
            self.center_y = clamp(self.min_y + unit * (value - self.parent.min_value), self.max_y, self.min_y)


class Hint(Sprite, ToggledElement):

    def __init__(self, texture_name: str, align: str='left', delay: float=0):
        super().__init__(get_path_to_file(texture_name), center_x=0, center_y=0)
        ToggledElement.__init__(self, visible=False, active=True)
        self.time_since_triggered = 0
        self.delay = delay
        self.align = align

    def _reset_delay(self):
        self.time_since_triggered = time.time() + self.delay

    @property
    def should_show(self) -> bool:
        return time.time() >= self.time_since_triggered

    def show(self):
        self._reset_delay()
        super().show()

    def draw(self):
        if self._visible:
            super().draw()


class UnitProductionCostsHint(Hint):
    """
    This monit is shown to the player when the player hoovers the mouse over the button in construction panel, and
    displays the cost of the construction.
    """

    def __init__(self, local_human_player: Player, production_costs: Dict[str, int], delay: float = 0):
        super().__init__('unit_production_hint.png', delay=delay)
        self.local_human_player = local_human_player
        self.production_costs = production_costs
        self.label_height = self.height / len(production_costs)
        self.labels = []

    def show(self):
        for i, (resource, cost) in enumerate(self.production_costs.items()):
            color = GREEN if self.local_human_player.has_resource(resource, cost) else RED
            self.labels.append(
                (str(cost), self.center_x, self.top - (i + 0.5) * self.label_height, color, 15)
            )
        super().show()

    def hide(self):
        self.labels.clear()
        super().hide()

    def draw(self):
        super().draw()
        for label in self.labels:
            draw_text(*label, anchor_x='left', anchor_y='center')


@dataclass
class UiElementsBundle(Observed):
    """
    A bundle of UiElement objects kept together to easy switch between Menu
    submenus and dynamically change UI content.

    Initialize with params:\n
    index: int \n
    name: str \n
    elements: Optional[List[UiElement]]
    """
    name: str
    elements: List[UiElement]
    register_to: Observer
    owner = None
    _on_load: Optional[Callable] = None
    _on_unload: Optional[Callable] = None
    ui_bundles_handler: Optional[UiBundlesHandler] = None
    displayed: bool = True
    observed_attributes = defaultdict(list)

    def __post_init__(self):
        self.attach(observer=self.register_to)
        self.bind_elements_to_bundle(self.elements)

    def bind_elements_to_bundle(self, elements):
        for element in elements:
            element.bundle = self

    def extend(self, elements):
        for element in elements:
            self.append(element)

    def append(self, element: UiElement):
        self.elements.append(element)
        element.bundle = self
        if self.ui_bundles_handler is not None:
            self.ui_bundles_handler.append(element)

    def remove(self, name: str):
        if (element := self.find_by_name(name)) is not None:
            self._remove(element)
            element.bundle = None
            if self.ui_bundles_handler is not None:
                self.ui_bundles_handler.remove(element)

    def __iter__(self):
        return self.elements.__iter__()

    def get_elements(self) -> List[UiElement]:
        # elements = []
        # for element in self.elements:
        #     elements.append(element)
            # if (children := element.children) is not None:
            #     elements.extend(children)
        return self.elements

    def toggle_element(self, name: str, state: bool):
        if (element := self.find_by_name(name)) is not None:
            element.toggle(state)

    def show_element(self, name: str):
        if (element := self.find_by_name(name)) is not None:
            element.show()

    def hide_element(self, name: str):
        if (element := self.find_by_name(name)) is not None:
            element.hide()

    def activate_element(self, name: str):
        if (element := self.find_by_name(name)) is not None:
            element.activate()

    def deactivate_element(self, name: str):
        if (element := self.find_by_name(name)) is not None:
            element.deactivate()

    def remove_subgroup(self, subgroup: int):
        for element in self.elements[::]:
            if element.subgroup == subgroup:
                element.hide()
                element.deactivate()
                self.elements.remove(element)

    def switch_to_subgroup(self, subgroup: int):
        for element in self.elements:
            if element.subgroup in (None, subgroup):
                element.show()
                element.activate()
            else:
                element.hide()
                element.deactivate()

    def find_by_name(self, name: str) -> Optional[UiElement]:
        for element in (e for e in self.elements if e.name == name):
            return element

    def get_elements_of_type(self, class_name: Type[UiElement]) -> List:
        return [e for e in self.elements if isinstance(e, class_name)]

    def _remove(self, element: UiElement):
        self.elements.remove(element)
        element._bundle = None

    def update_elements_positions(self, dx, dy):
        for element in self.elements:
            element.update_position(dx, dy)

    def on_load(self):
        self.displayed = True
        if self._on_load is not None:
            self._on_load()

    def on_unload(self):
        self.displayed = False
        self.ui_bundles_handler = None
        if self._on_unload is not None:
            self._on_unload()

    def clear(self):
        self.elements.clear()


class UiBundlesHandler(Observer):
    """
    The UiBundlesHandler class is responsible for managing and displaying different groups of UI elements, such as
    buttons and checkboxes.

    It keeps track of currently loaded and displayed UiElements, allowing for dynamic composition of the screen.

    The class has a list of UiElementsBundle objects, which are groups of UI elements that can be loaded and displayed
    together.

    The UiSpriteList class is used as a wrapper for spritelists containing UiElements, allowing for quick identification
    of the spritelists that should be collided with the MouseCursor.

    The class has a set of active_bundles, which is used to quickly check if a bundle is displayed or not.

    The class has a dictionary of selectable_groups, which allows for grouping together a bunch of same-context UI
    elements and providing a convenient way to communicate between them.

    The class has methods for loading and unloading UiElementsBundle objects, as well as switching between them.

    The class has methods for appending and removing UiElement and UiElementsBundle objects from the UiSpriteList.

    The class has a method for updating the positions of UI elements that are not currently displayed.

    The class implements the Observer pattern, with methods for being attached, notified, and detached.

    The main methods of the class include set_keyboard_handler, open_confirmation_dialog, switch_to_bundle, load_bundle,
     unload_bundle, and update_not_displayed_bundles_positions.

    The main fields of the class include ui_elements_bundles, ui_elements_spritelist, active_bundles, and
    selectable_groups.
    """

    def __init__(self, use_spatial_hash=False):
        """
        To add UiElementsBundle to this handler you need only to initialize
        this bundle inside the class inheriting from the handler, and it
        will automatically add itself to the list of bundles, and it's all
        elements will .
        """
        Observer.__init__(self)
        # all bundles available to load and display:
        self.ui_elements_bundles: Dict[str, UiElementsBundle] = {}
        # currently displayed UiElements of the chosen bundle/s:
        self.ui_elements_spritelist = UiSpriteList(use_spatial_hash)
        # set used to quickly check if a bundle is displayed or not:
        self.active_bundles: Set[str] = set()
        # is_controlled_by_player groups allow to group together a bunch of same-context
        # UiElements and provide a convenient way to communicate between them:
        self.selectable_groups: Dict[str, SelectableGroup] = {}

    def set_keyboard_handler(self, handler: KeyboardHandler):
        for bundle in self.ui_elements_bundles.values():
            for element in bundle.elements:
                if isinstance(element, TextInputField):
                    element.set_keyboard_handler(handler)

    def open_confirmation_dialog(self,
                                 position: Tuple,
                                 after_switch_to_bundle: str,
                                 function_if_yes: Callable):
        x, y = position
        close_dialog = partial(self.close_confirmation_dialog, after_switch_to_bundle)
        self.switch_to_bundle(UiElementsBundle(
            name=CONFIRMATION_DIALOG,
            elements=[
                UiTextLabel(x, y * 1.5, 'Are you sure?', 30),
                Button('menu_button_confirm.png', x // 2, y,
                       functions=(function_if_yes, close_dialog)),
                Button('menu_button_cancel.png', x * 1.5, y,
                       functions=(close_dialog, ))
            ],
            register_to=self
        ))

    def close_confirmation_dialog(self, after_switch_to_bundle: str):
        self.switch_to_bundle(after_switch_to_bundle)
        self.remove(self.ui_elements_bundles[CONFIRMATION_DIALOG])

    def on_being_attached(self, attached: Observed):
        self.append(attached)

    def notify(self, attribute: str, value: Any):
        pass

    def on_being_detached(self, detached: Observed):
        self.remove(detached)

    def switch_to_bundle(self, bundle: Union[str, UiElementsBundle], exceptions: Union[Tuple[str], None] = None):
        if isinstance(bundle, UiElementsBundle):
            self._switch_to_bundle(bundle, exceptions)
        else:
            try:
                self._switch_to_bundle(self.ui_elements_bundles[bundle], exceptions)
            except KeyError:
                raise KeyError(bundle)

    def _switch_to_bundle(self, bundle: UiElementsBundle, exceptions: Optional[Tuple[str, ...]] = None):
        log(f'Switched to submenu {bundle.name}')
        self._unload_all(exceptions)
        self._load_bundle(bundle)

    def bind_ui_elements_with_ui_spritelist(self, elements):
        for ui_element in elements:
            ui_element.ui_spritelist = self.ui_elements_spritelist

    def load_bundle(self,
                    name: Optional[str] = None,
                    index: Optional[int] = None,
                    clear: bool = False):
        """
        Only add UiElementsBundle elements to the current list, without
        removing anything from it.
        TODO: change this method to three methods using singledispatch
        """
        if name is not None:
            bundle = self.ui_elements_bundles.get(name, None)
        elif index is not None:
            bundle = self.get_bundle_of_index(index)
        else:
            return
        if bundle is not None:
            self._load_bundle(bundle, clear)

    def unload_bundle(self,
                      name: Optional[str] = None,
                      index: Optional[int] = None):
        bundle = self.ui_elements_bundles.get(name, None) or self.get_bundle_of_index(index)
        if bundle is not None:
            self._unload_bundle(bundle)

    def __getitem__(self, name: Union[str, int]) -> Optional[UiElementsBundle]:
        return self.ui_elements_bundles.get(name, self.get_bundle_of_index(name))

    def get_bundle(self, name: str) -> UiElementsBundle:
        try:
            return self.ui_elements_bundles[name]
        except KeyError:
            raise KeyError(f'UiElementsBundle: {name} not found!')

    def get_bundle_of_index(self, index: int) -> Optional[UiElementsBundle]:
        try:
            return next(b for b in self.ui_elements_bundles.values() if b.index == index)
        except StopIteration:
            return

    def _load_bundle(self, bundle: UiElementsBundle, clear: bool = False):
        log(f'Loading Ui_Elemnts_Bundle: {bundle.name}')
        if clear:
            bundle.elements.clear()
        bundle.on_load()
        bundle.ui_bundles_handler = self
        self.active_bundles.add(bundle.name)
        self.ui_elements_spritelist.extend(bundle.elements)
        self.bind_ui_elements_with_ui_spritelist(bundle.elements)

    @singledispatchmethod
    def append(self, element):
        raise TypeError('Bad argument. Accepted: UiELement, UiElementsBundle')

    @append.register
    def _(self, element: UiElement):
        self.ui_elements_spritelist.append(element)

    @append.register
    def _(self, element: UiElementsBundle):
        self.ui_elements_bundles[element.name] = element
        self.ui_elements_spritelist.extend(element.elements)
        self.bind_ui_elements_with_ui_spritelist(element.elements)

    def _unload_bundle(self, bundle: UiElementsBundle):
        self.active_bundles.discard(bundle.name)
        for element in (e for e in self.ui_elements_spritelist if e.bundle == bundle):
            self.remove(element)
        bundle.ui_bundles_handler = None
        bundle.on_unload()
        print(f'Bundle {bundle.name} unloaded!')

    @singledispatchmethod
    def remove(self, element):
        raise TypeError('Bad argument. Accepted: UiElement, UiElementsBundle')

    @remove.register
    def _(self, element: UiElement):
        self.ui_elements_spritelist.remove(element)

    @remove.register
    def _(self, element: UiElementsBundle):
        self._unload_bundle(element)
        del self.ui_elements_bundles[element.name]

    def _unload_all(self, exceptions: Optional[Tuple[str]] = None):
        for bundle in self.ui_elements_bundles.values():
            bundle.on_unload()
        self.active_bundles.clear()
        self.ui_elements_spritelist.clear()
        if exceptions is not None:
            self._reload_exceptions_bundles(exceptions)

    def _reload_exceptions_bundles(self, exceptions: Tuple[str]):
        for exception in exceptions:
            self.load_bundle(exception)

    def update_not_displayed_bundles_positions(self, dx, dy):
        for bundle in self.ui_elements_bundles.values():
            if bundle.name not in self.active_bundles:
                bundle.update_elements_positions(dx, dy)

    def update_ui_elements_from_variables(self):
        for bundle in self.ui_elements_bundles.values():
            for element in bundle:
                if hasattr(element, 'variable') and element.variable is not None:
                    element.update_from_variable()


# To avoid circular imports
if __name__ == '__main__':
    from controllers.keyboard import KeyboardHandler
    from players_and_factions.player import Player