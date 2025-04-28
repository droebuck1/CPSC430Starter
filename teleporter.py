from panda3d.core import Quat, lookAt, Vec3
from game_object import GameObject
from pubsub import pub

class Teleporter(GameObject):
    def __init__(self, position, kind, id, size, physics):
        super().__init__(position, kind, id, size, physics)

    def collision(self, other):
        # Must use jump_to_position here to avoid messing with the player's kcc interaction
        current = other.position
        other.jump_to_position((current[0], current[1]-5, current[2]))

