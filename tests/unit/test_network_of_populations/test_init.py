# pylint: disable=too-many-lines
import copy
import datetime as dt

from data_pipeline_api import standard_api
import networkx as nx
import numpy
import pandas as pd
import pytest

from simple_network_sim import loaders
from simple_network_sim import network_of_populations as np


def _count_people_per_region(state):
    return [sum(region.values()) for region in state.values()]


@pytest.mark.parametrize("region", ["S08000024", "S08000030"])
@pytest.mark.parametrize("num_infected", [0, 10])
def test_basicSimulationInternalAgeStructure_invariants(data_api, region, num_infected, short_simulation_dates):
    network, _ = np.createNetworkOfPopulation(
        data_api.read_table("human/compartment-transition", "compartment-transition"),
        data_api.read_table("human/population", "population"),
        data_api.read_table("human/commutes", "commutes"),
        data_api.read_table("human/mixing-matrix", "mixing-matrix"),
        data_api.read_table("human/infectious-compartments", "infectious-compartments"),
        data_api.read_table("human/infection-probability", "infection-probability"),
        data_api.read_table("human/initial-infections", "initial-infections"),
        data_api.read_table("human/trials", "trials"),
        short_simulation_dates,
    )

    initial_population = sum(_count_people_per_region(network.initialState))
    old_network = copy.deepcopy(network)

    result, _ = np.basicSimulationInternalAgeStructure(network, {region: {"[0,17)": num_infected}}, numpy.random.default_rng(123))

    # population remains constant
    populations = result.groupby("date").total.sum()
    assert all([total == pytest.approx(initial_population) for node, total in populations.to_dict().items()])

    # the graph is unchanged
    assert nx.is_isomorphic(old_network.graph, network.graph)

    # infection matrix is unchanged
    assert list(network.mixingMatrix) == list(old_network.mixingMatrix)
    for a in network.mixingMatrix:
        assert list(network.mixingMatrix[a]) == list(old_network.mixingMatrix[a])
        for b in network.mixingMatrix[a]:
            assert network.mixingMatrix[a][b] == old_network.mixingMatrix[a][b]


@pytest.mark.parametrize("region", ["S08000024", "S08000030", "S08000016"])
@pytest.mark.parametrize("num_infected", [0, 10, 1000])
def test_basicSimulationInternalAgeStructure_no_movement_of_people_invariants(data_api, region, num_infected,
                                                                              short_simulation_dates):
    network, _ = np.createNetworkOfPopulation(
        data_api.read_table("human/compartment-transition", "compartment-transition"),
        data_api.read_table("human/population", "population"),
        data_api.read_table("human/commutes", "commutes"),
        data_api.read_table("human/mixing-matrix", "mixing-matrix"),
        data_api.read_table("human/infectious-compartments", "infectious-compartments"),
        data_api.read_table("human/infection-probability", "infection-probability"),
        data_api.read_table("human/initial-infections", "initial-infections"),
        data_api.read_table("human/trials", "trials"),
        short_simulation_dates,
        pd.DataFrame([{"Date": "2020-03-16", "Movement_Multiplier": 0.0, "Contact_Multiplier": 1.0}]),
    )

    initial_population = sum(_count_people_per_region(network.initialState))
    old_network = copy.deepcopy(network)

    result, _ = np.basicSimulationInternalAgeStructure(network, {region: {"[0,17)": num_infected}}, numpy.random.default_rng(123))

    # population remains constant
    populations = result.groupby("date").total.sum()
    assert all([total == pytest.approx(initial_population) for node, total in populations.to_dict().items()])

    # the graph is unchanged
    assert nx.is_isomorphic(old_network.graph, network.graph)

    # infection matrix is unchanged
    assert list(network.mixingMatrix) == list(old_network.mixingMatrix)
    for a in network.mixingMatrix:
        assert list(network.mixingMatrix[a]) == list(old_network.mixingMatrix[a])
        for b in network.mixingMatrix[a]:
            assert network.mixingMatrix[a][b] == old_network.mixingMatrix[a][b]

    # no spread across regions
    assert result[(result.node != region) & (result.state.isin(network.infectiousStates))].total.sum() == 0.0


@pytest.mark.parametrize("n_infected", [0, 10, 1000])
def test_basicSimulationInternalAgeStructure_no_node_infection_invariant(data_api, n_infected, short_simulation_dates):
    nodes = pd.DataFrame([{"source": "S08000016", "target": "S08000016", "weight": 0.0, "delta_adjustment": 1.0}])
    population = pd.DataFrame([
        {"Health_Board": "S08000016", "Sex": "Female", "Age": "[0,17)", "Total": 31950},
        {"Health_Board": "S08000016", "Sex": "Female", "Age": "[17,70)", "Total": 31950},
        {"Health_Board": "S08000016", "Sex": "Female", "Age": "70+", "Total": 31950},
    ])
    dampening = pd.DataFrame([{"Date": "2020-03-16", "Movement_Multiplier": 1.0, "Contact_Multiplier": 0.0}])
    network, _ = np.createNetworkOfPopulation(
        data_api.read_table("human/compartment-transition", "compartment-transition"),
        population,
        nodes,
        data_api.read_table("human/mixing-matrix", "mixing-matrix"),
        data_api.read_table("human/infectious-compartments", "infectious-compartments"),
        data_api.read_table("human/infection-probability", "infection-probability"),
        data_api.read_table("human/initial-infections", "initial-infections"),
        data_api.read_table("human/trials", "trials"),
        short_simulation_dates,
        dampening,
    )

    initial_population = sum(_count_people_per_region(network.initialState))

    result, _ = np.basicSimulationInternalAgeStructure(network, {"S08000016": {"[17,70)": n_infected}}, numpy.random.default_rng(123))

    # population remains constant
    populations = result.groupby("date").total.sum()
    assert all([total == pytest.approx(initial_population) for node, total in populations.to_dict().items()])

    # susceptibles are never infected
    for total in result[result.state == "S"].groupby("date").total.sum().to_list():
        assert total == 3 * 31950 - n_infected


def test_basicSimulationInternalAgeStructure_no_infection_prob(data_api, short_simulation_dates):
    network, _ = np.createNetworkOfPopulation(
        data_api.read_table("human/compartment-transition", "compartment-transition"),
        data_api.read_table("human/population", "population"),
        data_api.read_table("human/commutes", "commutes"),
        data_api.read_table("human/mixing-matrix", "mixing-matrix"),
        data_api.read_table("human/infectious-compartments", "infectious-compartments"),
        pd.DataFrame([{"Date": "2020-03-16", "Value": 0.0}]),
        data_api.read_table("human/initial-infections", "initial-infections"),
        data_api.read_table("human/trials", "trials"),
        short_simulation_dates
    )
    susceptibles = 0.0
    for region in network.initialState.values():
        for (age, state) in region.keys():
            if state == "S":
                susceptibles += region[(age, state)]

    people_to_infect = 30
    result, _ = np.basicSimulationInternalAgeStructure(network, {"S08000024": {"[0,17)": people_to_infect}}, numpy.random.default_rng(123))

    new_susceptibles = result[(result.date == result.date.max()) & (result.state == "S")].total.sum()
    assert new_susceptibles + people_to_infect == susceptibles


def test_basicSimulationInternalAgeStructure_no_infection_prob_before_time_25(data_api, short_simulation_dates):
    def count_susceptibles(states):
        susceptibles = 0.0
        for region in states.values():
            for (age, state) in region.keys():
                if state == "S":
                    susceptibles += region[(age, state)]
        return susceptibles

    network, _ = np.createNetworkOfPopulation(
        data_api.read_table("human/compartment-transition", "compartment-transition"),
        data_api.read_table("human/population", "population"),
        data_api.read_table("human/commutes", "commutes"),
        data_api.read_table("human/mixing-matrix", "mixing-matrix"),
        data_api.read_table("human/infectious-compartments", "infectious-compartments"),
        pd.DataFrame([{"Date": "2020-03-16", "Value": 0.0}, {"Date": "2020-04-10", "Value": 1.0}]),
        data_api.read_table("human/initial-infections", "initial-infections"),
        data_api.read_table("human/trials", "trials"),
        short_simulation_dates
    )
    people_to_infect = 30
    susceptibles = count_susceptibles(network.initialState) - people_to_infect

    result, _ = np.basicSimulationInternalAgeStructure(network, {"S08000024": {"[0,17)": people_to_infect}}, numpy.random.default_rng(123))
    result.date = pd.to_datetime(result.date)
    inflection_date = pd.Timestamp(network.startDate + dt.timedelta(days=25))

    # no infection before time 25
    for total in result[(result.date < inflection_date) & (result.state == "S")].groupby("date").total.sum().to_list():
        assert total == susceptibles

    # infections happen after time 25
    for total in result[(result.date >= inflection_date) & (result.state == "S")].groupby("date").total.sum().to_list():
        assert total != susceptibles


def test_createNetworkOfPopulation_missing_population_table_nodes(data_api, short_simulation_dates):
    progression = pd.DataFrame([
        {"age": "70+", "src": "D", "dst": "D", "rate": 1.0},
        {"age": "70+", "src": "A", "dst": "D", "rate": 0.1},
        {"age": "70+", "src": "A", "dst": "A", "rate": 0.9},
        {"age": "70+", "src": "E", "dst": "E", "rate": 0.1},
        {"age": "70+", "src": "E", "dst": "A", "rate": 0.9},
    ])
    population = pd.DataFrame([
        {"Health_Board": "S08000016", "Sex": "Female", "Age": "70+", "Total": 31950},
    ])
    commutes = pd.DataFrame([
        {"source": "S08000015", "target": "S08000016", "weight": 100777.0, "delta_adjustment": 1.0},
        {"source": "S08000016", "target": "S08000015", "weight": 107.0, "delta_adjustment": 1.0},
    ])
    mixingMatrix = pd.DataFrame([{"source": "70+", "target": "70+", "mixing": 2.0}])
    infectious = pd.DataFrame({"Compartment": ["A"]})
    infection_prob = pd.DataFrame([{"Date": "2020-03-16", "Value": 1.0}])
    initial = pd.DataFrame({"Health_Board": ["S08000016"], "Age": ["70+"], "Infected": [40]})

    model, issues = np.createNetworkOfPopulation(
        progression,
        population,
        commutes,
        mixingMatrix,
        infectious,
        infection_prob,
        initial,
        data_api.read_table("human/trials", "trials"),
        short_simulation_dates
    )

    result, sim_issues = np.basicSimulationInternalAgeStructure(model, {"S08000016": {"70+": 40}}, numpy.random.default_rng(123))

    assert result[result.node == "S08000015"].total.sum() == 0
    assert pytest.approx(result[(result.date == "2020-04-16") & (result.state == "D")].total.sum(), 31950)
    assert issues == [
        standard_api.Issue(
            description="Node S08000015 is not in the population table, assuming population of 0 for all ages",
            severity=5,
        )
    ]
    assert not sim_issues


def test_createNetworkOfPopulation_missing_connections(data_api, short_simulation_dates):
    progression = pd.DataFrame([
        {"age": "70+", "src": "D", "dst": "D", "rate": 1.0},
        {"age": "70+", "src": "A", "dst": "D", "rate": 0.1},
        {"age": "70+", "src": "A", "dst": "A", "rate": 0.9},
        {"age": "70+", "src": "E", "dst": "E", "rate": 0.1},
        {"age": "70+", "src": "E", "dst": "A", "rate": 0.9},
    ])
    population = pd.DataFrame([
        {"Health_Board": "S08000016", "Sex": "Female", "Age": "70+", "Total": 31950},
        {"Health_Board": "S08000015", "Sex": "Female", "Age": "70+", "Total": 12342},
    ])
    commutes = pd.DataFrame([
        {"source": "S08000016", "target": "S08000016", "weight": 107.0, "delta_adjustment": 1.0},
    ])
    mixingMatrix = pd.DataFrame([{"source": "70+", "target": "70+", "mixing": 2.0}])
    infectious = pd.DataFrame({"Compartment": ["A"]})
    infection_prob = pd.DataFrame([{"Date": "2020-03-16", "Value": 1.0}])
    initial = pd.DataFrame({"Health_Board": ["S08000016"], "Age": ["70+"], "Infected": [40]})

    model, issues = np.createNetworkOfPopulation(
        progression,
        population,
        commutes,
        mixingMatrix,
        infectious,
        infection_prob,
        initial,
        data_api.read_table("human/trials", "trials"),
        short_simulation_dates
    )

    result, sim_issues = np.basicSimulationInternalAgeStructure(model, {"S08000016": {"70+": 40}}, numpy.random.default_rng(123))

    assert pytest.approx(result[(result.date == "2020-04-16") & (result.state == "D")].total.sum(), 31950)
    assert result[result.node == "S08000015"].empty
    assert issues == [
        standard_api.Issue(
            description="These nodes have no contacts in the current network: S08000015",
            severity=5,
        )
    ]
    assert not sim_issues


def test_internalStateDiseaseUpdate_one_transition():
    current_state = {("o", "E"): 100.0, ("o", "A"): 0.0}
    probs = {"o": {"E": {"A": 0.4, "E": 0.6}, "A": {"A": 1.0}}}

    new_state = np.internalStateDiseaseUpdate(current_state, probs, False, None)

    assert new_state == {("o", "E"): 60.0, ("o", "A"): 40.0}


def test_internalStateDiseaseUpdate_no_transitions():
    current_state = {("o", "E"): 100.0, ("o", "A"): 0.0}
    probs = {"o": {"E": {"E": 1.0}, "A": {"A": 1.0}}}

    new_state = np.internalStateDiseaseUpdate(current_state, probs, False, None)

    assert new_state == {("o", "E"): 100.0, ("o", "A"): 0.0}


def test_doInternalProgressionAllNodes_e_to_a_progression():
    states = {"region1": {("o", "E"): 100.0, ("o", "A"): 0.0}}
    probs = {"o": {"E": {"A": 0.4, "E": 0.6}, "A": {"A": 1.0}}}

    progression = np.getInternalProgressionAllNodes(states, probs, False, None)

    assert progression == {"region1": {("o", "E"): 60.0, ("o", "A"): 40.0}}
    assert states == {"region1": {("o", "E"): 100.0, ("o", "A"): 0.0}}  # unchanged


@pytest.mark.parametrize("susceptible", [0.5, 100.0, 300.0])
@pytest.mark.parametrize("infectious", [0.5, 100.0, 300.0])
@pytest.mark.parametrize("asymptomatic", [0.5, 100.0, 300.0])
@pytest.mark.parametrize("contact_rate", [0.0, 0.2, 1.0, 3.0])
@pytest.mark.parametrize("dampening", [1.0, 0.0, 0.5, 2.0])
def test_doInternalInfectionProcess_simple(susceptible, infectious, asymptomatic, contact_rate, dampening):
    current_state = {("m", "S"): susceptible, ("m", "A"): asymptomatic, ("m", "I"): infectious}
    age_matrix = loaders.MixingMatrix({"m": {"m": contact_rate}})

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, dampening, ["I", "A"], False, None)

    probability_of_susceptible = susceptible / (susceptible + infectious + asymptomatic)
    contacts = contact_rate * (asymptomatic + infectious)
    assert new_infected["m"] == probability_of_susceptible * contacts * dampening


def test_doInternalInfectionProcess_simple_stochastic():
    current_state = {("m", "S"): 100, ("m", "A"): 50, ("m", "I"): 50}
    age_matrix = loaders.MixingMatrix({"m": {"m": 2}})

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], True,
                                                          numpy.random.default_rng(123))
    assert new_infected["m"] == 93


def test_doInternalInfectionProcess_stochastic():
    current_state = {("m", "S"): 100, ("m", "A"): 50, ("m", "I"): 50}
    age_matrix = loaders.MixingMatrix({"m": {"m": 200}})

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], True,
                                                          numpy.random.default_rng(123))
    assert new_infected["m"] == 9678


def test_doInternalInfectionProcess_empty_age_group():
    current_state = {("m", "S"): 0.0, ("m", "A"): 0.0, ("m", "I"): 0.0}
    age_matrix = loaders.MixingMatrix({"m": {"m": 0.0}})

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], False, None)
    assert new_infected["m"] == 0.0

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], True,
                                                          numpy.random.default_rng(123))
    assert isinstance(new_infected["m"], int)
    assert new_infected["m"] == 0


def test_doInternalInfectionProcess_no_contact():
    current_state = {("m", "S"): 500.0, ("m", "A"): 100.0, ("m", "I"): 100.0}
    age_matrix = loaders.MixingMatrix({"m": {"m": 0.0}})

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], False, None)
    assert new_infected["m"] == 0.0

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], True,
                                                          numpy.random.default_rng(123))
    assert new_infected["m"] == 0


def test_doInternalInfectionProcess_no_susceptibles():
    current_state = {("m", "S"): 0.0, ("m", "A"): 100.0, ("m", "I"): 100.0}
    age_matrix = loaders.MixingMatrix({"m": {"m": 0.2}})

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], False, None)
    assert new_infected["m"] == 0.0

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], True,
                                                          numpy.random.default_rng(123))
    assert isinstance(new_infected["m"], int)
    assert new_infected["m"] == 0


def test_doInternalInfectionProcess_no_infectious():
    current_state = {("m", "S"): 300.0, ("m", "A"): 0.0, ("m", "I"): 0.0}
    age_matrix = loaders.MixingMatrix({"m": {"m": 0.2}})

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], False, None)
    assert new_infected["m"] == 0.0

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], True,
                                                          numpy.random.default_rng(123))
    assert new_infected["m"] == 0


def test_doInternalInfectionProcess_only_A_and_I_count_as_infectious():
    current_state = {
        ("m", "S"): 300.0,
        ("m", "E"): 100.0,
        ("m", "A"): 0.0,
        ("m", "I"): 0.0,
        ("m", "H"): 100.0,
        ("m", "D"): 100.0,
        ("m", "R"): 100.0,
    }
    age_matrix = loaders.MixingMatrix({"m": {"m": 0.2}})

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], False, None)
    assert new_infected["m"] == 0.0

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], True,
                                                          numpy.random.default_rng(123))
    assert new_infected["m"] == 0


def test_doInternalInfectionProcess_between_ages():
    current_state = {
        ("m", "S"): 20.0,
        ("m", "A"): 150.0,
        ("m", "I"): 300,
        ("o", "S"): 15.0,
        ("o", "A"): 200.0,
        ("o", "I"): 100.0,
    }
    age_matrix = loaders.MixingMatrix({"m": {"m": 0.2, "o": 0.5}, "o": {"o": 0.3, "m": 0.5}})

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], False, None)

    assert new_infected["m"] == (20.0 / 470.0) * ((450.0 * 0.2) + (300.0 * 0.5))
    assert new_infected["o"] == (15.0 / 315.0) * ((300.0 * 0.3) + (450.0 * 0.5))

    new_infected = np.getInternalInfectiousContactsInNode(current_state, age_matrix, 1.0, ["I", "A"], True,
                                                          numpy.random.default_rng(123))
    assert new_infected == {"m": 12, "o": 13}


def test_doInternalInfectionProcessAllNodes_single_compartment():
    nodes = {"region1": {("m", "S"): 300.0, ("m", "E"): 0.0, ("m", "A"): 100.0, ("m", "I"): 0.0}}
    age_matrix = loaders.MixingMatrix({"m": {"m": 0.2}})

    infections = np.getInternalInfectiousContacts(nodes, age_matrix, 1.0, ["I", "A"], False, None)
    assert infections == {"region1": {"m": (300.0 / 400.0) * (0.2 * 100.0)}}
    assert nodes == {"region1": {("m", "S"): 300.0, ("m", "E"): 0.0, ("m", "A"): 100.0, ("m", "I"): 0.0}}  # unchanged

    infections = np.getInternalInfectiousContacts(nodes, age_matrix, 1.0, ["I", "A"], True, numpy.random.default_rng(1))
    assert infections == {"region1": {"m": 14}}
    assert nodes == {"region1": {("m", "S"): 300.0, ("m", "E"): 0.0, ("m", "A"): 100.0, ("m", "I"): 0.0}}  # unchanged


def test_doInternalInfectionProcessAllNodes_large_num_infected_ignored():
    nodes = {"region1": {("m", "S"): 300.0, ("m", "E"): 0.0, ("m", "A"): 100.0, ("m", "I"): 0.0}}
    age_matrix = loaders.MixingMatrix({"m": {"m": 5.0}})

    new_infected = np.getInternalInfectiousContacts(nodes, age_matrix, 1.0, ["I", "A"], False, None)
    assert new_infected == {"region1": {"m": (300.0 / 400.0) * (100.0 * 5.0)}}

    new_infected = np.getInternalInfectiousContacts(nodes, age_matrix, 1.0, ["I", "A"], True,
                                                    numpy.random.default_rng(1))
    assert new_infected == {"region1": {"m": 385}}


def test_dateRange():
    start_date = dt.date(2020, 1, 1)
    end_date = dt.date(2020, 2, 1)

    dates = list(np.dateRange(start_date, end_date))

    assert start_date not in dates
    assert end_date in dates
    assert len(dates) == 31
    assert len(sorted(dates)) == 31


def test_dateRange_invalid_dates():
    with pytest.raises(ValueError):
        _ = list(np.dateRange(dt.date(2020, 1, 1), dt.date(2019, 1, 1)))


def test_dateRange_empty_dates():
    dates = list(np.dateRange(dt.date(2020, 1, 1), dt.date(2020, 1, 1)))
    assert len(dates) == 0


def test_getInitialParameter_multipliers():
    multipliers = np.getInitialParameter(dt.date(2020, 1, 1), {dt.date(2020, 1, 1): loaders.Multiplier(0., 0.)},
                                         None, False)
    assert multipliers == loaders.Multiplier(0., 0.)

    multipliers = np.getInitialParameter(dt.date(2020, 1, 1), {dt.date(2019, 1, 1): loaders.Multiplier(0., 0.)},
                                         None, False)
    assert multipliers == loaders.Multiplier(0., 0.)

    multipliers = np.getInitialParameter(dt.date(2020, 1, 1), {dt.date(2020, 1, 2): loaders.Multiplier(0., 0.)},
                                         loaders.Multiplier(1.0, 1.0), False)
    assert multipliers == loaders.Multiplier(1.0, 1.0)

    multipliers = np.getInitialParameter(dt.date(2020, 12, 31), {
        dt.date(2020, 1, 1): loaders.Multiplier(0., 0.),
        dt.date(2021, 1, 1): loaders.Multiplier(10., 10.),
    }, None, False)
    assert multipliers == loaders.Multiplier(0., 0.)


def test_getInitialParameter_infection_proba():
    multipliers = np.getInitialParameter(dt.date(2020, 1, 1), {dt.date(2020, 1, 1): 1.0}, None, True)
    assert multipliers == 1.0

    multipliers = np.getInitialParameter(dt.date(2020, 1, 1), {dt.date(2019, 1, 1): 1.0}, None, True)
    assert multipliers == 1.0

    with pytest.raises(ValueError):
        np.getInitialParameter(dt.date(2020, 1, 1), {dt.date(2020, 1, 2): 1.0}, None, True)

    with pytest.raises(ValueError):
        np.getInitialParameter(dt.date(2020, 1, 1), {dt.date(2020, 1, 2): 1.0}, 1.0, True)

    multipliers = np.getInitialParameter(dt.date(2020, 12, 31), {dt.date(2020, 1, 1): 0.5, dt.date(2021, 1, 1): 1.0},
                                         None, True)
    assert multipliers == 0.5


def test_doIncomingInfectionsByNode_no_susceptibles():
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")
    graph.add_edge("r1", "r2")

    state = {
        "r1": {("m", "S"): 0.0, ("m", "E"): 0.0, ("m", "A"): 10.0, ("m", "I"): 5.0},
        "r2": {("m", "S"): 0.0, ("m", "E"): 0.0, ("m", "A"): 10.0, ("m", "I"): 5.0},
    }

    totalIncomingInfectionsByNode = np.getIncomingInfectiousContactsByNode(graph, state, 1.0, ["I", "A"], False, None)
    assert totalIncomingInfectionsByNode == {"r1": 0.0, "r2": 0.0}

    totalIncomingInfectionsByNode = np.getIncomingInfectiousContactsByNode(graph, state, 1.0, ["I", "A"], True,
                                                                           numpy.random.default_rng(123))
    assert isinstance(totalIncomingInfectionsByNode["r1"], int)
    assert isinstance(totalIncomingInfectionsByNode["r2"], int)
    assert totalIncomingInfectionsByNode == {"r1": 0, "r2": 0}


def test_doIncomingInfectionsByNode_no_connections():
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")

    state = {
        "r1": {("m", "S"): 100.0, ("m", "E"): 0.0, ("m", "A"): 10.0, ("m", "I"): 5.0},
        "r2": {("m", "S"): 100.0, ("m", "E"): 0.0, ("m", "A"): 10.0, ("m", "I"): 5.0},
    }

    totalIncomingInfectionsByNode = np.getIncomingInfectiousContactsByNode(graph, state, 1.0, ["I", "A"], False, None)
    assert totalIncomingInfectionsByNode == {"r1": 0.0, "r2": 0.0}

    totalIncomingInfectionsByNode = np.getIncomingInfectiousContactsByNode(graph, state, 1.0, ["I", "A"], True,
                                                                           numpy.random.default_rng(123))
    assert isinstance(totalIncomingInfectionsByNode["r1"], int)
    assert isinstance(totalIncomingInfectionsByNode["r2"], int)
    assert totalIncomingInfectionsByNode == {"r1": 0, "r2": 0}


def test_doIncomingInfectionsByNode_weight_delta_adjustment():
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")
    graph.add_edge("r1", "r2", weight=100, delta_adjustment=0.75)

    state = {
        "r1": {("m", "S"): 90.0, ("m", "E"): 0.0, ("m", "A"): 5.0, ("m", "I"): 5.0},
        "r2": {("m", "S"): 80.0, ("m", "E"): 0.0, ("m", "A"): 10.0, ("m", "I"): 10.0},
    }

    weight = 100 - (50 * 0.75)

    totalIncomingInfectionsByNode = np.getIncomingInfectiousContactsByNode(graph, state, 0.5, ["I", "A"], False, None)
    assert totalIncomingInfectionsByNode == {"r1": 0.0, "r2": weight * 0.1 * 0.8}

    totalIncomingInfectionsByNode = np.getIncomingInfectiousContactsByNode(graph, state, 0.5, ["I", "A"], True,
                                                                           numpy.random.default_rng(123))
    assert isinstance(totalIncomingInfectionsByNode["r1"], int)
    assert isinstance(totalIncomingInfectionsByNode["r2"], int)
    assert totalIncomingInfectionsByNode == {"r1": 0, "r2": 2}


def test_doIncomingInfectionsByNode_weight_multiplier():
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")
    graph.add_edge("r1", "r2", weight=100, delta_adjustment=1.0)

    state = {
        "r1": {("m", "S"): 90.0, ("m", "E"): 0.0, ("m", "A"): 5.0, ("m", "I"): 5.0},
        "r2": {("m", "S"): 80.0, ("m", "E"): 0.0, ("m", "A"): 10.0, ("m", "I"): 10.0},
    }

    totalIncomingInfectionsByNode = np.getIncomingInfectiousContactsByNode(graph, state, 0.3, ["I", "A"], False, None)
    assert totalIncomingInfectionsByNode == {"r1": 0.0, "r2": 100 * 0.3 * 0.1 * 0.8}

    totalIncomingInfectionsByNode = np.getIncomingInfectiousContactsByNode(graph, state, 0.3, ["I", "A"], True,
                                                                           numpy.random.default_rng(123))
    assert isinstance(totalIncomingInfectionsByNode["r1"], int)
    assert isinstance(totalIncomingInfectionsByNode["r2"], int)
    assert totalIncomingInfectionsByNode == {"r1": 0, "r2": 0}


def test_doBetweenInfectionAgeStructured():
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")
    graph.add_edge("r1", "r2", weight=0.5, delta_adjustment=1.0)

    nodes = {
        "r1": {("m", "S"): 90.0, ("m", "E"): 0.0, ("m", "A"): 5.0, ("m", "I"): 5.0},
        "r2": {("m", "S"): 80.0, ("m", "E"): 0.0, ("m", "A"): 10.0, ("m", "I"): 10.0},
    }
    original_states = copy.deepcopy(nodes)

    num_infections = np.getExternalInfectiousContacts(graph, nodes, 1.0, ["I", "A"], False, None)
    assert num_infections == {"r1": {"m": 0.0}, "r2": {"m": 0.5 * 0.1 * 0.8}}
    assert nodes == original_states

    num_infections = np.getExternalInfectiousContacts(graph, nodes, 1.0, ["I", "A"], True, numpy.random.default_rng(12))
    assert isinstance(num_infections["r1"]["m"], numpy.int64)
    assert isinstance(num_infections["r2"]["m"], numpy.int64)
    assert num_infections == {"r1": {"m": 0}, "r2": {"m": 0}}
    assert nodes == original_states


def test_doBetweenInfectionAgeStructured_multiplier():
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")
    graph.add_edge("r1", "r2", weight=15, delta_adjustment=1.0)

    nodes = {
        "r1": {("m", "S"): 90.0, ("m", "E"): 0.0, ("m", "A"): 5.0, ("m", "I"): 5.0},
        "r2": {("m", "S"): 80.0, ("m", "E"): 0.0, ("m", "A"): 10.0, ("m", "I"): 10.0},
    }
    original_states = copy.deepcopy(nodes)

    num_infections = np.getExternalInfectiousContacts(graph, nodes, 0.3, ["I", "A"], False, None)
    assert num_infections == {"r1": {"m": 0.0}, "r2": {"m": 15 * 0.3 * 0.1 * 0.8}}
    assert nodes == original_states

    num_infections = np.getExternalInfectiousContacts(graph, nodes, 0.3, ["I", "A"], True, numpy.random.default_rng(12))
    assert isinstance(num_infections["r1"]["m"], numpy.int64)
    assert isinstance(num_infections["r2"]["m"], numpy.int64)
    assert num_infections == {"r1": {"m": 0}, "r2": {"m": 1}}
    assert nodes == original_states


def test_doBetweenInfectionAgeStructured_delta_adjustment():
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")
    graph.add_edge("r1", "r2", weight=15, delta_adjustment=0.3)

    states = {
        "r1": {("m", "S"): 90.0, ("m", "E"): 0.0, ("m", "A"): 5.0, ("m", "I"): 5.0},
        "r2": {("m", "S"): 80.0, ("m", "E"): 0.0, ("m", "A"): 10.0, ("m", "I"): 10.0},
    }
    original_states = copy.deepcopy(states)

    delta = 15 - (15 * 0.5)
    weight = 15 - (delta * 0.3)

    num_infections = np.getExternalInfectiousContacts(graph, states, 0.5, ["I", "A"], False, None)
    assert num_infections == {"r1": {"m": 0.0}, "r2": {"m": weight * 0.1 * 0.8}}
    assert states == original_states

    num_infections = np.getExternalInfectiousContacts(graph, states, 0.3, ["I", "A"], True, numpy.random.default_rng(1))
    assert isinstance(num_infections["r1"]["m"], numpy.int64)
    assert isinstance(num_infections["r2"]["m"], numpy.int64)
    assert num_infections == {"r1": {"m": 0}, "r2": {"m": 3}}
    assert states == original_states


def test_doBetweenInfectionAgeStructured_caps_number_of_infections():
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")
    graph.add_edge("r1", "r2", weight=60, delta_adjustment=1.0)

    nodes = {
        "r1": {("m", "S"): 0.0, ("m", "E"): 0.0, ("m", "A"): 100.0, ("m", "I"): 0.0},
        "r2": {("m", "S"): 30.0, ("m", "E"): 0.0, ("m", "A"): 0.0, ("m", "I"): 0.0},
    }
    original_states = copy.deepcopy(nodes)

    issues = []
    new_infections = np.getExternalInfectiousContacts(graph, nodes, 1.0, ["I", "A"], False, None, issues=issues)
    assert new_infections == {"r1": {"m": 0.0}, "r2": {"m": 30.0}}
    assert nodes == original_states
    assert issues == [
        standard_api.Issue(
            description="totalSus < incoming contacts (30.0 < 60.0) - adjusting to totalSus",
            severity=10,
        )
    ]

    issues = []
    num_infections = np.getExternalInfectiousContacts(
        graph,
        nodes,
        1.0,
        ["I", "A"],
        True,
        numpy.random.default_rng(12),
        issues=issues,
    )
    assert isinstance(num_infections["r1"]["m"], int)
    assert isinstance(num_infections["r2"]["m"], numpy.int64)
    assert num_infections == {"r1": {"m": 0}, "r2": {"m": 30}}
    assert nodes == original_states
    assert issues == [
        standard_api.Issue(
            description="totalSus < incoming contacts (30.0 < 60) - adjusting to totalSus",
            severity=10,
        )
    ]


def test_distributeInfections_cap_infections():
    state = {("m", "S"): 20.0}

    infections = np.distributeContactsOverAges(state, 100, False, None)
    assert infections == {"m": 20.0}

    infections = np.distributeContactsOverAges(state, 100, True, numpy.random.default_rng(123))
    assert isinstance(infections["m"], numpy.int64)
    assert infections == {"m": 20}


def test_distributeInfections_single_age_always_gets_full_infections():
    state = {("m", "S"): 20.0}

    infections = np.distributeContactsOverAges(state, 10, False, None)
    assert infections == {"m": 10.0}

    infections = np.distributeContactsOverAges(state, 10, True, numpy.random.default_rng(123))
    assert isinstance(infections["m"], numpy.int64)
    assert infections == {"m": 10}


def test_distributeInfections_infect_proportional_to_susceptibles_in_age_group():
    state = {("m", "S"): 20.0, ("o", "S"): 30.0, ("y", "S"): 40.0}

    infections = np.distributeContactsOverAges(state, 60, False, None)
    assert infections == {"m": (20.0 / 90.0) * 60, "o": (30.0 / 90.0) * 60, "y": (40.0 / 90.0) * 60}

    infections = np.distributeContactsOverAges(state, 60, True, numpy.random.default_rng(123))
    assert isinstance(infections["m"], numpy.int64)
    assert isinstance(infections["o"], numpy.int64)
    assert isinstance(infections["y"], numpy.int64)
    assert sum(infections.values()) == 60
    assert infections == {"m": 15, "o": 14, "y": 31}


def test_expose_infect_more_than_susceptible():
    region = {("m", "S"): 5.0, ("m", "E"): 0.0}

    with pytest.raises(AssertionError):
        np.expose("m", 10.0, region)


def test_expose():
    region = {("m", "S"): 15.0, ("m", "E"): 2.0}

    np.expose("m", 10.0, region)

    assert region == {("m", "S"): 5.0, ("m", "E"): 12.0}


def test_expose_change_only_desired_age():
    region = {("m", "S"): 15.0, ("m", "E"): 2.0, ("o", "S"): 10.0, ("o", "E"): 0.0}

    np.expose("m", 10.0, region)

    assert region == {("m", "S"): 5.0, ("m", "E"): 12.0, ("o", "S"): 10.0, ("o", "E"): 0.0}


def test_exposeRegion_distributes_multiple_ages():
    state = {"region1": {("m", "S"): 15.0, ("m", "E"): 0.0, ("o", "S"): 10.0, ("o", "E"): 0.0}}

    exposed_state = np.createExposedRegions({"region1": {"m": 5.0, "o": 5.0}}, state)

    assert exposed_state == {"region1": {("m", "S"): 10.0, ("m", "E"): 5.0, ("o", "S"): 5.0, ("o", "E"): 5.0}}


def test_exposeRegion_requires_probabilities_fails_if_age_group_does_not_exist():
    state = {"region1": {("m", "S"): 15.0, ("m", "E"): 0.0}}

    with pytest.raises(KeyError):
        np.createExposedRegions({"region1": {"m": 10.0, "o": 0.0}}, state)


def test_exposeRegion_multiple_regions():
    state = {"region1": {("m", "S"): 15.0, ("m", "E"): 0.0}, "region2": {("m", "S"): 15.0, ("m", "E"): 0.0}}

    exposed_state = np.createExposedRegions({"region1": {"m": 10.0}, "region2": {"m": 10.0}}, state)

    assert exposed_state == {
        "region1": {("m", "S"): 5.0, ("m", "E"): 10.0},
        "region2": {("m", "S"): 5.0, ("m", "E"): 10.0}
    }


def test_exposeRegion_only_desired_region():
    state = {"region1": {("m", "S"): 15.0, ("m", "E"): 0.0}, "region2": {("m", "S"): 15.0, ("m", "E"): 0.0}}

    exposed_state = np.createExposedRegions({"region1": {"m": 10.0}}, state)

    assert exposed_state == {
        "region1": {("m", "S"): 5.0, ("m", "E"): 10.0},
        "region2": {("m", "S"): 15.0, ("m", "E"): 0.0}
    }


def test_createNetworkOfPopulation(data_api):
    network, _ = np.createNetworkOfPopulation(
        data_api.read_table("human/compartment-transition", "compartment-transition"),
        data_api.read_table("human/population", "population"),
        data_api.read_table("human/commutes", "commutes"),
        data_api.read_table("human/mixing-matrix", "mixing-matrix"),
        data_api.read_table("human/infectious-compartments", "infectious-compartments"),
        data_api.read_table("human/infection-probability", "infection-probability"),
        data_api.read_table("human/initial-infections", "initial-infections"),
        data_api.read_table("human/trials", "trials"),
        data_api.read_table("human/start-end-date", "start-end-date"),
    )

    assert network.graph
    assert network.mixingMatrix
    assert network.initialState
    assert network.progression
    assert network.movementMultipliers == {}
    assert set(network.infectiousStates) == {"I", "A"}
    assert network.infectionProb == {dt.date(2020, 3, 16): 1.0}
    assert network.initialInfections == {"S08000016": {"[17,70)": 100}}
    assert network.trials == 1
    assert network.startDate == dt.date(2020, 3, 16)
    assert network.endDate == dt.date(2020, 10, 2)


def test_basicSimulationInternalAgeStructure_invalid_compartment(data_api):
    with pytest.raises(AssertionError):
        np.createNetworkOfPopulation(
            data_api.read_table("human/compartment-transition", "compartment-transition"),
            data_api.read_table("human/population", "population"),
            data_api.read_table("human/commutes", "commutes"),
            data_api.read_table("human/mixing-matrix", "mixing-matrix"),
            pd.DataFrame([{"Compartment": "INVALID"}]),
            data_api.read_table("human/infection-probability", "infection-probability"),
            data_api.read_table("human/initial-infections", "initial-infections"),
            data_api.read_table("human/trials", "trials"),
            data_api.read_table("human/start-end-date", "start-end-date"),
        )


@pytest.mark.parametrize("date,prob", [("2020-03-16", -0.5), ("2020-03-16", 10.0)])
def test_createNetworkOfPopulation_invalid_infection_probability(data_api, date, prob):
    with pytest.raises(ValueError):
        np.createNetworkOfPopulation(
            data_api.read_table("human/compartment-transition", "compartment-transition"),
            data_api.read_table("human/population", "population"),
            data_api.read_table("human/commutes", "commutes"),
            data_api.read_table("human/mixing-matrix", "mixing-matrix"),
            data_api.read_table("human/infectious-compartments", "infectious-compartments"),
            pd.DataFrame([{"Date": date, "Value": prob}]),
            data_api.read_table("human/initial-infections", "initial-infections"),
            data_api.read_table("human/trials", "trials"),
            data_api.read_table("human/start-end-date", "start-end-date"),
        )


def test_createNetworkOfPopulation_invalid_infection_probability_date(data_api, short_simulation_dates):
    with pytest.raises(ValueError):
        network, _ = np.createNetworkOfPopulation(
            data_api.read_table("human/compartment-transition", "compartment-transition"),
            data_api.read_table("human/population", "population"),
            data_api.read_table("human/commutes", "commutes"),
            data_api.read_table("human/mixing-matrix", "mixing-matrix"),
            data_api.read_table("human/infectious-compartments", "infectious-compartments"),
            pd.DataFrame([{"Date": "2020-03-17", "Value": 1.0}]),
            data_api.read_table("human/initial-infections", "initial-infections"),
            data_api.read_table("human/trials", "trials"),
            short_simulation_dates,
        )

        np.basicSimulationInternalAgeStructure(network, network.initialInfections, numpy.random.default_rng(123))

    network, _ = np.createNetworkOfPopulation(
        data_api.read_table("human/compartment-transition", "compartment-transition"),
        data_api.read_table("human/population", "population"),
        data_api.read_table("human/commutes", "commutes"),
        data_api.read_table("human/mixing-matrix", "mixing-matrix"),
        data_api.read_table("human/infectious-compartments", "infectious-compartments"),
        pd.DataFrame([{"Date": "2020-03-15", "Value": 1.0}]),
        data_api.read_table("human/initial-infections", "initial-infections"),
        data_api.read_table("human/trials", "trials"),
        short_simulation_dates,
    )

    np.basicSimulationInternalAgeStructure(network, network.initialInfections, numpy.random.default_rng(123))


def test_createNetworkOfPopulation_age_mismatch_matrix(data_api):
    progression = pd.DataFrame(
        [{"age": "70+", "src": "A", "dst": "A", "rate": 1.0}, {"age": "70+", "src": "I", "dst": "I", "rate": 1.0}]
    )
    population = pd.DataFrame([
        {"Health_Board": "S08000015", "Sex": "Female", "Age": "70+", "Total": 31950},
    ])
    commutes = pd.DataFrame([
        {"source": "S08000015", "target": "S0800001", "weight": 100777.0, "delta_adjustment": 1.0}
    ])
    mixingMatrix = pd.DataFrame([{"source": "71+", "target": "71+", "mixing": 1.0}])

    with pytest.raises(AssertionError):
        np.createNetworkOfPopulation(
            progression,
            population,
            commutes,
            mixingMatrix,
            data_api.read_table("human/infectious-compartments", "infectious-compartments"),
            data_api.read_table("human/infection-probability", "infection-probability"),
            data_api.read_table("human/initial-infections", "initial-infections"),
            data_api.read_table("human/trials", "trials"),
            data_api.read_table("human/start-end-date", "start-end-date"),
        )


def test_createNetworkOfPopulation_age_mismatch_matrix_internal(data_api):
    progression = pd.DataFrame(
        [{"age": "70+", "src": "A", "dst": "A", "rate": 1.0}, {"age": "70+", "src": "I", "dst": "I", "rate": 1.0}]
    )
    population = pd.DataFrame([
        {"Health_Board": "S08000015", "Sex": "Female", "Age": "70+", "Total": 31950},
    ])
    commutes = pd.DataFrame([
        {"source": "S08000015", "target": "S0800001", "weight": 100777.0, "delta_adjustment": 1.0}
    ])
    mixingMatrix = pd.DataFrame([{"source": "71+", "target": "70+", "mixing": 1.0}])

    with pytest.raises(AssertionError):
        np.createNetworkOfPopulation(
            progression,
            population,
            commutes,
            mixingMatrix,
            data_api.read_table("human/infectious-compartments", "infectious-compartments"),
            data_api.read_table("human/infection-probability", "infection-probability"),
            data_api.read_table("human/initial-infections", "initial-infections"),
            data_api.read_table("human/trials", "trials"),
            data_api.read_table("human/start-end-date", "start-end-date"),
        )


def test_createNetworkOfPopulation_age_mismatch_population(data_api):
    progression = pd.DataFrame(
        [{"age": "70+", "src": "A", "dst": "A", "rate": 1.0}, {"age": "70+", "src": "I", "dst": "I", "rate": 1.0}]
    )
    population = pd.DataFrame([
        {"Health_Board": "S08000015", "Sex": "Female", "Age": "71+", "Total": 31950},
    ])
    commutes = pd.DataFrame([
        {"source": "S08000015", "target": "S0800001", "weight": 100777.0, "delta_adjustment": 1.0}
    ])
    mixingMatrix = pd.DataFrame([{"source": "70+", "target": "70+", "mixing": 1.0}])

    with pytest.raises(AssertionError):
        np.createNetworkOfPopulation(
            progression,
            population,
            commutes,
            mixingMatrix,
            data_api.read_table("human/infectious-compartments", "infectious-compartments"),
            data_api.read_table("human/infection-probability", "infection-probability"),
            data_api.read_table("human/initial-infections", "initial-infections"),
            data_api.read_table("human/trials", "trials"),
            data_api.read_table("human/start-end-date", "start-end-date"),
        )


def test_createNetworkOfPopulation_age_mismatch_progression(data_api):
    progression = pd.DataFrame(
        [{"age": "71+", "src": "A", "dst": "A", "rate": 1.0}, {"age": "70+", "src": "I", "dst": "I", "rate": 1.0}]
    )
    population = pd.DataFrame([
        {"Health_Board": "S08000015", "Sex": "Female", "Age": "70+", "Total": 31950},
    ])
    commutes = pd.DataFrame([
        {"source": "S08000015", "target": "S0800001", "weight": 100777.0, "delta_adjustment": 1.0}
    ])
    mixingMatrix = pd.DataFrame([{"source": "70+", "target": "70+", "mixing": 1.0}])

    with pytest.raises(AssertionError):
        np.createNetworkOfPopulation(
            progression,
            population,
            commutes,
            mixingMatrix,
            data_api.read_table("human/infectious-compartments", "infectious-compartments"),
            data_api.read_table("human/infection-probability", "infection-probability"),
            data_api.read_table("human/initial-infections", "initial-infections"),
            data_api.read_table("human/trials", "trials"),
            data_api.read_table("human/start-end-date", "start-end-date"),
        )


def test_createNetworkOfPopulation_susceptible_in_progression(data_api):
    progression = pd.DataFrame([
        {"age": "70+", "src": "S", "dst": "E", "rate": 0.5},
        {"age": "70+", "src": "S", "dst": "S", "rate": 0.5},
        {"age": "70+", "src": "E", "dst": "E", "rate": 1.0},
    ])
    population = pd.DataFrame([
        {"Health_Board": "S08000016", "Sex": "Female", "Age": "70+", "Total": 31950},
    ])
    commutes = pd.DataFrame([
        {"source": "S08000015", "target": "S08000015", "weight": 100777.0, "delta_adjustment": 1.0}
    ])
    mixingMatrix = pd.DataFrame([{"source": "70+", "target": "70+", "mixing": 1.0}])

    with pytest.raises(AssertionError):
        np.createNetworkOfPopulation(
            progression,
            population,
            commutes,
            mixingMatrix,
            data_api.read_table("human/infectious-compartments", "infectious-compartments"),
            data_api.read_table("human/infection-probability", "infection-probability"),
            data_api.read_table("human/initial-infections", "initial-infections"),
            data_api.read_table("human/trials", "trials"),
            data_api.read_table("human/start-end-date", "start-end-date"),
        )


def test_createNetworkOfPopulation_transition_to_exposed(data_api):
    progression = pd.DataFrame([
        {"age": "70+", "src": "A", "dst": "E", "rate": 0.7},
        {"age": "70+", "src": "A", "dst": "A", "rate": 0.3},
        {"age": "70+", "src": "E", "dst": "E", "rate": 1.0},
    ])
    population = pd.DataFrame([
        {"Health_Board": "S08000016", "Sex": "Female", "Age": "70+", "Total": 31950},
    ])
    commutes = pd.DataFrame([
        {"source": "S08000015", "target": "S08000015", "weight": 100777.0, "delta_adjustment": 1.0}
    ])
    mixingMatrix = pd.DataFrame([{"source": "70+", "target": "70+", "mixing": 1.0}])

    with pytest.raises(AssertionError):
        np.createNetworkOfPopulation(
            progression,
            population,
            commutes,
            mixingMatrix,
            data_api.read_table("human/infectious-compartments", "infectious-compartments"),
            data_api.read_table("human/infection-probability", "infection-probability"),
            data_api.read_table("human/initial-infections", "initial-infections"),
            data_api.read_table("human/trials", "trials"),
            data_api.read_table("human/start-end-date", "start-end-date"),
        )


def test_getAges_multiple_ages():
    assert np.getAges({("[0,17)", "S"): 10, ("70+", "S"): 10}) == ["70+", "[0,17)"]


def test_getAges_repeated_ages():
    assert np.getAges({("[0,17)", "S"): 10, ("[0,17)", "S"): 10}) == ["[0,17)"]


def test_getAges_empty():
    assert np.getAges({}) == list()


@pytest.mark.parametrize("progression,exposed,currentState", [
    ({}, {"region1": {}}, {"region1": {}}),
    ({"region1": {}}, {}, {"region1": {}}),
    ({"region1": {}}, {"region1": {}}, {}),
])
def test_createNextStep_region_mismatch_raises_assert_error(progression, exposed, currentState):
    with pytest.raises(AssertionError):
        np.createNextStep(progression, exposed, currentState, 1.0, False, None)


def test_createNextStep_keep_susceptibles():
    currState = {"r1": {("70+", "S"): 30.0, ("70+", "E"): 20.0}}

    nextStep = np.createNextStep({"r1": {}}, {"r1": {}}, currState, 1.0, False, None)

    assert nextStep == {"r1": {("70+", "S"): 30.0, ("70+", "E"): 0.0}}


def test_createNextStep_update_infection():
    currState = {"r1": {("70+", "S"): 30.0, ("70+", "E"): 0.0}}
    progression = {"r1": {}}
    exposed = {"r1": {"70+": 20.0}}

    nextStep = np.createNextStep(progression, exposed, currState, 1.0, False, None)

    assert nextStep == {"r1": {("70+", "S"): 15.22846460770688, ("70+", "E"): 14.77153539229312}}


def test_createNextStep_use_infection_rate():
    currState = {"r1": {("70+", "S"): 30.0, ("70+", "E"): 0.0}}
    progression = {"r1": {}}
    exposed = {"r1": {"70+": 20.0}}

    nextStep = np.createNextStep(progression, exposed, currState, 0.5, False, None)

    assert nextStep == {"r1": {("70+", "S"): 22.61423230385344, ("70+", "E"): 7.38576769614656}}


def test_createNextStep_susceptible_in_progression():
    currState = {"r1": {("70+", "S"): 30.0}}
    progression = {"r1": {("70+", "S"): 7.0}}
    exposed = {"r1": {}}

    with pytest.raises(AssertionError):
        np.createNextStep(progression, exposed, currState, 1.0, False, None)


def test_createNextStep_progression_nodes():
    currState = {"r1": {("70+", "S"): 30.0, ("70+", "E"): 10.0}}
    progression = {"r1": {("70+", "E"): 7.0, ("70+", "A"): 3.0}}
    exposed = {"r1": {"70+": 10.0}}

    nextStep = np.createNextStep(progression, exposed, currState, 1.0, False, None)

    assert nextStep == {"r1": {("70+", "S"): 21.374141812742014, ("70+", "E"): 15.625858187257986, ("70+", "A"): 3.0}}


def test_createNextStep_very_small_susceptible():
    currState = {"r1": {("70+", "S"): 0.7, ("70+", "E"): 0.0}}
    progression = {"r1": {}}
    exposed = {"r1": {"70+": 0.5}}

    nextStep = np.createNextStep(progression, exposed, currState, 1.0, False, None)

    assert nextStep == {"r1": {("70+", "S"): 0.19999999999999996, ("70+", "E"): 0.5}}


def test_createNextStep_zero_susceptible():
    currState = {"r1": {("70+", "S"): 0., ("70+", "E"): 0.0}}
    progression = {"r1": {}}
    exposed = {"r1": {"70+": 0.}}

    nextStep = np.createNextStep(progression, exposed, currState, 1.0, False, None)

    assert nextStep == {"r1": {("70+", "S"): 0., ("70+", "E"): 0.}}


def test_createNextStep_susceptible_smaller_than_exposed():
    currState = {"r1": {("70+", "S"): 10., ("70+", "E"): 10.}}
    progression = {"r1": {}}
    exposed = {"r1": {"70+": 15.}}
    nextStep = np.createNextStep(progression, exposed, currState, 1.0, False, None)

    assert nextStep == {"r1": {("70+", "S"): 2.058911320946491, ("70+", "E"): 7.941088679053509}}

    currState = {"r1": {("70+", "S"): 0.5, ("70+", "E"): 0.}}
    progression = {"r1": {}}
    exposed = {"r1": {"70+": 0.75}}
    nextStep = np.createNextStep(progression, exposed, currState, 1.0, False, None)

    assert nextStep == {"r1": {("70+", "S"): 0., ("70+", "E"): 0.5}}


def test_getSusceptibles():
    states = {("70+", "S"): 10, ("70+", "E"): 20, ("[17,70)", "S"): 15}

    assert np.getSusceptibles("70+", states) == 10


def test_getSusceptibles_non_existent():
    states = {}

    with pytest.raises(KeyError):
        np.getSusceptibles("75+", states)


def test_getInfectious():
    states = {("70+", "S"): 10, ("70+", "E"): 20, ("70+", "I"): 7, ("70+", "A"): 11, ("[17,70)", "S"): 15}

    assert np.getInfectious("70+", states, ["I", "A"]) == 18


def test_getInfectious_with_a2():
    states = {("70+", "S"): 10, ("70+", "E"): 20, ("70+", "I"): 7,
              ("70+", "A"): 11, ("70+", "A2"): 5, ("[17,70)", "S"): 15}

    assert np.getInfectious("70+", states, ["I", "A", "A2"]) == 23.0


def test_getInfectious_empty():
    states = {("70+", "S"): 10, ("70+", "E"): 20, ("70+", "I"): 7, ("70+", "A"): 11, ("[17,70)", "S"): 15}

    assert np.getInfectious("70+", states, []) == 0.0


def test_getInfectious_invalid_state():
    states = {("70+", "S"): 10, ("70+", "E"): 20, ("70+", "I"): 7, ("70+", "A"): 11, ("[17,70)", "S"): 15}

    with pytest.raises(KeyError):
        np.getInfectious("70+", states, ["X"])


def test_getInfectious_non_existant():
    states = {}

    with pytest.raises(KeyError):
        np.getInfectious("70+", states, ["I", "A"])


@pytest.mark.parametrize(
    "delta_adjustment,multiplier",
    [(1.0, 1.0), (0.7, 1.0), (1.0, 0.7), (0.0, 0.8), (0.8, 0.0), (2.0, 1.0), (2.0, 2.0), (0.7, 2.0)]
)
def test_getWeight(delta_adjustment, multiplier):
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")
    graph.add_edge("r1", "r2", weight=30.0, delta_adjustment=delta_adjustment)

    assert np.getWeight(graph, "r1", "r2", multiplier) == 30.0 - delta_adjustment * (1 - multiplier) * 30.0


def test_getWeight_no_weight():
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")
    graph.add_edge("r1", "r2", delta_adjustment=0.7)

    with pytest.raises(KeyError):
        np.getWeight(graph, "r1", "r2", 1.0)


def test_getWeight_no_delta_adjustment():
    graph = nx.DiGraph()
    graph.add_node("r1")
    graph.add_node("r2")
    graph.add_edge("r1", "r2", weight=100.0)

    with pytest.raises(KeyError):
        np.getWeight(graph, "r1", "r2", 0.5)


@pytest.mark.parametrize("regions", [2, 4])
@pytest.mark.parametrize("age_groups", [['70+']])
@pytest.mark.parametrize("infected", [100, 10])
def test_randomlyInfectRegions(data_api, regions, age_groups, infected):
    network, _ = np.createNetworkOfPopulation(
        data_api.read_table("human/compartment-transition", "compartment-transition"),
        data_api.read_table("human/population", "population"),
        data_api.read_table("human/commutes", "commutes"),
        data_api.read_table("human/mixing-matrix", "mixing-matrix"),
        data_api.read_table("human/infectious-compartments", "infectious-compartments"),
        data_api.read_table("human/infection-probability", "infection-probability"),
        data_api.read_table("human/initial-infections", "initial-infections"),
        data_api.read_table("human/trials", "trials"),
        data_api.read_table("human/start-end-date", "start-end-date"),
    )

    infections = np.randomlyInfectRegions(network, regions, age_groups, infected, numpy.random.default_rng(1))

    assert len(infections) == regions
    assert list(age_groups[0] in infection for infection in infections.values())
    assert all(infection[age_groups[0]] == infected for infection in infections.values())


def test_computeInfectiousContactsStochastic_arg_mismatch():
    with pytest.raises(ValueError):
        np._computeInfectiousContactsStochastic([1.0], [1.2, 1.3], 10, 10, numpy.random.default_rng(1))
