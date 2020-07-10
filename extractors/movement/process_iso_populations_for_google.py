import sys
import pandas as pd
import matplotlib.pyplot as plt


population_table = pd.read_csv(sys.argv[1], low_memory=False)
population_table.columns = ['la_code', 'la_name', 'population']
population_table  = population_table[['la_code', 'population']]
# 

lookup_table = pd.read_csv(sys.argv[2], low_memory=False)


lookup_table['full_iso_code'] = "GB-" + lookup_table.iso_3166_2
codes_of_interest = list(lookup_table['full_iso_code'])


lookup_table = lookup_table[['full_iso_code', 'la_code']]


with_pops = lookup_table.join(population_table.set_index('la_code'), on='la_code')
totalPop = sum(with_pops['population'])
with_pops['pop_weighting'] = with_pops['population']/totalPop

weights = with_pops[['full_iso_code','pop_weighting']]
weights.set_index('full_iso_code',inplace = True)


googleTable = pd.read_csv(sys.argv[3], low_memory=False)
justScotGoogle = googleTable[googleTable['iso_3166_2_code'].isin(with_pops['full_iso_code'])]


justScotGoogle['movements_for_decrease'] = (justScotGoogle['transit_stations_percent_change_from_baseline'] + justScotGoogle['workplaces_percent_change_from_baseline'] + justScotGoogle['retail_and_recreation_percent_change_from_baseline'])/3

categories_for_decrease = ['transit_stations_percent_change_from_baseline', 'workplaces_percent_change_from_baseline', 'retail_and_recreation_percent_change_from_baseline']
justScotGoogle = justScotGoogle[['iso_3166_2_code', 'date', 'movements_for_decrease']]

justScotGoogle = justScotGoogle.merge(weights,left_on = 'iso_3166_2_code',right_index = True,how='left')
justScotGoogle ['weighted_moves'] = (justScotGoogle['movements_for_decrease']*justScotGoogle['pop_weighting'])
justScotGoogle = justScotGoogle [['date', 'weighted_moves']]
justScotGoogle['date'] = pd.to_datetime(justScotGoogle['date'])

justScotGoogle = justScotGoogle.groupby('date').sum()
justScotGoogle['weighted_moves'] = 1.0 + justScotGoogle['weighted_moves']/100.0
justScotGoogle.index = pd.to_datetime(justScotGoogle.index)

justScotGoogle = justScotGoogle[justScotGoogle.index.dayofweek <5]

justScotGoogle.to_csv('movement_multiplier.csv')
