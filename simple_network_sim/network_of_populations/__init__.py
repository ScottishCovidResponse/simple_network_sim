"""
This package implements the network of populations simulation. This models regions as nodes with intra node rules and
different inter node transmission rules. The end result of the model is a timeseries of the number of people in each
node, compartment and age.

The compartments and age groups are defined in the inputs for the model. The only hardcoded compartment are:

1. Susceptibles (S) -- people who are not immune to the disease and can catch it at any moment.
2. Exposed (E) -- people who already have the disease, whoever do not yet show symptoms and do not yet infectious.

The main type of this module is the `NetworkOfPopulation` class, which is a data object with all the data needed to run
the model. The main entrypoint function for the simulation is :meth:`basicSimulationInternalAgeStructure`. That function
will run a simulation based on the data in the `NetworkOfPopulation` instance and it will output a pandas DataFrame
with disease progression over time. Just like most public functions in this module, it does not make changes to the
objects passed as inputs.
"""
# pylint: disable=import-error
# pylint: disable=too-many-lines
import copy
import datetime as dt
import logging
from typing import Dict, Tuple, NamedTuple, List, Optional, Iterable, cast, Any, Union

from data_pipeline_api import standard_api
import networkx as nx  # type: ignore
import numpy as np  # type: ignore
import pandas as pd  # type: ignore

from simple_network_sim import loaders
from simple_network_sim.common import Lazy, IssueSeverity, log_issue

logger = logging.getLogger(__name__)

# Type aliases used to make the types for the functions below easier to read
Age = str
Compartment = str
NodeName = str

RESULT_DTYPES = {"date": str, "age": "category", "state": "category", "node": "category"}


class NetworkOfPopulation(NamedTuple):
    """
    This type has all the internal data used by this model
    """
    progression: Dict[Age, Dict[Compartment, Dict[Compartment, float]]]
    initialState: Dict[NodeName, Dict[Tuple[Age, Compartment], float]]
    graph: nx.DiGraph
    mixingMatrix: loaders.MixingMatrix
    movementMultipliers: Dict[dt.date, loaders.Multiplier]
    infectiousStates: List[Compartment]
    infectionProb: Dict[dt.date, float]
    initialInfections: Dict[NodeName, Dict[Age, float]]
    trials: int
    startDate: dt.date
    endDate: dt.date
    stochastic: bool
    falsePositiveRate: float


def dateRange(startDate: dt.date, endDate: dt.date) -> Iterable[dt.date]:
    """Generator of day and time from start date and end date

    :param startDate: Start date of the network
    :param endDate: End date of the network
    :return: Generator of days as datetime.date
    """
    if startDate > endDate:
        raise ValueError("Model start date should be <= end date")

    for days in range(int((endDate - startDate).days)):
        yield startDate + dt.timedelta(days=days + 1)


def getInitialParameter(
        startDate: dt.date,
        timeSeries: Dict[dt.date, Any],
        default: Any,
        raise_on_missing: bool = False
):
    """Queries the timeSeries at the most recent date before
    (and including) model start date. If no such date is found
    returns the default value if raise_on_missing == False,
    otherwise returns ValueError.

    :param startDate: Start date of the network
    :param timeSeries: dict of parameters indexed by dates
    :param default: default value to use if not date before or at startDate is found
    :param raise_on_missing: If not date before or at startDate is found, raise or return default
    :return: Multipliers for initial day
    """
    dates = [d for d in list(timeSeries.keys()) if d <= startDate]

    if not dates:
        if raise_on_missing:
            raise ValueError("No parameter found at or before start date")
        return default

    return timeSeries.get(max(dates))


def basicSimulationInternalAgeStructure(
        network: NetworkOfPopulation,
        initialInfections: Dict[NodeName, Dict[Age, float]],
        generator: np.random.Generator,
) -> Tuple[pd.DataFrame, List[standard_api.Issue]]:
    """Run the simulation of a disease progressing through a network of regions.

    :param network: This is a NetworkOfPopulation instance which will have the states field modified by this function.
    :param initialInfections: Initial infections of the disease
    :param generator: Seeded random number generated to use in this simulation
    :return: A time series of the size of the infectious population.
    """
    history: List[pd.DataFrame] = []
    issues: List[standard_api.Issue] = []

    defaultMultipliers = loaders.Multiplier(contact=1.0, movement=1.0)
    multipliers = getInitialParameter(network.startDate, network.movementMultipliers, defaultMultipliers)
    infectionProb = getInitialParameter(network.startDate, network.infectionProb, default=None, raise_on_missing=True)

    current = createExposedRegions(initialInfections, network.initialState)
    df = nodesToPandas(network.startDate, current)
    logger.debug("Date (%s/%s). Status: %s", network.startDate, network.endDate,
                 Lazy(lambda: df.groupby("state").total.sum().to_dict()))
    history.append(df)

    for date in dateRange(network.startDate, network.endDate):
        
        multipliers = network.movementMultipliers.get(date, multipliers)
        infectionProb = network.infectionProb.get(date, infectionProb)

        progression = getInternalProgressionAllNodes(
            current,
            network.progression,
            network.stochastic,
            generator,
        )
        
        
        internalContacts = getInternalInfectiousContacts(
            current,
            network.mixingMatrix,
            multipliers.contact,
            network.infectiousStates,
            network.stochastic,
            generator,
        )
        
        
        externalContacts = getExternalInfectiousContacts(
            network.graph,
            current,
            multipliers.movement,
            network.infectiousStates,
            network.stochastic,
            generator,
            issues=issues,
        )
        contacts = mergeContacts(internalContacts, externalContacts)

        
        current = createNextStep(
            progression,
            contacts,
            current,
            infectionProb,
            network.stochastic,
            generator,
            network.falsePositiveRate
        )

        
        df = nodesToPandas(date, current)
        logger.debug(
            "Date (%s/%s). Status: %s",
            date,
            network.endDate,
            Lazy(lambda: df.groupby("state").total.sum().to_dict())
        )
        history.append(df)
        # print(df)

    return (pd.concat(history, copy=False, ignore_index=True), issues)


def nodesToPandas(date: dt.date, nodes: Dict[NodeName, Dict[Tuple[Age, Compartment], float]]) -> pd.DataFrame:
    """
    Converts a dict of nodes into a pandas DataFrame

    >>> nodesToPandas(dt.date(2020, 1, 1), {"nodea": {("70+", "S"): 10.0, ("70+", "E"): 15.0}, "nodeb": {("[17,70", "S"): 15.0}})  # doctest: +NORMALIZE_WHITESPACE
        date         node     age  state  total
    0   2020-01-01  nodea     70+     S   10.0
    1   2020-01-01  nodea     70+     E   15.0
    2   2020-01-01  nodeb  [17,70     S   15.0
    >>> nodesToPandas(dt.date(2020, 1, 1), {})  # doctest: +NORMALIZE_WHITESPACE
    Empty DataFrame
    Columns: [date, node, age, state, total]
    Index: []

    :param date: date that will be inserted into every row
    :param nodes: a dict of nodes
    :return: a pandas dataframe representation of the nodes
    """
    rows = []
    for name, node in nodes.items():
        for (age, state), value in node.items():
            rows.append([date, name, age, state, value])
    return pd.DataFrame(rows, columns=["date", "node", "age", "state", "total"]).astype(RESULT_DTYPES, copy=True)


def totalIndividuals(nodeState: Dict[Tuple[Age, Compartment], float]) -> float:
    """This function takes a node (region) and counts individuals from every age and state.

    :param nodeState: The disease status of a node (or region) stratified by age.
    :return: The total number of individuals.
    """
    return sum(nodeState.values())


def getAges(node: Dict[Tuple[Age, Compartment], float]) -> List[Age]:
    """Get the set of ages from the node.

    :param node: The disease states of the population stratified by age.
    :return: The unique collection of ages.
    """
    ages = set()
    for (age, _) in node:
        ages.add(age)
    return sorted(list(ages))


def getTotalInAge(nodeState: Dict[Tuple[Age, Compartment], float], ageTest: Age) -> float:
    """Get the size of the population within an age group.

    :param nodeState: The disease states of the population stratified by age.
    :param ageTest: The age range of the population.
    :return: The population size within the age range.
    """
    total = 0.0
    for (age, _), value in nodeState.items():
        if age == ageTest:
            total += value
    return total


def getTotalInfectious(node: Dict[Tuple[Age, Compartment], float], infectiousStates: List[Compartment]) -> float:
    """
    Get the total number of infectious individuals regardless of age in the node.

    :param node: The disease status of the population stratified by age.
    :param infectiousStates: States that are considered infectious
    :return: The total number of infectious individuals.
    """
    total = 0.0
    for (_, compartment), value in node.items():
        if compartment in infectiousStates:
            total += value
    return total


def getTotalSuscept(nodeState: Dict[Tuple[Age, Compartment], float]) -> float:
    """Get the total number of susceptible individuals regardless of age in the node

    :param nodeState: The disease status of the population stratified by age.
    :return: The total number of susceptible individuals.
    """
    totalSusHere = 0.0
    for age in getAges(nodeState):
        totalSusHere += getSusceptibles(age, nodeState)
    return totalSusHere


def distributeContactsOverAges(
        nodeState: Dict[Tuple[Age, Compartment], float],
        newContacts: float,
        stochastic: bool,
        random_state: Optional[np.random.Generator],
        issues: Optional[List[standard_api.Issue]] = None,
) -> Dict[Age, float]:
    r"""
    Distribute the number of new contacts across a region. There are two possible implementations:

    1. Deterministic (``stochastic=False``) -- We simply allocate newContacts by proportion of people in each age groups
    2. Stochastic (``stochastic=True``) -- newContacts are sampled randomly from the population from a Multinomial
       distribution, with: :math:`k=\text{new contacts}`, :math:`p=\text{proportion of people in age groups}`

    Note: fractional people will come out of this.

    :param nodeState: The disease status of the population stratified by age.
    :param newContacts: The number of new contacts to be distributed across age ranges.
    :param stochastic: Whether to run the model in a stochastic or deterministic mode
    :param random_state: Random number generator used for the model
    :param issues: if any issues are found and a list is passed as this parameter, append the issues to it. Logging will
                   happen regardless.
    :return: The number of new infections in each age group.
    """
    ageToSus = {}
    totalSus = 0.0
    for age in getAges(nodeState):
        sus = getSusceptibles(age, nodeState)
        ageToSus[age] = sus
        totalSus += sus

    if totalSus < newContacts:
        log_issue(
            logger,
            f"totalSus < incoming contacts ({totalSus} < {newContacts}) - adjusting to totalSus",
            IssueSeverity.HIGH,
            issues if issues is not None else [],
        )
        newContacts = totalSus

    if totalSus > 0:
        if stochastic:
            newInfectionsByAge = _distributeContactsOverAgesStochastic(ageToSus, totalSus, newContacts, random_state)
        else:
            newInfectionsByAge = _distributeContactsOverAgesDeterministic(ageToSus, totalSus, newContacts)
    else:
        newInfectionsByAge = {age: 0 for age in ageToSus}

    return newInfectionsByAge


def _distributeContactsOverAgesStochastic(
        ageToSusceptibles: Dict[Age, float],
        totalSusceptibles: float,
        newContacts: float,
        random_state: np.random.Generator
) -> Dict[Age, float]:
    """
    Distribute the number of new contacts across a region using the stochastic algorithm.

    :param ageToSusceptibles: The number of susceptibles in each age group
    :param totalSusceptibles: Total number of susceptible people in all age groups
    :param newContacts: The number of new contacts to be distributed across age ranges.
    :param random_state: Random number generator used for the model
    :return: The number of new infections in each age group.
    """
    assert isinstance(newContacts, int) or newContacts.is_integer()

    ageProbabilities = np.array(list(ageToSusceptibles.values())) / totalSusceptibles
    allocationsByAge = random_state.multinomial(newContacts, ageProbabilities)

    return dict(zip(ageToSusceptibles.keys(), allocationsByAge))


def _distributeContactsOverAgesDeterministic(
        ageToSusceptibles: Dict[Age, float],
        totalSusceptibles: float,
        newContacts: float,
) -> Dict[Age, float]:
    """
    Distribute the number of new contacts across a region deterministically.

    :param ageToSusceptibles: The number of susceptibles in each age group
    :param totalSusceptibles: Total number of susceptible people in all age groups
    :param newContacts: The number of new contacts to be distributed across age ranges.
    :return: The number of new infections in each age group.
    """
    return {age: (sus / totalSusceptibles) * newContacts for age, sus in ageToSusceptibles.items()}


# pylint: disable=too-many-arguments
def getIncomingInfectiousContactsByNode(
        graph: nx.DiGraph,
        currentState: Dict[NodeName, Dict[Tuple[Age, Compartment], float]],
        movementMultiplier: float,
        infectiousStates: List[Compartment],
        stochastic: bool,
        random_state: Optional[np.random.Generator],
) -> Dict[NodeName, float]:
    r"""
    Determine the number of new infections at each node of a graph based on incoming people from neighbouring nodes.
    The `stochastic` parameter can be used to select between the two modes of operation:

    1. Deterministic (``stochastic=False``) -- We multiply the commute by the proportion of infectious people in giving
       node, and by the proportion of susceptible people in receiving age group.
    2. Stochastic (``stochastic=True``) -- We assume commutes are randomly distributed across people. We sample
       the weight (movements between nodes) from a binomial distribution with
       :math:`p = \frac{\text{totalSusceptibleInNode}}{\text{totalPeopleInNode}}`. This gives the number of commutes
       that target susceptible people. Then we sample the result into another binomial distribution with
       :math:`p = \frac{\text{totalInfectiousInNeighbor}}{\text{totalPeopleInNeighbor}}`. This gives the number of
       commutes that target susceptible people, and originate from infectious people. That calculation is done for each
       pair of connected nodes

    :param graph: A graph with each region as a node and the weights corresponding to the movements
                  between regions. Edges must contain weight and delta_adjustment attributes (assumed 1.0)
    :param currentState: The current state for every region.
    :param movementMultiplier: a multiplier applied to each edge (movement) in the network.
    :param infectiousStates: States that are considered infectious
    :param stochastic: Whether to run the model in a stochastic or deterministic mode
    :param random_state: Random number generator used for the model
    :return: the number of new infections in each region.
    """
    infectiousByNode: Dict[NodeName, float] = {}
    totalByNode: Dict[NodeName, float] = {}
    # Precompute this so that we avoid expensive calls inside the O(n^2) part of the algorithm as most as we can
    for name, node in currentState.items():
        infectiousByNode[name] = getTotalInfectious(node, infectiousStates)
        totalByNode[name] = totalIndividuals(node)
    contactsByNode: Dict[NodeName, float] = {}

    # Surprisingly, iterating over graph.edges is actually slower than going through the dicts and calling
    # graph.predecessor when needed
    for receivingVertex in currentState:
        totalSusceptHere = getTotalSuscept(currentState[receivingVertex])
        contactsByNode[receivingVertex] = 0

        if totalSusceptHere > 0:
            for givingVertex in graph.predecessors(receivingVertex):
                if givingVertex == receivingVertex:
                    continue
                totalInfectedGiving = infectiousByNode[givingVertex]
                if totalInfectedGiving > 0:
                    weight = getWeight(graph, givingVertex, receivingVertex, movementMultiplier)
                    fractionGivingInfected = totalInfectedGiving / totalByNode[givingVertex]
                    fractionReceivingSus = totalSusceptHere / totalByNode[receivingVertex]

                    if stochastic:
                        contactsByNode[receivingVertex] += _computeInfectiousCommutesStochastic(
                            weight,
                            fractionGivingInfected,
                            fractionReceivingSus,
                            random_state,
                        )
                    else:
                        contactsByNode[receivingVertex] += weight * fractionGivingInfected * fractionReceivingSus
    return contactsByNode


def _computeInfectiousCommutesStochastic(
        weight: float,
        fractionGivingInfected: float,
        fractionReceivingSus: float,
        random_state: np.random.Generator
) -> float:
    """
    Stochastic implementation of movement based transmission

    :param weight: Raw number of commutes
    :param fractionGivingInfected: Fraction of infectious people in source node of commute
    :param fractionReceivingSus: Fraction of susceptible people in destination node of commute
    :param random_state: Random number generator used for the model
    :return: the number of new infections in each region.
    """
    # weight can be fractional because of the movement multiplier, round it
    contacts = random_state.binomial(int(round(weight)), fractionReceivingSus)
    return random_state.binomial(contacts, fractionGivingInfected)


def getWeight(graph: nx.DiGraph, orig: str, dest: str, multiplier: float) -> float:
    """Get the weight of the edge from orig to dest in the graph. This weight is expected to be
    proportional to the movement between nodes. If the edge doesn't have a weight, 1.0 is assumed
    and the returned weight is adjusted by the multiplier and any delta_adjustment on the edge.

    :param graph: A graph with each region as a node and the weights corresponding to the commutes
                  between regions. Edges must contain weight and delta_adjustment attributes (assumed 1.0)
    :param orig: The vertex people are coming from.
    :param dest: The vertex people are going to.
    :param multiplier: Value that will dampen or heighten movements between nodes.
    :return: The final weight value
    """
    edge = graph.get_edge_data(orig, dest)

    # The data loaders force weight and delta_adjustment to always be present
    weight = edge["weight"]
    delta_adjustment = edge["delta_adjustment"]

    delta = weight - (weight * multiplier)
    # The delta_adjustment is applied on the delta. It can either completely cancel any changes (factor = 0.0) or
    # enable it fully (factor = 1.0). If the movement multiplier doesn't make any changes to the node's movements (ie.
    # multiplier = 1.0), then the delta_adjustment will have no effect.
    return weight - (delta * delta_adjustment)


# pylint: disable=too-many-arguments
def getExternalInfectiousContacts(
        graph: nx.DiGraph,
        nodes: Dict[NodeName, Dict[Tuple[Age, Compartment], float]],
        movementMultiplier: float,
        infectiousStates: List[Compartment],
        stochastic: bool,
        random_state: Optional[np.random.Generator],
        issues: Optional[List[standard_api.Issue]] = None,
) -> Dict[NodeName, Dict[Age, float]]:
    """Calculate the number of new infections in each region. The infections are distributed
    proportionally to the number of susceptibles in the destination node and infected in the origin
    node. The infections are distributed to each age group according to the number of susceptible
    people in them.

    :param graph: A graph with each region as a node and the weights corresponding to the movements
                  between regions. Edges must contain weight and delta_adjustment attributes (assumed 1.0)
    :param nodes: The disease status in each region stratified by age.
    :param movementMultiplier: A multiplier applied to each edge (movement between nodes) in the
                               network.
    :param infectiousStates: States that are considered infectious
    :param stochastic: Whether to run the model in a stochastic or deterministic mode
    :param random_state: Random number generator used for the model
    :param issues: if any issues are found and a list is passed as this parameter, append the issues to it.
    :return: The number of new infections in each region stratified by age.
    """
    infectionsByNode = {}

    incomingContacts = getIncomingInfectiousContactsByNode(
        graph,
        nodes,
        movementMultiplier,
        infectiousStates,
        stochastic,
        random_state
    )

    for name, vertex in incomingContacts.items():
        infectionsByNode[name] = distributeContactsOverAges(nodes[name], vertex, stochastic, random_state, issues=issues)

    return infectionsByNode


# pylint: disable=too-many-arguments
def getInternalInfectiousContactsInNode(
        currentInternalStateDict: Dict[Tuple[Age, Compartment], float],
        mixingMatrix: loaders.MixingMatrix,
        contactsMultiplier: float,
        infectiousStates: List[Compartment],
        stochastic: bool,
        random_state: Optional[np.random.Generator],
) -> Dict[Age, float]:
    """
    Calculate the new infections due to mixing within the region and stratify them by age. The `stochastic` parameter
    can be used to select between two modes:

    1. Deterministic (``stochastic=False``) -- We simply multiply the contacts by number of infectious, and by
       proportion of susceptibles
    2. Stochastic (``stochastic=True``) -- For each infectious individual we sample from a Poisson distribution with
       mean the number of contacts. Then the output k (number of contacts for one particular person), is inputted
       in a Hypergeometric distribution, where we sample k individuals with replacement in the population of
       susceptibles. This provides potentially infectious contacts, which are summed.

    :param currentInternalStateDict: The disease status of the population stratified by age.
    :param mixingMatrix: Stores expected numbers of interactions between people of
                         different ages.
    :param contactsMultiplier: Multiplier applied to the number of infectious contacts.
    :param infectiousStates: States that are considered infectious
    :param stochastic: Whether to run the model in a stochastic or deterministic mode
    :param random_state: Random number generator used for the model
    :return: The number of new infections stratified by age.
    """
    infectiousContacts: Dict[Age, float] = {}
    for ageTo in mixingMatrix:
        infectiousContacts[ageTo] = 0

        susceptibles = getSusceptibles(ageTo, currentInternalStateDict)
        totalInAge = getTotalInAge(currentInternalStateDict, ageTo)

        contacts_series: List[float] = []
        infectious_series: List[float] = []

        acc = 0.0

        if susceptibles > 0 and totalInAge > 0.0:
            for ageFrom in mixingMatrix[ageTo]:
                contacts_series.append(mixingMatrix[ageTo][ageFrom] * contactsMultiplier)
                infectious_series.append(getInfectious(ageFrom, currentInternalStateDict, infectiousStates))
                acc += contacts_series[-1] * infectious_series[-1] * (susceptibles / totalInAge)

            if stochastic:
                infectiousContacts[ageTo] = _computeInfectiousContactsStochastic(
                    contacts_series,
                    infectious_series,
                    susceptibles,
                    totalInAge,
                    random_state,
                )
            else:
                infectiousContacts[ageTo] = acc

    return infectiousContacts


def _computeInfectiousContactsStochastic(
        contacts: List[float],
        infectious: List[float],
        susceptibles: Union[int, float],
        totalInAge: Union[int, float],
        random_state: np.random.Generator
) -> float:
    """
    Takes a list of contacts (usually coming from other age groups) which should be paired with a list of infectious
    people from the same group. This function will then estimate the number of infectious contacts those people will
    produce.

    :param contacts: A list with the number of contacts per incoming group
    :param infectious: The number of incoming infectious people, paired with the the list of contacts
    :param susceptibles: The number of susceptible people to which the contacts can target
    :param totalInAge: Total number of people in target population
    :param random_state: Random number generator used for the model
    :return: The number of potentially infectious contacts
    """
    if len(contacts) != len(infectious):
        raise ValueError("contacts and infectious must have the same length")
    assert isinstance(totalInAge, int) or totalInAge.is_integer()
    assert isinstance(susceptibles, int) or susceptibles.is_integer()

    inf_max = int(round(max(infectious)))
    # each np.array represent one original (contact, infectious) pair
    numbersOfContacts: np.array = np.zeros((len(contacts), inf_max), dtype=int)
    for n, (contact, infected) in enumerate(zip(contacts, infectious)):
        x = random_state.poisson(contact, int(round(infected)))
        numbersOfContacts[n, :len(x)] = x
    # Number of contacts cannot be higher than the number of people in the node
    numbersOfContacts = np.minimum(np.array(numbersOfContacts).T, int(totalInAge))
    result = random_state.hypergeometric(
        np.full(len(contacts), int(susceptibles)),
        np.full(len(contacts), int(totalInAge - susceptibles)),
        numbersOfContacts,
    ).T
    return cast(float, np.sum(result))


# pylint: disable=too-many-arguments
def getInternalInfectiousContacts(
        nodes: Dict[NodeName, Dict[Tuple[Age, Compartment], float]],
        mixingMatrix: loaders.MixingMatrix,
        contactsMultiplier: float,
        infectiousStates,
        stochastic: bool,
        random_state: Optional[np.random.Generator],
) -> Dict[NodeName, Dict[Age, float]]:
    """Calculate the new infections and stratify them by region and age.

    :param nodes: The disease status in each region stratified by age.
    :param mixingMatrix: Stores expected numbers of interactions between people of different ages.
    :param contactsMultiplier: Multiplier applied to the number of infectious contacts.
    :param infectiousStates: States that are considered infectious
    :param stochastic: Whether to run the model in a stochastic or deterministic mode
    :param random_state: Random number generator used for the model
    :return: The number of exposed in each region stratified by age.
    """
    contacts: Dict[NodeName, Dict[Age, float]] = {}

    for name, node in nodes.items():
        contacts[name] = getInternalInfectiousContactsInNode(
            node,
            mixingMatrix,
            contactsMultiplier,
            infectiousStates,
            stochastic,
            random_state
        )

    return contacts


def internalStateDiseaseUpdate(
        currentInternalStateDict: Dict[Tuple[Age, Compartment], float],
        diseaseProgressionProbs: Dict[Age, Dict[Compartment, Dict[Compartment, float]]],
        stochastic: bool,
        random_state: Optional[np.random.Generator],
) -> Dict[Tuple[Age, Compartment], float]:
    r"""
    Returns the status of exposed individuals, moving them into the next disease state with a probability defined in the
    given progression matrix. The `stochastic` parameters selects between two modes:

    1. Deterministic (``stochastic=False``) -- The people in the given state are transferred into the next available
       states by multiplying by the probability of going to each state.
    2. Stochastic (``stochastic=True``) -- We sample from a multinomial distribution with parameters:
       :math:`k=\text{people in state}`, :math:`p=\text{state transition probability}`.

    :param currentInternalStateDict: The disease status of the population stratified by age.
    :param diseaseProgressionProbs: A matrix with the probabilities if progressing from one state
                                    to the next.
    :param stochastic: Whether to run the model in a stochastic or deterministic mode
    :param random_state: Random number generator used for the model
    :return: the numbers in each exposed state stratified by age
    """
    newStates: Dict[Tuple[Age, Compartment], float] = {}

    for (age, state), people in currentInternalStateDict.items():
        outTransitions = diseaseProgressionProbs[age].get(state, {})
        _internalStateDiseaseUpdate(age, state, people, outTransitions, newStates, stochastic, random_state)

    return newStates


# pylint: disable=too-many-arguments
def _internalStateDiseaseUpdate(
        age: Age,
        state: Compartment,
        people: float,
        outTransitions: Dict[Compartment, float],
        newStates: Dict[Tuple[Age, Compartment], float],
        stochastic: bool,
        random_state: np.random.Generator
):
    """
    Returns the status of exposed individuals, moving them into the next disease state with a
    probability defined in the given progression matrix.

    :param age: Current age
    :param age: Current state
    :param people: Number of people in current age, state
    :param outTransitions: Transition probabilities out of the current age, state,
                           to next potential ones
    :param newStates: Distribution of people in next states
    :param stochastic: Use the model in stochastic mode?
    :param random_state: Random number generator used for the model
    :return: the numbers in each exposed state stratified by age
    """
    if stochastic:
        if state == SUSCEPTIBLE_STATE:
            return

        assert isinstance(people, int) or people.is_integer()

        outRepartitions = random_state.multinomial(people, list(outTransitions.values()))
        outRepartitions = dict(zip(outTransitions.keys(), outRepartitions))

        for nextState, nextStateCases in outRepartitions.items():
            newStates.setdefault((age, nextState), 0.0)
            newStates[(age, nextState)] += nextStateCases
    else:
        for nextState, transition in outTransitions.items():
            newStates.setdefault((age, nextState), 0.0)
            newStates[(age, nextState)] += transition * people


def getInternalProgressionAllNodes(
        currStates: Dict[NodeName, Dict[Tuple[Age, Compartment], float]],
        diseaseProgressionProbs: Dict[Age, Dict[Compartment, Dict[Compartment, float]]],
        stochastic: bool,
        random_state: Optional[np.random.Generator],
) -> Dict[NodeName, Dict[Tuple[Age, Compartment], float]]:
    """
    Given the size of the population in each exposed state, calculate the numbers that progress
    the next disease state based on the progression matrix.

    :param currStates: The current state for every region is not modified.
    :param diseaseProgressionProbs: A matrix with the probabilities if progressing from one state
                                    to the next.
    :param stochastic: Whether to run the model in a stochastic or deterministic mode
    :param random_state: Random number generator used for the model
    :return: The number of individuals that have progressed into each exposed stage, stratified by
             region and age.
    """
    progression = {}
    for regionID, currRegion in currStates.items():
        progression[regionID] = internalStateDiseaseUpdate(
            currRegion,
            diseaseProgressionProbs,
            stochastic,
            random_state
        )
    
    return progression


def mergeContacts(*args) -> Dict[NodeName, Dict[Age, float]]:
    """From a list of exposed cases stratified by age and region, merge them into a single
    collection

    :param args: A variable list of regional exposure numbers by age.
    :type args: A variable list of dictionaries that have a region as a key and the value is a
                dictionary of {age:number of exposed}.
    :return: A dictionary containing the merged number of exposed.
    """
    exposedTotal: Dict[NodeName, Dict[Age, float]] = {}
    for infectionsDict in args:
        for regionID, region in infectionsDict.items():
            exposedRegionTotal = exposedTotal.setdefault(regionID, {})
            for age, exposed in region.items():
                exposedRegionTotal[age] = exposedRegionTotal.setdefault(age, 0.0) + exposed
    return exposedTotal


def createExposedRegions(
        infections: Dict[NodeName, Dict[Age, float]],
        states: Dict[NodeName, Dict[Tuple[Age, Compartment], float]],
) -> Dict[NodeName, Dict[Tuple[Age, Compartment], float]]:
    """Creates a new the state of a region, adding the new infections.

    :param infections: The number of infections per region per age
    :param states: The current state for every region is not modified
    :return: A dictionary containing the merged number of exposed
    """
    exposedStates = copy.deepcopy(states)
    for nodeName, node in infections.items():
        for age, value in node.items():
            expose(age, value, exposedStates[nodeName])

    return exposedStates


def getInfectious(
        age: Age,
        currentInternalStateDict: Dict[Tuple[Age, Compartment], float],
        infectiousStates: List[Compartment],
) -> float:
    """Calculate the total number of individuals in infectious states in an age range.

    :param age: The age (range)
    :param currentInternalStateDict: The disease status of the population stratified by age.
    :param infectiousStates: States that are considered infectious
    :return: The number of individuals in an infectious state and age range.
    """
    total = 0.0
    for state in infectiousStates:
        total += currentInternalStateDict[(age, state)]
    return total


# The functions below are the only operations that need to know about the actual state values.
SUSCEPTIBLE_STATE = "S"
EXPOSED_STATE = "E"
FALSE_POS_STATE = "P_F"


# pylint: disable=too-many-arguments
def createNetworkOfPopulation(
        compartment_transition_table: pd.DataFrame,
        population_table: pd.DataFrame,
        commutes_table: pd.DataFrame,
        mixing_matrix_table: pd.DataFrame,
        infectious_states: pd.DataFrame,
        infection_prob: pd.DataFrame,
        initial_infections: pd.DataFrame,
        trials: pd.DataFrame,
        start_end_date: pd.DataFrame,
        movement_multipliers_table: pd.DataFrame = None,
        stochastic_mode: pd.DataFrame = None,
        false_positive_rate: float = 0.0
) -> Tuple[NetworkOfPopulation, List[standard_api.Issue]]:
    """Create the network of the population, loading data from files.

    :param compartment_transition_table: pd.Dataframe specifying the transition rates between infected compartments.
    :param population_table: pd.Dataframe with the population size in each region by gender and age.
    :param commutes_table: pd.Dataframe with the movements between regions.
    :param mixing_matrix_table: pd.Dataframe with the age infection matrix.
    :param infectious_states: States that are considered infectious
    :param infection_prob: Probability that a given contact will result in an infection
    :param initial_infections: Initial infections of the population at time 0
    :param trials: Number of trials for the model
    :param start_end_date: Starting and ending dates of the model
    :param movement_multipliers_table: pd.Dataframe with the movement multipliers. This may be None, in
                                       which case no multipliers are applied to the movements.
    :param stochastic_mode: Use stochastic mode for the model
    :return: A tuple with the constructed network and a list of any issues found. Although it may look convenient,
             storing this list inside of NetworkOfPopulation is not a good idea, as that may give the functions that
             receive it the false impression they can just append new issues there
    """
    issues: List[standard_api.Issue] = []
    infection_prob = loaders.readInfectionProbability(infection_prob)

    infectious_states = loaders.readInfectiousStates(infectious_states)
    initial_infections = loaders.readInitialInfections(initial_infections)
    trials = loaders.readTrials(trials)
    start_date, end_date = loaders.readStartEndDate(start_end_date)
    stochastic_mode = loaders.readStochasticMode(stochastic_mode)

    # diseases progression matrix
    progression = loaders.readCompartmentRatesByAge(compartment_transition_table)

    # population census data
    population = loaders.readPopulationAgeStructured(population_table)

    # Check some requirements for this particular model to work with the progression matrix
    all_states = set()
    for states in progression.values():
        # assert SUSCEPTIBLE_STATE not in states, "progression from susceptible state is not allowed"
        for state, nextStates in states.items():
            for nextState in nextStates:
                all_states.add(state)
                all_states.add(nextState)
                assert state == nextState or nextState != EXPOSED_STATE, \
                    "progression into exposed state is not allowed other than in self reference"
    assert (set(infectious_states) - all_states) == set(), \
        f"mismatched infectious states and states {infectious_states} {all_states}"

    # people movement's graph
    graph = loaders.genGraphFromContactFile(commutes_table)

    # movement multipliers (dampening or heightening)
    if movement_multipliers_table is not None:
        movementMultipliers = loaders.readMovementMultipliers(movement_multipliers_table)
    else:
        movementMultipliers = {}

    # age-based infection matrix
    mixingMatrix = loaders.MixingMatrix(mixing_matrix_table)

    agesInInfectionMatrix = set(mixingMatrix)
    for age in mixingMatrix:
        assert agesInInfectionMatrix == set(mixingMatrix[age]), "infection matrix columns/rows mismatch"

    # Checks across datasets
    assert agesInInfectionMatrix == set(progression.keys()), "infection matrix and progression ages mismatch"
    assert agesInInfectionMatrix == {age for region in population.values() for age in region}, \
        "infection matrix and population ages mismatch"
    disconnected_nodes = set(population.keys()) - set(graph.nodes())
    if disconnected_nodes:
        log_issue(
            logger,
            f"These nodes have no contacts in the current network: {','.join(disconnected_nodes)}",
            IssueSeverity.MEDIUM,
            issues,
        )

    state0: Dict[str, Dict[Tuple[str, str], float]] = {}
    for node in list(graph.nodes()):
        region = state0.setdefault(node, {})
        for age, compartments in progression.items():
            if node not in population:
                log_issue(
                    logger,
                    f"Node {node} is not in the population table, assuming population of 0 for all ages",
                    IssueSeverity.MEDIUM,
                    issues,
                )
                pop = 0.0
            else:
                pop = population[node][age]
            region[(age, SUSCEPTIBLE_STATE)] = pop
            for compartment in compartments:
                region[(age, compartment)] = 0

    logger.info("Nodes: %s, Ages: %s, States: %s", len(state0), agesInInfectionMatrix, all_states)
    nop = NetworkOfPopulation(
        progression=progression,
        graph=graph,
        initialState=state0,
        mixingMatrix=mixingMatrix,
        movementMultipliers=movementMultipliers,
        infectiousStates=infectious_states,
        infectionProb=infection_prob,
        initialInfections=initial_infections,
        trials=trials,
        startDate=start_date,
        endDate=end_date,
        stochastic=stochastic_mode,
        falsePositiveRate=false_positive_rate
    )
    return (nop, issues)


# pylint: disable=too-many-arguments
# pylint: disable=too-many-locals
def createNextStep(
        progression: Dict[NodeName, Dict[Tuple[Age, Compartment], float]],
        infectiousContacts: Dict[NodeName, Dict[Age, float]],
        currState: Dict[NodeName, Dict[Tuple[Age, Compartment], float]],
        infectionProb: float,
        stochastic: bool,
        random_state: Optional[np.random.Generator],
        false_positive_rate: float
) -> Dict[NodeName, Dict[Tuple[Age, Compartment], float]]:
    """
    Update the current state of each regions population by allowing infected individuals
    to progress to the next infection stage and infecting susceptible individuals. The state is not
    modified in this function, rather the updated details are returned.

    See the documentation for :meth:`calculateExposed` for an explanation of how new people are exposed from one step
    into the next.

    :param progression: The number of individuals that have progressed into each exposed stage, stratified by
                        region and age.
    :param infectiousContacts: The number of contacts per region per age.
    :param currState: The current state for every region.
    :param infectionProb: the expected rate at which contacts will transmit the diseases
    :param stochastic: Whether to run the model in a stochastic or deterministic mode
    :param random_state: Random number generator used for the model
    :return: The new state of the regions.
    """

    assert progression.keys() == infectiousContacts.keys() == currState.keys(), "missing regions"

    nextStep: Dict[NodeName, Dict[Tuple[Age, Compartment], float]] = {}
    for name, node in currState.items():
        new_node = nextStep.setdefault(name, {})
        for key, value in node.items():
            # We need to keep the susceptibles in order to infect them
            if key[1] == SUSCEPTIBLE_STATE:
                new_node[key] = value
            else:
                new_node[key] = 0.0

    for name, node in progression.items():
        for key, value in node.items():
            # Note that the progression is responsible for populating every other state
            # assert key[1] != SUSCEPTIBLE_STATE, "Susceptibles can't be part of progression states"
            if key[1] != SUSCEPTIBLE_STATE:
               nextStep[name][key] = value
            else: 
               nextStep[name][key] = nextStep[name][key] + value
               
    for name, nodeByAge in infectiousContacts.items():
        for age, contacts in nodeByAge.items():
            exposed = calculateExposed(
                nextStep[name][(age, SUSCEPTIBLE_STATE)],
                contacts,
                infectionProb,
                stochastic,
                random_state,
            )
            expose(age, exposed, nextStep[name])
    
    for name, node in nextStep.items():
        _doTesting(false_positive_rate, node)
        
    return nextStep


def calculateExposed(
        susceptible: float,
        contacts: float,
        infectionProb: float,
        stochastic: bool,
        random_state: Optional[np.random.Generator],
):
    r"""
    From the number of contacts (between infectious and susceptible) people, compute the number of actual infectious
    contacts. Two modes:

    1. Deterministic (``stochastic=False``) -- Adjusts the contacts (see explanation below), then multiply by infection
       probability
    2. Stochastic (``stochastic=True``) -- Adjusts the contacts (see explanation below), then sample from a binomial
       distribution with :math:`n=\text{adjusted contacts}`, :math:`p=\text{infection probability}`.

    When using :math:`k` contacts from a susceptible population of size :math:`n`, we sample
    these :math:`k` people **with** replacement, as in several infections can target the same person.
    This will decrease the exposed number for small values of :math:`k`, :math:`n`. This is not sampled
    stochastically as it seems no such distribution exists.

    :math:`N` = Number of different people chosen when picking k in a population of size n, with replacement

    .. math::

        E[N] &= \sum_{i=1,...,n} P(\text{person i is chosen at least once}) \\
        &= \sum_{i=1,...,n} (1 - P(\text{person i is never chosen in k samples})) \\
        &= \sum_{i=1,...,n} (1 - P(\text{person i is not chosen once})^k) \\
        &= \sum_{i=1,...,n} (1 - (1 - P(\text{person i is chosen once}))^k) \\
        &= \sum_{i=1,...,n} (1 - (1 - P(\text{person i is chosen once}))^k) \\
        &= n * (1 - (1 - 1 / n)^k)

    :param susceptible: number (float) of susceptible individuals
    :param contacts: number (float) of exposed individuals
    :param infectionProb: probability (float) that a given contact will result in infection
    :param stochastic: Whether to run the model in a stochastic or deterministic mode
    :param random_state: Random number generator used for the model
    """
    if susceptible > 1.:
        probaNeverChosen = (1 - (1 / susceptible)) ** contacts
        adjustedContacts = susceptible * (1 - probaNeverChosen)
    else:
        # For susceptible < 1., the formula (which theoretically works
        # only for integers) breaks down and returns nan. In that case
        # several choices are acceptable, we assume the fractional person will
        # be chosen with 100% probability, taking the minimum to ensure
        # exposed < susceptible is always true.
        adjustedContacts = contacts

    if stochastic:
        # AdjustedContacts can be non integer because of the adjustment, round it
        infectiousContacts = random_state.binomial(int(round(adjustedContacts)), infectionProb)
    else:
        infectiousContacts = adjustedContacts * infectionProb

    return min(infectiousContacts, susceptible)


def getSusceptibles(age: str, currentInternalStateDict: Dict[Tuple[Age, Compartment], float]) -> float:
    """Calculate the total number of individuals in a susceptible state in an age range within a
    region.

    :param age: The age (range)
    :param currentInternalStateDict: The disease status of the population in a region stratified
                                     by age.
    :return: The number of individuals in a susceptible state and age range.
    """
    return currentInternalStateDict[(age, SUSCEPTIBLE_STATE)]


def expose(age: Age, exposed: float, region: Dict[Tuple[Age, Compartment], float]):
    """Update the region in place, moving people from susceptible to exposed.

    :param age: age group that will be exposed.
    :param exposed: The number of exposed individuals.
    :param region: A region, with all the (age, state) tuples.
    """
    # print(region)
    # if region[(age, SUSCEPTIBLE_STATE)] >= exposed:
    #     print('WARNING - 'f"S:{region[(age, SUSCEPTIBLE_STATE)]} < E:{exposed}")
    #     exposed = region[(age, SUSCEPTIBLE_STATE)]
#         
    assert region[(age, SUSCEPTIBLE_STATE)] >= exposed, f"S:{region[(age, SUSCEPTIBLE_STATE)]} < E:{exposed}"

    region[(age, EXPOSED_STATE)] += exposed
    region[(age, SUSCEPTIBLE_STATE)] -= exposed


def randomlyInfectRegions(
        network: NetworkOfPopulation,
        regions: int,
        age_groups: List[Age],
        infected: float,
        random_state: np.random.Generator
) -> Dict[NodeName, Dict[Age, float]]:
    """Randomly infect regions to initialize the random simulation

    :param network: object representing the network of populations
    :param regions: The number of regions to expose.
    :param age_groups: Age groups to infect
    :param infected: People to infect
    :param random_state: Random state for random number generation
    :return: Structure of initially infected regions with number
    """
    infections: Dict[NodeName, Dict[Age, float]] = {}
    for regionID in random_state.choice(list(network.graph.nodes()), size=regions):
        infections[regionID] = {}
        for age in age_groups:
            infections[regionID][age] = infected

    return infections

def _doTesting(false_pos, region: Dict[Tuple[Age, Compartment], float], lockdown_regions=True):
#     DANGER - this will modify the next-step in place.
# Also, won't work in the stochastic version yet
    for key, value in region.items():
        if key[1] == SUSCEPTIBLE_STATE:
            num_false_pos = false_pos*value
            region[key] = value - num_false_pos
            region[(key[0], FALSE_POS_STATE)] = region[(key[0], FALSE_POS_STATE)] + num_false_pos
            

            
    