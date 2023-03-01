#!/usr/bin/env python
from __future__ import annotations

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
from utils.classes import Observed, Observer
from utils.geometry import clamp
from utils.colors import rgb_to_rgba
from utils.improved_spritelists import UiSpriteList

from utils.functions import (
    get_path_to_file, name_to_texture_name, get_texture_size
)
from utils.game_logging import log

from utils.colors import GREEN, RED, WHITE, BLACK, FOG


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
                 parent: Optional[Hierarchical] = None):
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

    def unselect_all_except_selected(self, selected: Selectable):
        for element in (e for e in self.selectable_elements if e is not selected):
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

    def __init__(self, texture_name: str, x: int, y: int,
                 name: Optional[str] = None, active: bool = True,
                 visible: bool = True, parent: Optional[Hierarchical] = None,
                 functions: Optional[Union[Callable, Tuple[Callable]]] = None,
                 can_be_dragged: bool = False, subgroup: Optional[int] = None,
                 selectable_group: Optional[SelectableGroup] = None):
        full_texture_name = get_path_to_file(name_to_texture_name(texture_name))
        super().__init__(full_texture_name, center_x=x, center_y=y)
        ToggledElement.__init__(self, active, visible)
        CursorInteractive.__init__(self, can_be_dragged, functions, parent=parent)
        Selectable.__init__(self, selectable_group=selectable_group)
        self.name = name
        self._bundle = None
        self.subgroup = subgroup
        self.ui_spritelist = None

    @property
    def bundle(self):
        return self._bundle

    @bundle.setter
    def bundle(self, bundle: UiElementsBundle):
        self._bundle = bundle

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
        if self._active and (self.pointed or self.selected):
            self.draw_highlight_around_element()

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
                 subgroup: Optional[int] = None
                 ):
        super().__init__(texture_name, x, y, name, active, visible, parent,
                         subgroup=subgroup)
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
                 parent: Optional[Hierarchical] = None,
                 functions: Optional[Union[Callable, Tuple[Callable]]] = None,
                 subgroup: Optional[int] = None,
                 selectable_group: Optional[SelectableGroup] = None,
                 color: Optional[Color] = None):
        super().__init__('', x, y, name, active, visible, parent,
                         functions, subgroup=subgroup,
                         selectable_group=selectable_group)
        # we load 2 textures for button: normal and for 'highlighted' button:
        full_texture_name = get_path_to_file(texture_name)
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
    This button displays a progress of some process it is attached to. Updating
    and tracking of this progress is up to user.
    """
    _progress = 0
    _counter = 0

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
                 other_tabs: Tuple[Tab, ...] = ()):
        super().__init__(texture_name, x, y, name, active, visible, parent,
                         functions, subgroup)
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
                 selectable_group: Optional[SelectableGroup] = None):
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
                         selectable_group=selectable_group)
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
    Used to pick objects from ScenarioEditor panel in the UI in ditor mode and
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


class _SliderHandle(UiElement):
    """Used internally by the Slider class."""

    def __init__(self, texture_name: str, x: int, y: int, axis, parent):
        super().__init__(texture_name, x, y, parent=parent, can_be_dragged=True)
        self.min_x = self.parent.left if axis == HORIZONTAL else self.parent.center_x
        self.max_x = self.parent.right if axis == HORIZONTAL else self.parent.center_x
        self.min_y = self.parent.bottom if axis == VERTICAL else self.parent.center_y
        self.max_y = self.parent.top if axis == VERTICAL else self.parent.center_y
        self.range_x = self.max_x - self.min_x
        self.range_y = self.max_y - self.min_y

    def on_mouse_drag(self, x: float = None, y: float = None):
        self.center_x = clamp(x, self.max_x, self.min_x)
        self.center_y = clamp(y, self.max_y, self.min_y)
        self.update_value()

    def update_value(self):
        if self.range_x:
            self.parent.value = (self.center_x - self.min_x) / self.range_x
        else:
            self.parent.value = (self.center_y - self.min_y) / self.range_y

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
            self.center_x = self.min_x + unit * value
        else:
            unit = self.range_y / value_range
            self.center_y = self.min_y + unit * value


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
            self._value = getattr(variable[0], variable[1])
        else:
            self.value = 0.5

        self.show_value = show_value

        self.handle = _SliderHandle('slider_handle.png', x, y, axis, self)
        self.handle.value_to_position(self._value)

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
        return value

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


def ask_player_for_confirmation(position: Tuple, after_switch_to_bundle: str):
    """
    Use this function to decorate method you want, to be preceded by display of
    simple confirm-or-cancel dialog for the player. The dialog would be shown
    first, and after player clicks 'confirm' decorated method would be called.
    If player clicks 'cancel', method would be ignored and a UiElementsBundle
    of name provided in after_switch_to_bundle param is loaded.\n
    To IGNORE this prompt, pass special argument ignore_confirmation=True to
    the called decorated method - it will be digested by the internal wrapper,
    and will cause aborting of the dialog procedure, and decorated method is
    going to be executed instead.

    :param position: Tuple[x, y] -- position on which dialog will be centered
    :param after_switch_to_bundle: str -- name of the UiElementsBundle to be
    displayed after player makes choice.
    :return: Callable
    """
    def decorator(function):
        def wrapper(self, ignore_confirmation=False):
            if ignore_confirmation:
                return function(self)
            function_on_yes = partial(function, self)
            return self.menu_view.open_confirmation_dialog(
                position, after_switch_to_bundle, function_on_yes
            )
        return wrapper
    return decorator


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
    displayed_in_manager: Optional[UiBundlesHandler] = None
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
            self.add(element)

    def add(self, element: UiElement):
        self.elements.append(element)
        element.bundle = self
        if self.displayed_in_manager is not None:
            self.displayed_in_manager.append(element)

    def remove(self, name: str):
        if (element := self.find_by_name(name)) is not None:
            self._remove(element)
            element.bundle = None
            if self.displayed_in_manager is not None:
                self.displayed_in_manager.remove(element)

    def __iter__(self):
        return self.elements.__iter__()

    def get_elements(self) -> List[UiElement]:
        elements = []
        for element in self.elements:
            elements.append(element)
            # if (children := element.children) is not None:
            #     elements.extend(children)
        return elements

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
        if self._on_unload is not None:
            self._on_unload()


class UiBundlesHandler(Observer):
    """
    This class keeps track of currently is_loaded and displayed UiElements,
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
        Observer.__init__(self)
        # all bundles available to load and display:
        self.ui_elements_bundles: Dict[str, UiElementsBundle] = {}
        # currently displayed UiElements of the chosen bundle/s:
        self.ui_elements_spritelist = UiSpriteList(use_spatial_hash)
        # set used to quickly check if a bundle is displayed or not:
        self.active_bundles: Set[str] = set()
        # selectable groups allow to group together a bunch of same-context
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
        self.switch_to_bundle_of_name(name=after_switch_to_bundle)
        self.remove(self.ui_elements_bundles[CONFIRMATION_DIALOG])

    def on_being_attached(self, attached: Observed):
        self.append(attached)

    def notify(self, attribute: str, value: Any):
        pass

    def on_being_detached(self, detached: Observed):
        self.remove(detached)

    def switch_to_bundle(self,
                         bundle: UiElementsBundle = None,
                         name: str = None):
        if bundle is not None:
            return self._switch_to_bundle(bundle)
        elif name in self.ui_elements_bundles:
            return self._switch_to_bundle(self.ui_elements_bundles[name])

    def switch_to_bundle_of_name(self, name: str):
        if name in self.ui_elements_bundles:
            self._switch_to_bundle(self.ui_elements_bundles[name])

    def _switch_to_bundle(self, bundle: UiElementsBundle):
        log(f'Switched to submenu {bundle.name}')
        self._unload_all()
        self._load_bundle(bundle)
        self.active_bundles.add(bundle.name)

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
        log(f'LOADING BUNDLE: {bundle.name}')
        if clear:
            bundle.elements.clear()
        bundle.on_load()
        bundle.displayed_in_manager = self
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
        for element in self.ui_elements_spritelist[::-1]:
            if element.bundle == bundle:
                bundle.displayed_in_manager = None
                self.remove(element)
        bundle.on_unload()

    @singledispatchmethod
    def remove(self, element):
        raise TypeError('Bad argument. Accepted: UiELement, UiElementsBundle')

    @remove.register
    def _(self, element: UiElement):
        self.ui_elements_spritelist.remove(element)

    @remove.register
    def _(self, element: UiElementsBundle):
        self._unload_bundle(element)
        del self.ui_elements_bundles[element.name]

    def _unload_all(self,
                    exception: Optional[str] = None,
                    exceptions: Optional[List[str]] = None):
        for bundle in self.ui_elements_bundles.values():
            bundle.on_unload()
        self.active_bundles.clear()
        self.ui_elements_spritelist.clear()
        self._reload_exceptions_bundles(exception, exceptions)

    def _reload_exceptions_bundles(self, exception, exceptions):
        if exception is not None:
            self.load_bundle(name=exception)
        elif exceptions is not None:
            for exception in exceptions:
                self.load_bundle(exception)

    def update_not_displayed_bundles_positions(self, dx, dy):
        for bundle in self.ui_elements_bundles.values():
            if bundle.name not in self.active_bundles:
                bundle.update_elements_positions(dx, dy)


# To avoid circular imports
from controllers.keyboard import KeyboardHandler
