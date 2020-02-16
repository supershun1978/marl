import os
import marl
from .agent import TrainableAgent, Agent

class MAS():
    def __init__(self, agents_list=[], name="mas"):
        self.name = name
        self.agents = agents_list
        
        
    def __len__(self):
        return len(self.agents)

class MARL(TrainableAgent):
    
    def __init__(self, agents_list=[], name='marl'):
        self.name = name
        self.agents = agents_list
        self.experience = marl.experience.make("ReplayMemory", capacity=10000)
        
    def store_experience(self, *args):
        TrainableAgent.store_experience(self, *args)
        observation, action, reward, next_observation, done = args
        for i, ag in enumerate(self.agents):
            if isinstance(ag, TrainableAgent):
                ag.store_experience(observation[i], action[i], reward[i], next_observation[i], done[i])
            
    def update_model(self, t):
        # TrainableAgent.update_model(self, t)        
        for ag in self.agents:
            if isinstance(ag, TrainableAgent):
                ag.update_model(t)
    
    def reset_exploration(self, nb_timesteps):
        # TrainableAgent.update_exploration(self, nb_timesteps)        
        for ag in self.agents:
            if isinstance(ag, TrainableAgent):
                ag.reset_exploration(nb_timesteps)
    
    def update_exploration(self, t):
        # TrainableAgent.update_exploration(self, t)        
        for ag in self.agents:
            if isinstance(ag, TrainableAgent):
                ag.exploration.update(t)
        
    def action(self, observation):
        return [ag.action(obs) for ag, obs in zip(self.agents, observation)]
        
    def greedy_action(self, observation):
        return [Agent.action(ag, obs) for ag, obs in zip(self.agents, observation)]
    
    def save_policy(self, folder='.', filename='', timestep=None):
        """
        Save the policy in a file called '<filename>-<agent_name>-<timestep>'.
        
        :param folder: (str) The path to the directory where to save the model(s)
        :param filename: (str) A specific name for the file (ex: 'test2')
        :param timestep: (int) The current timestep  
        """
        if not os.path.exists(folder):
            os.makedirs(folder)
        filename_tmp = "{}-{}".format(filename, self.name) if filename is not '' else "{}".format(self.name)
        for ag in self.agents:
            if isinstance(ag, TrainableAgent):
                ag.save_policy(folder=folder, filename=filename_tmp, timestep=timestep)
                
    def load_model(self, filename):
        for ag in self.agents:
            if isinstance(ag, TrainableAgent):
                ag.load_model(filename)
                
    def append(self, agent):
        self.agents.append(agent)          
        
    def get_by_name(self, name):
        for ag in self.agents:
            if ag.name == name:
                return ag
        return None
    
    def get_by_id(self, id):
        for ag in self.agents:
            if ag.id == id:
                return ag
        return None
    
    def __len__(self):
        return len(self.agents)     