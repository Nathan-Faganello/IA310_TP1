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
from mesa.visualization.ModularVisualization import VisualizationElement, ModularServer
from mesa.visualization.modules import ChartModule

MAX_ITERATION = 100
PROBA_CHGT_ANGLE = 0.01


def move(x, y, speed, angle):
    return x + speed * math.cos(angle), y + speed * math.sin(angle)


def go_to(x, y, speed, dest_x, dest_y):
    if np.linalg.norm((x - dest_x, y - dest_y)) < speed:
        return (dest_x, dest_y), 2 * math.pi * random.random()
    else:
        angle = math.acos(
            (dest_x - x)/np.linalg.norm((x - dest_x, y - dest_y)))
        if dest_y < y:
            angle = - angle
        return move(x, y, speed, angle), angle


class MarkerPurpose(Enum):
    DANGER = enum.auto(),
    INDICATION = enum.auto()


class ContinuousCanvas(VisualizationElement):
    local_includes = [
        "./js/simple_continuous_canvas.js",
    ]

    def __init__(self, canvas_height=500, canvas_width=500, instantiate=True):
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
                     "Color": "black",
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
                raise ValueError(
                    "Direction should not be none for indication marker")

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
        self.max_speed = speed  # On conserve un attribut "max_speed" dans le constructeur afin de comparer notre vitesse courante à la vitesse maximale du robot attribué à l'initialisation
        self.speed = speed
        self.sight_distance = sight_distance
        self.angle = angle
        # On initialise une variable servant de compteur afin d'ignorer sa propre balise à la sortie d'un sable mouvant
        self.ignore_steps_count = 0
        # On initialise une variable booléenne identifiant si l'on vient de sortir des sables mouvants ou non
        self.bool_out_quicksand = False
        # On initialise une variable booléenne identifiant si l'on vient de déminer ou non
        self.bool_deminage = False

    def step(self):

        # Traitement des sables mouvants

        # On regarde si le compteur d'ignorance des balises est à 0 ou non. Si il n'est pas à 0, on le décrémente
        if self.ignore_steps_count > 0:
            self.ignore_steps_count -= 1

        # On regarde si l'on est sur un sable mouvant ou non
        on_quicksand = [quicksand for quicksand in self.model.quicksands if np.linalg.norm(
            (quicksand.x - self.x, quicksand.y - self.y)) <= quicksand.r]
        # Soit on est sur un sable mouvant et la vitesse n'est pas réduite (on vient d'entrer), alors on la réduit
        if on_quicksand:
        	self.model.counter_quicksand += 1
        # Soit on est sur un sable mouvant et la vitesse n'est pas réduite (on vient d'entrer), alors on la réduit
        if on_quicksand and self.speed == self.max_speed:
            self.speed = self.speed/2
        # Soit on est pas sur un sable mouvant et la vitesse est réduite (on vient d'en sortir), auquel cas on rétablit la vitesse normale
        elif not on_quicksand and self.speed != self.max_speed:
            self.speed = self.max_speed
            self.bool_out_quicksand = True

        # On conserve les données de l'étape précédente
        old_x, old_y, old_angle = self.x, self.y, self.angle

        # Niveau 0 ###########################################
        bool_evitement = 0
        while not bool_evitement:
            # Position future si l'on considère l'angle courant
            potential_x, potential_y = move(
                self.x, self.y, self.speed, self.angle)
            nearby_robots = [robot for robot in self.model.schedule.agents if (robot.x, robot.y) != (self.x, self.y) and np.linalg.norm(
                (robot.x - potential_x, robot.y - potential_y)) < robot.speed]  # Liste des robots trop proche de la position future : si la nouvelle position potentielle calculée est à une distance inférieure à la vitesse de l'autre robot, alors ce robot peut potentiellement choisir le même point de coordonnée pour position future, ce qui entraîne une collision.
            nearby_obstacles = [obstacle for obstacle in self.model.obstacles if np.linalg.norm(
                (obstacle.x - potential_x, obstacle.y - potential_y)) < obstacle.r]  # Liste des obstacles trop proches de la position future
            # Booléen vérifiant si la future position est en dehors de l'environnement ou non
            outside_environment = potential_x < 0 or potential_x > self.model.canvas_width or potential_y < 0 or potential_y > self.model.canvas_height
            # Si aucun robot n'est trop proche et si la position future n'est pas en dehors de l'environnement, on conserve l'angle
            if not (nearby_robots or nearby_obstacles or outside_environment):
                bool_evitement = True
            else:
                self.angle = 2 * math.pi * random.random()  # Sinon, on essaie un autre angle
        ######################################################

        # On regarde la liste des mines présentes dans notre champ de vision
        nearby_mines_sublist = [(mine, np.linalg.norm((mine.x - self.x, mine.y - self.y)))
                                for mine in self.model.mines if np.linalg.norm((mine.x - self.x, mine.y - self.y)) <= self.sight_distance]  # On conserve les couples de mines dans le champ de vision, et la distance associée
        # Niveau 1 ###########################################
        # Détruire une mine
        if nearby_mines_sublist:
            goal_mine = min(nearby_mines_sublist, key=lambda x: x[1])[0]
        # Si la mine la plus proche est à une distance de 0, on détruit la mine
            if (goal_mine.x, goal_mine.y) == (self.x, self.y):
                nearby_mines_sublist.remove((goal_mine, np.linalg.norm(
                    (goal_mine.x - self.x, goal_mine.y - self.y))))
                self.model.mines.remove(goal_mine)
                self.model.counter += 1
                self.bool_deminage = True
        ######################################################

        # Niveau 2 ###########################################
        # Détection d'une balise DANGER et faire demi-tour
        nearby_danger = [(danger, np.linalg.norm((danger.x - self.x, danger.y - self.y))) for danger in self.model.markers if danger.purpose ==
                         MarkerPurpose.DANGER and np.linalg.norm((danger.x - self.x, danger.y - self.y)) <= self.sight_distance]
        # Si on détecte au moins une balise DANGER dans son champ de vision et que l'on ne doit pas l'ignorer
        if self.angle == old_angle and nearby_danger and self.ignore_steps_count == 0:
            # On considère la balise la plus proche
            balise = min(nearby_danger, key=lambda x: x[1])[0]
            (self.x, self.y), self.angle = go_to(self.x, self.y, self.speed,
                                                 balise.x, balise.y)  # On se déplace jusqu'à la balise
            self.model.markers.remove(balise)  # On la ramasse
            # On effectue un demi-tour
            self.angle = (self.angle + math.pi) % (2*math.pi)
        ######################################################

        # Niveau 3 ###########################################
        # Détection d'une balise INDICATION et rotation de 90° dans le sens indiqué par la balise
        nearby_indication = [(indication, np.linalg.norm((indication.x - self.x, indication.y - self.y))) for indication in self.model.markers if indication.purpose ==
                             MarkerPurpose.INDICATION and np.linalg.norm((indication.x - self.x, indication.y - self.y)) <= self.sight_distance]
        # Si on détecte une balise DANGER dans son champ de vision et que l'on ne doit pas l'ignorer
        if self.angle == old_angle and nearby_indication and self.ignore_steps_count == 0:
            # On considère la balise la plus proche
            balise = min(nearby_indication, key=lambda x: x[1])[0]
            (self.x, self.y), self.angle = go_to(self.x, self.y, self.speed,
                                                 balise.x, balise.y)  # On se déplace jusqu'à la balise
            self.model.markers.remove(balise)  # On la ramasse
            # On effectue une rotation de 90% par rapport à la direction de la balise détectée
            self.angle = (balise.direction + math.pi/2) % (2*math.pi)
        ######################################################
        
        # Niveau 4 ###########################################
        # Dépôt d'une balise
        if self.bool_out_quicksand or self.bool_deminage:
            # On initialise le compteur de tour durant lequel le robot ignore les balises qu'il voit
            self.ignore_steps_count = self.max_speed/2
            if self.bool_out_quicksand:
                self.model.markers.append(
                    Marker(self.x, self.y, MarkerPurpose.DANGER))  # Dépôt d'une balise DANGER à la sortie du sable mouvant
                # Réinitialisation de la valeur de la variable de sortie du sable mouvant
                self.bool_out_quicksand = False
            if self.bool_deminage:
                self.model.markers.append(
                    Marker(self.x, self.y, MarkerPurpose.INDICATION, self.angle))  # Dépôt d'une balise DANGER à la sortie du sable mouvant
                self.bool_deminage = False  # Réinitialisation de la valeur de la variable de déminage
        ######################################################

        # Niveau 5 (Niveau 2 de la partie 1) #################
        # Se diriger vers une mine
        if nearby_mines_sublist:
            # Le minimum est forcément une mine sur laquelle on est pas, car soit on était pas sur une mine à la base soit on l'a supprimé juste avant
            goal_mine = min(nearby_mines_sublist, key=lambda x: x[1])[0]
            if self.angle == old_angle:
                (self.x, self.y), self.angle = go_to(
                    self.x, self.y, self.speed, goal_mine.x, goal_mine.y)
        ######################################################

        # Niveau 6 (Niveau 3 de la partie 1) #################
        if self.angle == old_angle:  # On change l'angle si on ne l'a pas changé au niveau 0
            if random.random() <= PROBA_CHGT_ANGLE:
                # QUESTION BONUS : Prise en compte du signal
                sighted_robots = [robot for robot in self.model.schedule.agents if (robot.x, robot.y) != (self.x, self.y) and np.linalg.norm((robot.x - self.x, robot.y - self.y)) <= self.sight_distance] # On regarde tous les robots dans notre champs de vision.
                # On définit une nouvelle direction aléatoire
                new_direction = 2 * math.pi * random.random()
                if sighted_robots:
                    sighted_robots = sorted(sighted_robots, key=lambda robot: np.linalg.norm(
                        (robot.x - self.x, robot.y - self.y)))  # On trie la liste de robots par ordre croissant de distance
                    # On détermine l'angle en fonction des deux robots les plus proches
                    if len(sighted_robots) >= 2:
                        # On identifie la direction au premier robot
                        (_, _), angle1 = go_to(self.x, self.y, self.speed,
                                               sighted_robots[0].x, sighted_robots[0].y)
                        # On identifie la direction au second robot
                        (_, _), angle2 = go_to(self.x, self.y, self.speed,
                                               sighted_robots[1].x, sighted_robots[1].y)
                        # On considère l'angle le plus petit
                        first_angle = min(angle1, angle2)
                        second_angle = angle1 if angle1 != first_angle else angle2
                        # On maximise l'angle entre la nouvelle direction et la direction des 2 robots plus proches voisins
                        self.angle = max(new_direction, first_angle + (second_angle - first_angle)/2 % (2*math.pi))
                    else:  # Sinon, un seul robot est dans le champ de vision et on maximise la distance entre ce robot et la nouvelle direction
                        (_, _), angle_robot = go_to(self.x, self.y,
                                                    self.speed, sighted_robots[0].x, sighted_robots[0].y)
                        self.angle = max(new_direction, angle_robot)
                else:  # Si aucun robot n'est dans le champ de vision, alors on effectue une marche aléatoire comme précédemment
                    self.angle = new_direction

        # Si on ne se dirige pas vers une mine, on effectue une marche aléatoire
        if (self.x, self.y) == (old_x, old_y):
            # Mise à jour finale de la position
            self.x, self.y = move(self.x, self.y, self.speed, self.angle)
        ######################################################

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
                         "Deactivated mines": lambda model: model.counter,
                         "Time in quicksands": lambda model: model.counter_quicksand
                         },
        agent_reporters={})

    def __init__(self, n_robots, n_obstacles, n_quicksand, n_mines, speed, canvas_height=500, canvas_width=500):
        Model.__init__(self)
        self.canvas_height = canvas_height
        self.canvas_width = canvas_width
        self.space = mesa.space.ContinuousSpace(600, 600, False)
        self.schedule = RandomActivation(self)
        self.counter = 0  # Compteur de mines désamorcées
        self.counter_quicksand = 0  # Compteur de temps passé dans les sables mouvants
        self.mines = []
        self.markers = []
        self.obstacles = []
        self.quicksands = []
        for _ in range(n_obstacles):
            self.obstacles.append(Obstacle(
                random.random() * 500, random.random() * 500, 10 + 20 * random.random()))
        for _ in range(n_quicksand):
            self.quicksands.append(Quicksand(
                random.random() * 500, random.random() * 500, 10 + 20 * random.random()))
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
                          "Color": "Green"},
                         {"Label": "Deactivated mines",
                          "Color": "Black"},
                         #{ "Label": "Time in quicksands",
                         # "Color": "Blue"}
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
    server.launch()


if __name__ == "__main__":
    run_single_server()
