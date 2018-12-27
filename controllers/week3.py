#
# (c) PySimiam Team 2013
# 
# Contact person: Tim Fuchs <typograph@elec.ru>
#
# This class was implemented for the weekly programming excercises
# of the 'Control of Mobile Robots' course by Magnus Egerstedt.
#
from controller import Controller
import math
from pprint import pprint
import bluetooth
import numpy

class GoToGoal(Controller):
    """Go-to-goal steers the robot to a predefined position in the world."""
    def __init__(self, params):
        '''Initialize some variables'''
        
        Controller.__init__(self,params)
        self.heading_angle = 0

    def set_parameters(self, params):
        """Set PID values
        
        The params structure is expected to have in the `gains` field three
        parameters for the PID gains.
        
        :param params.gains.kp: Proportional gain
        :type params.gains.kp: float
        :param params.gains.ki: Integral gain
        :type params.gains.ki: float
        :param params.gains.kd: Differential gain
        :type params.gains.kd: float
        """
        self.kp = params.gains.kp
        self.ki = params.gains.ki
        self.kd = params.gains.kd

    def restart(self):
        """Actual and previous error restart"""
        self.E_k = 0
        self.e_k_1 = 0 # Previous error calculation


    def get_heading_angle(self, state):
        """Get the heading angle in the world frame of reference."""
        
        x_g, y_g = state.goal.x, state.goal.y
        x_r, y_r, theta = state.pose
        distance = [x_g - x_r, y_g - y_r]
        norm = math.sqrt(distance[0] ** 2 + distance[1] ** 2)
        direction = [distance[0] / norm, distance[1] / norm]

        return math.atan2(direction[1], direction[0])

    def execute(self, state, dt):
        """Executes trajectory behavior based on state and dt.
        state --> the state of the robot and the goal
        dt --> elapsed time
        return --> unicycle model list [velocity, omega]"""

        self.heading_angle = self.get_heading_angle(state)
        #pprint(state.pose)
        # error between the heading angle and robot's angle
        x, y, theta = state.pose
        e_k = self.get_heading_angle(state) - theta
        
        # error for the proportional term
        e_P = e_k
        
        # error for the integral term. Hint: Approximate the integral using
        # the accumulated error, self.E_k, and the error for
        # this time step, e_k.
        e_I = self.E_k + e_k*dt
                    
        # error for the derivative term. Hint: Approximate the derivative
        # using the previous error, obj.e_k_1, and the
        # error for this time step, e_k.
        e_D = (e_k - self.e_k_1)/dt
        
        w_ = self.kp*e_P + self.ki*e_I + self.kd*e_D
        
        v_ = state.velocity.v #esto se mantiene re fijo, solo devuelve el setpoint aparentemente
        # save errors
        self.e_k_1 = e_k
        self.E_k = e_I
        #print('control en execute de week3:')
        #pprint([v_, w_])
        #Capaz aca se puede poner la comunicacion por BT (control de motores)
        return [v_, w_]