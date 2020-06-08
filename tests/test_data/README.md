This file will contain brief descriptions of the sample file formats in the sample_input_files directory, or other descriptions where suitable.  This will likely be deprecated by a later move to HDF5 I/O, but for development for now we need to use the data in the formats we have it (as of Thursday, May 7, 2020)

# Files

## paramsFile
**Deprecated**. Use compartmentTransitionByAge.csv

This contains epidemiological rate parameters for movement within the compartmental model - not all rates are included, since some can be inferred from the ones that are provided.
compartment_escape entries are the rate at which individual `s` leave that compartment *to any other* per timestep - e.g. `e_escape:0.427` says that the rate at which individuals leave the `E` state is 0.427
Explicit compartment transfer rates rates from the first compartment in the name to the second - e.g: `i_to_h:0.15` says the rate of movement from `I` to `H` is 0.15
*TODO* for the future - amend the format of this file to make chaining compartmental structure even easier - that is, e.g., `i_to_h:0.15` might become `(I,H):0.15` - not doing for now because of likely change to HDF5

## compartmentTransitionByAge.csv
This contains epidemiological rate parameters for movement within the compartmental model split by ages. Each row represents a transition between two compartmens within a specific age.

## sample_hb2019_pop_est_2018.csv
**Deprecated**. Use sample_hb2019_pop_est_2018_row_based.csv
This file contains age-and-sex-stratified population numbers by geographic unit (here Scottish health board areas, but same format is available for other geographic units).  Columns are:
Health_Board,Sex,Total_across_age,Young,Medium,Old

* Health_board is the name of the geographic unit.
* Sex is male or female.
* Total_across_age is the total population of the sex in this row across all ages
* Young is the population of the sex in this row of people 16 and under
* Mature is the population of the sex in this row from ages 17-69
* Old is the population of the sex in this row from ages 70 upwards

## sample_hb2019_pop_est_2018_row_based.csv
This file has the same data as the deprecated format above. The difference is that each age group is a new row now, so we have a single Age column now, instead of one per group.

## sample_scotHB_commute_moves_wu01.sampleCSV
This contains origin-destination flow data during peacetime for health boards in Scotland, derived from the dataset [wu01uk](https://www.nomisweb.co.uk/census/2011/wu01uk).
This is essentially a weighted edge list.
* First column is the source location label
* Second column is the destination location label
* Third column is the number of individuals undertaking that journey as reported in wu01uk

## sample_20200327_comix_social_contacts.csv
This is a possible square matrix of mixing - each column and row header is an age category. For a simplified version, look at simplified_age_infection_matrix_from_comix.csv.  It is from https://cmmid.github.io/topics/covid19/comix-impact-of-physical-distance-measures-on-transmission-in-the-UK.html, and includes all imputed contacts (both face-to-face conversation and physical contact).

## sample_20200327_comix_social_contacts_old.csv
This is a possible square matrix of mixing - each column and row header is an age category. For a simplified version, look at simplified_age_infection_matrix_from_comix.csv.  It is from https://cmmid.github.io/topics/covid19/comix-impact-of-physical-distance-measures-on-transmission-in-the-UK.html, and includes all imputed contacts (both face-to-face conversation and physical contact). This file is an older version of `sample_20200327_comix_social_contacts.csv` retained only for testing.

## simplified_age_infection_matrix_from_comix.csv
This is a sample *simplified* square matrix describing age mixing between aggregated age categories, generated from sample_20200327_comix_social_contacts.csv by summing over the columns that need to be aggregated, and then summing (weighted by the approximate population in each category) over the rows that need to be aggregated.  This includes both face-to-face and physical contacts, and is not yet down-weighted to approximate infection probability.  
Age proportion estimated from https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/articles/overviewoftheukpopulation/august2019.


## movement_multipliers.csv

This table has two columns: Time and Movement Multiplier. For instance, if the file looks like this:

```
Time,Movement_Multiplier
0,1.0
3,0.7
10,0.9
```

it means we ought to use full network movements at times 0, 1, 2, then 70% volume network movements at times 3-9, then 90% from then on.
