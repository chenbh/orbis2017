from PythonClientAPI.Game import PointUtils
from PythonClientAPI.Game.Entities import FriendlyUnit, EnemyUnit, Tile
from PythonClientAPI.Game.Enums import Direction, MoveType, MoveResult
from PythonClientAPI.Game.World import World
from pprint import pprint

# Range that Drones use to consider actions
PERSONAL_SPACE = 4
# Min HP for a Drone to initiate a bullrush at the enemy
# I'm the Juggernaut, bitch.
JUGGERNAUT = 18
# Some arbitrary large value used for bypassing some stuff
MAX_VALUE = 2147483647


class PlayerAI:

    def __init__(self):
        # list of locations that have been designated as future nest locations
        self.nests = []
        # occupied means don't make a nest here
        self.occupied = []
        # list of current friendly nests
        self.current_nests = []

    def do_move(self, world, friendly_units, enemy_units):
        # dictionary of Units whose' task it is to go to a spot to build a nest
        builders = {}

        # go through list of designated nests and assign builders to finish it or remove the designation if needed
        for n in self.nests:
            # check to see the designated nest location is still valid
            if not world.get_tile_at(n).is_neutral():
                self.nests.remove(n)
                self.occupied.append(n)
            else:
                is_invalid_nest = False
                tiles = world.get_tiles_around(n)

                # save possible builders
                candidate_builders = []

                # assign a builder Drone to each neighbour tile of a designated nest
                for d, t in tiles.items():
                    if world.get_tile_at(t.position) and not t.is_friendly():
                        if t.position in self.nests:
                            self.nests.remove(n)
                            self.occupied.append(n)
                            is_invalid_nest = True
                            break
                        closest_friendly = world.get_closest_friendly_from(t.position, self.nests)
                        if world.get_shortest_path(t.position, closest_friendly.position, self.nests):
                            # FIXME: some fireflies are assigned two spots. Only one will be taken
                            candidate_builders.append((closest_friendly.uuid, t.position))
                        else:
                            self.nests.remove(n)
                            self.occupied.append(n)
                            is_invalid_nest = True
                            break
                for builder in candidate_builders:
                    builders[builder[0]] = builder[1]
                    self.occupied.append(builder[1])

        self.current_nests = world.get_friendly_nest_positions()

        # Fly away to freedom, daring fireflies
        # Build thou nests
        # Grow, become stronger
        # Take over the world
        for unit in friendly_units:
            Drone(unit, world, friendly_units, enemy_units, builders, self)

    # way for Drones to communicate to the mastermind (PlayerAI) about strategic objectives
    def start_nest(self, pos):
        self.nests.append(pos)
        self.occupied.append(pos)


# Single minded, follows list of priorities, hits performance issues when there's a lot of these
class Drone:
    def __init__(self, unit, world, friendly_units, enemy_units, builders, controller):
        self.unit = unit
        self.world = world
        self.friendly_units = friendly_units
        self.enemy_units = enemy_units
        self.nests = controller.nests
        self.occupied = controller.occupied
        self.current_nests = controller.current_nests
        self.builders = builders
        self.controller = controller

        # find the closest enemy (roughly) by taxicab distance, saves on performance when there's a lot of Drones
        self.closest_enemy = self.closest_taxicab_enemy()

        self.enemy_distance = self.world.get_taxicab_distance(self.unit.position, self.closest_enemy.position)

        # if the rough distance is within a certain range, use A* distance to refine the details
        if self.enemy_distance < PERSONAL_SPACE * 2:
            enemy_path = self.world.get_shortest_path(unit.position,
                                                      self.closest_enemy.position,
                                                      self.nests)
            self.enemy_distance = len(enemy_path) if enemy_path else MAX_VALUE

        # list of actions the drone should execute in order
        actions = [self.fight,
                   self.defend,
                   self.chase,
                   self.strengthen,
                   self.reinforce,
                   self.build_nest,
                   self.start_nest,
                   self.invade,
                   self.expand]

        for a in actions:
            if a():
                break

    # custom move function that does some additional proccessing based on the outcome of the previous move command
    def move(self, pos):
        # blocked by nest or newly spawned => use A* instead of cached
        if self.unit.last_move_result == MoveResult.BLOCKED_BY_NEST \
                or self.unit.last_move_result == MoveResult.NEWLY_SPAWNED:
            blocked = self.nests + list(set(self.current_nests) - set(self.nests))
            path = self.world.get_shortest_path(self.unit.position, pos, blocked)
            if path:
                self.world.move(self.unit, path[0])
        else:
            self.world.move(self.unit, pos)

    # find closest enemy by taxicab distance (saves on performance when there is large amounts of Drones
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

    # what to do if there's an enemy adjacent to this drone
    def fight(self):
        if self.enemy_distance == 1:
            self.move(self.closest_enemy.position)
            return True

            # Attack the largest health enemy
            #enemy_dict = self.world.get_position_to_enemy_dict()
            # target_enemy = None
            # for d, position in self.world.get_neighbours(self.unit.position).items():
            #     if position in enemy_dict:
            #         candidate_enemy = enemy_dict[position]
            #         if target_enemy is None:
            #             target_enemy = candidate_enemy
            #         else:
            #             target_enemy = candidate_enemy if candidate_enemy.health > target_enemy.health else target_enemy
            #         self.move(target_enemy.position)
            #         return True
        return False

    # what to do if there's an enemy threatening a nest
    def defend(self):
        in_danger_nest = self.world.get_closest_friendly_nest_from(self.closest_enemy.position, None)

        if self.world.get_taxicab_distance(self.closest_enemy.position, in_danger_nest) < PERSONAL_SPACE * 1:
            neighbours = self.world.get_tiles_around(in_danger_nest)
            closest = in_danger_nest
            shortest = self.world.get_taxicab_distance(self.closest_enemy.position, closest)

            # find the neighbour tiles of the nest that is the closest to the enemy
            for d, t in neighbours.items():
                distance = self.world.get_taxicab_distance (self.closest_enemy.position, t.position)
                if distance < shortest:
                    closest = t.position
                    shortest = distance

            # calculate self and enemy distance from the vulnerable nest
            enemy_distance_from_nest = self.world.get_shortest_path_distance(self.closest_enemy.position,
                                                                             closest)
            self_distance_from_nest = self.world.get_shortest_path_distance(self.unit.position,
                                                                            closest)

            if self_distance_from_nest < enemy_distance_from_nest < int(PERSONAL_SPACE * 1):
                self.move(closest)
                return True
        return False

    # what to do if this Drone has enough hp or is near an enemy nest
    def invade(self):
        if self.unit.health > int(JUGGERNAUT / 2):
            target_nest = self.world.get_closest_enemy_nest_from(self.unit.position, None)
            nest_path = self.world.get_shortest_path(self.unit.position, target_nest, self.current_nests)
            if nest_path and (self.unit.health >= JUGGERNAUT or len(nest_path) < PERSONAL_SPACE * 1):
                self.move(nest_path[0])
                return True
        return False

    # what to do if there's an enemy with lower hp than this Drone in range
    def chase(self):
        if self.enemy_distance < PERSONAL_SPACE and self.unit.health > self.closest_enemy.health:
            self.move(self.closest_enemy.position)
            return True
        return False

    # what to do if there's an enemy with higher hp than this Drone in range
    def strengthen(self):
        if self.enemy_distance < PERSONAL_SPACE \
                and self.closest_enemy.health - self.unit.health > 0 \
                and self.world.get_closest_friendly_from(self.closest_enemy.position, None).uuid == self.unit.uuid:
            # Do nothing and gain 1 health
            return True
        return False

    # what to do if there's an enemy with higher hp than this Drone and there's an ally closer to the enemy
    def reinforce(self):
        if self.enemy_distance < PERSONAL_SPACE and self.closest_enemy.health > self.unit.health:
            # move to merge with closest ally to the enemy
            self.move(self.world.get_closest_friendly_from(self.closest_enemy.position, None).position)
            return True
        return False

    # what to do if this Drone is desginated as a builder for a nest
    def build_nest(self):
        # does checking for merged uuids help?
        # if any(self.unit.is_merged_with_unit(uuid) for uuid in self.builders.keys()) or self.unit.uuid in self.builders:
        if self.unit.uuid in self.builders:
            path = self.world.get_shortest_path(self.unit.position, self.builders[self.unit.uuid], self.nests)
            if path:
                self.move(path[0])
                return True
        return False

    # check the surroundings to see if they make good nest locations
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

        # designate nest locations to mastermind (PlayerAI)
        if self.enemy_distance < PERSONAL_SPACE * 3 and most_ideal_tile is not None:
            self.controller.start_nest(most_ideal_tile.position)
        elif first_candidate_tile is not None:
            self.controller.start_nest(first_candidate_tile.position)
        return False

    # default / catch-all: expand your territory if all the other actions are exhausted
    def expand(self):
        # use cached path if really far from enemy (saves on performance)
        if self.enemy_distance > PERSONAL_SPACE * 2:
            closest_tile = self.world.get_closest_capturable_tile_from(self.unit.position, self.nests)
            path = self.world.get_next_point_in_shortest_path(self.unit.position, closest_tile.position)
        # closer to enemy, use A* for more intelligent path finding
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
            self.move(path)
        return True
