from pathlib import Path
import pandas as pd
import urllib.request
from data_pipeline_api.data_processing_api import DataProcessingAPI

config_filename = Path(__file__).parent / "data_processing_config.yaml"
uri = "data_processing_uri"
git_sha = "data_processing_git_sha"
with DataProcessingAPI(config_filename, uri=uri, git_sha=git_sha) as api:

    # The lookup table file below is available externally from
    # https://www2.gov.scot/Resource/0046/00462936.csv
    upward = "00462936.csv"
    # The commutes file below is available from  http://wicid.ukdataservice.ac.uk/ to academics and local
    # government after making an account and agreeing to a EULA for access to safeguarded data
    flows = "wu03buk_oa_wz_v4.csv"

    with api.read_external_object(upward) as file:
        dfUp = pd.read_csv(file)

    dfUp = dfUp[["OutputArea", "DataZone", "InterZone"]]
    dfUp = dfUp.set_index("OutputArea")

    with api.read_external_object(flows) as file:
        dfMoves = pd.read_csv(
            file,
            names=[
                "sourceOA",
                "destOA",
                "total",
                "breakdown1",
                "breakdown2",
                "breakdown3",
            ],
        )

    withSourceDZ = dfMoves.merge(
        dfUp, how="inner", left_on="sourceOA", right_index=True
    )
    withBothDZ = withSourceDZ.merge(
        dfUp, how="inner", left_on="destOA", right_index=True
    )

    withBothIZ = withBothDZ[["InterZone_x", "InterZone_y", "total"]]
    withBothIZ.columns = ["source_IZ", "dest_IZ", "weight"]
    withBothIZ = withBothIZ.groupby(["source_IZ", "dest_IZ"]).sum()
    withBothIZ = withBothIZ.reset_index()

    withBothDZ = withBothDZ[["DataZone_x", "DataZone_y", "total"]]
    withBothDZ.columns = ["source_DZ", "dest_DZ", "weight"]

    withBothDZ = withBothDZ.groupby(["source_DZ", "dest_DZ"]).sum()
    withBothDZ = withBothDZ.reset_index()

    api.write_table(
        "generated_sns_products/wu03buk_oa_wz_v4_scottish_datazones",
        "wu03buk_oa_wz_v4_scottish_datazones",
        withBothDZ,
    )
    api.write_table(
        "generated_sns_products/wu03buk_oa_wz_v4_scottish_interzones",
        "wu03buk_oa_wz_v4_scottish_interzones",
        withBothIZ,
    )
