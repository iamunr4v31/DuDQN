import numpy as np
import torch as T
from DeepQNet import DQN
from replay_memory import ReplayBuffer


class Agent:
    def __init__(self, gamma, epsilon, lr, n_actions, input_dims,
                 memory_size, batch_size, eps_min=0.01, decay_rate=5e-7,
                 replace=1000, algo=None, env_name=None, checkpoint_dir="tmp/dqn") -> None:
        self.gamma = gamma
        self.epsilon = epsilon
        self.lr = lr
        self.n_actions = n_actions
        self.input_dims = input_dims
        self.memory_size = memory_size
        self.batch_size = batch_size
        self.eps_min = eps_min
        self.decay_rate = decay_rate
        self.replace_target_count = replace
        self.algo = algo
        self.env_name = env_name
        self.checkpoint_dir = checkpoint_dir
        self.action_space = list(range(self.n_actions))
        self.learn_step_counter = 0 # C steps

        self.memory = ReplayBuffer(self.memory_size, self.input_dims, self.n_actions)
        
        self.Q_eval = DQN(self.lr, self.n_actions, name=f"{self.env_name}_{self.algo}_q_eval",
                        input_dims=self.input_dims, checkpoint_dir=self.checkpoint_dir)
        
        self.Q_next = DQN(self.lr, self.n_actions, name=f"{self.env_name}_{self.algo}_q_next",
                        input_dims=self.input_dims, checkpoint_dir=self.checkpoint_dir)

    def choose_action(self, observation):
        if np.random.random() > self.epsilon:
            state = T.tensor(np.array([observation]), dtype=T.float).to(self.Q_eval.device) # batch_size * input_dims
            q_values = self.Q_eval.forward(state)
            action = T.argmax(q_values).item()
        else:
            action = np.random.choice(self.action_space)
        
        return action
    
    def decrement_epsilon(self):
        self.epsilon = self.epsilon - self.decay_rate if self.epsilon > self.eps_min else self.eps_min
    
    def store_transition(self, state, action, reward, done, next_state):
        self.memory.store_transition(state, action, reward, done, next_state)

    def sample_memory(self):
        state, action, reward, done, next_state = self.memory.sample_buffer(self.batch_size)
    
        states = T.tensor(state, dtype=T.float).to(self.Q_eval.device)
        actions = T.tensor(action, dtype=T.long).to(self.Q_eval.device)
        rewards = T.tensor(reward, dtype=T.float).to(self.Q_eval.device)
        dones = T.tensor(done, dtype=T.bool).to(self.Q_eval.device)
        next_states = T.tensor(next_state, dtype=T.float).to(self.Q_eval.device)

        return states, actions, rewards, dones, next_states
    
    def replace_target_network(self):
        if self.learn_step_counter == self.replace_target_count:
            self.Q_next.load_state_dict(self.Q_eval.state_dict())
    
    def save_models(self):
        self.Q_eval.save_checkpoint()
        self.Q_next.save_checkpoint()
    
    def load_models(self):
        self.Q_eval.load_checkpoint()
        self.Q_next.load_checkpoint()
    
    def learn(self):
        if self.memory.memory_counter > self.batch_size:
            self.Q_eval.optimizer.zero_grad()
            self.replace_target_network()
            states, actions, rewards, dones, next_states = self.sample_memory()
            
            indicies = np.arange(self.batch_size)
            q_pred = self.Q_eval.forward(states)[indicies, actions]
            q_next = self.Q_next.forward(next_states).max(dim=1)[0]

            q_next[dones] = 0.0
            q_target = rewards + self.gamma * q_next
            loss = self.Q_eval.criterion(q_target, q_pred).to(self.Q_eval.device)
            loss.backward()
            self.Q_eval.optimizer.step()
            self.learn_step_counter+=1

            self.decrement_epsilon()

