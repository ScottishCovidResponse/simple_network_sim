"""
This script will create the movement multipliers using:
- A populations estimate for each local authority in Scotland from 2018 (mid year) https://www2.gov.scot/Resource/0046/00462936.csv
- Google mobility data giving the number of movements between geographic regions in 2020 https://www.gstatic.com/covid19/mobility/Global_Mobility_Report.csv
- A table mapping the iso_3166_2 name of each local authority to the local authority name and code
   compiled by hand, Jess Enright, 30 June 2020

Python requirements:
- pathlib
- pandas
- zipfile
- ftplib.FTP  ??? Only if the hand generated lookup table is hosted on the FTP server.
- urllib.request
- data_pipeline_api

How to run this module:
This script uses the data_pipeline_api.data_processing_api, and therefore makes use of both
- data_processing_config.yaml, and
- metadata.yaml
metadata.yaml should include something like:
```
- doi_or_unique_name: mid-year-pop-est-18-tabs_Table 2.csv
  filename: human/external/mid-year-pop-est-18-tabs_Table 2.csv
- doi_or_unique_name: Global_Mobility_Report.csv
  filename: human/external/Global_Mobility_Report.csv
```
This script can be run with
```
python aggregate_flows_from_google_data.py
```
The script generates .h5 files in generated_sns_products/movement_multiplier
"""

from pathlib import Path
import pandas as pd
import urllib.request
from data_pipeline_api.data_processing_api import DataProcessingAPI
from ftplib import FTP
import zipfile


config_filename =  Path(__file__).parent / "data_processing_config.yaml"
uri = "data_processing_uri"
git_sha = "data_processing_git_sha"
data_path = Path(__file__).parent / "human/external"


def download_pop_table():
    """
    Download the population data from an external source if it doesn't exists in data_path, using only the Area1 data and the first 3 columns
    the LA code, name and population, removing the commas in the population numbers.
    :return: A dataframe containing the local authority code, name and population
             and the total polulation
    """

    population_table = "mid-year-pop-est-18-tabs_Table 2.csv"


    # If the population table doesn't exist download it.
    if not Path(data_path / population_table).exists():
        print(f"Could not find {data_path}/{population_table}, downloading it")
        url = "https://www.nrscotland.gov.uk/files//statistics/population-estimates/mid-18/mid-year-pop-est-18-tabs.zip"
        zip_filename = "mid-year-pop-est-18-tabs.zip"
        urllib.request.urlretrieve(
            url, zip_filename
        )

        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(data_path, members=[population_table])

        # clean up (i.e. remove) the downloaded datafile(s)
        Path(zip_filename).unlink(missing_ok=False)

    with DataProcessingAPI(config_filename, uri=uri, git_sha=git_sha) as api:
        with api.read_external_object(population_table) as file:
            dfPop = pd.read_csv(file, skiprows=5, nrows=32, usecols=[0, 1, 2])
            dfPop.columns = ['la_code', 'la_name', 'population']
            dfPop['population'] = dfPop['population'].str.replace(',', '').astype(int)

    total_population =  dfPop['population'].sum()

    return dfPop, total_population

def download_lookup_table():
    """
    Downloads the mapping of iso_3166_2 codes to local authority from the SCRC database, 
    if it doesn't exist, upload it
    :return: A dataframe containing the full ISO code (GB-iso_3166_2) and the corresponding local authority code.
    """
    
    #TODO - should I check if these files are in the pipeline and if not upload them before starting?
    # If so - I don't know how to write the metadata…yaml file stuff

    # ISO region to LA best-attempt lookup table: compiled by hand, Jess Enright, 30 June 2020
    lookup_table = "iso-3166-2_to_scottishLA.csv"

    """
    TODO - Question: Do we want this file to be saved somewhere, or save the data here as a dataframe?
    if <download_lookup_from ftp_server>:
         dfLookup = pd.read_csv(lookup_table, low_memory=False)
    else:
        # ISO region to LA best-attempt lookup table: compiled by hand, Jess Enright, 30 June 2020
        data = [['ABE','Aberdeen','S12000033','Aberdeen City'],
['ABD','Aberdeenshire','S12000034','Aberdeenshire'],
['ANS','Angus','S12000041','Angus'],
['AGB','Argyll and Bute','S12000035','Argyll and Bute'],
['EDH','Edinburgh','S12000036','City of Edinburgh'],
['CLK','Clackmannanshire','S12000005','Clackmannanshire'],
['DGY','Dumfries and Galloway','S12000006','Dumfries and Galloway'],
['DND','Dundee','S12000042','Dundee City'],
['EAY','East Ayrshire','S12000008','East Ayrshire'],
['EDU','East Dunbartonshire','S12000045','East Dunbartonshire'],
['ELN','East Lothian','S12000010','East Lothian'],
['ERW','East Renfrewshire','S12000011','East Renfrewshire'],
['FAL','Falkirk','S12000014','Falkirk'],
['FIF','Fife','S12000047','Fife'],
['GLG','Glasgow','S12000046','Glasgow City'],
['HLD','Highland','S12000017','Highland'],
['IVC','Inverclyde','S12000018','Inverclyde'],
['MLN','Midlothian','S12000019','Midlothian'],
['MRY','Moray','S12000020','Moray'],
['ELS','Eilean Siar','S12000013','Na h-Eileanan Siar'],
['NAY','North Ayrshire','S12000021','North Ayrshire'],
['NLK','North Lanarkshire','S12000044','North Lanarkshire'],
['ORK','Orkney Islands','S12000023','Orkney Islands'],
['PKN','Perth and Kinross','S12000048','Perth and Kinross'],
['RFW','Renfrewshire','S12000038','Renfrewshire'],
['SCB','Scottish Borders The','S12000026','Scottish Borders'],
['ZET','Shetland Islands','S12000027','Shetland Islands'],
['SAY','South Ayrshire','S12000028','South Ayrshire'],
['SLK','South Lanarkshire','S12000029','South Lanarkshire'],
['STG','Stirling','S12000030','Stirling'],
['WDU','West Dunbartonshire','S12000039','West Dunbartonshire'],
['WLN','West Lothian','S12000040','West Lothian']]
        dfLookup = pd.DataFrame(data,columns=['iso_3166_2','name_of_subdivision','la_code','la_name'])
        dfLookup.set_index('iso_3166_2',inplace = True)
        dfLookup.to_csv('iso_codes.csv')
        #upload dfLookup.to_csv() to server
    """

    dfLookup = pd.read_csv(lookup_table, low_memory=False)
    dfLookup['full_iso_code'] = "GB-" + dfLookup.iso_3166_2
    codes_of_interest = list(dfLookup['full_iso_code'])
    dfLookup = dfLookup[['full_iso_code', 'la_code']]

    # clean up (i.e. remove) the downloaded datafile(s)
    #Path(lookup_table).unlink(missing_ok=False)

    return dfLookup, codes_of_interest

def download_google_mogility_data(la_list):
    """
    Downloads the mobility data from google for Scottish local authorities if it doesn't exists in data_path
    :param: The list of local åuthorities for which we want the movement data
    :return: A dataframe containing the full ISO code (GB-iso_3166_2) and the corresponding local authority code
    """

    google_mobility_table = "Global_Mobility_Report.csv"

    # If the population table doesn't exist download it.
    if not Path(data_path / google_mobility_table).exists():
        print(f"Could not find {data_path}/{google_mobility_table}, downloading it")
        url = "https://www.gstatic.com/covid19/mobility/Global_Mobility_Report.csv"
        urllib.request.urlretrieve(
                url, data_path / google_mobility_table
                )

    with DataProcessingAPI(config_filename, uri=uri, git_sha=git_sha) as api:
        with api.read_external_object(google_mobility_table) as file:
            justScotGoogle = pd.read_csv(google_mobility_table, low_memory=False)
            justScotGoogle = justScotGoogle[justScotGoogle['iso_3166_2_code'].isin(la_list) == True]

    return justScotGoogle



def main():
 
    dfPop, totalPop = download_pop_table()
    dfLookup, codes_of_interest = download_lookup_table()

    # We only want the iso-code and the population weighting so add a column for it and remove the extranoeus columns
    dfLookup = dfLookup.join(dfPop.set_index('la_code'), on='la_code')
    dfLookup['pop_weighting'] = dfLookup['population']/totalPop

    dfLookup = dfLookup[['full_iso_code','pop_weighting']]
    dfLookup.set_index('full_iso_code',inplace = True)

    dfScotGoogle = download_google_mogility_data(codes_of_interest)

    dfScotGoogle['movements_for_decrease'] = (dfScotGoogle['transit_stations_percent_change_from_baseline'] + dfScotGoogle['workplaces_percent_change_from_baseline'] + dfScotGoogle['retail_and_recreation_percent_change_from_baseline'])/3

    categories_for_decrease = ['transit_stations_percent_change_from_baseline', 'workplaces_percent_change_from_baseline', 'retail_and_recreation_percent_change_from_baseline']
    dfScotGoogle = dfScotGoogle[['iso_3166_2_code', 'date', 'movements_for_decrease']]

    dfScotGoogle = dfScotGoogle.merge(dfLookup, left_on = 'iso_3166_2_code',right_index = True,how='left')
    dfScotGoogle ['weighted_moves'] = (dfScotGoogle['movements_for_decrease']*dfScotGoogle['pop_weighting'])
    dfScotGoogle = dfScotGoogle [['date', 'weighted_moves']]
    dfScotGoogle['date'] = pd.to_datetime(dfScotGoogle['date'])

    dfScotGoogle = dfScotGoogle.groupby('date').sum()
    dfScotGoogle['weighted_moves'] = 1.0 + dfScotGoogle['weighted_moves']/100.0
    dfScotGoogle.index = pd.to_datetime(dfScotGoogle.index)

    dfScotGoogle = dfScotGoogle[dfScotGoogle.index.dayofweek <5]


    # TODO - upload this to the database; human/movement-multipliers/1/data.h5
    dfScotGoogle.to_csv('movement_multiplier.csv')
    with DataProcessingAPI(config_filename, uri=uri, git_sha=git_sha) as api:
        api.write_table(
            "generated_sns_products/movement_multiplier",
            "movement_multiplier",
            dfScotGoogle,
            )    

if __name__ == "__main__":
    main()
