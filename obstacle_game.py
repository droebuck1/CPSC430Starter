from direct.showbase.ShowBase import ShowBase
from direct.showbase.ShowBaseGlobal import globalClock
from direct.task import Task
from panda3d.bullet import BulletDebugNode
from panda3d.core import WindowProperties, Vec3, Point3, CollisionTraverser
from direct.showbase.InputStateGlobal import inputState
from pubsub import pub

from kcc import PandaBulletCharacterController
from game_world import GameWorld
from world_view import WorldView
from game_object import GameObject
from player import Player

controls = {
    'escape': 'toggleMouseMove',
    'space': 'jump',
    'c': 'crouch',
}

held_keys = {
    'w': 'moveForward',
    's': 'moveBackward',
    'a': 'moveLeft',
    'd': 'moveRight',
}


class ObstacleGame(ShowBase):
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

        # Create player manually (no level file)
        player_size = [2.0, 1.0, 0.5, 0.5]  # walkHeight, crouchHeight, stepHeight, radius
        player_pos = (0, 0, 2)
        self.player_obj = self.game_world.create_object(
            player_pos, "player", player_size, 1.0, Player
        )

        # Create obstacles
        # Tall obstacle (jump over)
        tall_obstacle_size = [1.0, 1.0, 1.0]
        tall_obstacle_pos = (5, 0, 0.5)
        self.tall_obstacle = self.game_world.create_object(
            tall_obstacle_pos, "red box", tall_obstacle_size, 0, GameObject
        )

        # Low obstacle (crawl under)
        ceiling_size = [10.0, 1.0, 0.5]
        ceiling_pos = (12, 0, 2.0)
        self.ceiling = self.game_world.create_object(
            ceiling_pos, "floor", ceiling_size, 0, GameObject
        )

        # Floor
        floor_size = [40.0, 10.0, 0.5]
        floor_pos = (0, 0, 0)
        self.floor = self.game_world.create_object(
            floor_pos, "floor", floor_size, 0, GameObject
        )

        # End goal to show completion
        goal_size = [1.0, 3.0, 3.0]
        goal_pos = (20, 0, 1.5)
        self.goal = self.game_world.create_object(
            goal_pos, "crate", goal_size, 0, GameObject
        )

        # Set up player controller
        self.player = PandaBulletCharacterController(self.game_world.physics_world, self.render, self.player_obj)

        # Set up camera
        self.taskMgr.add(self.update_camera, "UpdateCamera")

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
        self.taskMgr.add(self.game_loop, "GameLoop")

    def input_event(self, event):
        self.input_events[event] = True

    def handle_input(self, events=None):
        if 'crouch' in events:
            if self.player.isCrouching:
                self.player.stopCrouch()
            else:
                self.player.startCrouch()

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
        self.move_player(self.input_events)

        # Process mouse for camera control
        if self.CursorOffOn == 'Off':
            md = self.win.getPointer(0)
            x = md.getX()
            y = md.getY()

            if self.win.movePointer(0, self.win.getXSize() // 2, self.win.getYSize() // 2):
                z_rotation = self.player.getH() - (x - self.win.getXSize() / 2) * self.SpeedRot
                x_rotation = self.camera.getP() - (y - self.win.getYSize() / 2) * self.SpeedRot
                if x_rotation <= -90.1:
                    x_rotation = -90
                if x_rotation >= 90.1:
                    x_rotation = 90

                self.player.setH(z_rotation)
                self.camera_pitch = x_rotation

        # Update game components
        dt = globalClock.getDt()
        self.player.update(dt)
        self.game_world.tick(dt)
        self.world_view.tick()

        # Check if player reached the goal
        player_pos = self.player.getPos()
        if player_pos[0] > 20:
            # Print victory message when reaching the goal
            print("Congratulations! You completed the obstacle course!")

        # Clear input events for next frame
        self.input_events.clear()

        return Task.cont

    def update_camera(self, task):
        # Update camera position and rotation to follow player
        h = self.player.getH()
        p = self.camera_pitch
        r = self.player.getR()
        self.camera.setHpr(h, p, r)

        # Position camera at player's head level with slight offset
        player_pos = self.player.getPos()
        z_adjust = 1.7  # head level
        self.camera.setPos(player_pos[0], player_pos[1], player_pos[2] + z_adjust)

        return Task.cont

    def move_player(self, events=None):
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

        if 'crouch' in events:
            if self.player.isCrouching:
                self.player.stopCrouch()
            else:
                self.player.startCrouch()

        if 'jump' in events:
            self.player.startJump(2)

        self.player.setLinearMovement(speed)


if __name__ == '__main__':
    game = ObstacleGame()
    game.run()
