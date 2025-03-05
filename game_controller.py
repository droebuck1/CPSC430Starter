from direct.showbase.InputStateGlobal import inputState
from direct.showbase.ShowBase import ShowBase
from direct.showbase.ShowBaseGlobal import globalClock
from direct.task import Task
from panda3d.bullet import BulletDebugNode
from panda3d.core import CollisionNode, GeomNode, CollisionRay, CollisionHandlerQueue, CollisionTraverser, MouseButton, \
    WindowProperties, Quat
from pubsub import pub
import sys

from world_view import WorldView
from game_world import GameWorld

controls = {
    'escape': 'toggleMouseMove',
    't': 'toggleTexture',
    'mouse1': 'toggleTexture',
}

held_keys = {
    'w': 'moveForward',
    's': 'moveBackward',
    'a': 'moveLeft',
    'd': 'moveRight',
}

class Main(ShowBase):
    def go(self):
        self.cTrav = CollisionTraverser()

        self.game_world.load_world()

        picker_node = CollisionNode('mouseRay')
        picker_np = self.camera.attachNewNode(picker_node)
        picker_node.setFromCollideMask(GeomNode.getDefaultCollideMask())
        picker_node.set_into_collide_mask(0)
        self.pickerRay = CollisionRay()
        picker_node.addSolid(self.pickerRay)
        # picker_np.show()
        self.rayQueue = CollisionHandlerQueue()
        self.cTrav.addCollider(picker_np, self.rayQueue)

        self.taskMgr.add(self.tick)

        self.input_events = {}
        for key in controls:
            self.accept(key, self.input_event, [controls[key]])

        for key in held_keys:
            inputState.watchWithModifiers(held_keys[key], key)

        self.SpeedRot = 0.05
        self.CursorOffOn = 'Off'
        self.props = WindowProperties()
        self.props.setCursorHidden(True)
        self.win.requestProperties(self.props)

        self.run()

    def get_nearest_object(self):
        self.pickerRay.setFromLens(self.camNode, 0, 0)
        if self.rayQueue.getNumEntries() > 0:
            self.rayQueue.sortEntries()
            entry = self.rayQueue.getEntry(0)
            picked_np = entry.getIntoNodePath()
            picked_np = picked_np.findNetTag('selectable')
            if not picked_np.isEmpty() and picked_np.getPythonTag("owner"):
                return picked_np.getPythonTag("owner")

        return None

    def input_event(self, event):
        self.input_events[event] = True

    def tick(self, task):
        if 'toggleMouseMove' in self.input_events:
            if self.CursorOffOn == 'Off':
                self.CursorOffOn = 'On'
                self.props.setCursorHidden(False)
            else:
                self.CursorOffOn = 'Off'
                self.props.setCursorHidden(True)

            self.win.requestProperties(self.props)

        pub.sendMessage('input', events=self.input_events)

        picked_object = self.get_nearest_object()
        if picked_object:
            picked_object.selected()

        if self.CursorOffOn == 'Off':
            # TODO: camera mouse rotation needs to work with the physics object
            # we only want z rotations translated to the player.
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

                self.player.z_rotation = z_rotation
                self.player.x_rotation = x_rotation

        h = self.player.z_rotation
        p = self.player.x_rotation
        r = self.player.y_rotation
        self.camera.setHpr(h, p, r)

        # This seems to work to prevent seeing into objects the player collides with.
        # It moves the camera a bit back from the center of the player object.
        q = Quat()
        q.setHpr((h, p, r))
        forward = q.getForward()
        delta_x = -forward[0]
        delta_y = -forward[1]
        delta_z = -forward[2]
        x, y, z = self.player.position
        z_adjust = self.player.size[1]/2
        distance_factor = 0.5
        self.camera.set_pos(x + delta_x*distance_factor, y + delta_y*distance_factor, z + delta_z*distance_factor + z_adjust)

        self.game_world.tick(globalClock.getDt())
        self.player_view.tick()

        if self.game_world.get_property("quit"):
            sys.exit()

        self.input_events.clear()
        return Task.cont

    def new_player_object(self, game_object):
        if game_object.kind != 'player':
            return

        self.player = game_object

    def __init__(self):
        ShowBase.__init__(self)

        self.disableMouse()
        self.render.setShaderAuto()

        self.instances = []
        self.player = None
        pub.subscribe(self.new_player_object, 'create')

        # Debug visualization for physics objects
        debugNode = BulletDebugNode('Debug')
        debugNode.showWireframe(True)
        debugNode.showConstraints(True)
        debugNode.showBoundingBoxes(False)
        debugNode.showNormals(False)
        debugNP = render.attachNewNode(debugNode)
        debugNP.show()

        # create model and view
        self.game_world = GameWorld(debugNode)
        self.player_view = WorldView(self.game_world)


if __name__ == '__main__':
    main = Main()
    main.go()
