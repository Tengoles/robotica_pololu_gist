#
# (c) PySimiam Team 2013
# 
# Contact person: Tim Fuchs <typograph@elec.ru>
#
# This class was implemented for the weekly programming excercises
# of the 'Control of Mobile Robots' course by Magnus Egerstedt.
#
from supervisors.quickbot import QuickBotSupervisor
from simobject import Path
from supervisor import Supervisor
from math import sqrt, sin, cos, atan2, copysign
from pose import Pose

class QBGTGSupervisor(QuickBotSupervisor):
    """QBGTG supervisor uses one go-to-goal controller to make the robot reach the goal."""
    def __init__(self, robot_pose, robot_info):
        """Create the controller"""
        QuickBotSupervisor.__init__(self, robot_pose, robot_info)
        
        # Create the tracker
        self.tracker = Path(robot_pose, 0)

        # Create the controller
        self.gtg = self.create_controller('week3.GoToGoal', self.parameters)

        # Set the controller
        self.current = self.gtg

    def set_parameters(self,params):
        """Set parameters for itself and the controllers"""
        QuickBotSupervisor.set_parameters(self,params)
        self.gtg.set_parameters(self.parameters)

    def process_state_info(self, state):
        """Update state parameters for the controllers and self"""

        QuickBotSupervisor.process_state_info(self,state)

        # The pose for controllers
        self.parameters.pose = self.pose_est
        
        # Update the trajectory
        self.tracker.add_point(self.pose_est)

    def draw_background(self, renderer):
        """Draw controller info"""
        QuickBotSupervisor.draw_background(self,renderer)

        # Draw robot path
        self.tracker.draw(renderer)
            
    def draw_foreground(self, renderer):
        """Draw controller info"""
        QuickBotSupervisor.draw_foreground(self,renderer)
       
        renderer.set_pose(Pose(self.pose_est.x,self.pose_est.y))
        arrow_length = self.robot_size*5
        
        # Draw arrow to goal
        renderer.set_pen(0x00FF00)
        renderer.draw_arrow(0,0,
            arrow_length*cos(self.gtg.heading_angle),
            arrow_length*sin(self.gtg.heading_angle))

    def at_goal(self):
        distance_to_goal = sqrt( \
                                (self.pose_est.x - self.parameters.goal.x)**2
                              + (self.pose_est.y - self.parameters.goal.y)**2)
        
        return distance_to_goal < 0.02

            
    def ensure_w(self,v_lr):

        #Week 3 Assignment Code:
                
        #End Week 3 Assigment
        # This code is taken directly from Sim.I.Am week 4
        # I'm sure one can do better.

        v_max = self.robot.wheels.max_velocity
        v_min = self.robot.wheels.min_velocity

        R = self.robot.wheels.radius
        L = self.robot.wheels.base_length

        def diff2uni(vl, vr):
            return (vl + vr) * R / 2, (vr - vl) * R / L

        v, w = diff2uni(*v_lr)

        if v == 0:

            # Robot is stationary, so we can either not rotate, or
            # rotate with some minimum/maximum angular velocity

            w_min = R / L * (2 * v_min);
            w_max = R / L * (2 * v_max);

            if abs(w) > w_min:
                w = copysign(max(min(abs(w), w_max), w_min), w)
            else:
                w = 0

            return self.uni2diff((0, w))

        else:
            # 1. Limit v,w to be possible in the range [vel_min, vel_max]
            # (avoid stalling or exceeding motor limits)
            v_lim = max(min(abs(v), (R / 2) * (2 * v_max)), (R / 2) * (2 * v_min))
            w_lim = max(min(abs(w), (R / L) * (v_max - v_min)), 0)

            # 2. Compute the desired curvature of the robot's motion

            vl, vr = self.uni2diff((v_lim, w_lim))

            # 3. Find the max and min vel_r/vel_l
            v_lr_max = max(vl, vr);
            v_lr_min = min(vl, vr);

            # 4. Shift vr and vl if they exceed max/min vel
            if (v_lr_max > v_max):
                vr -= v_lr_max - v_max
                vl -= v_lr_max - v_max
            elif (v_lr_min < v_min):
                vr += v_min - v_lr_min
                vl += v_min - v_lr_min

            # 5. Fix signs (Always either both positive or negative)
            v_shift, w_shift = diff2uni(vl, vr)

            v = copysign(v_shift, v)
            w = copysign(w_shift, w)

            return self.uni2diff((v, w))
        #return v_l, v_r

    def execute(self, robot_info, dt):
        """Inherit default supervisor procedures and return unicycle model output (vl,vr)"""
        if not self.at_goal():
            output = Supervisor.execute(self, robot_info, dt)
            #print(output)
            return self.ensure_w(self.uni2diff(output))
            #return output
        else:
            return 0,0