from PythonClientAPI.Game import PointUtils
from PythonClientAPI.Game.Entities import FriendlyUnit, EnemyUnit, Tile
from PythonClientAPI.Game.Enums import Direction, MoveType, MoveResult
from PythonClientAPI.Game.World import World
from pprint import pprint

# Range that Drones use to consider actions
PERSONAL_SPACE = 4
# Min HP for a Drone to initiate a bullrush at the enemy
# I'm the Juggernaut, bitch.
JUGGERNAUT = 20


MAX_VALUE = 2147483647

class PlayerAI:

    def __init__(self):
        self.nests = []
        # occupied means don't make a nest here
        self.occupied = []

    def do_move(self, world, friendly_units, enemy_units):
        builders = {}
        assigned_builder_units = set()

        for n in self.nests:
            if not world.get_tile_at(n).is_neutral():
                self.nests.remove(n)
                self.occupied.append(n)
            else:
                is_invalid_nest = False
                tiles = world.get_tiles_around(n)

                # save possible builders
                candidate_builders = []
                candidate_assigned_builder_units = set()

                for d, t in tiles.items():
                    if world.get_tile_at(t.position) and not t.is_friendly():
                        if t.position in self.nests:
                            self.nests.remove(n)
                            self.occupied.append(n)
                            is_invalid_nest = True
                            break
                        closest_friendly = world.get_closest_friendly_from(
                            t.position,
                            assigned_builder_units.union(candidate_assigned_builder_units)
                        )
                        if closest_friendly and world.get_shortest_path(t.position, closest_friendly.position, self.nests):
                            candidate_builders.append((closest_friendly.uuid, t.position))
                            assigned_builder_units.add(closest_friendly.position)
                        else:
                            self.nests.remove(n)
                            self.occupied.append(n)
                            is_invalid_nest = True
                            break

                if not is_invalid_nest:
                    for builder in candidate_builders:
                        builders[builder[0]] = builder[1]
                        self.occupied.append(builder[1])
                    assigned_builder_units.update(candidate_assigned_builder_units)


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
            self.enemy_distance = len(enemy_path) if enemy_path else MAX_VALUE
 
        actions = [self.fight,
                   self.invade,
                   self.defend,
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

    def num_adjacent_friendly_and_walls(self, tile):
        num_friendly_adjacent = 0
        for d, adj_tile in self.world.get_tiles_around(tile.position).items():
            if self.world.is_wall(adj_tile.position) or adj_tile.is_friendly():
                num_friendly_adjacent+=1
        return num_friendly_adjacent

    def tiles_distance_two_around(self, position):
        immediate_tiles = self.world.get_tiles_around(position)
        all_nearby_tiles = set([tile for nearby_tile in immediate_tiles for tile in self.world.get_tiles_around(nearby_tile)])
        current_tile = world.get_tile_at(position)
        all_nearby_tiles.discard(current_tile)
        return list(all_nearby_tiles)

    def fight(self):
        if self.enemy_distance == 1:
            self.world.move(self.unit, self.closest_enemy.position)
            return True
        return False

    def defend(self):
        in_danger_nest = self.world.get_closest_friendly_nest_from(self.closest_enemy.position, None)
        enemy_distance_from_nest = self.world.get_shortest_path_distance(self.closest_enemy.position,
                                                                         in_danger_nest)
        self_distance_from_nest = self.world.get_shortest_path_distance(self.unit.position,
                                                                        in_danger_nest)
        if self_distance_from_nest < enemy_distance_from_nest < int(PERSONAL_SPACE * 1):
            self.world.move(self.unit, in_danger_nest)
            return True
        return False

    def invade(self):
        if self.unit.health > int(JUGGERNAUT / 2):
            target_nest = self.world.get_closest_enemy_nest_from(self.unit.position, None)
            nest_path = self.world.get_shortest_path(self.unit.position, target_nest, self.nests)
            if self.unit.health > JUGGERNAUT or len(nest_path) < PERSONAL_SPACE * 2:
                self.world.move(self.unit, nest_path[0])
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
            # Do nothing and gain 1 health
            return True
        return False

    def reinforce(self):
        if self.enemy_distance < PERSONAL_SPACE and self.closest_enemy.health > self.unit.health:
            self.world.move(self.unit, self.world.get_closest_friendly_from(self.closest_enemy.position, None).position)
            return True
        return False

    def build_nest(self):
        #does checking for merged uuids help?
        #if any(self.unit.is_merged_with_unit(uuid) for uuid in self.builders.keys()) or self.unit.uuid in self.builders:
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

        most_ideal_tile = None
        most_adjacent_friendly = -1
        first_candidate_tile = None
        for d, t in tiles.items():
            if t.is_neutral() and t.position not in self.nests and t.position not in self.occupied:
                num_friendly = self.num_adjacent_friendly_and_walls(t)
                if first_candidate_tile is None:
                    first_candidate_tile = t
                if num_friendly > most_adjacent_friendly:
                    most_adjacent_friendly = num_friendly
                    most_ideal_tile = t

        if self.enemy_distance < PERSONAL_SPACE * 3 and most_ideal_tile is not None:
            self.controller.start_nest(most_ideal_tile.position)
        elif first_candidate_tile is not None:
            self.controller.start_nest(first_candidate_tile.position)
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
