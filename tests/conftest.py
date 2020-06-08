import csv

from pathlib import Path

import pytest

# Path to directory containing test files for fixtures
FIXTURE_DIR = Path(__file__).parents[0] / "test_data"


@pytest.fixture
def compartmentTransitionsByAge(compartmentTransitionsByAgeFilename):
    with open(compartmentTransitionsByAgeFilename) as fp:
        yield fp


@pytest.fixture
def compartmentTransitionsByAgeFilename():
    yield FIXTURE_DIR / "compartmentTransitionByAge.csv"


@pytest.fixture
def initial_infection():
    yield FIXTURE_DIR / "initial_infection.csv"


@pytest.fixture
def multipliers(multipliers_filename):
    with open(multipliers_filename) as fp:
        yield fp


@pytest.fixture
def multipliers_filename():
    yield FIXTURE_DIR / "movement_multipliers.csv"


@pytest.fixture
def demographics(demographicsFilename):
    with open(demographicsFilename) as fp:
        yield fp


@pytest.fixture
def demographicsFilename():
    yield FIXTURE_DIR / "sample_hb2019_pop_est_2018_row_based.csv"


@pytest.fixture
def mixing_matrix():
    yield FIXTURE_DIR / "sample_20200327_comix_social_contacts_old.csv"


@pytest.fixture
def simplified_mixing_matrix():
    yield FIXTURE_DIR / "simplified_age_infection_matrix.csv"


@pytest.fixture
def commute_moves():
    yield FIXTURE_DIR / "sample_scotHB_commute_moves_wu01.csv"


@pytest.fixture
def locations():
    yield FIXTURE_DIR / "sampleNodeLocations.json"


@pytest.fixture
def compartment_names():
    yield ["S", "E", "A", "I", "H", "R", "D"]


@pytest.fixture
def age_infection_matrix(compartmentTransitionsByAge):
    ages = set()

    for row in csv.DictReader(compartmentTransitionsByAge):
        ages.add(row["age"])
    compartmentTransitionsByAge.seek(
        0
    )  # we need to seek back to the beginning since the fixture scope is function

    matrix = {}
    for a in ages:
        for b in ages:
            matrix.setdefault(a, {})[b] = 0.2

    yield matrix
