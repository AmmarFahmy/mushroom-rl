import numpy as np

from PyPi.algorithms.agent import Agent
from PyPi.utils.dataset import max_QA
from PyPi.utils.replay_memory import ReplayMemory


class Buffer(object):
    def __init__(self, size):
        self._size = size

        self._buf = [None] * self._size

    def add(self, sample):
        self._buf.append(sample)
        self._buf = self._buf[1:]

    def get(self):
        s = np.empty(self._buf[0].shape + (self._size,), dtype=np.float32)
        for i in xrange(self._size):
            s[..., i] = self._buf[i]

        return s

class DQN(Agent):
    """
    Deep Q-Network algorithm.
    "Human-Level Control Through Deep Reinforcement Learning".
    Mnih V. et. al.. 2015.
    """
    def __init__(self, approximator, policy, **params):
        self.__name__ = 'DQN'

        alg_params = params['algorithm_params']
        self._batch_size = alg_params.get('batch_size')
        self._clip_reward = alg_params.get('clip_reward', True)
        self._target_approximator = alg_params.get('target_approximator')
        self._train_frequency = alg_params.get('train_frequency')
        self._target_update_frequency = alg_params.get(
            'target_update_frequency')
        self._max_no_op_actions = alg_params.get('max_no_op_actions', 0)
        self._no_op_action_value = alg_params.get('no_op_action_value', 0)

        self._replay_memory = ReplayMemory(alg_params.get('max_replay_size'),
                                           alg_params.get('history_length', 1))
        self._buffer = Buffer(size=alg_params.get('history_length', 1))

        self._n_updates = 0
        self._episode_steps = None
        self._no_op_actions = None

        super(DQN, self).__init__(approximator, policy, **params)

    def fit(self, dataset, n_iterations=1):
        """
        Single fit step.

        # Arguments
            dataset (list): the dataset to use.
        """
        self._replay_memory.add(dataset)
        if n_iterations == 0:
            pass
        else:
            assert n_iterations == 1

            state, action, reward, next_state, absorbing, _ =\
                self._replay_memory.get(self._batch_size)

            if self._clip_reward:
                reward = np.clip(reward, -1, 1)

            sa = [state, action]

            q_next = self._next_q(next_state, absorbing)
            q = reward + self.mdp_info['gamma'] * q_next

            self.approximator.train_on_batch(
                sa, q, **self.params['fit_params'])

            self._n_updates += 1

            if self._n_updates % self._target_update_frequency == 0:
                self._target_approximator.model.set_weights(
                    self.approximator.model.get_weights())

    def _next_q(self, next_state, absorbing):
        """
        Arguments
            next_state (np.array): the state where next action has to be
                evaluated.
            absorbing (np.array): the absorbing flag for the states in
                'next_state'.

        # Returns
            Maximum action-value in 'next_state'.
        """
        max_q, _ = max_QA(next_state, absorbing, self._target_approximator)

        return max_q

    def initialize(self, mdp_info):
        super(DQN, self).initialize(mdp_info)

        self._replay_memory.initialize(self.mdp_info)

    def draw_action(self, state):
        self._buffer.add(state)

        if self._episode_steps < self._no_op_actions:
            action = np.array([self._no_op_action_value])
            self.policy.update()
        else:
            extended_state = self._buffer.get()

            action = super(DQN, self).draw_action(extended_state)

        self._episode_steps += 1

        return action

    def episode_start(self):
        self._no_op_actions = np.random.randint(
            self._replay_memory._history_length, self._max_no_op_actions + 1)
        self._episode_steps = 0

    def __str__(self):
        return self.__name__


class DoubleDQN(DQN):
    """
    Implements functions to run the Double DQN algorithm.
    """
    def __init__(self, approximator, policy, **params):
        self.__name__ = 'DoubleDQN'

        super(DoubleDQN, self).__init__(approximator, policy, **params)

    def _next_q(self, next_state, absorbing):
        """
        Arguments
            next_state (np.array): the state where next action has to be
                evaluated.
            absorbing (np.array): the absorbing flag for the states in
                'next_state'.

        # Returns
            Maximum action-value in 'next_state'.
        """
        _, a_n = max_QA(next_state, absorbing, self.approximator)
        sa_n = [next_state, a_n]

        return self._target_approximator.predict(sa_n)
