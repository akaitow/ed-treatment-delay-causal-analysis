import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from analysis import CONFOUNDERS, estimate_aipw, load_data, model


class AnalysisTests(unittest.TestCase):
    def test_model_uses_calibrated_probabilities(self):
        self.assertIsNone(model().get_params()["logisticregression__class_weight"])

    def test_aipw_runs(self):
        n = 200
        data = pd.DataFrame({
            "Severity_Level": np.tile([1, 2, 3, 4, 5], n // 5),
            "Dim_Patient.Age": np.arange(n) % 70 + 18,
            "Treatment_Delay_Minutes": np.where(np.arange(n) % 2, 200, 100),
            "Mortality_Flag": (np.arange(n) % 11 == 0).astype(int),
        })
        result = estimate_aipw(data)
        self.assertTrue(np.isfinite(result["risk_difference"]))
        self.assertEqual(CONFOUNDERS, ["Severity_Level", "Dim_Patient.Age"])

    def test_load_data_keeps_every_severity_level(self):
        data = pd.DataFrame({
            "Severity_Level": [1, 2, 3, 4, 5],
            "Dim_Patient.Age": [20, 30, 40, 50, 60],
            "Treatment_Delay_Minutes": [100, 200, 100, 200, 100],
            "Mortality_Flag": [0, 0, 1, 0, 1],
        })
        with TemporaryDirectory() as folder:
            path = Path(folder) / "mortality.xlsx"
            data.to_excel(path, sheet_name="model", index=False)
            _, analysis_data = load_data(path)
        self.assertEqual(analysis_data["Severity_Level"].tolist(), [1, 2, 3, 4, 5])


if __name__ == "__main__":
    unittest.main()
