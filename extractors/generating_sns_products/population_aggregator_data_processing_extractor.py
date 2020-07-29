"""
This package will create the row-wise table of health board population numbers needed by simple_network_sim basing itself in the following data:

- The Scottish demographics (NRS): ftp://boydorr.gla.ac.uk/scrc/human/demographics/scotland/1.0.0.h5

How to run this module:
Assuming you have your environment setup with conda, this script can be run with

```
python population_aggregator_data_processing_extractor.py
```
That will generate a file called check_pop_table.csv (for convenient sanity-checking), and a .h5 file with the same information for use
inside the simple network sim model at generated_sns_products/population_healthboards_scotland
(https://github.com/ScottishCovidResponse/simple_network_sim)
"""
from typing import NamedTuple, List
from pathlib import Path
from data_pipeline_api.data_processing_api import DataProcessingAPI
import h5py
import pandas as pd


def main():
    config_filename = Path(__file__).parent / "data_processing_config.yaml"
    uri = "data_processing_uri"
    git_sha = "data_processing_git_sha"
    with DataProcessingAPI(config_filename, uri=uri, git_sha=git_sha) as api:

        nrs_internal = "human/demographics/population/scotland/1.0.0.h5"
        data_plus_lists = api.read_array(nrs_internal, "health_board/age/genders")

        female_data = data_plus_lists[0][0]
        male_data = data_plus_lists[0][1]
        placeNames = list(data_plus_lists[1][0][1])
        ageNames = list(data_plus_lists[1][1][1])

        ages = [int(s.replace("AGE", "").replace("+", "")) for s in ageNames]
        female_pop = pd.DataFrame(female_data, index=ages, columns=placeNames).T
        male_pop = pd.DataFrame(male_data, index=ages, columns=placeNames).T

        age_class_dict = {
            "[0,17)": range(0, 17),
            "[17,70)": range(17, 70),
            "70+": range(70, 91),
        }

        aggFemale = aggregate_columns_and_rename(female_pop, age_class_dict, "Female")
        aggMale = aggregate_columns_and_rename(male_pop, age_class_dict, "Male")
        aggTogether = pd.concat([aggFemale, aggMale])
        aggTogether = aggTogether.set_index(["Health_Board", "Sex"]).stack()
        aggTogether = aggTogether.reset_index()
        aggTogether.columns = ["Health_Board", "Sex", "Age", "Total"]
        aggTogether.to_csv("check_pop_table.csv", index=False)

        api.write_table(
            "generated_sns_products/population_healthboards_scotland",
            "population_healthboards_scotland",
            aggTogether,
        )


def aggregate_columns_and_rename(
    df: pd.DataFrame, aggregate_dict: dict, sex_name: str
) -> pd.DataFrame:
    """
    This function aggregates ages in df using the mapping in aggregate_dict,
    adds a column with the uniform value sex_name, and
    renames the columns conveniently for simple_network_sim's population table

    :param df: a dataframe in which the columns are health boards and ages that should appear in the union of the values of aggregate_dict
    :param aggreagate_dict: a dictionary with new column names as keys and lists of the columns to sum as values
    :param sex_name: name of the new column and row that will be created
    :return: A dataframe with collapsed columns with the new collapsed column names as well as a Health_Board column and a Sex column
    """
    for age in aggregate_dict:
        df[age] = df[aggregate_dict[age]].sum(axis=1)
    df = df[aggregate_dict.keys()]
    df["Sex"] = sex_name
    df = df.reset_index()
    df.columns = ["Health_Board", "[0,17)", "[17,70)", "70+", "Sex"]
    return df


if __name__ == "__main__":
    main()
