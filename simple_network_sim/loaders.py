"""This module contains functions and classes to read and check input files."""

import csv
import json
import math
import re
from typing import Dict, TextIO, NamedTuple, List

import networkx as nx
import pandas as pd

# CurrentlyInUse
def _checkAgeParameters(agesDictionary):
    """Check the consistency of data within the ages dictionary.

    :param agesDictionary:
    :type agesDictionary: dictionary
    :return: agesDictionary
    """
    all_compartments = None
    for age, compartments in agesDictionary.items():
        if all_compartments is None:
            all_compartments = list(compartments.keys())
        else:
            assert all_compartments == list(compartments.keys()), f"compartments mismatch in {age}"
        for compartment, transitions in compartments.items():
            assert compartment in transitions.keys(), f"{age},{compartment} does not have self referencing key"
            assert math.isclose(sum(transitions.values()), 1.0), f"{age},{compartment} transitions do not add up to 1.0"
            for new_name, prob in transitions.items():
                assert 0.0 <= prob <= 1.0, f"{age},{compartment},{new_name},{prob} not a valid probability"

    return agesDictionary


# CurrentlyInUse
def readCompartmentRatesByAge(table: pd.DataFrame,) -> Dict[str, Dict[str, Dict[str, float]]]:
    """Read a file containing a list of age-specific epidemiological parameters.
    
    Epidemiological parameters are transition rates between or out of epidemiological compartments,
    here they differ by age group.

    :param fp: Age transition data
    :type fp: file-like object
    :return: A dictionary of in the format {age: {src: {dest: prob}}}
    """
    agesDictionary = {}
    for row in table.to_dict(orient="row"):
        compartments = agesDictionary.setdefault(row["age"], {})
        transitions = compartments.setdefault(row["src"], {})
        transitions[row["dst"]] = float(row["rate"])
    return _checkAgeParameters(agesDictionary)


# CurrentlyInUse

def readPopulationAgeStructured(table: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """Read a file containing population data.

    Population is labelled by node ID, sex and age. Sex is currently ignored.
    
    :param fp: Population data
    :type fp: file-like object
    :return: A dictionary in the format {health_board: {age: pop, age: pop, age: pop}}
    """
    dictOfPops = {}

    for row in table.to_dict(orient="row"):
        board = dictOfPops.setdefault(row["Health_Board"], {})
        total = int(row["Total"])
        if total < 0:
            raise ValueError(f"invalid total {total}")
        # We are ignoring the Sex column here. The same age group will appear multiple times (once per age) and we will
        # end up just grouping them all together
        board.setdefault(row["Age"], 0)
        board[row["Age"]] += total

    return dictOfPops


# CurrentlyInUse
# making this general to include arbitrary future attributes.  Location is the primary one for right now
# keeps them in a dictionary and returns that.  Keys are
def readNodeAttributesJSON(filename):
    """Read a file containing node (health board) attributes.

    This might include health board name and geographic co-ordinates.

    :param filename: Health board attributes in json format. 
    :type filename: file-like object
    :return: Dictionary of health board attributes.
    """
    f = open(filename,)
    node_data = json.load(f)
    return node_data


# CurrentlyInUse
# at the moment this uses vanilla networkx edge list reading - needs weights
#  I've set it apart as its own function in case we want to do anything fancier with edge files
# in future - e.g. sampling, generating movements, whatever
# it should return a networkx graph, ideally with weighted edges
# eventual replacement with HDF5 reading code?
def genGraphFromContactFile(commutes: pd.DataFrame) -> nx.DiGraph:
    """Read a file containing edge weights between nodes.

    Pairs of nodes are listed in the file by source, destination, weight and adjustment.

    :param commutes: Weighted edge list.
    :type pd.DataFrame: pandas DataFrame.
    :return: `networkx.classes.digraph.DiGraph` object representing the graph.
    """
    G = nx.convert_matrix.from_pandas_edgelist(commutes, edge_attr=True, create_using=nx.DiGraph)
    for edge in G.edges.data():
        assert edge[2]["weight"] >= 0.0
        assert edge[2]["delta_adjustment"] >= 0.0
    return G


def readInitialInfections(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Read initial numbers of infected individuals by health board and age.

    :param df: raw data to be loaded
    :type df: a pandas DataFrame with columns Health_Board (str), Age (str) and Infected (float)
    :return: A dict in the format {<region:str>: {<age:str>: <num infected>}}
    """
    infections: Dict[str, Dict[str, float]] = {}
    for row in df.to_dict(orient="row"):
        if float(row["Infected"]) >= 0.0 and row["Infected"] != math.inf:
            infections.setdefault(row["Health_Board"], {})[row["Age"]] = row["Infected"]
        else:
            raise ValueError(f"Invalid infected value: {row['Infected']}")
    return infections


class Multiplier(NamedTuple):
    movement: float
    contact: float


def _assertPositiveNumber(value: float):
    if value < 0.0 or math.isinf(value) or math.isnan(value):
        raise ValueError(f"{value} must be a positive number")


def readMovementMultipliers(table: pd.DataFrame) -> Dict[int, Multiplier]:
    """Read file containing movement multipliers by time.

    :param table: pandas DataFrame containing movement multipliers
    :return: A dict of ints (time) pointing to a (named)tuple (contact=float, movement=float). Contact will alter how
             the disease spreads inside of a node, whereas movement will change how it spread across nodes
    """
    multipliers = {}
    for row in table.to_dict(orient="row"):
        time = int(row["Time"])
        if time < 0:
            raise ValueError("can't have negative time")

        movement = float(row["Movement_Multiplier"])
        _assertPositiveNumber(movement)

        contact = float(row["Contact_Multiplier"])
        _assertPositiveNumber(contact)

        multipliers[time] = Multiplier(movement=movement, contact=contact)

    return multipliers


def readInfectiousStates(infectious_states: pd.DataFrame) -> List[str]:
    """
    Transforms the API output of infectious_states into the internal representation: a list of strings
    :param infectious_states: API dataframe
    :return: a list of strings of infectious compartments
    """
    if infectious_states.size == 0:
        return []
    return list(infectious_states.Compartment)


def _check_overlap(one, two):
    """Check two AgeRange objects to see if they overlap.
    
    If they do, raise an Exception.
    :param one:
    :type one: simple_network_sim.loaders.AgeRange
    :param two:
    :type two: simple_network_sim.loaders.AgeRange
    """
    assert one._upper <= two._lower or two._upper <= one._lower, \
            (f"Overlap in age ranges with {one} and {two}")


# We use this to match an age range in the AgeRange class
AGE_RE = re.compile(r'\[(\d+),\s*(\d+)\)')


class AgeRange:
    """A helper class for an age range.
    
    If b is None, it is assumed that a is a tuple holding the 
    upper and lower values of the range or a string to be parsed.

    The string can be one of the two formats:
    [a,b) - that's an age range from a to b (not including b)
    a+    - that means any age greater than a, equivalent to [a,MAX_AGE)

    Otherwise, the age range is assumed to be [a, b), where a and b are positive integers.
    """

    # A marker for no upper limit
    MAX_AGE = 200

    def __init__(self, a, b=None):
        """Initialise."""
        if b is None:
            if isinstance(a, tuple) and len(a) == 2:
                self._lower = a[0]
                self._upper = a[1]
            else:
                match = AGE_RE.match(a)
                if match:
                    self._lower = int(match.group(1))
                    self._upper = int(match.group(2))
                elif a[-1] == "+":
                    self._lower = int(a[:-1])
                    self._upper = AgeRange.MAX_AGE
                else:
                    raise Exception(f'Invalid age range specified: "{a}"')
        else:
            self._lower = int(a)
            self._upper = int(b)

        assert self._lower < self._upper, f'Invalid age range specified: [{self._lower},{self._upper})'
        assert self._upper <= AgeRange.MAX_AGE, f"No one is {self._upper} years old"
        assert self._lower >= 0, f"No one is {self._lower} years old"

    def __contains__(self, age):
        """Return true if age is inside this age range."""
        if age < self._lower:
            return False
        return age < self._upper

    def __str__(self):
        """Return a string representation of the current AgeRange instance."""
        if self._upper == AgeRange.MAX_AGE:
            return f"{self._lower}+"
        return f"[{self._lower},{self._upper})"

    def __eq__(self, other):
        """Return true if "other" is the same as the current AgeRange instance."""
        return self._lower == other._lower and self._upper == other._upper

    def __neq__(self, other):
        """Return true if "other" is not the same as the current AgeRange instance."""
        return not self == other

    def __hash__(self):
        """Return a hash of the current AgeRange instance."""
        return hash((self._lower, self._upper))


class MixingRow:
    """One row of a mixing table.
    
    This is a helper class. A row represents a given population, 
    and can return the expected number of interactions (per unit time) 
    a member of this population will have with some other target.
    
    :param ages: Ages
    :type ages: list
    :param interactions: Interactions / person / day
    :type interactions: list

    Both lists must be the same length.

    Upon initialization, the property `self._entries` is set to a dictionary mapping 
    AgeRange objects to numbers of interactions / person / day.
    """

    def __init__(self, ages, interactions):
        """Initialise."""        
        self._entries = {}
        for age, interact in zip(ages, interactions):
            self._entries[age] = float(interact)

    def __getitem__(self, age):
        """Return expected number of interactions.
        
        Return the expected number of interactions (per day) that someone from
        this MixingRow would have with someone with the given age, or age
        range.
        """
        if isinstance(age, str) or isinstance(age, tuple):
            return self._entries[AgeRange(age)]
        for key, value in self._entries.items():
            if age in key:
                return value
        raise Exception(f'Could not find {age} in MixingRow')

    def __str__(self):
        """Return a string representing the current MixingRow instance."""
        return "[" + ", ".join(f"{str(key)}: {str(val)}"
                               for key, val in self._entries.items()) + "]"

    def __iter__(self):
        """Iterate through age-interactions dictionary."""
        return iter(str(age_range) for age_range in self._entries)


class MixingMatrix:
    """Stores expected numbers of interactions between people of different ages.
    
    Stores expected number of interactions per day a given person will
    have with some other person, based on the ages of the two people, or given
    age-ranges.
    
    Examples:    
    `mm = MixingMatrix("sample_input_file/sample_20200327_comix_social_contacts.sampleCsv")`
    `print(mm[28][57])` Prints the expected number of interactions a 28 year old
    would have with a 57 year old in a day
    `print(mm["[30,40)"]["70+"])` or `print(mm[(30,40)]["70+"])` Prints the expected number of interactions someone in the
    age range [30-40) would have with someone aged 70 or older
    in any given day.

    :param infile: The input file should be a `.csv` file, with the
        first row and column as headers. These contain age ranges in either the
        format "[a, b)", or the format "a+". The entry in the table in row R
        and column C then indicates how many expected interactions per day a
        member of the R column interacts with a member of the C columns.
    :type infile: file-like object

    """

    def __init__(self, mixing_table: pd.DataFrame):
        """Initialise."""
        self._matrix = {
            AgeRange(group_name): MixingRow([AgeRange(target) for target in group["target"]], list(group["mixing"]))
            for group_name, group in mixing_table.groupby("source")
        }

        # Check for any overlap in the column headers
        for i, one in enumerate(self._matrix.keys()):
            for j, two in enumerate(self._matrix.keys()):
                if i == j:
                    continue
                _check_overlap(one, two)

    def __getitem__(self, age):
        """Return MixingRow for given age.
        
        Gets a MixingRow for the given age, which in turn can give the
        expected number of interactions. Most often, you will probably want to
        just use MixingMatrix[age1][age2] to get the expected number of
        interactions that a person of age1 will have with a person of age2.
        Note that either age1 or age2 can be numbers, or age ranges.
        """
        if isinstance(age, str) or isinstance(age, tuple):
            return self._matrix[AgeRange(age)]
        for key, value in self._matrix.items():
            if age in key:
                return value
        raise Exception(f'Could not find {age} in MixingMatrix')

    def __str__(self):
        """Return a string representing the current MixingMatrix instance."""
        return "\n".join(f"{str(key)}: {str(row)}" for key, row in self._matrix.items())

    def __iter__(self):
        """Iterate by row.

        Iterator that iterates over the matrix keys (a key points to a row). The values returned by the iterator will
        all be strings, since that's how the public interface when indexing the matrix.
        """
        return iter(str(age_range) for age_range in self._matrix)
