"""
    This package will create the simplified comix matrix needed by simple_network_sim basing itself in the following data:
    
    - The CoMix matrix: https://cmmid.github.io/topics/covid19/reports/20200327_comix_social_contacts.xlsx
    - The Scottish demographics (NRS): ftp://boydorr.gla.ac.uk/scrc/human/demographics/scotland/1.0.0.h5
    - The England & Wales demographics (ONS): https://www.nomisweb.co.uk/api/v01/dataset/NM_2010_1.data.csv (the data was
      aggregated into the wales_england_pop.csv file)
    metadata.yaml and data_processing_config.yaml should contain pointers to these data
    Python requirements:
    - pandas
    - xlrd
    - h5py
    
    How to run this module:
    
    Assuming you have your environment setup with conda, this script can be run with
    
    ```
    python comix_downsampler_data_processing_extractor.py
    ```
    
    That will generate a file called mixing-matrix.csv (for convenient sanity-checking), and a .h5 file with the same information for use
    inside the simple network sim model
    (https://github.com/ScottishCovidResponse/simple_network_sim)
"""
from typing import NamedTuple, List

from pathlib import Path
from data_pipeline_api.data_processing_api import DataProcessingAPI

import numpy as np
import pandas as pd

ContactsTable = pd.DataFrame
ComixTable = pd.DataFrame


class Data(NamedTuple):
    """
    All data needed to do the downsampling
    """

    comix: ComixTable
    population: pd.Series


def main():
    config_filename = Path(__file__).parent / "data_processing_config.yaml"
    uri = "data_processing_uri"
    git_sha = "data_processing_git_sha"
    with DataProcessingAPI(config_filename, uri=uri, git_sha=git_sha) as api:

        # first get the comix
        comix_external = "https://cmmid.github.io/topics/covid19/reports/20200327_comix_social_contacts.xlsx"
        with api.read_external_object(comix_external) as file:
            df_comix = pd.read_excel(file, sheet_name="All_contacts_imputed")
        df_comix = df_comix.set_index("Unnamed: 0")
        # then get the population - ONS, and NRS
        ons_external = "wales_england_pop.csv"
        with api.read_external_object(ons_external) as file:
            ons_pop = pd.read_csv(
                "human/wales_england_pop.csv", index_col="AGE"
            ).POPULATION

        nrs_internal = "human/demographics/population/scotland/1.0.0.h5"
        data_plus_lists = api.read_array(nrs_internal, "health_board/age/persons")
        data = data_plus_lists[0]
        placeNames = list(data_plus_lists[1][0][1])
        ageNames = list(data_plus_lists[1][1][1])
        # print(placeNames)

        ages = [int(s.replace("AGE", "").replace("+", "")) for s in ageNames]
        df = pd.DataFrame(data, index=ages, columns=placeNames).T

        nrs_pop = df.sum()

        data = Data(comix=df_comix, population=ons_pop + nrs_pop)
        contacts = comix_to_contacts(
            data.comix, _aggregate_pop_full_comix(data.population, data.comix)
        )

        contacts = split_17_years_old(contacts, data.population)

        contacts = collapse_columns(contacts, ["[0,5)", "[5,17)"], "[0,17)")
        contacts = collapse_columns(
            contacts,
            ["17", "[18,30)", "[30,40)", "[40,50)", "[50,60)", "[60,70)"],
            "[17,70)",
        )
        # The 70+ entry is already what we want

        comix = contacts_to_comix(
            contacts, _aggregate_pop_simplified_comix(data.population, contacts)
        )

        flattened = _flatten(comix)
        flattened.to_csv("mixing-matrix.csv", index=False)
        api.write_table(
            "generated_sns_products/simplified_comix_matrix",
            "simplified_comix_matrix",
            flattened,
        )


def collapse_columns(
    df: ContactsTable, names: List[str], new_name: str
) -> ContactsTable:
    """
    This function assumes that df has both columns and indexes identified by the same `names`. They will all be added
    together to create a new column and row named `new_name`. Eg.:

    >>> df = ContactsTable(pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6], "c": [7, 8, 9]}, index=list("abc")))
    >>> collapse_columns(df, ["a", "b"], "a'")
        a'   c
    a'  12  15
    c    9   9

    :param df: a contacts table type table. That means it's a upper triangle matrix
    :param names: name of the columns and indexes to aggregate
    :param new_name: name of the new column and row that will be created
    :return: A dataframe with collapsed columns and indexes
    """
    if not names:
        raise ValueError("Names must be a non-empty list")
    missing_columns = set(names) - set(df.columns)
    if missing_columns:
        raise ValueError(f"Names mismatch: {missing_columns}")
    if not all(df.columns == df.index):
        raise ValueError("Indexes and columns must match")

    agg = df.copy()

    agg[names[0]] = df[names].sum(axis=1)
    agg = agg.rename({names[0]: new_name}, axis=1)
    agg = agg.drop(columns=names[1:])

    agg.loc[names[0]] = agg.loc[names].sum()
    agg = agg.rename({names[0]: new_name}, axis=0)
    agg = agg.drop(index=names[1:])

    return ContactsTable(agg)


def comix_to_contacts(comix: ComixTable, agg: pd.DataFrame) -> ContactsTable:
    """
    Converts the CoMix matrix to a matrix of contacts (total number of contacts rather than averages). Although the
    CoMix matrix is not symmetric, the contacts matrix should be. That will not always happen given the population
    we have. Therefore, we average out both triangles and return a upper triangular matrix
    """
    contacts = comix * agg

    # Now we are averaging out the triangles so the matrix becomes symmetric
    averaged = (np.tril(contacts).T + np.triu(contacts)) / 2

    return ContactsTable(
        pd.DataFrame(averaged, columns=comix.columns, index=comix.index)
    )


def contacts_to_comix(contacts: ContactsTable, agg: pd.DataFrame) -> ComixTable:
    """
    Converts a matrix of contacts to the CoMix matrix
    """
    contacts = pd.DataFrame(
        contacts.T + np.triu(contacts, k=1),
        columns=contacts.columns,
        index=contacts.index,
    )

    return ComixTable(contacts / agg)


def split_17_years_old(contacts: ContactsTable, pop: pd.Series) -> ContactsTable:
    """
    The original CoMix matrix has the ranges [0,5) and [5,18) ranges, whereas we need it to be [0,17). Adding two
    columns together is a simple operation, but we must first need to move the 17 year olds out of [5,18) into the
    [18,30) range and rename the ranges.

    Based the age stratified population, this function will move a number of contacts proportional to the proportion
    of 17 year olds in the [5,18) population
    :param contacts: The upper triangular contact matrix
    :param pop: age stratified population series
    :return:
    """
    age_groups = list(contacts.columns)

    proportion_17 = pop[17] / pop[5:17].sum()

    contacts = contacts.copy()
    contacts["17"] = contacts["[5,18)"] * proportion_17
    contacts.loc["17"] = contacts.loc["[5,18)"] * proportion_17
    # special case
    contacts["17"]["17"] = contacts["[5,18)"]["[5,18)"] * proportion_17 ** 2

    # The following two lines will calculate contacts["[5,17)"]["[5,17)"] twice
    contacts["[5,17)"] = contacts["[5,18)"] * (1 - proportion_17)
    contacts.loc["[5,17)"] = contacts.loc["[5,18)"] * (1 - proportion_17)
    # this will fix that
    contacts["[5,17)"]["[5,17)"] = contacts["[5,18)"]["[5,18)"] * (1 - proportion_17)
    # special cases
    contacts.loc["[5,17)", "17"] = (
        contacts.loc["[5,18)", "[5,18)"] * (1 - proportion_17) * proportion_17
    )
    contacts.loc["17", "[5,17)"] = 0.0

    # reorder the table columns and indexes
    age_groups.insert(age_groups.index("[18,30)"), "17")
    age_groups[age_groups.index("[5,18)")] = "[5,17)"
    return ContactsTable(contacts.loc[age_groups, age_groups])


def download_ons() -> pd.Series:
    """
    Downlads ONS data from university's FTP

    :return: Population series, indexed by age
    """
    # TODO: This data is not yet integrated into SCRCdata. Below are the steps to generate it:
    #
    # The bash script below was used to scrape all the data from upstream (takes ~5 hours to finish):
    # set -ex
    #
    # offset=0
    # step=24000
    # while true; do
    #     curl -H 'Accept-Encoding: deflate, gzip;q=1.0, *;q=0.5' -s "https://www.nomisweb.co.uk/api/v01/dataset/NM_2010_1.data.csv?measures=20100&time=latest&gender=0&geography=TYPE299&RecordLimit=$step&RecordOffset=$offset" > NM_2010_1.$offset.csv.gz
    #     if [ $(zcat "NM_2010_1.$offset.csv.gz" | wc -l) -lt $step ]; then
    #         break
    #     fi
    #     offset=$(( offset + step ))
    # done
    #
    # After running that, a bit of bash processing is still required. First, we need to decompress it
    # $ for x in *gz; do gunzip $x; done
    # Then we need to remove the header
    # $ head -1 NM_2010_1.0.csv > header
    # $ for x in *.csv; do sed -i 1d $x; done
    # Aggregate them all into a single file
    # cat header $(for x in $(ls -1 *.csv | sed 's/NM_2010_1.//' | sort -n); do echo NM_2010_1.$x; done) > NM_2010_1.csv
    # Finally, this will need dask, if you don't have enough memory:
    # >>> import dask.dataframe as dd
    # >>> df = dd.read_csv("NM_2010_1.csv")
    # >>> tot = df[df.C_AGE.isin(list(range(101,192)))].groupby("C_AGE").OBS_VALUE.sum().compute()
    # >>> tot.index = list(range(0,91)
    # >>> tot.to_frame("POPULATION").to_csv("wales_england_pop.csv", index_label="AGE")
    # That's the csv file we are reading below

    df = pd.read_csv("human/wales_england_pop.csv", index_col="AGE")
    return df.POPULATION


def _aggregate_pop_full_comix(pop: pd.Series, target: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates the population matrix based on the CoMix table.

    :param pop: 1-year based population
    :param target: target dataframe we will want to multiply or divide with
    :return: Retuns a dataframe that can be multiplied with the comix matrix to get a table of contacts or it can be
             used to divide the contacts table to get the CoMix back
    """
    agg = pd.DataFrame(
        {
            "[0,5)": [pop[:5].sum()],
            "[5,18)": [pop[5:18].sum()],
            "[18,30)": [pop[18:30].sum()],
            "[30,40)": [pop[30:40].sum()],
            "[40,50)": [pop[40:50].sum()],
            "[50,60)": [pop[50:60].sum()],
            "[60,70)": [pop[60:70].sum()],
            "70+": [pop[70:].sum()],
        }
    )
    return pd.concat([agg] * len(target.columns)).set_index(target.index).T


def _aggregate_pop_simplified_comix(
    pop: pd.Series, target: pd.DataFrame
) -> pd.DataFrame:
    """
    Aggregates the population matrix based on the CoMix table.

    :param pop: 1-year based population
    :param target: target dataframe we will want to multiply or divide with
    :return: Retuns a dataframe that can be multiplied with the comix matrix to get a table of contacts or it can be
             used to divide the contacts table to get the CoMix back
    """
    agg = pd.DataFrame(
        {
            "[0,17)": [pop[:17].sum()],
            "[17,70)": [pop[17:69].sum()],
            "70+": [pop[70:].sum()],
        }
    )
    return pd.concat([agg] * len(target.columns)).set_index(target.index).T


def _flatten(comix: ComixTable):
    rows = []
    for source, columns in comix.iterrows():
        for target, mixing in columns.iteritems():
            rows.append({"source": source, "target": target, "mixing": mixing})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    main()
