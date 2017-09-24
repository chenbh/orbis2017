from PythonClientAPI.Game import PointUtils
from PythonClientAPI.Game.Entities import FriendlyUnit, EnemyUnit, Tile
from PythonClientAPI.Game.Enums import Direction, MoveType, MoveResult
from PythonClientAPI.Game.World import World
from pprint import pprint

PERSONAL_SPACE = 4


class PlayerAI:

    def __init__(self):
        self.nests = []
        self.occupied = []

    def do_move(self, world, friendly_units, enemy_units):
        builders = {}

        for n in self.nests:
            if not world.get_tile_at(n).is_neutral():
                self.nests.remove(n)
                self.occupied.append(n)
            else:
                tiles = world.get_tiles_around(n)
                for d, t in tiles.items():
                    if world.get_tile_at(t.position) and not t.is_friendly():
                        closest_friendly = world.get_closest_friendly_from(t.position, self.nests)
                        if world.get_shortest_path(t.position, closest_friendly.position, self.nests):
                            builders[closest_friendly.uuid] = t.position
                            self.occupied.append(t.position)
                        else:
                            self.nests.remove(n)
                            self.occupied.append(n)

        # Fly away to freedom, daring fireflies
        # Build thou nests
        # Grow, become stronger
        # Take over the world
        for unit in friendly_units:
            Drone(unit, world, friendly_units, enemy_units, builders, self)

    def start_nest(self, pos):
        self.nests.append(pos)
        self.occupied.append(pos)


class Drone:
    def __init__(self, unit, world, friendly_units, enemy_units, builders, controller):
        self.unit = unit
        self.world = world
        self.friendly_units = friendly_units
        self.enemy_units = enemy_units
        self.nests = controller.nests
        self.occupied = controller.occupied
        self.builders = builders
        self.controller = controller
        self.closest_enemy = self.closest_taxicab_enemy()

        self.enemy_distance = self.world.get_taxicab_distance(self.unit.position, self.closest_enemy.position)

        if self.enemy_distance < PERSONAL_SPACE * 2:
            enemy_path = self.world.get_shortest_path(unit.position,
                                                      self.closest_enemy.position,
                                                      self.nests)
            self.enemy_distance = len(enemy_path) if enemy_path else 2147483647
 
        actions = [self.fight,
                   self.chase,
                   self.strengthen,
                   self.reinforce,
                   self.build_nest,
                   self.start_nest,
                   self.expand]

        for a in actions:
            if a():
                break

    def closest_taxicab_enemy(self):
        shortest = self.world.get_taxicab_distance(self.unit.position, self.enemy_units[0].position)
        closest = self.enemy_units[0]

        for enemy in self.enemy_units:
            distance = self.world.get_taxicab_distance(self.unit.position, enemy.position)
            if distance < shortest:
                shortest = distance
                closest = enemy
        return closest

    def fight(self):
        if self.enemy_distance == 1:
            self.world.move(self.unit, self.closest_enemy.position)
            return True
        return False

    def chase(self):
        if self.enemy_distance < PERSONAL_SPACE and self.unit.health > self.closest_enemy.health:
            self.world.move(self.unit, self.closest_enemy.position)
            return True
        return False

    def strengthen(self):
        if self.enemy_distance < PERSONAL_SPACE \
                and self.closest_enemy.health - self.unit.health > 0 \
                and self.world.get_closest_friendly_from(self.closest_enemy.position, None).uuid == self.unit.uuid:
            return True
        return False

    def reinforce(self):
        if self.enemy_distance < PERSONAL_SPACE and self.closest_enemy.health > self.unit.health:
            self.world.move(self.unit, self.world.get_closest_friendly_from(self.closest_enemy.position, None).position)
            return True
        return False

    def build_nest(self):
        if self.unit.uuid in self.builders:
            path = self.world.get_shortest_path(self.unit.position, self.builders[self.unit.uuid], self.nests)
            if path:
                self.world.move(self.unit, path[0])
                return True
        return False

    def start_nest(self):
        if self.enemy_distance < PERSONAL_SPACE * 2:
            return False
        tiles = self.world.get_tiles_around(self.unit.position)
        for d, t in tiles.items():
            if t.is_neutral() and t.position not in self.nests and t.position not in self.occupied:
                self.controller.start_nest(t.position)
        return False

    def expand(self):
        if self.enemy_distance > PERSONAL_SPACE * 3:
            closest_tile = self.world.get_closest_capturable_tile_from(self.unit.position, self.nests)
            path = self.world.get_next_point_in_shortest_path(self.unit.position, closest_tile.position)
        else:
            unavailable = list(self.nests)
            while True:
                closest_tile = self.world.get_closest_capturable_tile_from(self.unit.position, unavailable)
                test_path = self.world.get_shortest_path(self.unit.position, closest_tile.position, unavailable)
                if test_path:
                    path = test_path[0]
                    break
                else:
                    unavailable.append(closest_tile.position)
        if path:
            self.world.move(self.unit, path)
        return True
