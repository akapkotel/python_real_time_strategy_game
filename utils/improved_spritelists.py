#!/usr/bin/env python
from __future__ import annotations

from typing import Dict, Optional, Union, Iterable, Iterator

from arcade import SpriteList, Sprite


class SpriteListWithSwitch(SpriteList):
    """
    This is a arcade Spritelist improved with parameters: update_on, draw_on
    and method toggle_update() and toggle_draw() which controls if this
    SpriteList is updated and drawn each frame or not.
    """

    def __init__(self, use_spatial_hash=False,
                 spatial_hash_cell_size: int = 128,
                 is_static=False,
                 update_on=True,
                 draw_on=True):
        super().__init__(use_spatial_hash, spatial_hash_cell_size, is_static)
        self.update_on = update_on
        self.draw_on = draw_on

    def get_by_id(self, sprite_id: int) -> Optional[Sprite]:
        for sprite in self:
            if sprite.id == sprite_id:
                return sprite

    def on_update(self, delta_time: float = 1/60):
        if self.update_on:
            super().on_update(delta_time)

    def update(self):
        if self.update_on:
            super().update()

    def draw(self, **kwargs):
        if self.draw_on:
            super().draw(**kwargs)

    def toggle_update(self):
        self.update_on = not self.update_on

    def toggle_draw(self):
        self.draw_on = not self.draw_on


# noinspection PyUnresolvedReferences
class LayeredSpriteList(SpriteList):
    """
    This SpriteList works with Sprites having attributes: 'id', 'updated' and
    'rendered'. It is possible to switch updating and drawing of single
    sprites by changing their 'updated' and 'rendered' attributes inside
    their own logic, or by calling 'start_updating', 'start_rendering',
    'stop_updating' and 'stop_rendering' methods of SelectableSpriteList with
    the chosen Sprite as parameter.
    LayeredSpritelist also maintains hashmap of all Sprites which allows for
    fast lookups by their 'id' attribute.
    """
    game = None

    def __init__(self,
                 use_spatial_hash=False,
                 spatial_hash_cell_size=128,
                 is_static=False,
                 update_on=True,
                 draw_on=True):
        super().__init__(use_spatial_hash, spatial_hash_cell_size, is_static)
        self.game_objects: Dict[int, GameObject] = {}

        # layers are ordering Sprites spatially from top of the map to bottom
        # what allows rendering them in reversed way to avoid Sprites being
        # 'closer' to the player'spoint of view being obstructed by those which
        # are more distant
        # self.rendering_layers = self.create_rendering_layers()
        self.update_on = update_on
        self.draw_on = draw_on

    def create_rendering_layers(self) -> List[List]:
        return [[] for _ in range(self.game.settings.map_height)]

    def get(self, game_object_id: int) -> Optional[Sprite]:
        return self.game_objects.get(game_object_id)

    def __len__(self) -> int:
        return len(self.game_objects)

    def __contains__(self, game_object: GameObject) -> bool:
        return game_object.id in self.game_objects

    def append(self, game_object: GameObject) -> None:
        game_object.layered_spritelist = self
        if game_object.id not in self.game_objects:
            self.game_objects[game_object.id] = game_object
            super().append(game_object)

    def add_to_rendering_layer(self, game_object: GameObject) -> None:
        pass
        # try:
        #     self.rendering_layers[sprite.current_node.grid[1]].append(sprite)
        # except (AttributeError, ValueError):
        #     pass

    def swap_rendering_layers(self, game_object: GameObject, old_layer: int, new_layer: int) -> None:
        pass
        # try:
        #     self.rendering_layers[old_layer].remove(sprite)
        # except ValueError:
        #     pass
        # finally:
        #     self.rendering_layers[new_layer].append(sprite)

    def remove(self, game_object: GameObject) -> None:
        try:
            del self.game_objects[game_object.id]
            super().remove(game_object)
            game_object.layered_spritelist = None
            if game_object.is_rendered:
                self.rendered.remove(game_object)
        except KeyError:
            pass

    def remove_from_rendering_layer(self, game_object: GameObject) -> None:
        pass
        # try:
        #     self.rendering_layers[sprite.current_node.grid[1]].remove(sprite)
        # except (AttributeError, ValueError):
        #     if sprite.is_building:
        #         for layer in (l for l in self.rendering_layers if sprite in l):
        #             layer.remove(sprite)

    def extend(self, game_objects: Iterable[GameObject]) -> None:
        for game_object in game_objects:
            self.append(game_object)

    def on_update(self, delta_time: float = 1/60) -> None:
        if self.update_on:
            for game_object in (gobj for gobj in self if gobj.is_updated):
                game_object.on_update(delta_time)

    def draw(self) -> None:
        if self.draw_on:
            super().draw()
            self.draw_buildings()

    def draw_buildings(self):
        if any(game_object.is_building for game_object in self.game_objects.values()):
            for building in self:
                building.draw()

            # for layer in self.rendering_layers[::-1]:  # from bottom to top
            #     for sprite in (s for s in layer if s.is_rendered):
            #         sprite.draw()

    def pop(self, index: int = -1) -> Sprite:
        game_object = super().pop(index)
        del self.game_objects[game_object.id]
        # self.remove_from_rendering_layer(game_object)
        return game_object

    def clear(self) -> None:
        """Safe clearing of the whole SpriteList using reversed order."""
        for _ in range(len(self)):
            self.pop()


class UiSpriteList(SpriteList):
    """
    Wrapper for spritelists containing UiElements for quick identifying the
    spritelists which should be collided with the MouseCursor.
    """

    def __init__(self, use_spatial_hash=False, spatial_hash_cell_size=128,
                 is_static=False):
        super().__init__(use_spatial_hash, spatial_hash_cell_size, is_static)

    def append(self, item):
        if hasattr(item, 'visible') and hasattr(item, 'active'):
            super().append(item)

    def extend(self, items: Union[list, 'SpriteList']):
        for item in (i for i in items if hasattr(i, 'visible') and hasattr(i, 'active')):
            super().append(item)

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


if __name__ == '__main__':
    from gameobjects.gameobject import GameObject