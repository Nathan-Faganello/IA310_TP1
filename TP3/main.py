import enum
import math
import random
import uuid
from enum import Enum

import mesa
import numpy as np
from collections import defaultdict

import mesa.space
from mesa import Agent, Model
from mesa.datacollection import DataCollector
from mesa.time import RandomActivation
from mesa.visualization.ModularVisualization import VisualizationElement, ModularServer, UserSettableParameter
from mesa.visualization.modules import ChartModule

MAX_ITERATION = 100
PROBA_CHGT_ANGLE = 0.01


def move(x, y, speed, angle):
    return x + speed * math.cos(angle), y + speed * math.sin(angle)


def go_to(x, y, speed, dest_x, dest_y):
    if np.linalg.norm((x - dest_x, y - dest_y)) < speed:
        return (dest_x, dest_y), 2 * math.pi * random.random()
    else:
        angle = math.acos((dest_x - x)/np.linalg.norm((x - dest_x, y - dest_y)))
        if dest_y < y:
            angle = - angle
        return move(x, y, speed, angle), angle


class MarkerPurpose(Enum):
    DANGER = enum.auto(),
    INDICATION = enum.auto()


class ContinuousCanvas(VisualizationElement):
    local_includes = [
        "./js/simple_continuous_canvas.js",
        "./js/jquery.js"
    ]

    def __init__(self, canvas_height=500,
                 canvas_width=500, instantiate=True):
        VisualizationElement.__init__(self)
        self.canvas_height = canvas_height
        self.canvas_width = canvas_width
        self.identifier = "space-canvas"
        if (instantiate):
            new_element = ("new Simple_Continuous_Module({}, {},'{}')".
                           format(self.canvas_width, self.canvas_height, self.identifier))
            self.js_code = "elements.push(" + new_element + ");"

    def portrayal_method(self, obj):
        return obj.portrayal_method()

    def render(self, model):
        representation = defaultdict(list)
        for obj in model.schedule.agents:
            portrayal = self.portrayal_method(obj)
            if portrayal:
                portrayal["x"] = ((obj.x - model.space.x_min) /
                                  (model.space.x_max - model.space.x_min))
                portrayal["y"] = ((obj.y - model.space.y_min) /
                                  (model.space.y_max - model.space.y_min))
            representation[portrayal["Layer"]].append(portrayal)
        for obj in model.mines:
            portrayal = self.portrayal_method(obj)
            if portrayal:
                portrayal["x"] = ((obj.x - model.space.x_min) /
                                  (model.space.x_max - model.space.x_min))
                portrayal["y"] = ((obj.y - model.space.y_min) /
                                  (model.space.y_max - model.space.y_min))
            representation[portrayal["Layer"]].append(portrayal)
        for obj in model.markers:
            portrayal = self.portrayal_method(obj)
            if portrayal:
                portrayal["x"] = ((obj.x - model.space.x_min) /
                                  (model.space.x_max - model.space.x_min))
                portrayal["y"] = ((obj.y - model.space.y_min) /
                                  (model.space.y_max - model.space.y_min))
            representation[portrayal["Layer"]].append(portrayal)
        for obj in model.obstacles:
            portrayal = self.portrayal_method(obj)
            if portrayal:
                portrayal["x"] = ((obj.x - model.space.x_min) /
                                  (model.space.x_max - model.space.x_min))
                portrayal["y"] = ((obj.y - model.space.y_min) /
                                  (model.space.y_max - model.space.y_min))
            representation[portrayal["Layer"]].append(portrayal)
        for obj in model.quicksands:
            portrayal = self.portrayal_method(obj)
            if portrayal:
                portrayal["x"] = ((obj.x - model.space.x_min) /
                                  (model.space.x_max - model.space.x_min))
                portrayal["y"] = ((obj.y - model.space.y_min) /
                                  (model.space.y_max - model.space.y_min))
            representation[portrayal["Layer"]].append(portrayal)
        return representation


class Obstacle:  # Environnement: obstacle infranchissable
    def __init__(self, x, y, r):
        self.x = x
        self.y = y
        self.r = r

    def portrayal_method(self):
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 1,
                     "Color": "black",
                     "r": self.r}
        return portrayal


class Quicksand:  # Environnement: ralentissement
    def __init__(self, x, y, r):
        self.x = x
        self.y = y
        self.r = r

    def portrayal_method(self):
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 1,
                     "Color": "olive",
                     "r": self.r}
        return portrayal


class Mine:  # Environnement: élément à ramasser
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def portrayal_method(self):
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 2,
                     "Color": "blue",
                     "r": 2}
        return portrayal


class Marker:  # La classe pour les balises
    def __init__(self, x, y, purpose, direction=None):
        self.x = x
        self.y = y
        self.purpose = purpose
        if purpose == MarkerPurpose.INDICATION:
            if direction is not None:
                self.direction = direction
            else:
                raise ValueError("Direction should not be none for indication marker")

    def portrayal_method(self):
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 2,
                     "Color": "red" if self.purpose == MarkerPurpose.DANGER else "green",
                     "r": 2}
        return portrayal


class Robot(Agent):  # La classe des agents
    def __init__(self, unique_id: int, model: Model, x, y, speed, sight_distance, angle=0.0):
        super().__init__(unique_id, model)
        self.x = x
        self.y = y
        self.speed = speed
        self.sight_distance = sight_distance
        self.angle = angle
        self.counter = 0
        self.isInQuicksand = False
        self.isMoving = False




    def detect_markers(self, purpose):
        detected_markers = []
        for marker in self.model.markers:
            if ((math.sqrt((self.x-marker.x)**2 + (self.y-marker.y)**2) < self.sight_distance) and (marker.purpose == purpose)):
                detected_markers.append([marker, math.sqrt((self.x-marker.x)**2 + (self.y-marker.y)**2)])
        return sorted(detected_markers, key = lambda x : x[1])


    def detect_quicksand(self):
        for quicksand in self.model.quicksands:
            if (math.sqrt((self.x-quicksand.x)**2 + (self.y-quicksand.y)**2) < quicksand.r):
                if self.isInQuicksand == False:
                    self.isInQuicksand = True
                    self.speed = self.speed / 2
                self.model.nb_quicksands +=1
                return True
        self.isInQuicksand = False
        return False

    def detect_obstacles(self, nextX, nextY):
      ##on considèrera qu'un robot 'peut' traverser un obstacle : si l'obstacle est entre le point de départ et le point d'arrivée du robot, il le traversera
      in_range_obstacles = [obstacle for obstacle in self.model.obstacles if math.sqrt((self.x - obstacle.x)**2 + (self.y - obstacle.y)**2) < self.sight_distance+obstacle.r ]
      collision_obstacles = []
      for obstacle in in_range_obstacles :
      #for obstacle in self.model.obstacles:
        if (math.sqrt((nextX-obstacle.x)**2 + (nextY-obstacle.y)**2) < obstacle.r):
          collision_obstacles.append(obstacle)
      return collision_obstacles
    
    def detect_robots(self, nextX, nextY):
      in_range_robots = [robot for robot in self.model.schedule.agents if math.sqrt((self.x - robot.x)**2+(self.y - robot.y)**2) < self.sight_distance]

      collision_robots = []

      for robot in in_range_robots:
        if ((math.sqrt((nextX - robot.x)**2+(nextY - robot.y)**2) < robot.speed)):
          collision_robots.append(robot)
      return collision_robots

    def detect_bord(self, nextX, nextY):
      return self.model.space.out_of_bounds([nextX,nextY])
    
    def detect_mines(self):
      in_range_mines = [[mine, math.sqrt((self.x - mine.x)**2 + (self.y - mine.y)**2)] for mine in self.model.mines if math.sqrt((self.x - mine.x)**2 + (self.y - mine.y)**2) < self.sight_distance]
      
      if (len(in_range_mines) > 0):
        idxMine = 0
        minDist = math.inf
        for i in range(len(in_range_mines)):
          if in_range_mines[i][1] < minDist:
            idxMine = i
            minDist = in_range_mines[i][1]

        return [in_range_mines[idxMine][0], in_range_mines[idxMine][1]]
      return []

    def step(self):
        #pass
        ### AJOUTER CODE ICI ###
        ##du code a été ajouté juste au-dessus de la fonction step


        #### 1ère étape : détection des quicksands afin de mettre à jour notre vitesse --> étape nécessaire afin de prédire correctement notre position ####
        
        temp_quicksand = self.isInQuicksand
        self.detect_quicksand()
        if temp_quicksand == True and self.isInQuicksand == False:
            self.speed *= 2
            self.model.markers.append(Marker(self.x, self.y, MarkerPurpose.DANGER, direction=None))
            self.counter = int(self.speed / 2)
        
        #### mise à jour du compteur ####
        if self.counter > 0 :
            self.counter -=1
        
        #### se déplacer : placé au début, le mouvement sera remplacé si une étape plus importante est réalisée ####
        ##calcul d'un nouvel angle de déplacement si aucun obstacle/robot/mine n'est détecté
        p = random.random()
        if (p < PROBA_CHGT_ANGLE):
            self.angle = random.uniform(0, 2*math.pi)

        ###### calcul de l'emplacement potentiel au prochain tour ######
        nextX, nextY = move(self.x, self.y, self.speed, self.angle)


        #### Niveau 0 : contraintes de déplacement ####
        isCollidingRobots = True
        isCollidingObstacles = True
        isCollidingBord = True
        while isCollidingRobots or isCollidingObstacles or isCollidingBord :
          ##détection et évitement des autres robots
          collision_robots = self.detect_robots(nextX, nextY)
          isCollidingRobots = (len(collision_robots) != 0)
          ##détection et évitement des obstacles
          collision_obstacles = self.detect_obstacles(nextX, nextY)
          isCollidingObstacles = (len(collision_obstacles) != 0)
          ##détection des bors de la zone
          isCollidingBord = self.detect_bord(nextX, nextY)
          if isCollidingRobots or isCollidingObstacles or isCollidingBord :
            self.angle = random.random() * 2 * math.pi
            nextX, nextY = move(self.x, self.y, self.speed, self.angle)

        
        ## Niveau 1 : détection des mines et déminage 
        ##détection des mines : on retourne la mine plus proche dans notre champ de détection
        mineAimed = self.detect_mines()
        if mineAimed != []:
          if mineAimed[1] == 0:
            self.model.disarmed_mines += 1
            self.model.mines.remove(mineAimed[0])
            self.model.markers.append(Marker(self.x, self.y, MarkerPurpose.INDICATION, direction=self.angle))
            self.counter = int(self.speed / 2)
          else :
            (self.x, self.y), self.angle = go_to(self.x, self.y, self.speed, mineAimed[0].x, mineAimed[0].y)
            self.isMoving = True
        
        
        #### Gestion des balises : les dangers sont plus importantes que les indications et on ignore les balises si on se dirige vers une mine ####
        if self.counter == 0 and not self.isMoving:
            detected_dangers = self.detect_markers(MarkerPurpose.DANGER)
            if len(detected_dangers) > 0 :
                self.angle += math.pi * 0.95 #pas exactement un demi-tour pour pas qu'un robot reste coincé entre deux balises dangers

            else:
                detected_indications = self.detect_markers(MarkerPurpose.INDICATION)
                if len(detected_indications) > 0:
                    indication = detected_indications[0]
                    if indication[1] == 0:
                        self.angle = indication[0].direction + math.pi/2
                        self.model.markers.remove(indication[0])

                    else :
                        (self.x, self.y), self.angle = go_to(self.x, self.y, self.speed, indication[0].x, indication[0].y)
                        self.isMoving = True
        


        ##déplacement de base

        if not self.isMoving:
          self.x, self.y = move(self.x, self.y, self.speed, self.angle)

        self.isMoving = False
          

    def portrayal_method(self):
        portrayal = {"Shape": "arrowHead", "s": 1, "Filled": "true", "Color": "Red", "Layer": 3, 'x': self.x,
                     'y': self.y, "angle": self.angle}
        return portrayal


class MinedZone(Model):
    collector = DataCollector(
        model_reporters={"Mines": lambda model: len(model.mines),
                         "Danger markers": lambda model: len([m for m in model.markers if
                                                          m.purpose == MarkerPurpose.DANGER]),
                         "Indication markers": lambda model: len([m for m in model.markers if
                                                          m.purpose == MarkerPurpose.INDICATION]),
                         "Mines désamorcées": lambda model: model.disarmed_mines,
                         "#tours moyen dans les quicksands": lambda model: model.nb_quicksands / model.n_robots
                         },
        agent_reporters={})

    def __init__(self, n_robots, n_obstacles, n_quicksand, n_mines, speed):
        Model.__init__(self)
        self.space = mesa.space.ContinuousSpace(600, 600, False)
        self.schedule = RandomActivation(self)
        self.mines = []  # Access list of mines from robot through self.model.mines
        self.markers = []  # Access list of markers from robot through self.model.markers (both read and write)
        self.obstacles = []  # Access list of obstacles from robot through self.model.obstacles
        self.quicksands = []  # Access list of quicksands from robot through self.model.quicksands
        self.disarmed_mines = 0
        self.nb_quicksands = 0
        self.n_robots = n_robots
        for _ in range(n_obstacles):
            self.obstacles.append(Obstacle(random.random() * 500, random.random() * 500, 10 + 20 * random.random()))
        for _ in range(n_quicksand):
            self.quicksands.append(Quicksand(random.random() * 500, random.random() * 500, 10 + 20 * random.random()))
        for _ in range(n_robots):
            x, y = random.random() * 500, random.random() * 500
            while [o for o in self.obstacles if np.linalg.norm((o.x - x, o.y - y)) < o.r] or \
                    [o for o in self.quicksands if np.linalg.norm((o.x - x, o.y - y)) < o.r]:
                x, y = random.random() * 500, random.random() * 500
            self.schedule.add(
                Robot(int(uuid.uuid1()), self, x, y, speed,
                      2 * speed, random.random() * 2 * math.pi))
        for _ in range(n_mines):
            x, y = random.random() * 500, random.random() * 500
            while [o for o in self.obstacles if np.linalg.norm((o.x - x, o.y - y)) < o.r] or \
                    [o for o in self.quicksands if np.linalg.norm((o.x - x, o.y - y)) < o.r]:
                x, y = random.random() * 500, random.random() * 500
            self.mines.append(Mine(x, y))
        self.datacollector = self.collector

        self.running = True

    def step(self):
        self.datacollector.collect(self)
        self.schedule.step()
        if not self.mines:
            self.running = False


def run_single_server():
    chart = ChartModule([{"Label": "Mines",
                          "Color": "Orange"},
                         {"Label": "Danger markers",
                          "Color": "Red"},
                         {"Label": "Indication markers",
                          "Color": "Green"}, { "Label": "Mines désamorcées", "Color": "Blue"}, {"Label": "#tours moyen dans les quicksands", "Color": "Yellow"}

                         ],
                        data_collector_name='datacollector')
    server = ModularServer(MinedZone,
                           [ContinuousCanvas(),
                            chart],
                           "Deminer robots",
                           {"n_robots": UserSettableParameter('slider', "Number of robots", 7, 3,
                                                             15, 1),
                            "n_obstacles": UserSettableParameter('slider', "Number of obstacles", 5, 2, 10, 1),
                            "n_quicksand": UserSettableParameter('slider', "Number of quicksand", 5, 2, 10, 1),
                            "speed": UserSettableParameter('slider', "Robot speed", 15, 5, 40, 5),
                            "n_mines": UserSettableParameter('slider', "Number of mines", 15, 5, 30, 1)})
    server.port = 8521
    server.launch()


if __name__ == "__main__":
    run_single_server()
