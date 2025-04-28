from direct.showbase.ShowBase import ShowBase
from direct.showbase.ShowBaseGlobal import globalClock
from direct.task import Task
from panda3d.bullet import BulletDebugNode
from panda3d.core import CollisionNode, GeomNode, CollisionRay, CollisionHandlerQueue, CollisionTraverser, MouseButton, \
    WindowProperties, Quat, Vec3, Point3
from direct.showbase.InputStateGlobal import inputState
from pubsub import pub
import sys
import random

from kcc import PandaBulletCharacterController
from world_view import WorldView
from game_world import GameWorld
from game_object import GameObject
from player import Player
from teleporter import Teleporter

controls = {
    'escape': 'toggleMouseMove',
    't': 'teleport',
    'mouse1': 'toggleTexture',
    'space': 'jump',
    'c': 'crouch',
    'r': 'restart',
}

held_keys = {
    'w': 'moveForward',
    's': 'moveBackward',
    'a': 'moveLeft',
    'd': 'moveRight',
}


class ObstacleGameController(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        self.disableMouse()
        self.render.setShaderAuto()

        # Set up debug
        debugNode = BulletDebugNode('Debug')
        debugNode.showWireframe(True)
        debugNode.showConstraints(True)
        debugNode.showBoundingBoxes(False)
        debugNode.showNormals(False)
        debugNP = self.render.attachNewNode(debugNode)
        debugNP.show()

        # Set up game world
        self.game_world = GameWorld(debugNode)
        self.world_view = WorldView(self.game_world)

        # Set up collision traverser
        self.cTrav = CollisionTraverser()

        # Track player
        self.instances = []
        self.player = None
        pub.subscribe(self.new_player_object, 'create')

        # Build the obstacle course
        self.create_obstacle_course()

        # Set up inputs
        self.input_events = {}
        for key in controls:
            self.accept(key, self.input_event, [controls[key]])

        for key in held_keys:
            inputState.watchWithModifiers(held_keys[key], key)

        # Set up window properties
        self.SpeedRot = 0.05
        self.CursorOffOn = 'Off'
        self.props = WindowProperties()
        self.props.setCursorHidden(True)
        self.win.requestProperties(self.props)

        self.camera_pitch = 0

        # Subscribe to input events
        pub.subscribe(self.handle_input, 'input')

        # Add game loop task
        self.taskMgr.add(self.tick, "GameLoop")

        # Run the game
        self.run()

    def create_obstacle_course(self):
        # Create ground floor
        floor_size = [100.0, 40.0, 1.0]
        floor_pos = (0, 0, -0.5)
        self.floor = self.game_world.create_object(
            floor_pos, "floor", floor_size, 0, GameObject
        )

        # Create starting platform
        start_size = [5.0, 5.0, 1.0]
        start_pos = (0, 0, 0)
        self.start = self.game_world.create_object(
            start_pos, "floor", start_size, 0, GameObject
        )

        # Create player at start position
        player_size = [2.0, 1.0, 0.5, 0.5]  # walkHeight, crouchHeight, stepHeight, radius
        player_pos = (0, 0, 2)
        self.player_obj = self.game_world.create_object(
            player_pos, "player", player_size, 1.0, Player
        )

        # ---- OBSTACLE 1: Small jump ----
        self.create_gap(5, 0, 2, 1)

        # ---- OBSTACLE 2: Crouch under ceiling ----
        self.create_low_ceiling(10, 0, 3, 1.5)

        # ---- OBSTACLE 3: Medium jump ----
        self.create_gap(15, 0, 3, 1)

        # ---- OBSTACLE 4: Tall barrier to jump over ----
        self.create_barrier(20, 0, 1.5, 1)

        # ---- OBSTACLE 5: Two-step crouch section ----
        self.create_crouch_tunnel(25, 0, 5, 1.2)

        # ---- OBSTACLE 6: Wide gap ----
        self.create_gap(35, 0, 4, 1)

        # ---- OBSTACLE 7: Staggered blocks to climb ----
        self.create_stair_blocks(42, 0)

        # ---- OBSTACLE 8: Low then high ----
        self.create_low_high_combo(50, 0)

        # ---- OBSTACLE 9: Zigzag jump platforms ----
        self.create_zigzag_platforms(60, 0)

        # ---- OBSTACLE 10: Long crouch tunnel with varying height ----
        self.create_variable_tunnel(70, 0, 8)

        # ---- OBSTACLE 11: Teleporter trap ----
        self.create_teleporter_trap(82, 0)

        # ---- OBSTACLE 12: Final challenge - combination ----
        self.create_final_challenge(90, 0)

        # Create end goal
        goal_size = [5.0, 5.0, 3.0]
        goal_pos = (100, 0, 1.5)
        self.goal = self.game_world.create_object(
            goal_pos, "crate", goal_size, 0, GameObject
        )

    def create_gap(self, x, y, width, height):
        """Create a gap obstacle that requires jumping"""
        # Platform before gap
        platform1_size = [3.0, 5.0, 1.0]
        platform1_pos = (x - 2, y, height - 0.5)
        self.game_world.create_object(platform1_pos, "floor", platform1_size, 0, GameObject)

        # Platform after gap
        platform2_size = [3.0, 5.0, 1.0]
        platform2_pos = (x + width + 2, y, height - 0.5)
        self.game_world.create_object(platform2_pos, "floor", platform2_size, 0, GameObject)

    def create_low_ceiling(self, x, y, length, height):
        """Create a low ceiling that requires crouching"""
        # Platform below
        platform_size = [length, 5.0, 1.0]
        platform_pos = (x + length / 2, y, 0)
        self.game_world.create_object(platform_pos, "floor", platform_size, 0, GameObject)

        # Ceiling above
        ceiling_size = [length, 5.0, 0.5]
        ceiling_pos = (x + length / 2, y, height)
        self.game_world.create_object(ceiling_pos, "floor", ceiling_size, 0, GameObject)

    def create_barrier(self, x, y, height, width):
        """Create a tall barrier to jump over"""
        barrier_size = [width, 5.0, height]
        barrier_pos = (x, y, height / 2)
        self.game_world.create_object(barrier_pos, "red box", barrier_size, 0, GameObject)

        # Platforms on either side
        platform1_size = [3.0, 5.0, 1.0]
        platform1_pos = (x - 2, y, 0)
        self.game_world.create_object(platform1_pos, "floor", platform1_size, 0, GameObject)

        platform2_size = [3.0, 5.0, 1.0]
        platform2_pos = (x + 2, y, 0)
        self.game_world.create_object(platform2_pos, "floor", platform2_size, 0, GameObject)

    def create_crouch_tunnel(self, x, y, length, height):
        """Create a tunnel that requires crouching for a distance"""
        # Platform below
        platform_size = [length, 5.0, 1.0]
        platform_pos = (x + length / 2, y, 0)
        self.game_world.create_object(platform_pos, "floor", platform_size, 0, GameObject)

        # First ceiling section
        ceiling1_size = [2.0, 5.0, 0.5]
        ceiling1_pos = (x + 1, y, height)
        self.game_world.create_object(ceiling1_pos, "floor", ceiling1_size, 0, GameObject)

        # Second ceiling section - lower
        ceiling2_size = [length - 4, 5.0, 0.5]
        ceiling2_pos = (x + length / 2, y, height - 0.2)
        self.game_world.create_object(ceiling2_pos, "floor", ceiling2_size, 0, GameObject)

        # Third ceiling section
        ceiling3_size = [2.0, 5.0, 0.5]
        ceiling3_pos = (x + length - 1, y, height)
        self.game_world.create_object(ceiling3_pos, "floor", ceiling3_size, 0, GameObject)

    def create_stair_blocks(self, x, y):
        """Create staggered blocks that can be climbed with jumps"""
        heights = [0.5, 1.0, 1.5, 2.0, 1.5, 1.0]
        offsets = [0, 0, 0, 0, 0, 0]

        for i, (height, offset) in enumerate(zip(heights, offsets)):
            block_size = [2.0, 2.0, height]
            block_pos = (x + i * 2, y + offset, height / 2)
            self.game_world.create_object(block_pos, "crate", block_size, 0, GameObject)

    def create_low_high_combo(self, x, y):
        """Create an obstacle requiring first crouching then jumping"""
        # Low ceiling section
        self.create_low_ceiling(x, y, 3, 1.2)

        # Gap after low ceiling
        self.create_gap(x + 5, y, 2, 0)

    def create_zigzag_platforms(self, x, y):
        """Create zigzag platforms requiring jumps in different directions"""
        offsets = [0, 2, -2, 2, -2]
        widths = [3, 2, 2, 2, 3]

        for i, (offset, width) in enumerate(zip(offsets, widths)):
            platform_size = [width, 2.0, 0.5]
            platform_pos = (x + i * 3, y + offset, 0)
            self.game_world.create_object(platform_pos, "floor", platform_size, 0, GameObject)

    def create_variable_tunnel(self, x, y, length):
        """Create a tunnel with varying height that requires precise crouching"""
        # Platform below
        platform_size = [length, 5.0, 1.0]
        platform_pos = (x + length / 2, y, 0)
        self.game_world.create_object(platform_pos, "floor", platform_size, 0, GameObject)

        heights = [1.4, 1.2, 1.3, 1.1, 1.4, 1.2, 1.0, 1.3]
        segment_width = length / len(heights)

        for i, height in enumerate(heights):
            ceiling_size = [segment_width, 5.0, 0.5]
            ceiling_pos = (x + i * segment_width + segment_width / 2, y, height)
            self.game_world.create_object(ceiling_pos, "floor", ceiling_size, 0, GameObject)

    def create_teleporter_trap(self, x, y):
        """Create a trap with teleporters that send player backwards if touched"""
        # Main platform
        platform_size = [8.0, 5.0, 1.0]
        platform_pos = (x + 4, y, 0)
        self.game_world.create_object(platform_pos, "floor", platform_size, 0, GameObject)

        # Teleporters
        teleporter_positions = [(x + 2, y - 1, 0.5), (x + 4, y + 1, 0.5), (x + 6, y - 1, 0.5)]

        for pos in teleporter_positions:
            teleporter_size = [1.0, 1.0, 1.0]
            teleporter = self.game_world.create_object(
                pos, "teleporter", teleporter_size, 0, Teleporter
            )
            teleporter.is_collision_source = True

    def create_final_challenge(self, x, y):
        """Create a final challenge combining multiple obstacle types"""
        # First part: low ceiling
        self.create_low_ceiling(x, y, 2, 1.1)

        # Second part: small gap
        self.create_gap(x + 3, y, 1.5, 0)

        # Third part: barrier
        barrier_size = [0.5, 5.0, 1.2]
        barrier_pos = (x + 6, y, 0.6)
        self.game_world.create_object(barrier_pos, "red box", barrier_size, 0, GameObject)

        # Fourth part: final platform to goal
        platform_size = [3.0, 5.0, 1.0]
        platform_pos = (x + 8, y, 0)
        self.game_world.create_object(platform_pos, "floor", platform_size, 0, GameObject)

    def input_event(self, event):
        self.input_events[event] = True

    def new_player_object(self, game_object):
        if game_object.kind != 'player':
            return

        self.player = PandaBulletCharacterController(self.game_world.physics_world, self.render, game_object)

    def handle_input(self, events=None):
        # Debug output on click
        if 'toggleTexture' in events:
            print(f"Player position: {self.player.getPos()}")

        # Handle crouch toggle
        if 'crouch' in events:
            if self.player.isCrouching:
                self.player.stopCrouch()
            else:
                self.player.startCrouch()

    def forward(self, hpr, pos, distance):
        h, p, r = hpr
        x, y, z = pos
        q = Quat()
        q.setHpr((h, p, r))
        forward = q.getForward()
        delta_x = forward[0]
        delta_y = forward[1]
        delta_z = forward[2]
        return x + delta_x * distance, y + delta_y * distance, z + delta_z * distance

    def is_key_active(self, key):
        if key in self.input_events:
            return True

        if inputState.isSet(key):
            return True

        return False

    # In obstacle_game.py file
    # Modify the tick method in ObstacleGameController class

    def tick(self, task):
        # Handle escape key for mouse control
        if 'toggleMouseMove' in self.input_events:
            if self.CursorOffOn == 'Off':
                self.CursorOffOn = 'On'
                self.props.setCursorHidden(False)
            else:
                self.CursorOffOn = 'Off'
                self.props.setCursorHidden(True)

            self.win.requestProperties(self.props)

        # Send input events to subscribers
        pub.sendMessage('input', events=self.input_events)

        # Move player based on input
        self.move_player(self.input_events)

        # Check for object interaction
        picked_object = self.game_world.get_nearest(self.player.getPos(),
                                                    self.forward(self.player.getHpr(), self.player.getPos(), 5))
        if picked_object and picked_object.getNode() and picked_object.getNode().getPythonTag("owner"):
            picked_object.getNode().getPythonTag("owner").selected()

        # Handle mouse movement for camera rotation
        if self.CursorOffOn == 'Off':
            md = self.win.getPointer(0)
            x = md.getX()
            y = md.getY()

            if self.win.movePointer(0, base.win.getXSize() // 2, self.win.getYSize() // 2):
                z_rotation = self.camera.getH() - (x - self.win.getXSize() / 2) * self.SpeedRot
                x_rotation = self.camera.getP() - (y - self.win.getYSize() / 2) * self.SpeedRot
                if (x_rotation <= -90.1):
                    x_rotation = -90
                if (x_rotation >= 90.1):
                    x_rotation = 90

                self.player.setH(z_rotation)
                self.camera_pitch = x_rotation

        # Update camera position and rotation
        h = self.player.getH()
        p = self.camera_pitch
        r = self.player.getR()
        self.camera.setHpr(h, p, r)

        # Position camera at player's head level with slight offset
        x, y, z = self.player.getPos()
        if self.player.isCrouching:
            z_adjust = self.player.game_object.size[1]
        else:
            z_adjust = self.player.game_object.size[0]

        self.camera.set_pos(x, y, z + z_adjust)

        # Check if player reached the goal
        player_pos = self.player.getPos()
        if player_pos[0] > 95:
            print("Congratulations! You completed the obstacle course!")
            # Optional: exit the game after a delay
            # import sys
            # sys.exit()

        # Check if player has fallen below a threshold
        if player_pos[2] < -10:  # Adjust this value based on your level design
            print("Game Over! You fell off the course.")
            self.game_world.set_property("quit", True)  # This will trigger exit in the next frame

        # Update physics and game state
        dt = globalClock.getDt()
        self.player.update(dt)
        self.game_world.tick(dt)
        self.world_view.tick()

        # Check for quit command
        if self.game_world.get_property("quit"):
            sys.exit()

        # Clear input events for next frame
        self.input_events.clear()
        return Task.cont

    def move_player(self, events=None):
        speed = Vec3(0, 0, 0)
        delta = 5.0

        if self.is_key_active('moveForward'):
            speed.setY(delta)

        if self.is_key_active('moveBackward'):
            speed.setY(-delta)

        if self.is_key_active('moveLeft'):
            speed.setX(-delta)

        if self.is_key_active('moveRight'):
            speed.setX(delta)

        if self.is_key_active('jump'):
            self.player.startJump(2)

        self.player.setLinearMovement(speed)


if __name__ == '__main__':
    game = ObstacleGameController()