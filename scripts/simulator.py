import threading
try:
    import Queue as queue
except ImportError:
    import queue
from collections import deque
from time import sleep, clock
from xmlreader import XMLReader
import helpers
import math
import sys
import time
import pose
import simobject
import supervisor
from quadtree import QuadTree, Rect
import bluetooth
from pprint import pprint

PAUSE = 0
RUN = 1
RUN_ONCE = 2
DRAW_ONCE = 3

class Simulator(threading.Thread):
    """The simulator manages simobjects and their collisions, commands supervisors
       and draws the world using the supplied *renderer*.
       
       The simulator runs in a separate thread. None of its functions are thread-safe,
       and should never be called directly from other objects (except for the functions
       inherited from `threading.Thread`). The communication with the simulator
       should be done through its *in_queue* and *out_queue*. See :ref:`ui-sim-queue`.
       
       :param renderer: The renderer that will be used to draw the world.
                        The simulator will assume control of the renderer.
                        The renderer functions also have to be considered thread-unsafe.
       :type renderer: :class:`~renderer.Renderer`
       :param in_queue: The queue that is used to send events to the simulator.
       :type in_queue: :class:`Queue.Queue`
    """
    
    __nice_colors = (0x55AAEE, 0x66BB22, 0xFFBB22, 0xCC66AA,
                     0x77CCAA, 0xFF7711, 0xFF5555, 0x55CC88)

    def __init__(self, renderer, in_queue):
        """Create a simulator with *renderer* and *in_queue*
        """
        super(Simulator, self).__init__()
        print("Estableciendo conexion BT")
        addr = "20:15:11:02:89:17"  # Device Address
        port = 1  # RFCOMM port
        BT = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
        BT.connect((addr, port))
        sleep(1)
        self.BTcon = BT
        #Attributes
        self.__stop = False
        self.__state = PAUSE
        self.__renderer = renderer
        self.__center_on_robot = False
        self.__orient_on_robot = False
        self.__show_sensors = True
        self.__draw_supervisors = False
        self.__show_tracks = True
        
        self.__in_queue = in_queue
        self._out_queue = queue.Queue()

        # Zoom on scene - Move to read_config later
        self.__time_multiplier = 1.0
        self.__time = 0.0

        # Plots
        self.plot_expressions = []

        # World objects
        self.__robots = []
        self.__trackers = []
        self.__obstacles = []
        self.__supervisors = []
        self.__background = []
        self.__zoom_default = 1

        self.__world = None
        
        self.__log_queue = deque()
        
        # Internal objects
        self.__qtree = None

    def read_config(self, filename):
        '''Load in the objects from the world XML file '''

        self.log('reading initial configuration')
        try:
            self.__world = XMLReader(filename, 'simulation').read()
        except Exception as e:
            raise Exception('[Simulator.read_config] Failed to parse ' + filename \
                + ': ' + str(e))
        else:
            self.__supervisor_param_cache = None
            self.__center_on_robot = False
            self.__construct_world()

    def __construct_world(self):
        """Creates objects previously loaded from the world xml file.
           
           This function uses the world in ``self.__world``.
           
           All the objects will be created anew, including robots and supervisors.
           All of the user's code is reloaded.
        """
        if self.__world is None:
            return

        helpers.unload_user_modules()

        self.__state = DRAW_ONCE            
            
        self.__robots = []
        self.__obstacles = []
        self.__supervisors = []
        self.__background = []
        self.__trackers = []
        self.__qtree = None
        
        for thing in self.__world:
            thing_type = thing[0]
            if thing_type == 'robot':
                robot_type, supervisor_type, robot_pose, robot_color  = thing[1:5]
                try:
                    # Create robot
                    robot_class = helpers.load_by_name(robot_type,'robots')
                    robot = robot_class(pose.Pose(robot_pose))
                    if robot_color is not None:
                        robot.set_color(robot_color)
                    elif len(self.__robots) < 8:
                        robot.set_color(self.__nice_colors[len(self.__robots)])
                        
                    # Create supervisor
                    sup_class = helpers.load_by_name(supervisor_type,'supervisors')
                    
                    info = robot.get_info()
                    info.color = robot.get_color()
                    supervisor = sup_class(robot.get_pose(), info)
                    supervisor.set_logqueue(self.__log_queue)
                    name = "Robot {}: {}".format(len(self.__robots)+1, sup_class.__name__)
                    if self.__supervisor_param_cache is not None and \
                       len(self.__supervisor_param_cache) > len(self.__supervisors):
                        supervisor.set_parameters(self.__supervisor_param_cache[len(self.__supervisors)])
                    self._out_queue.put(("make_param_window",
                                            (robot, name,
                                             supervisor.get_ui_description())))
                    self.__supervisors.append(supervisor)
                    
                    # append robot after supervisor for the case of exceptions
                    self.__robots.append(robot)
                    
                    # Create trackers
                    self.__trackers.append(simobject.Path(robot.get_pose(),robot))
                    self.__trackers[-1].set_color(robot.get_color())
                except:
                    self.log("[Simulator.construct_world] Robot creation failed!")
                    raise
                    #raise Exception('[Simulator.construct_world] Unknown robot type!')
            elif thing_type == 'obstacle':
                obstacle_pose, obstacle_coords, obstacle_color = thing[1:4]
                if obstacle_color is None:
                    obstacle_color = 0xFF0000
                self.__obstacles.append(
                    simobject.Polygon(pose.Pose(obstacle_pose),
                                      obstacle_coords,
                                      obstacle_color))
            elif thing_type == 'marker':
                obj_pose, obj_coords, obj_color = thing[1:4]
                if obj_color is None:
                    obj_color = 0x00FF00
                self.__background.append(
                    simobject.Polygon(pose.Pose(obj_pose),
                                      obj_coords,
                                      obj_color))
            else:
                raise Exception('[Simulator.construct_world] Unknown object: '
                                + str(thing_type))
                                
        self.__time = 0.0
        if not self.__robots:
            raise Exception('[Simulator.construct_world] No robot specified!')
        else:
            self.__recalculate_default_zoom()
            if not self.__center_on_robot:
                self.focus_on_world()
            self.__supervisor_param_cache = None
            self.step_simulation()
            
        self._out_queue.put(('reset',()))

    def __recalculate_default_zoom(self):
        """Calculate the zoom level that will show the robot at about 10% its size
        """
        maxsize = 0
        for robot in self.__robots:
            xmin, ymin, xmax, ymax = robot.get_bounds()
            maxsize = max(maxsize,math.sqrt(float(xmax-xmin)**2 + float(ymax-ymin)**2))
        if maxsize == 0:
            self.__zoom_default = 1
        else:
            self.__zoom_default = max(self.__renderer.size)/maxsize/10
            
    def __reset_world(self):
        """Resets the world and objects to starting position.
        
           All the user's code will be reloaded.
        """
        if self.__world is None:
            return
        self.__supervisor_param_cache = [sv.get_parameters() for sv in self.__supervisors ]
        self.__construct_world()

    def mandar_velocidades(self, BT, inputs):
        def sign(x):
            return (1 - (x<=0))

        if (sign(inputs[0]) == 1) and (sign(inputs[1]) == 1):
            hexa = '\x55'

        if (sign(inputs[0]) == 0) and (sign(inputs[1]) == 0):
            hexa = '\xaa'

        if (sign(inputs[0]) == 0) and (sign(inputs[1]) == 1):
            hexa = '\x5a'

        if (sign(inputs[0]) == 1) and (sign(inputs[1]) == 0):
            hexa = '\xa5'
        rpml = abs(inputs[0])*(60/(2*math.pi))
        rpmr = abs(inputs[1])*(60/(2*math.pi))
        if inputs[0] == 0:
            vl_new = 0
        else:
            #vl_new = chr(int(round(((25*abs(inputs[0] - 160))*2*math.pi)/(60*11))))
            vl_new = (11*rpml + 160)/25
        if inputs[1] == 0:
            vr_new = 0
        else:
            #vr_new = chr(int(round(((25*abs(inputs[1] - 160))*2*math.pi)/(60*11))))
            vr_new = (11 * rpmr + 160) / 25
        print(str(inputs[0]))
        print(str(inputs[1]))
        BT.send(hexa)
        BT.send(chr(int(round(vl_new))))
        BT.send(chr(int(round(vr_new))))
        BT.send('\n')
        #print('vl_new:' + str((int(round(((25*abs(inputs[0] - 160))*2*math.pi)/(60*11))))))
        #print('vr_new:' + str((int(round(((25*abs(inputs[1] - 160))*2*math.pi)/(60*11))))))
        print('vl_new:' + str(int(round(vl_new))))
        print('vr_new:' + str(int(round(vr_new))))
        return vl_new,vr_new

    def run(self):
        """Start the thread. In the beginning there's no world, no obstacles
           and no robots.
           
           The simulator will try to draw the world independently of the
           simulation status, so that the commands from the UI get processed.
        """
        self.log('starting simulator thread')

        time_constant = 0.01 # 20 milliseconds
        
        self.__renderer.clear_screen() #create a white screen
        self.__update_view()
        primera_vuelta = True
        while not self.__stop:
            #print("__time:")
            #print(self.__time)
            try:
                #sleep(time_constant/self.__time_multiplier)

                self.__process_queue()
                if self.__state == RUN or \
                   self.__state == RUN_ONCE:

                    self.__time += time_constant
                    # First, move robots
                    for i, robot in enumerate(self.__robots):
                        robot.move(time_constant)
                        #robot.move(time.time() - self.__time)
                        self.__trackers[i].add_point(robot.get_pose())

                    self.fwd_logqueue()

                    # Second, check for collisions and update sensors
                    if self.__check_collisions():
                        print("Collision detected!")
                        self.__state = DRAW_ONCE

                    self.fwd_logqueue()

                    # Now calculate supervisor outputs for the new position
                    for i, supervisor in enumerate(self.__supervisors):
                        """ACA ESTA EL PUTO QUE LLAMA A LAS FUNCIONES"""
                        info = self.__robots[i].get_info()  #de aca saca el estado del robot (x,y,theta,v,etc)

                        inputs = supervisor.execute(info, time_constant)  #el execute es el calculo de error y la accion de control.
                                                                        #Ya devuelve el resultado de uni2diff
                        #print("inputs en simulator:")
                        #pprint(inputs)
                        if primera_vuelta == True:
                            primera_vuelta = False
                        else:
                            #print("MANDO VELOCIDADES")
                            #print(" ")
                            self.mandar_velocidades(self.BTcon, inputs)
                        #self.BTcon.send("Z  \n")
                        self.__robots[i].set_inputs(inputs)
                        self.fwd_logqueue()

                    if self.plot_expressions:
                        self.announce_plotables()

                # Draw to buffer-bitmap
                # Note that if the robot moves immediately after calculation,
                # the supervisor would draw the previous state.
                if self.__state != PAUSE:
                    self.__draw()

                if self.__state == DRAW_ONCE or \
                   self.__state == RUN_ONCE:
                    self.pause_simulation()

                self.fwd_logqueue()
            
            except Exception as e:
                self._out_queue.put(("exception",sys.exc_info()))
                self.pause_simulation()
                self.fwd_logqueue()

    def __draw(self):
        """Draws the world and items in it.
        
           This will draw the markers, the obstacles,
           the robots, their tracks and their sensors
        """
        
        if self.__robots and self.__center_on_robot:
            # Temporary fix - center onto first robot
            robot = self.__robots[0]
            if self.__orient_on_robot:
                self.__renderer.set_screen_center_pose(robot.get_pose())
            else:
                self.__renderer.set_screen_center_pose(pose.Pose(robot.get_pose().x, robot.get_pose().y, 0.0))

        self.__renderer.clear_screen()

        if self.__draw_supervisors:
            for supervisor in self.__supervisors:
                supervisor.draw_background(self.__renderer)

        for bg_object in self.__background:
            bg_object.draw(self.__renderer)
        for obstacle in self.__obstacles:
            obstacle.draw(self.__renderer)

        # Draw the robots, trackers and sensors after obstacles
        if self.__show_tracks:
            for tracker in self.__trackers:
                tracker.draw(self.__renderer)
        for robot in self.__robots:
            robot.draw(self.__renderer)
            if self.__show_sensors:
                robot.draw_sensors(self.__renderer)

        if self.__draw_supervisors:
            for supervisor in self.__supervisors:
                supervisor.draw_foreground(self.__renderer)

        # update view
        self.__update_view()

    def __update_view(self):
        """Signal the UI that the drawing process is finished,
           and it is safe to access the renderer.
        """
        self._out_queue.put(('update_view',()))
        self._out_queue.join() # wait until drawn

    def __draw_once(self):
        if self.__state == PAUSE:
            self.__state = DRAW_ONCE
            
    def refresh(self):
        self.__draw_once()
        
    def focus_on_world(self):
        """Scale the view to include all of the world (including robots)"""
        def include_bounds(bounds, o_bounds):
            xl, yb, xr, yt = bounds
            xlo, ybo, xro, yto = o_bounds
            if xlo < xl: xl = xlo
            if xro > xr: xr = xro
            if ybo < yb: yb = ybo
            if yto > yt: yt = yto
            return xl, yb, xr, yt
        
        def bloat_bounds(bounds, factor):
            xl, yb, xr, yt = bounds
            w = xr-xl
            h = yt-yb
            factor = (factor-1)/2.0
            return xl - w*factor, yb - h*factor, xr + w*factor, yt + h*factor
            
        self.__center_on_robot = False
        bounds = self.__robots[0].get_bounds()
        for robot in self.__robots:
            bounds = include_bounds(bounds, bloat_bounds(robot.get_bounds(),4))
        for obstacle in self.__obstacles:
            bounds = include_bounds(bounds, obstacle.get_bounds())
        xl, yb, xr, yt = bounds
        self.__renderer.set_view_rect(xl,yb,xr-xl,yt-yb)
        self.__draw_once()

    def focus_on_robot(self, rotate = True):
        """Center the view on the (first) robot and follow it.
        
           If *rotate* is true, also follow the robot's orientation.
        """
        self.__center_on_robot = True
        self.__orient_on_robot = rotate
        self.__draw_once()

    def show_sensors(self, show = True):
        """Show or hide the robots' sensors on the simulation view
        """
        self.__show_sensors = show
        self.__draw_once()

    def show_tracks(self, show = True):
        """Show/hide tracks for every robot on simulator view"""
        self.__show_tracks = show
        self.__draw_once()

    def show_supervisors(self, show = True):
        """Show/hide the information from the supervisors"""
        self.__draw_supervisors = show
        self.__draw_once()

    def show_grid(self, show=True):
        """Show/hide gridlines on simulator view"""
        self.__renderer.show_grid(show)
        self.__draw_once()

    def adjust_zoom(self,factor):
        """Zoom the view by *factor*"""
        self.__renderer.set_zoom_level(self.__zoom_default*factor)
        self.__draw_once()
        
    def apply_parameters(self,robot,parameters):
        """Apply *parameters* to the supervisor of *robot*.
        
        The parameters have to correspond to the requirements of the supervisor,
        as specified in :meth:`supervisor.Supervisor.get_ui_description`
        """
        index = self.__robots.index(robot)
        if index < 0:
            self.log("Robot not found")
        else:
            self.__supervisors[index].set_parameters(parameters)
        self.__draw_once()

    def add_plotable(self,expression):
        """A plotable is an expression that yields a numerical
           value. It is evaluated every cycle and the values are announced by the
           simulator in the ``plot_update`` signal.
           
           The expression has access to the following variables:
           ``robot`` - the first robot in the scene
           ``supervisor`` - the supervisor of this robot
           ``math`` - the math module
           """
        if expression is not None and expression not in self.plot_expressions:
            self.plot_expressions.append(expression)

    def announce_plotables(self):
        plots = {'time':self.__time}
        for expr in self.plot_expressions:
            try:
                plots[expr] = \
                    eval(expr,{},
                         {'robot':self.__robots[0],
                          'supervisor':self.__supervisors[0],
                          'math':math})
            except Exception as e:
                self.log(str(e))
                plots[expr] = 0
        self._out_queue.put(('plot_update',(plots,)))

    def plotables(self):
        """ Returns a list with some examples of plotables"""
        return {
            "Robot's X coordinate":"robot.get_pose().x",
            "Robot's Y coordinate":"robot.get_pose().y",
            "Robot's orientation":"robot.get_pose().theta",
            "Robot's orientation (degrees)":"robot.get_pose().theta*57.29578",
            "Estimated X coordinate":"supervisor.pose_est.x",
            "Estimated Y coordinate":"supervisor.pose_est.y",
            "Estimated orientation":"supervisor.pose_est.theta",
            "Estimated orientation (degrees)":"supervisor.pose_est.theta*57.29578",
            "Left wheel speed":"robot.ang_velocity[0]",
            "Right wheel speed":"robot.ang_velocity[1]",
            "Linear velocity":"robot.diff2uni(robot.ang_velocity)[0]",
            "Angular velocity":"robot.diff2uni(robot.ang_velocity)[1]"
            # The possibilities are infinite
            #"":"",
            }

    # Stops the thread
    def stop(self):
        """Stop the simulator thread when the entire program is closed"""
        self.log('stopping simulator thread')
        self.__stop = True
        self._out_queue.put(('stopped',()))

    def start_simulation(self):
        """Start/continue the simulation"""
        if self.__robots:
            self.__state = RUN
            self._out_queue.put(('running',()))

    def pause_simulation(self):
        """Pause the simulation"""
        self.__state = PAUSE
        self._out_queue.put(('paused',()))

    def step_simulation(self):
        """Do one step"""
        if self.__state != RUN:
            self.__state = RUN_ONCE
        #self._out_queue.put(('paused',()))

    def reset_simulation(self):
        """Reset the simulation to the start position"""
        self.__state = DRAW_ONCE
        self.__reset_world()

    def set_time_multiplier(self,multiplier):
        """Shorten the interval between evaluation cycles by *multiplier*,
           speeding up the simulation"""
        self.__time_multiplier = multiplier

### FIXME Those two functions are not thread-safe
    def get_time(self):
        """Get the internal simulator time."""
        return self.__time

    def is_running(self):
        """Get the simulation state as a `bool`"""
        return self.__state == RUN
###------------------

    def __check_collisions(self):
        return False
        """Update proximity sensors and detect collisions between objects"""
        
        collisions = []
        checked_robots = []
        
        if self.__qtree is None:
            self.__qtree = QuadTree(self.__obstacles)
            
        if len(self.__robots) > 1:
            rqtree = QuadTree(self.__robots)
        else: rqtree = None
        
        # check each robot
        for robot in self.__robots:
                
            # update proximity sensors
            for sensor in robot.get_external_sensors():
                sensor.get_world_envelope(True)
                rect = Rect(sensor.get_bounding_rect())
                sensor.update_distance()
                # distance to obstacles
                for obstacle in self.__qtree.find_items(rect):
                    sensor.update_distance(obstacle)
                # distance to other robots
                if rqtree is None: continue
                for other in rqtree.find_items(rect):
                    if other is not robot:
                        sensor.update_distance(other)
            
            rect = Rect(robot.get_bounding_rect())
            
            # against nearest obstacles
            for obstacle in self.__qtree.find_items(rect):
                if robot.has_collision(obstacle):
                    collisions.append((robot, obstacle))
            
            # against other robots
            if rqtree is not None:
                for other in rqtree.find_items(rect):
                    if other is robot: continue
                    if other in checked_robots: continue
                    if robot.has_collision(other):
                        collisions.append((robot, other))

            checked_robots.append(robot)
            
        if len(collisions) > 0:
            # Test code - print out collisions
            for (robot, obstacle) in collisions:
                self.log("Collision with {}".format(obstacle), obj = robot)
            # end of test code
            return True
                
        return False

    def __process_queue(self):
        """Process external calls
        """
        while not self.__in_queue.empty():
            tpl = self.__in_queue.get()
            if isinstance(tpl,tuple) and len(tpl) == 2:
                name, args = tpl
                if name in self.__class__.__dict__:
                    try:
                        self.__class__.__dict__[name](self,*args)
                    except TypeError:
                        self.log("Wrong simulator event parameters {}{}".format(name,args))
                        self._out_queue.put(("exception",sys.exc_info()))
                    except Exception as e:
                        self._out_queue.put(("exception",sys.exc_info()))
                else:
                    self.log("Unknown simulator event '{}'".format(name))
            else:
                self.log("Wrong simulator event format '{}'".format(tpl))
            self.__in_queue.task_done()
    
    def log(self, message, obj=None):
        if obj is None:
            obj = self
        print("{}: {}".format(obj.__class__.__name__,message))
        self._out_queue.put(("log",(message,obj.__class__.__name__,None)))
        
    def fwd_logqueue(self):
        while self.__log_queue:
            obj, message = self.__log_queue.popleft()
            
            color = None
            # Get the color
            if isinstance(obj,simobject.SimObject):
                color = obj.get_color()
            elif isinstance(obj,supervisor.Supervisor):
                color = obj.robot_color
                
            self._out_queue.put(("log",(message,obj.__class__.__name__,color)))
    
#end class Simulator
