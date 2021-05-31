#!/usr/bin/env python
from __future__ import annotations

import PIL

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Set, Tuple, Union, Type

from arcade import (
    Sprite, SpriteList, load_texture, draw_rectangle_outline, draw_text,
    draw_rectangle_filled
)
from arcade.arcade_types import Color

from utils.ownership_relations import ObjectsOwner, OwnedObject

from utils.functions import log, make_texture, get_path_to_file, to_texture_name

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

    def on_update(self, delta_time: float = 1/60):
        # noinspection PyUnresolvedReferences
        for ui_element in (u for u in self if u.active):
            ui_element.on_update()


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
            if element.subgroup in (None, subgroup):
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

    def get_elements_of_type(self, class_name: Type[UiElement]) -> List:
        return [e for e in self.elements if isinstance(e, class_name)]

    def _remove(self, element: UiElement):
        self.elements.remove(element)
        element.bundle = None

    def update_elements_positions(self, dx, dy):
        for element in self.elements:
            element.center_x -= dx
            element.center_y -= dy


class UiBundlesHandler(ObjectsOwner):
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
        ObjectsOwner.__init__(self)
        # all bundles available to load and display:
        self.ui_elements_bundles: Dict[str, UiElementsBundle] = {}
        # currently displayed UiElements of the chosen bundle/s:
        self.ui_elements_spritelist = UiSpriteList(use_spatial_hash)
        # set used to quickly check if a bundle is displayed or not:
        self.active_bundles: Set[int] = set()

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
        self.active_bundles.add(bundle.index)

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
        self.active_bundles.add(bundle.index)
        self.ui_elements_spritelist.extend(bundle.elements)
        self.bind_ui_elements_with_ui_spritelist(bundle.elements)

    def _unload_bundle(self, bundle: UiElementsBundle):
        self.active_bundles.discard(bundle.index)
        for element in self.ui_elements_spritelist[::-1]:
            if element.bundle == bundle:
                self.ui_elements_spritelist.remove(element)

    def _unload_all(self, exception: Optional[str] = None):
        self.active_bundles.clear()
        self.ui_elements_spritelist.clear()
        if exception is not None:
            self.load_bundle(name=exception)

    def update_not_displayed_bundles_positions(self, dx, dy):
        for bundle in self.ui_elements_bundles.values():
            if bundle.index not in self.active_bundles:
                bundle.update_elements_positions(dx, dy)


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

        if functions is None:
            self.functions = []
        elif isinstance(functions, Callable):
            self.functions = [functions, ]
        else:
            self.functions = [f for f in functions]

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
        if self.functions:
            self._call_bound_functions()
        self.dragged = self.can_be_dragged

    def _call_bound_functions(self):
        for function in self.functions:
            function()

    def bind_function(self, function: Callable):
        self.functions.append(function)

    def unbind_function(self, function=None):
        self.functions.remove(function)

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
    sound_on_mouse_enter = 'cursor_over_ui_element.wav'
    sound_on_mouse_click = 'click_on_ui_element.wav'

    def __init__(self, texture_name: str, x: int, y: int,
                 name: Optional[str] = None, active: bool = True,
                 visible: bool = True, parent: Optional[Hierarchical] = None,
                 functions: Optional[Union[Callable, Tuple[Callable]]] = None,
                 can_be_dragged: bool = False, subgroup: Optional[int] = None):
        full_texture_name = get_path_to_file(to_texture_name(texture_name))
        super().__init__(full_texture_name, center_x=x, center_y=y)
        ToggledElement.__init__(self, active, visible)
        CursorInteractive.__init__(self, can_be_dragged, functions, parent=parent)
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
        if isinstance(self._parent, ScrollableContainer):
            self.cursor.pointed_scrollable = self._parent
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

    def deactivate(self):
        self._func_on_mouse_exit()
        super().deactivate()


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
                 active: bool = False,
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
                 subgroup: Optional[int] = None
                 ):
        super().__init__('', x, y, name, active, visible, parent,
                         functions, subgroup=subgroup)
        # we load 2 textures for button: normal and for 'highlighted' button:
        full_texture_name = get_path_to_file(texture_name)
        image = PIL.Image.open(full_texture_name)
        width, height = image.size[0] // 2, image.size[1]
        self.textures = [
            load_texture(full_texture_name, 0, 0, width, height),
            load_texture(full_texture_name, width, 0, width, height)
        ]
        self.set_texture(0)

    def draw(self):
        super().draw()
        if not self._active:
            draw_rectangle_filled(*self.position, self.width, self.height, FOG)


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

    def _call_bound_functions(self):
        super()._call_bound_functions()
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
        :param functions:
        :param ticked:
        :param variable: Tuple[object, str] -- to bind a variable to this
        Checkbox you must pass a tuple which first element is an reference
        to the python object and second is a string name of this object
        attribute, e.g. (self, 'name_of_my_attribute').
        """
        super().__init__(texture_name, x, y, name, active, visible,
                         parent, functions, subgroup=subgroup)
        self.ticked = ticked
        self.variable = variable
        full_texture_name = get_path_to_file(texture_name)
        self.textures = [
            load_texture(full_texture_name, 0, 0, 30, 30),
            load_texture(full_texture_name, 30, 0, 30, 30)
        ]
        self.set_texture(int(self.ticked))
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
        setattr(self.variable[0], self.variable[1], self.ticked)

    def draw(self):
        self.text_label.draw()
        super().draw()


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
                 can_be_dragged: bool = False, subgroup: Optional[int] = None):
        super().__init__(texture_name, x, y, name, active, visible, parent,
                         functions, can_be_dragged, subgroup)
        self.scrollable = set()

    def add_child(self, child: Hierarchical):
        self.scrollable.add(child)

    def put_child_before_self(self, child):
        if child in self.bundle.elements:
            self.bundle.elements.remove(child)
        index = self.bundle.elements.index(self)
        self.bundle.elements.insert(index, child)

    def _func_on_mouse_enter(self, cursor):
        super()._func_on_mouse_enter(cursor)
        cursor.pointed_scrollable = self

    def _func_on_mouse_exit(self):
        super()._func_on_mouse_exit()
        self.cursor.pointed_scrollable = None

    def on_mouse_scroll(self, scroll_x: int, scroll_y: int):
        if self.scrollable:
            for child in self.scrollable:
                child.center_y -= scroll_y * 15
                self._manage_child_visibility(child)

    def _manage_child_visibility(self, child):
        if child.top >= self.top or child.bottom <= self.bottom:
            child.deactivate()
            child.hide()
        else:
            child.activate()
            child.show()


class ListBox(UiElement):
    ...


class TextInputField(UiElement):
    ...


class ScrollBar(UiElement):
    sound_on_mouse_enter = None
    sound_on_mouse_click = None
    ...
