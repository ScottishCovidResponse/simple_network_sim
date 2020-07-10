# Movement Multipliers

Population data from: https://www.nrscotland.gov.uk/files//statistics/population-estimates/mid-18/mid-year-pop-est-18-tabs.zip

Table: mid-year-pop-est-18-tabs_Table 2.csv

Within that file, extract only data for all ages, all sexes at Area1 level (row 7-38, columns 1, 2, 3 indices starting at 1) currently done manually - stored in mid-year-pop-est-18_LA.csv

ISO region to LA best-attempt lookup table: compiled by hand, Jess Enright, 30 June 2020

Stored in file: [iso-3166-2_to_scottishLA.csv](iso-3166-2_to_scottishLA.csv).

Fetch  https://www.gstatic.com/covid19/mobility/Global_Mobility_Report.csv

run script (aggregates for Scotland by date, using transit, workplace, and retail mobility, reginos weighted by their population):

```{shell}
python -m process_iso_populations_for_google.py  mid-year-pop-est-18_LA.csv iso-3166-2_to_scottishLA.csv Global_Mobility_Report.csv
```

saves result to:
movement_multiplier.csv
