import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt

from simple_network_sim import network_of_populations as ss
from simple_network_sim.sampleUseOfModel import runSimulation, aggregateResults


def generate_education_network_and_pop(bubble_size=24, number_bubbles = 100, between_bubble_prob=0.10, seed=None):
    #  need to generate a pandas dataframe
    graph = nx.fast_gnp_random_graph(number_bubbles, between_bubble_prob, seed=seed)    
    population = pd.DataFrame(columns=['Health_Board', "Sex", "Age", "Total"])
    i = 0
    for node in graph.nodes():
        population.loc[i] = ['bubble_' + str(node), 'Female', 'student', bubble_size]
        i = i+1
    i = 0
    
    connections = pd.DataFrame(columns=['source', 'target', 'weight', 'delta_adjustment'])
    for (u, v) in graph.edges():
        connections.loc[i] = ['bubble_' + str(u), 'bubble_' + str(v), 1, 1.0]
        connections.loc[i+1] = ['bubble_' + str(v), 'bubble_' + str(u), 1, 1.0]
        i = i+2
        
    return population, connections

def plot_for_testing(df, filename):
    # df['date'] = pd.to_datetime(df['date'])    
    for state in ['S', 'E', 'A', 'I', 'R', 'P_T', 'P_F']:
    # for state in set(df['state']):
        thisDF = df[df.state == state][['date', 'mean']]
        plt.plot(range(len(list(thisDF['mean']))), list(thisDF['mean']), label=state)
    plt.legend()
    plt.savefig(filename)
        

pop, conn = generate_education_network_and_pop(bubble_size=20, number_bubbles = 100, between_bubble_prob=0.1)

for test_rate in [0.01, 0.05, 0.1]:
    
    
    prestring = 'test_rate-' + str(test_rate)
    
    transitionRates = pd.read_csv('education_input/compartment_transition_rates_for_education_rounded_test_rate-' + str(test_rate) +'.csv')
    print(transitionRates)
    print('\n\n\n')
    
    mixing_matrix = pd.read_csv('education_input/education_mixing_matrix.csv')
    infections_comps = pd.read_csv("education_input/infectious_comps.csv")
    infection_prob = pd.read_csv("education_input/infection_prob.csv")
    initial_infection = pd.read_csv('education_input/education_initial_infections.csv')
    # trials = pd.read_csv("education_input/trials.csv")
    trials = pd.DataFrame([1], columns=["Value"])
    dates = pd.read_csv("education_input/start_end.csv")
    stoch = pd.read_csv("education_input/stochastic_mode.csv")
    falsePos = 0.023*test_rate
    # print(trials)
    
    
    network, new_issues = ss.createNetworkOfPopulation(
        transitionRates,
        pop,
        conn,
        mixing_matrix,
        infections_comps,
        infection_prob,
        initial_infection,
        trials,
        dates,
        None,
        stoch,
        falsePos)
    
    # print(network)
    
    
    results = runSimulation(network, 143, [])
    
    
    res_agg = aggregateResults(results)
    res_agg[0].to_csv(prestring + 'just_for_jess.csv')
    
    forcheck = res_agg[0][['date', 'state', 'mean']]
    
    sanity_check = forcheck[['date', 'mean']].groupby(['date']).sum()
    print(sanity_check)
    
    # print (forcheck)
    forcheck = forcheck.groupby(['date', 'state']).sum()
    # print(forcheck)
    forcheck.to_csv(prestring + 'summary_for_jess.csv')
    forcheck = pd.read_csv(prestring + 'summary_for_jess.csv')
    plt.clf()
    plot_for_testing(forcheck, prestring + '_basic_output.pdf')
    
    print(res_agg)