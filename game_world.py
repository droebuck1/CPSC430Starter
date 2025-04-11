from panda3d.bullet import BulletWorld, BulletBoxShape, BulletRigidBodyNode, BulletCapsuleShape, ZUp, BulletPlaneShape, \
    BulletCharacterControllerNode, BulletDebugNode
from panda3d.core import Vec3, TransformState, VBase3, Point3
from pubsub import pub
import json
from game_object import GameObject
from player import Player
from teleporter import Teleporter


class GameWorld:
    def __init__(self, debugNode):
        self.properties = {}
        self.game_objects = {}

        self.next_id = 0
        self.physics_world = BulletWorld()
        self.physics_world.setGravity(Vec3(0, 0, -9.81))
        self.physics_world.setDebugNode(debugNode)

        self.kind_to_shape = {
            "crate": self.create_box,
            "floor": self.create_box,
            "red box": self.create_box,
            "teleporter": self.create_box,
        }

        self.class_to_type = {
            'GameObject': GameObject,
            'Teleporter': Teleporter,
            'Player': Player,
        }

    def create_capsule(self, position, size, kind, mass):
        radius = size[0]
        height = size[1]
        shape = BulletCapsuleShape(radius, height, ZUp)
        # node = BulletCharacterControllerNode(shape, radius, kind)
        node = BulletRigidBodyNode(kind)
        node.setMass(mass)
        node.addShape(shape)
        node.setRestitution(0.0)
        # node.setKinematic(True)

        node.setTransform(TransformState.makePos(VBase3(position[0], position[1], position[2])))

        # self.physics_world.attachCharacter(node)
        self.physics_world.attachRigidBody(node)

        return node

    def create_box(self, position, size, kind, mass):
        # The box shape needs half the size in each dimension
        shape = BulletBoxShape(Vec3(size[0] / 2, size[1] / 2, size[2] / 2))
        node = BulletRigidBodyNode(kind)
        node.setMass(mass)
        node.addShape(shape)
        node.setTransform(TransformState.makePos(VBase3(position[0], position[1], position[2])))
        node.setRestitution(0.0)

        self.physics_world.attachRigidBody(node)

        return node

    def create_physics_object(self, position, kind, size, mass):
        if kind in self.kind_to_shape:
            return self.kind_to_shape[kind](position, size, kind, mass)

        return None

    def create_object(self, position, kind, size, mass, subclass):
        physics = self.create_physics_object(position, kind, size, mass)
        obj = subclass(position, kind, self.next_id, size, physics)

        self.next_id += 1
        self.game_objects[obj.id] = obj

        pub.sendMessage('create', game_object=obj)
        return obj

    def tick(self, dt):
        for id in self.game_objects:
            self.game_objects[id].tick(dt)

        for id in self.game_objects:
            if self.game_objects[id].is_collision_source:
                contacts = self.get_all_contacts(self.game_objects[id])

                for contact in contacts:
                    if contact.getNode1() and contact.getNode1().getPythonTag("owner"):
                        # Notify both objects about the collision
                        contact.getNode1().getPythonTag("owner").collision(self.game_objects[id])
                        self.game_objects[id].collision(contact.getNode1().getPythonTag("owner"))

        self.physics_world.doPhysics(dt)

    def load_world(self, filename):
        # TODO: Need to do something here to remove old game objects and their views

        with open(filename) as infile:
            level_data = json.load(infile)
            if not "objects" in level_data:
                return False
            for game_object in level_data['objects']:
                collision_source = False
                if 'collision_source' in game_object:
                    collision_source = game_object['collision_source']

                class_object = self.class_to_type[game_object['class']]
                obj = self.create_object(game_object['position'], game_object['kind'], game_object['size'], game_object['mass'], class_object)
                obj.is_collision_source = collision_source

    def get_property(self, key):
        if key in self.properties:
            return self.properties[key]

        return None

    def set_property(self, key, value):
        self.properties[key] = value

        pub.sendMessage('property', key=key, value=value)

    def get_nearest(self, from_pt, to_pt):
        # This shows the technique of near object detection using the physics engine.
        fx, fy, fz = from_pt
        tx, ty, tz = to_pt
        result = self.physics_world.rayTestClosest(Point3(fx, fy, fz), Point3(tx, ty, tz))
        return result

    # TODO: use this to demonstrate a teleporting trap
    def get_all_contacts(self, game_object):
        if game_object.physics:
            return self.physics_world.contactTest(game_object.physics).getContacts()

        return []

    def reset(self):
        pass
