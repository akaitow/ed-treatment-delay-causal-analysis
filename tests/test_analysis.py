import unittest

import numpy as np
import pandas as pd

from analysis import CONFOUNDERS, estimate_aipw, model


class AnalysisTests(unittest.TestCase):
    def test_model_uses_calibrated_probabilities(self):
        self.assertIsNone(model().get_params()["logisticregression__class_weight"])

    def test_aipw_runs(self):
        n = 200
        data = pd.DataFrame({
            "Severity_Level": np.tile([1, 2, 3, 2], n // 4),
            "Dim_Patient.Age": np.arange(n) % 70 + 18,
            "Treatment_Delay_Minutes": np.where(np.arange(n) % 2, 200, 100),
            "Mortality_Flag": (np.arange(n) % 11 == 0).astype(int),
        })
        result = estimate_aipw(data)
        self.assertTrue(np.isfinite(result["risk_difference"]))
        self.assertEqual(CONFOUNDERS, ["Severity_Level", "Dim_Patient.Age"])


if __name__ == "__main__":
    unittest.main()
