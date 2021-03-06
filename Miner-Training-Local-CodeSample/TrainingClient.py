import sys
from DDQN_torch import DQN # A class of creating a deep q-learning model
from MinerEnv import MinerEnv # A class of creating a communication environment between the DQN model and the GameMiner environment (GAME_SOCKET_DUMMY.py)
from Memory import Memory # A class of creating a batch in order to store experiences for the training process
import torch
import pandas as pd
import datetime 
import numpy as np
import random


HOST = "localhost"
PORT = 1111
if len(sys.argv) == 3:
    HOST = str(sys.argv[1])
    PORT = int(sys.argv[2])

# Create header for saving DQN learning file
now = datetime.datetime.now() #Getting the latest datetime
header = ["Ep", "Step", "Reward","Score", "Total_reward", "Action", "Energy"] #Defining header for the save file
filename = "Data/data_" + now.strftime("%Y%m%d-%H%M") + ".csv" 
with open(filename, 'w') as f:
    pd.DataFrame(columns=header).to_csv(f, encoding='utf-8', index=False, header=True)

# Parameters for training a DQN model
N_EPISODE = 10000 #The number of episodes for training
MAX_STEP = 100   #The number of steps for each episode
BATCH_SIZE = 32   #The number of experiences for each replay 
MEMORY_SIZE = 100000 #The size of the batch for storing experiences
INITIAL_REPLAY_SIZE = 1000 #The number of experiences are stored in the memory batch before starting replaying
INPUTNUM = 198 #The number of input values for the DQN model
ACTIONNUM = 6  #The number of actions output from the DQN model
MAP_MAX_X = 21 #Width of the Map
MAP_MAX_Y = 9  #Height of the Map
update_peri = 10000
device = "cuda:0" if torch.cuda.is_available() else "cpu"
# Initialize a DQN model and a memory batch for storing experiences
DQNAgent = DQN(INPUTNUM, ACTIONNUM, device)
memory = Memory(MEMORY_SIZE)

# Initialize environment
minerEnv = MinerEnv(HOST, PORT) #Creating a communication environment between the DQN model and the game environment (GAME_SOCKET_DUMMY.py)
minerEnv.start()  # Connect to the game

train = False #The variable is used to indicate that the replay starts, and the epsilon starts decrease.
#Training Process
#the main part of the deep-q learning agorithm 
for episode_i in range(0, N_EPISODE):
    try:
        loss_lst = [0]
        maker = None
        # Choosing a map in the list
        mapID = random.choice([1,2]) #Choosing a map ID from 5 maps in Maps folder randomly
        posID_x = np.random.randint(MAP_MAX_X) #Choosing a initial position of the DQN agent on X-axes randomly
        posID_y = np.random.randint(MAP_MAX_Y) #Choosing a initial position of the DQN agent on Y-axes randomly
        #Creating a request for initializing a map, initial position, the initial energy, and the maximum number of steps of the DQN agent
        request = ("map" + str(mapID) + "," + str(posID_x) + "," + str(posID_y) + ",50,100") 
        #Send the request to the game environment (GAME_SOCKET_DUMMY.py)
        minerEnv.send_map_info(request)
        mine_bound = random.choice([i for i in range(3)])
        mine_explore = 1
        # Getting the initial state
        minerEnv.reset() #Initialize the game environment
        s = minerEnv.get_state()#Get the state after reseting. 
                                #This function (get_state()) is an example of creating a state for the DQN model 
        total_reward = 0 #The amount of rewards for the entire episode
        terminate = False #The variable indicates that the episode ends
        maxStep = minerEnv.state.mapInfo.maxStep #Get the maximum number of steps for each episode in training
        #Start an episde for training
        for step in range(0, maxStep):
            gold = minerEnv.state.mapInfo.golds
            posx = minerEnv.state.x
            posy = minerEnv.state.y
            action, mine_incre = DQNAgent.act(s, gold, posx, posy, mine_explore, mine_bound)
            if mine_incre:
                mine_explore += 1
            maker = DQNAgent.maker  # Getting an action from the DQN model from the state (s)
            minerEnv.step(str(action))  # Performing the action in order to obtain the new state
            s_next = minerEnv.get_state()  # Getting a new state
            reward = minerEnv.get_reward()  # Getting a reward
            terminate = minerEnv.check_terminate()  # Checking the end status of the episode
            done = 1 if terminate is True else 0
            score = minerEnv.state.score
            energy = minerEnv.state.energy
            status = minerEnv.state.status

            # Add this transition to the memory batch
            memory.push(s, action, reward, done , s_next)

            # Sample batch memory to train network
            if (memory.length > INITIAL_REPLAY_SIZE):
                #If there are INITIAL_REPLAY_SIZE experiences in the memory batch
                #then start replaying
                batch = memory.sample(BATCH_SIZE) #Get a BATCH_SIZE experiences for replaying
                DQNAgent.replay(batch, BATCH_SIZE)#Do relaying
                train = True #Indicate the training starts
                loss_lst.append(DQNAgent.loss)
            total_reward = total_reward + reward #Plus the reward to the total rewad of the episode
            s = s_next #Assign the next state for the next step.

            # Saving data to file if the decision is belong to agent
            if maker == "Agent":
              save_data = np.hstack(
                [episode_i + 1, step + 1, reward, score, total_reward, action, energy ]).reshape(1, 7)
              with open(filename, 'a') as f:
                  pd.DataFrame(save_data).to_csv(f, encoding='utf-8', index=False, header=False)
            
            if terminate == True:
                #If the episode ends, then go to the next episode
                break
        if ((episode_i+1) % update_peri == 0) and train == True:
            DQNAgent.target_train()
        #Print the training information after the episode
        print('Episode %d ends. Number of steps is: %d. Accumulated Reward = %.2f. Epsilon = %.2f .Score: %d .Energy: %d .Status: %d .Loss %d'  % (
            episode_i + 1, step + 1, total_reward, DQNAgent.epsilon, score, energy, status, sum(loss_lst)/(step+1)))
        
        #Decreasing the epsilon if the replay starts
        if train == True:
            DQNAgent.update_epsilon()
    except Exception as e:
      import traceback

      traceback.print_exc()
      print("Finished.")
      break

print("Finished")
DQNAgent.save_model("/content/Trained_Agent/", "DQN_ver1")
