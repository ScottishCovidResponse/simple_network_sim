"""
This script will create a compartmental transition rates file as required by simple_network_sim
from a number of direct epidemiological parameters, some age-stratified by the ages "[0,17)", "[17,70)", "70+"
- asymptomatic-period: expected length of pre-symptomatic period for an individual who will eventually devleop symptoms
- death-before-hospitalised: age-structured probability of death from symptomatic state, without being hospitalised
- death-in-hospital: age-structured probability of death given hospitalisation
- hospital-stay: expected length of a hospital stay in hours
- hospitalisation-from-symptoms: age-structured probability that an individual with symptoms will require hospitalisation
- infectious-duration: expected period in which an individual with symptoms is infectious after symptoms appear, in hours
- infectious-period-asymptomatics: expected time period during which true asymptomatics are infectious in hours
- latent-period: expected latent period in hours
- symptom-probability: age-structured probability of an exposed individual eventually developing symptoms (as opposed to being truly asymptomatic)
movement-to-work aggregated files at the Scottish Datazone and Intermediate Zone levels, using:
These are assumed to be accessible via the data_pipeline_api.data_processing_api, as described in the file data_processing_config.yaml
Python requirements:
- pathlib
- pandas
- data_pipeline_api
How to run this module:
```
This script can be run with
```
python generating_rates_from_epidemiological_params.py
```
The script generates a .h5 file of compartment transition rates, in the location specified in  data_processing_config.yaml
"""
from pathlib import Path
import pandas as pd
from data_pipeline_api.data_processing_api import DataProcessingAPI

config_filename = Path(__file__).parent / "data_processing_config.yaml"
uri = "data_processing_uri"
git_sha = "data_processing_git_sha"
with DataProcessingAPI(config_filename, uri=uri, git_sha=git_sha) as api:

    # States: S E A A_2 I H R D
    # We need to generate rates for transitions:
    # E E
    # E	A_2
    # A_2	A_2
    # A_2	R
    # E	A
    # A	A
    # A	I
    # I	I
    # I	D
    # I	H
    # I	R
    # H	H
    # H	D
    # H	R
    # R	R
    # D	D
    # for each age class in which they are present
    transitions = {}
    ages = ["[0,17)", "[17,70)", "70+"]
    for age in ages:
        transitions[age] = {}

    latent_period = api.read_estimate(
        "human/infection/SARS-CoV-2/latent-period", "latent-period"
    )

    ###########################
    # E E
    rate_leaves_E = 1.0 / (latent_period / 24)
    for age in ages:
        transitions[age][("E", "E")] = 1 - (rate_leaves_E)

    for age in ages:
        prob_symptoms = api.read_estimate(
            "human/infection/SARS-CoV-2/symptom-probability", age
        )
        transitions[age][("E", "A_2")] = rate_leaves_E * (1 - prob_symptoms)
        transitions[age][("E", "A")] = rate_leaves_E * (prob_symptoms)

    ###########################
    # A_2 A_2 ,R

    asympomatic_infectious_period = api.read_estimate(
        "human/infection/SARS-CoV-2/infectious-period-asymptomatics",
        "infectious-period-asymptomatics",
    )
    rate_leave_a2 = 1 / (asympomatic_infectious_period / 24)
    for age in ages:
        transitions[age][("A_2", "A_2")] = 1.0 - rate_leave_a2
        transitions[age][("A_2", "R")] = rate_leave_a2

    ###########################
    # A A, I
    presymptom_period = api.read_estimate(
        "human/infection/SARS-CoV-2/asymptomatic-period", "asymptomatic-period"
    )
    rate_leave_A = 1 / (presymptom_period / 24)
    for age in ages:
        transitions[age][("A", "A")] = 1.0 - rate_leave_A
        transitions[age][("A", "I")] = rate_leave_A

    ###########################
    # I I, D, H, R
    i_period = api.read_estimate(
        "human/infection/SARS-CoV-2/infectious-duration", "infectious-duration"
    )
    rate_leave_i = 1 / (i_period / 24)
    for age in ages:

        prob_community_death = api.read_estimate(
            "human/infection/SARS-CoV-2/death-before-hospitalised", age
        )
        prob_hospital = api.read_estimate(
            "human/infection/SARS-CoV-2/hospitalisation-from-symptoms", age
        )

        transitions[age][("I", "I")] = 1.0 - rate_leave_i
        transitions[age][("I", "D")] = rate_leave_i * (prob_community_death)
        transitions[age][("I", "H")] = rate_leave_i * (prob_hospital)
        transitions[age][("I", "R")] = rate_leave_i * (
            1 - prob_hospital - prob_community_death
        )

    ###########################
    # H H, D, R
    hospital_stay = api.read_estimate(
        "human/infection/SARS-CoV-2/hospital-stay", "hospital-stay"
    )
    rate_leave_hospital = 1 - 1 / (hospital_stay / 24)
    for age in ages:
        death_prob = api.read_estimate(
            "human/infection/SARS-CoV-2/death-in-hospital", age
        )
        transitions[age][("H", "H")] = 1 - rate_leave_hospital
        transitions[age][("H", "D")] = rate_leave_hospital * death_prob
        transitions[age][("H", "R")] = rate_leave_hospital * (1 - death_prob)

    ###########################
    # D D
    for age in ages:
        transitions[age][("D", "D")] = 1.0

    ###########################
    # R R
    for age in ages:
        transitions[age][("R", "R")] = 1.0

    # The writing
    df = pd.DataFrame(columns=["age", "src", "dst", "rate"])
    ind = 0
    for age in transitions:
        for (src, dest) in transitions[age]:
            # produce the csv
            df.loc[ind] = [str(age), str(src), str(dest), transitions[age][(src, dest)]]
            ind = ind + 1
    api.write_table(
        "generated_sns_products/compartment_transition_rates",
        "compartment_transition_rates",
        df,
    )
