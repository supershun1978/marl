import marl
from marl.agent import QAgent, TrainableAgent
from marl.policy import StochasticPolicy, DeterministicPolicy
from marl.tools import super_cat

import torch
import torch.nn as nn
import torch.optim as optim
import copy
import numpy as np


class MAPGAgent(TrainableAgent):
    def __init__(self, critic_model, actor_policy, actor_model, observation_space, action_space, index=None, mas=None, experience="ReplayMemory-1000", exploration="EpsGreedy", lr_actor=0.001, lr_critic=0.001, gamma=0.95, batch_size=32, tau=0.01, use_target_net=False, name="MAACAgent"):
        super(MAPGAgent, self).__init__(policy=actor_policy, model=actor_model, observation_space=observation_space, action_space=action_space, experience=experience, exploration=exploration, lr=lr_actor, gamma=gamma, batch_size=batch_size, name=name)
        
        self.tau = tau
        self.index = index
        self.mas = mas
        
        # Actor model
        self.actor_optimizer = optim.Adam(self.policy.model.parameters(), lr=self.lr)

        # Critic model
        self.critic_model = marl.model.make(critic_model)
        self.critic_criterion = nn.SmoothL1Loss() # Huber criterionin (or nn.MSELoss())
        self.lr_critic = lr_critic
        self.critic_optimizer = optim.Adam(self.critic_model.parameters(), lr=self.lr_critic)
        
        # Init target networks
        self.use_target_net = use_target_net
        if self.use_target_net:
            self.target_critic = copy.deepcopy(self.critic_model)
            self.target_critic.eval()
            
            self.target_policy = copy.deepcopy(self.policy)
            self.target_policy.eval()

            
    def set_mas(self, mas):
        self.mas = mas
    
    def soft_update(self, local_model, target_model, tau):
        for target_param, local_param in zip(target_model.parameters(), local_model.parameters()):
            target_param.data.copy_(tau*local_param.data + (1.0-tau)*target_param.data)
            
    def update_model(self, t):
        if len(self.experience) < self.batch_size:
            return
        
        # Get batches
        ind = self.experience.sample_index(self.batch_size)
        self.global_batch = self.mas.experience.get_transition(len(self.mas.experience) - np.array(ind)-1)
        self.local_batch = self.experience.get_transition(len(self.experience) - np.array(ind)-1)
        
        # Get changing policy
        self.curr_critic = self.target_critic if self.use_target_net else self.critic_model
        
        self.update_critic()
        self.update_actor()
        
        # Compute 
        if self.use_target_net:
            self.soft_update(self.policy.model, self.target_policy.model, self.tau)
            self.soft_update(self.critic_model, self.target_critic, self.tau)
            
    def update_critic(self):
        self.critic_optimizer.zero_grad()
        
        # Calculate target r_i + gamma * Q_i(x,a1',a2',...,aN')
        target_value = self.target()
        
        # Calculate value Q_i(x,a1,a2,...,aN)
        inputs_critic = self._critic_inputs(self.global_batch.observation, self.global_batch.action)
        curr_value = self.critic_model(inputs_critic)
        
        # Calculate critic loss 
        loss = self.critic_criterion(curr_value, target_value)
        
        # Update params
        loss.backward()
        self.critic_optimizer.step()
        
    def update_actor(self):
        self.actor_optimizer.zero_grad()
        # Calcul actor loss
        pd = self.policy.forward(self.local_batch.observation)
        log_prob = pd.log_prob(self.local_batch.action) #.unsqueeze(0)
        gae = self.critic_model(self.global_batch.observation, self.global_batch.action).detach()
        actor_loss = -(log_prob * gae).mean()
        actor_loss.backward()
        self.actor_optimizer.step()
     
    def target(self):
        join_by_agent = lambda  observation_batch, num_ag : [list(observation_batch[:,i]) for i in range(num_ag)]
        tensor_forme = lambda observation, i_ag : torch.tensor([list(i) for i in observation[i_ag]])
        
        next_observ = [tensor_forme(join_by_agent(self.global_batch.next_observation, len(self.mas)),i) for i in range(len(self.mas))]
        next_actions = self.mas.greedy_action(next_observ)

        nextact = []
        for bat in range(self.batch_size):
            nextact.append([next_actions[ag][bat] for ag in range(len(self.mas))])
            
        inputs_critic = self._critic_inputs(self.global_batch.observation, nextact)
        next_action_value = self.curr_critic(inputs_critic)
        
        my_reward = torch.tensor(self.local_batch.reward).view(-1,1)
        my_dones = torch.tensor(np.where(self.local_batch.done_flag,1,0)).view(-1,1)
        return (my_reward + self.gamma * next_action_value * (1-my_dones)).detach().float()
     
    def _critic_inputs(self, batch_obs, batch_act):
        return torch.tensor([super_cat(batch_obs[b], batch_act[b]) for b in range(self.batch_size)]).float()
        
class MAACAgent(MAPGAgent):
    def __init__(self, critic_model, actor_model, observation_space, action_space, index=None, experience="ReplayMemory-1000", exploration="Greedy", lr_actor=0.001, lr_critic=0.001, gamma=0.95, batch_size=32, tau=0.01, use_target_net=False, name="MAACAgent"):
        super(MAACAgent, self).__init__(critic_model=critic_model, actor_policy='StochasticPolicy', actor_model=actor_model, observation_space=observation_space, action_space=action_space, index=index, experience=experience, exploration=exploration, lr_actor=lr_actor, lr_critic=lr_critic, gamma=gamma, batch_size=batch_size, name=name)

class MADDPGAgent(MAPGAgent):
    def __init__(self, critic_model, actor_model, observation_space, action_space, index=None, experience="ReplayMemory-10000", exploration="Greedy", lr_actor=0.01, lr_critic=0.01, gamma=0.95, batch_size=32, tau=0.01, use_target_net=100, name="MAACAgent"):
        super(MADDPGAgent, self).__init__(critic_model=critic_model, actor_policy='DeterministicPolicy', actor_model=actor_model, observation_space=observation_space, action_space=action_space, index=index, experience=experience, exploration=exploration, lr_actor=lr_actor, lr_critic=lr_critic, gamma=gamma, batch_size=batch_size, name=name)
    
    def update_actor(self):
        self.actor_optimizer.zero_grad()
        # Calcul actor loss
        obs = torch.tensor(self.local_batch.observation).float()
        my_action_pred = self.policy.model(obs)
        
        join_by_agent = lambda  observation_batch, num_ag : [list(observation_batch[:,i]) for i in range(num_ag)]
        tensor_forme = lambda observation, i_ag : torch.tensor([list(i) for i in observation[i_ag]])
        
        action_batch = [tensor_forme(join_by_agent(self.global_batch.action, len(self.mas)),i) for i in range(len(self.mas))]
        observation_batch = [tensor_forme(join_by_agent(self.global_batch.observation, len(self.mas)), i) for i in range(len(self.mas))]
        
        action_batch[self.index] = my_action_pred
        
        inp_critic = []
        for b in range(self.batch_size):
            b_o = [observation_batch[ind_ag][b] for ind_ag in range(len(self.mas))]
            b_a = [action_batch[ind_ag][b] for ind_ag in range(len(self.mas))]
            inp_critic.append(torch.cat([torch.cat(b_o), torch.cat(b_a)]).unsqueeze(0))
        inputs_critic = torch.cat(inp_critic)
        actor_loss = -self.critic_model(inputs_critic).mean()

        actor_loss.backward(retain_graph=True)
        self.actor_optimizer.step()