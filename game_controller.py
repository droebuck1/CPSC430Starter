from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from direct.showbase.ShowBaseGlobal import globalClock
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

controls = {
    'escape': 'toggleMouseMove',
    'space': 'jump',
    'r': 'restart',
}

held_keys = {
    'w': 'moveForward',
    's': 'moveBackward',
    'a': 'moveLeft',
    'd': 'moveRight',
    'control': 'crouch',
}


class Main(ShowBase):
    def go(self):






















        self.disableMouse()
        self.render.setShaderAuto()

        # Set up debug
        self.debugNode = BulletDebugNode('Debug')
        self.debugNode.showWireframe(True)
        self.debugNode.showConstraints(True)
        self.debugNode.showBoundingBoxes(False)
        self.debugNode.showNormals(False)
        debugNP = self.render.attachNewNode(self.debugNode)
        debugNP.show()

        # Set up game world
        self.game_world = GameWorld(self.debugNode)
        self.world_view = WorldView(self.game_world)

        # Set up collision traverser
        self.cTrav = CollisionTraverser()

        # Player variables
        self.player = None
        self.player_obj = None
        self.start_position = Point3(0, 0, 2)

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

        # Subscribe to events
        pub.subscribe(self.handle_input, 'input')
        pub.subscribe(self.new_player_object, 'create')

        # Initialize the obstacle course
        self.create_obstacle_course()

        # Add game loop task
        self.taskMgr.add(self.game_loop, "GameLoop")

    def create_obstacle_course(self):
        # Reset any existing world
        self.game_world.reset()

        # Create player
        player_size = [2.0, 1.0, 0.5, 0.5]  # walkHeight, crouchHeight, stepHeight, radius
        self.player_obj = self.game_world.create_object(
            self.start_position, "player", player_size, 1.0, Player
        )

        # Create player controller
        self.player = PandaBulletCharacterController(self.game_world.physics_world, self.render, self.player_obj)

        # Create floor
        floor_size = [150.0, 10.0, 0.5]
        floor_pos = (50, 0, 0)
        self.floor = self.game_world.create_object(
            floor_pos, "floor", floor_size, 0, GameObject
        )

        # Create 15 varied obstacles
        self.create_obstacles()

        # Create finish line
        goal_size = [2.0, 10.0, 3.0]
        goal_pos = (130, 0, 1.5)
        self.goal = self.game_world.create_object(
            goal_pos, "goal", goal_size, 0, GameObject
        )

        # Set up checkpoints and finish line markers
        self.create_checkpoint_markers()

        # Reset camera
        self.camera_pitch = 0

    def create_obstacles(self):
        # This will create 15 different obstacles at various positions
        obstacle_types = [
            self.create_jump_obstacle,
            self.create_crouch_obstacle,
            self.create_step_up_obstacle,
            self.create_combined_obstacle,
            self.create_narrow_passage
        ]

        # Space intervals between obstacles
        start_pos = 10
        interval = 8

        for i in range(15):
            pos_x = start_pos + i * interval
            # Choose a random obstacle type
            obstacle_func = random.choice(obstacle_types)
            obstacle_func(pos_x)

    def create_jump_obstacle(self, pos_x):
        # Create an obstacle that requires jumping over
        height = random.uniform(0.8, 1.2)
        width = random.uniform(0.5, 1.5)

        obstacle_size = [width, 5.0, height]
        obstacle_pos = (pos_x, 0, height / 2)

        self.game_world.create_object(
            obstacle_pos, "jump_obstacle", obstacle_size, 0, GameObject
        )

    def create_crouch_obstacle(self, pos_x):
        # Create an obstacle that requires crouching under
        length = random.uniform(2.0, 3.5)
        height = 1.3  # Low enough to require crouching

        # Ground platform
        platform_size = [length, 5.0, 0.2]
        platform_pos = (pos_x, 0, 0.1)

        self.game_world.create_object(
            platform_pos, "platform", platform_size, 0, GameObject
        )

        # Ceiling that forces player to crouch
        ceiling_size = [length, 5.0, 0.2]
        ceiling_pos = (pos_x, 0, height)

        self.game_world.create_object(
            ceiling_pos, "ceiling", ceiling_size, 0, GameObject
        )

    def create_step_up_obstacle(self, pos_x):
        # Create a stepped platform to climb
        step_count = random.randint(2, 3)
        step_width = 1.0
        step_height = 0.4

        for i in range(step_count):
            step_size = [step_width, 5.0, step_height]
            step_pos = (pos_x + i * step_width, 0, i * step_height + step_height / 2)

            self.game_world.create_object(
                step_pos, "step", step_size, 0, GameObject
            )

    def create_combined_obstacle(self, pos_x):
        # Create a combined obstacle requiring both jumping and crouching
        # First a platform to jump on
        platform_size = [3.0, 5.0, 0.5]
        platform_pos = (pos_x, 0, 0.5)

        self.game_world.create_object(
            platform_pos, "platform", platform_size, 0, GameObject
        )

        # Then a ceiling to crouch under
        ceiling_size = [2.0, 5.0, 0.2]
        ceiling_pos = (pos_x + 0.5, 0, 1.5)

        self.game_world.create_object(
            ceiling_pos, "ceiling", ceiling_size, 0, GameObject
        )

    def create_narrow_passage(self, pos_x):
        # Create a narrow passage with walls
        passage_length = random.uniform(2.0, 4.0)

        # Left wall
        left_wall_size = [passage_length, 0.2, 2.0]
        left_wall_pos = (pos_x + passage_length / 2, -1.0, 1.0)

        self.game_world.create_object(
            left_wall_pos, "wall", left_wall_size, 0, GameObject
        )

        # Right wall
        right_wall_size = [passage_length, 0.2, 2.0]
        right_wall_pos = (pos_x + passage_length / 2, 1.0, 1.0)

        self.game_world.create_object(
            right_wall_pos, "wall", right_wall_size, 0, GameObject
        )

    def create_checkpoint_markers(self):
        # Create checkpoint markers every 20 units
        for i in range(1, 7):
            marker_size = [0.5, 5.0, 3.0]
            marker_pos = (i * 20, 0, 1.5)

            checkpoint = self.game_world.create_object(
                marker_pos, "checkpoint", marker_size, 0, GameObject
            )

    def input_event(self, event):
        self.input_events[event] = True

    def handle_input(self, events=None):
        if 'restart' in events:
            self.restart_game()

    def restart_game(self):
        print("Restarting game...")
        self.player.setPos(self.start_position)
        self.player.setLinearVelocity(Vec3(0, 0, 0))

    def new_player_object(self, game_object):
        if game_object.kind != 'player':
            return

        self.player_obj = game_object

    def game_loop(self, task):
        # Handle escape key
        if 'toggleMouseMove' in self.input_events:
            if self.CursorOffOn == 'Off':
                self.CursorOffOn = 'On'
                self.props.setCursorHidden(False)
            else:
                self.CursorOffOn = 'Off'
                self.props.setCursorHidden(True)

            self.win.requestProperties(self.props)

        # Send input events
        pub.sendMessage('input', events=self.input_events)

        # Move player based on input
        self.move_player()

        # Process mouse for camera control
        if self.CursorOffOn == 'Off':
            md = self.win.getPointer(0)
            x = md.getX()
            y = md.getY()

            if self.win.movePointer(0, self.win.getXSize() // 2, self.win.getYSize() // 2):
                z_rotation = self.player.getH() - (x - self.win.getXSize() / 2) * self.SpeedRot
                x_rotation = self.camera.getP() - (y - self.win.getYSize() / 2) * self.SpeedRot

                # Clamp camera pitch to avoid flipping
                if x_rotation <= -85:
                    x_rotation = -85
                if x_rotation >= 85:
                    x_rotation = 85

                self.player.setH(z_rotation)
                self.camera_pitch = x_rotation

        # Update camera
        self.update_camera()

        # Update game components
        dt = globalClock.getDt()
        self.player.update(dt)
        self.game_world.tick(dt)
        self.world_view.tick()

        # Check if player reached the goal
        player_pos = self.player.getPos()
        if player_pos[0] > 125:
            print("Congratulations! You completed the obstacle course!")

        # Check for player falling off the map
        if player_pos[2] < -5:
            print("You fell off the course! Restarting...")
            self.restart_game()

        # Check progress and show checkpoints
        checkpoint = int(player_pos[0] / 20)
        if checkpoint >= 1 and checkpoint <= 6:
            print(f"Checkpoint {checkpoint}/6 reached!")

        # Clear input events for next frame
        self.input_events.clear()

        # Check if game should quit
        if self.game_world.get_property("quit"):
            sys.exit()

        return Task.cont

    def update_camera(self):
        # Update camera position and rotation to follow player
        h = self.player.getH()
        p = self.camera_pitch
        r = self.player.getR()
        self.camera.setHpr(h, p, r)

        # Position camera at player's head level
        player_pos = self.player.getPos()

        if self.player.isCrouching:
            z_adjust = self.player_obj.size[1]  # crouch height
        else:
            z_adjust = self.player_obj.size[0]  # walk height

        # Camera follows player with slight offset
        self.camera.setPos(player_pos[0], player_pos[1], player_pos[2] + z_adjust * 0.8)

    def move_player(self):
        speed = Vec3(0, 0, 0)
        delta = 5.0  # Movement speed

        if inputState.isSet('moveForward'):
            speed.setY(delta)

        if inputState.isSet('moveBackward'):
            speed.setY(-delta)

        if inputState.isSet('moveLeft'):
            speed.setX(-delta)

        if inputState.isSet('moveRight'):
            speed.setX(delta)

        if inputState.isSet('crouch') and not self.player.isCrouching:
            self.player.startCrouch()
        elif not inputState.isSet('crouch') and self.player.isCrouching:
            self.player.stopCrouch()

        if 'jump' in self.input_events:
            self.player.startJump(2)

        self.player.setLinearMovement(speed)

    def run_game(self):
        # Start the game
        print("Welcome to the Obstacle Course!")
        print("Controls:")
        print("  WASD - Move")
        print("  Space - Jump")
        print("  Control - Crouch")
        print("  R - Restart")
        print("  Escape - Toggle mouse cursor")
        print("\nComplete all 15 obstacles to reach the finish line!")

        self.run()


if __name__ == '__main__':
    main = Main()
    main.go()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
