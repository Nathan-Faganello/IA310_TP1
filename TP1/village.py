import math
import random
import uuid
from collections import defaultdict

import mesa
import tornado, tornado.ioloop
from mesa import space
from mesa.time import RandomActivation
from mesa.visualization.ModularVisualization import ModularServer, VisualizationElement

#from IPython.display import display

evaluationFunctions = {"population": lambda m : m.schedule.get_agent_count(), "non-lycanthropes": lambda m : m.schedule.get_agent_count()-len([pers for pers in m.schedule.agents if isinstance(pers, Villager) and pers.isLycanthrope == True]),"lycanthropes": lambda m : len([pers for pers in m.schedule.agents if isinstance(pers, Villager) and pers.isLycanthrope == True]), 'loups-garous': lambda m : len([pers for pers in m.schedule.agents if isinstance(pers, Villager) and pers.isLycanthrope == True and pers.isTransformed == True])}

class Village(mesa.Model):

    def __init__(self, n_villagers, n_lycanthropes, n_clerics, n_hunters):
        mesa.Model.__init__(self)
        self.space = mesa.space.ContinuousSpace(600, 600, False)
        self.schedule = RandomActivation(self)
        for _ in range(n_villagers):
            self.schedule.add(Villager(random.random() * 500, random.random() * 500, 10, int(uuid.uuid1()), self))
        for _ in range(n_lycanthropes):
            self.schedule.add(Villager(random.random() * 500, random.random() * 500, 10, int(uuid.uuid1()), self, True))
        for _ in range(n_clerics):
            self.schedule.add(Cleric(random.random() * 500, random.random() * 500, 10, int(uuid.uuid1()), self))
        for _ in range(n_hunters):
            self.schedule.add(Hunter(random.random() * 500, random.random() * 500, 10, int(uuid.uuid1()), self))

        
        self.datacollector = mesa.DataCollector(model_reporters=evaluationFunctions)

        self.running = True

    def step(self):
        self.schedule.step()

        self.datacollector.collect(self)


        if self.schedule.steps >= 1000:
            self.running = False


class ContinuousCanvas(VisualizationElement):
    local_includes = [
        "./js/jquery.js",
        "./js/simple_continuous_canvas.js",
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
                portrayal["x"] = ((obj.pos[0] - model.space.x_min) /
                                  (model.space.x_max - model.space.x_min))
                portrayal["y"] = ((obj.pos[1] - model.space.y_min) /
                                  (model.space.y_max - model.space.y_min))
            representation[portrayal["Layer"]].append(portrayal)
        return representation


def wander(x, y, speed, model):
    r = random.random() * math.pi * 2
    new_x = max(min(x + math.cos(r) * speed, model.space.x_max), model.space.x_min)
    new_y = max(min(y + math.sin(r) * speed, model.space.y_max), model.space.y_min)

    return new_x, new_y


class Villager(mesa.Agent):
    def __init__(self, x, y, speed, unique_id: int, model: Village, isLycanthrope=False, isTransformed=False):
        super().__init__(unique_id, model)
        self.pos = (x, y)
        self.speed = speed
        self.model = model
        self.isLycanthrope = isLycanthrope
        self.isTransformed = isTransformed

    def portrayal_method(self):

        color = "blue"
        if self.isLycanthrope == True :
            color = "red"

        r = 3
        if self.isLycanthrope and self.isTransformed:
            r=6

        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 1,
                     "Color": color,
                     "r": r}
        return portrayal

    def step(self):
        self.pos = wander(self.pos[0], self.pos[1], self.speed, self.model)

        if not self.isTransformed:
            p=0.1
            self.isTransformed = random.random() < p

        if self.isTransformed:
            self.attack()


    def attack(self):
        proies = [villager for villager in self.model.schedule.agents if isinstance(villager, Villager) and villager.isLycanthrope == False and math.sqrt((self.pos[0]-villager.pos[0])**2 + (self.pos[1]-villager.pos[1])**2) < 40 ]
        if len(proies) > 0:
            idAttacked = random.randint(0,len(proies)-1)
            proies[idAttacked].isLycanthrope = True

class Cleric(mesa.Agent):
    def __init__(self, x, y, speed, unique_id: int, model: Village):
        super().__init__(unique_id, model)
        self.pos = (x, y)
        self.speed = speed
        self.model = model
        self.isLycanthrope = False


    def portrayal_method(self):

        color = "green"
        r = 3
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 1,
                     "Color": color,
                     "r": r}
        return portrayal

    def step(self):
        self.pos = wander(self.pos[0], self.pos[1], self.speed, self.model)
        self.heal()

    def heal(self):
        potentialHealed = [villager for villager in self.model.schedule.agents if isinstance(villager, Villager) and villager.isLycanthrope == True and villager.isTransformed == False and math.sqrt((self.pos[0]-villager.pos[0])**2 + (self.pos[1]-villager.pos[1])**2) < 30 ]
        if len(potentialHealed) > 0:
            idAttacked = random.randint(0,len(potentialHealed)-1)
            potentialHealed[idAttacked].isLycanthrope = False

class Hunter(mesa.Agent):
    def __init__(self, x, y, speed, unique_id: int, model: Village):
        super().__init__(unique_id, model)
        self.pos = (x, y)
        self.speed = speed
        self.model = model
        self.isLycanthrope = False


    def portrayal_method(self):

        color = "black"
        r = 3
        portrayal = {"Shape": "circle",
                     "Filled": "true",
                     "Layer": 1,
                     "Color": color,
                     "r": r}
        return portrayal

    def step(self):
        self.pos = wander(self.pos[0], self.pos[1], self.speed, self.model)
        self.kill()

    def kill(self):
        potentialKilled = [villager for villager in self.model.schedule.agents if isinstance(villager, Villager) and villager.isLycanthrope == True and villager.isTransformed == True and math.sqrt((self.pos[0]-villager.pos[0])**2 + (self.pos[1]-villager.pos[1])**2) < 40 ]
        if len(potentialKilled) > 0:
            idAttacked = random.randint(0,len(potentialKilled)-1)
            self.model.schedule.remove(potentialKilled[idAttacked])


def run_single_server():
    chart = mesa.visualization.ChartModule([{"Label": "population", 'Color': 'black'}, {"Label": "non-lycanthropes", 'Color': 'green'},{"Label": "lycanthropes", 'Color': 'red'}, {"Label": "loups-garous", 'Color': 'purple'}], data_collector_name= 'datacollector')
    slider_villagers = mesa.visualization.UserSettableParameter('slider', 'n_villagers', 25, 0, 100)
    slider_lycanthropes = mesa.visualization.UserSettableParameter('slider', 'n_lycanthropes', 5, 0, 100)
    slider_hunters = mesa.visualization.UserSettableParameter('slider', 'n_hunters', 2, 0, 100)
    slider_clerics = mesa.visualization .UserSettableParameter('slider', 'n_clerics', 1, 0, 100)
    '''
    server = ModularServer(Village,
               :            [ContinuousCanvas(), chart],
                           "Village",
                           {"n_villagers": 25, "n_lycanthropes": 5, "n_hunters": 2, "n_clerics": 1})
    '''
    server = ModularServer(Village,
                           [ContinuousCanvas(), chart],
                           "Village",
                           {"n_villagers": slider_villagers, "n_lycanthropes": slider_lycanthropes, "n_hunters": slider_hunters, "n_clerics": slider_clerics})
    server.port = 8521
    server.launch()


    tornado.ioloop.IOLoop.current().stop()


def run_batch():

    plageParams = {'n_villagers': 50, 'n_lycanthropes': 5, 'n_hunters': 1, 'n_clerics': range(0,6,1)}
    #batchrunnerr = mesa.batchrunner.BatchRunner(Village, plageParams, model_reporters = evaluationFunctions)
    #batchrunnerr.run_all()
    #result = batchrunnerr.get_model_vars_dataFrame()

    result = mesa.batchrunner.batch_run(Village, plageParams)
    print(result)

if __name__ == "__main__":
    #run_single_server()
    run_batch()
