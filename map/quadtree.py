
#!/usr/bin/env python
from __future__ import annotations

from abc import abstractmethod, ABC
from math import dist
from typing import Optional
from matplotlib import path as mpltPath
from collections import defaultdict
from numpy import array

from arcade import draw_rectangle_outline, draw_text, draw_polygon_outline

from utils.colors import RED


class Rect:
    __slots__ = ('cx', 'cy', 'position', 'width', 'height', 'smaller_dimension', 'left', 'right', 'bottom', 'top')

    def __init__(self, cx, cy, width, height):
        self.cx, self.cy = cx, cy
        self.position = self.cx, self.cy
        self.width, self.height = width, height
        self.smaller_dimension = min(self.width, self.height) / 2
        self.left = self.cx - self.width // 2
        self.right = self.left + self.width
        self.bottom = self.cy - self.height // 2
        self.top = self.bottom + self.height

    def in_bounds(self, item) -> bool:
        return (
                self.left <= item.position[0] <= self.right and self.bottom <= item.position[1] <= self.top
        )

    def intersects(self, other):
        return not ((other.right < self.left or self.right < other.left) and
                    (other.top < self.bottom or self.top < other.bottom))

    def draw(self):
        draw_rectangle_outline(*self.position, self.width, self.height, RED)


class IsometricRect(Rect):

    def __init__(self, cx, cy, width, height):
        super().__init__(cx, cy, width, height)
        x, y = self.cx, self.cy
        hh, hw = self.width // 4, self.width // 2
        self.points = [(x - hw, y), (x, y + hh), (x + hw, y), (x, y - hh), (x - hw, y)]
        self.polygon = mpltPath.Path(array(self.points))

    def in_bounds(self, item) -> bool:
        return self.polygon.contains_point(item.position)

    def intersects(self, other) -> bool:
        return any(self.polygon.contains_point(point) for point in other.points)

    def draw(self):
        draw_polygon_outline(self.points, RED, 1)


class QuadTree(ABC):

    def __init__(self, max_entities=5, depth=0):
        self.max_entities = max_entities
        self.entities_count = 0
        self.depth = depth
        self.entities = defaultdict(set)
        self.children = []

    @abstractmethod
    def query(self, hostile_factions_ids, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""
        raise NotImplementedError

    def find_visible_entities_in_circle(self, circle_x, circle_y, radius, hostile_factions_ids):
        diameter = radius + radius
        rect = Rect(circle_x, circle_y, diameter, diameter)
        possible_enemies = []
        possible_enemies = self.query(hostile_factions_ids, rect, possible_enemies)
        return {e for e in possible_enemies if dist(e.position, (circle_x, circle_y)) < radius}

    @abstractmethod
    def insert(self, entity) -> Optional[QuadTree]:
        raise NotImplementedError

    def insert_to_children(self, entity) -> Optional[QuadTree]:
        for child in self.children:
            if (quadtree := child.insert(entity)) is not None:
                return quadtree

    def add_to_entities(self, entity):
        faction_id = entity.faction.id
        self.entities[faction_id].add(entity)
        self.entities_count += 1

    def remove(self, entity):
        try:
            self.entities[entity.faction.id].remove(entity)
        except (KeyError, ValueError):
            for quadtree in self.children:
                quadtree.remove(entity)
        else:
            self.entities_count -= 1
            self.collapse()

    @abstractmethod
    def divide(self):
        raise NotImplementedError

    @property
    def empty(self):
        return not self.entities and all(child.empty() for child in self.children)

    def collapse(self) -> bool:
        if all(child.collapse() for child in self.children):
            self.children.clear()
        return not self.children and not self.entities_count

    def clear(self):
        for quadtree in self.children:
            quadtree.clear()
        self.entities.clear()

    def total_depth(self, depth=0) -> int:
        for quadtree in self.children:
            depth = quadtree.total_depth(depth)
        return max(depth, self.depth)

    def total_entities(self):
        return self.entities_count + sum(quadtree.total_entities() for quadtree in self.children)

    def get_entities(self):
        return [e.id for entities_list in self.entities.values() for e in entities_list]


class CartesianQuadTree(QuadTree, Rect):
    """This class provides fast and efficient way to detect Units which could see each other."""
    __slots__ = ('max_entities', 'true_max_entities','depth', 'entities_count', 'entities', 'children', 'max_size')

    def __init__(self, cx, cy, width, height, max_entities=5, depth=0):
        super().__init__(max_entities, depth)
        Rect.__init__(self, cx, cy, width, height)

    def __repr__(self) -> str:
        return f'QuadTree(depth: {self.depth}, l:{self.left}, r:{self.right}, b:{self.bottom}, t:{self.top})'

    def insert(self, entity) -> Optional[CartesianQuadTree]:
        if not Rect.in_bounds(self, entity):
            return None

        if self.entities_count < self.max_entities:
            self.add_to_entities(entity)
            return self

        if not self.children:
            self.divide()

        return self.insert_to_children(entity)

    def insert_to_children(self, entity) -> Optional[CartesianQuadTree]:
        for child in self.children:
            if (quadtree := child.insert(entity)) is not None:
                return quadtree

    def add_to_entities(self, entity):
        faction_id = entity.faction.id
        self.entities[faction_id].add(entity)
        self.entities_count += 1
        # faction_id = entity.faction.id
        # try:
        #     self.entities[faction_id].add(entity)
        # except KeyError:
        #     self.entities[faction_id] = {entity, }
        # finally:
        #     self.entities_count += 1

    def remove(self, entity):
        try:
            self.entities[entity.faction.id].remove(entity)
        except (KeyError, ValueError):
            for quadtree in self.children:
                quadtree.remove(entity)
        else:
            self.entities_count -= 1
            self.collapse()

    def divide(self):
        cx, cy = self.cx, self.cy
        half_width, half_height = self.width / 2, self.height / 2
        quart_width, quart_height = half_width / 2, half_height / 2
        new_depth = self.depth + 1
        self.children = [
            CartesianQuadTree(cx - quart_width, cy + quart_height, half_width, half_height, self.max_entities, new_depth),
            CartesianQuadTree(cx + quart_width, cy + quart_height, half_width, half_height, self.max_entities, new_depth),
            CartesianQuadTree(cx + quart_width, cy - quart_height, half_width, half_height, self.max_entities, new_depth),
            CartesianQuadTree(cx - quart_width, cy - quart_height, half_width, half_height, self.max_entities, new_depth)
        ]

    def query(self, hostile_factions_ids, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""
        if not self.intersects(bounds):
            return found_entities
        for faction_id, entities in self.entities.items():
            if faction_id in hostile_factions_ids:
                found_entities.extend(e for e in entities if bounds.in_bounds(e))
        for quadtree in self.children:
            found_entities = quadtree.query(hostile_factions_ids, bounds, found_entities)
        return found_entities

    def find_visible_entities_in_circle(self, circle_x, circle_y, radius, hostile_factions_ids):
        diameter = radius + radius
        rect = Rect(circle_x, circle_y, diameter, diameter)
        possible_enemies = []
        possible_enemies = self.query(hostile_factions_ids, rect, possible_enemies)
        return {e for e in possible_enemies if dist(e.position, (circle_x, circle_y)) < radius}

    @property
    def empty(self):
        return not self.entities and all(child.empty for child in self.children)

    def collapse(self) -> bool:
        if all(child.collapse() for child in self.children):
            self.children.clear()
        return not self.children and not self.entities_count

    def clear(self):
        for quadtree in self.children:
            quadtree.clear()
        self.entities.clear()

    def total_depth(self, depth=0) -> int:
        for quadtree in self.children:
            depth = quadtree.total_depth(depth)
        return max(depth, self.depth)

    def total_entities(self):
        return self.entities_count + sum(quadtree.total_entities() for quadtree in self.children)

    def get_entities(self):
        return [e.id for entities_list in self.entities.values() for e in entities_list]

    def draw(self):
        super().draw()
        if self.entities_count:
            draw_text(str(self.get_entities()), *self.position, RED, 20)
        for child in self.children:
            child.draw()


class IsometricQuadTree(QuadTree, IsometricRect):

    def __init__(self, cx, cy, width, height, max_entities=5, depth=0):
        super().__init__(max_entities, depth)
        IsometricRect.__init__(self, cx, cy, width, height)

    def __repr__(self) -> str:
        return f'QuadTree(depth: {self.depth}, l:{self.left}, r:{self.right}, b:{self.bottom}, t:{self.top})'

    def insert(self, entity) -> Optional[IsometricQuadTree]:
        if not Rect.in_bounds(self, entity):
            return None

        if self.entities_count < self.max_entities:
            self.add_to_entities(entity)
            return self

        if not self.children:
            self.divide()

        return self.insert_to_children(entity)

    def insert_to_children(self, entity) -> Optional[IsometricQuadTree]:
        for child in self.children:
            if (quadtree := child.insert(entity)) is not None:
                return quadtree

    def add_to_entities(self, entity):
        faction_id = entity.faction.id
        try:
            self.entities[faction_id].add(entity)
        except KeyError:
            self.entities[faction_id] = {entity, }
        finally:
            self.entities_count += 1

    def remove(self, entity):
        try:
            self.entities[entity.faction.id].remove(entity)
        except (KeyError, ValueError):
            for quadtree in self.children:
                quadtree.remove(entity)
        else:
            self.entities_count -= 1
            self.collapse()

    def divide(self):
        cx, cy = self.cx, self.cy
        half_width, half_height = self.width / 2, self.height / 2
        quart_width, quart_height = half_width / 2, half_height / 2
        new_depth = self.depth + 1
        self.children = [
            CartesianQuadTree(cx - quart_width, cy, half_width, half_height, self.max_entities, new_depth),
            CartesianQuadTree(cx, cy + quart_height, half_width, half_height, self.max_entities, new_depth),
            CartesianQuadTree(cx + quart_width, cy, half_width, half_height, self.max_entities, new_depth),
            CartesianQuadTree(cx, cy - quart_height, half_width, half_height, self.max_entities, new_depth)
        ]

    def query(self, hostile_factions_ids, bounds, found_entities):
        """Find the points in the quadtree that lie within boundary."""
        if not self.intersects(bounds):
            return found_entities
        for faction_id, entities in self.entities.items():
            if faction_id in hostile_factions_ids:
                found_entities.extend(e for e in entities if bounds.is_inside_map_grid(e))
        for quadtree in self.children:
            found_entities = quadtree.query(hostile_factions_ids, bounds, found_entities)
        return found_entities

    def find_visible_entities_in_circle(self, circle_x, circle_y, radius, hostile_factions_ids):
        diameter = radius + radius
        rect = Rect(circle_x, circle_y, diameter, diameter)
        possible_enemies = []
        possible_enemies = self.query(hostile_factions_ids, rect, possible_enemies)
        return {e for e in possible_enemies if dist(e.position, (circle_x, circle_y)) < radius}

    @property
    def empty(self):
        return not self.entities and all(child.empty for child in self.children)

    def collapse(self) -> bool:
        if all(child.collapse() for child in self.children):
            self.children.clear()
        return not self.children and not self.entities_count

    def clear(self):
        for quadtree in self.children:
            quadtree.clear()
        self.entities.clear()

    def total_depth(self, depth=0) -> int:
        for quadtree in self.children:
            depth = quadtree.total_depth(depth)
        return max(depth, self.depth)

    def total_entities(self):
        return self.entities_count + sum(quadtree.total_entities() for quadtree in self.children)

    def get_entities(self):
        return [e.id for entities_list in self.entities.values() for e in entities_list]

    def draw(self):
        super().draw()
        if self.entities_count:
            draw_text(str(self.get_entities()), *self.position, RED, 20)
        for child in self.children:
            child.draw()
