import os
import tempfile

from glob import glob
from pathlib import Path

import pandas as pd

from simple_network_sim import sampleUseOfModel
from tests.utils import create_baseline


def test_run_seeded(initial_infection):
    with tempfile.TemporaryDirectory() as dirname:
        sampleUseOfModel.main(
            ["seeded", str(initial_infection), str(Path(dirname) / "test")]
        )

        files = glob(os.path.join(dirname, "test*"))
        assert len(files) == 2
        assert len([f for f in files if f.endswith(".pdf")]) == 1
        assert len([f for f in files if f.endswith(".csv")]) == 1

        test_data = [f for f in files if f.endswith(".csv")][0]
        baseline = create_baseline(test_data)

        test_df = pd.read_csv(test_data)
        baseline_df = pd.read_csv(baseline)

        pd.testing.assert_frame_equal(test_df, baseline_df)
