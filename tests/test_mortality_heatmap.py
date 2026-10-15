"""Accuracy and export checks for the mortality/marginal heatmap."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from plot_mortality_heatmap import make_mortality_matrix, save_mortality_heatmap


class MortalityMatrixTests(unittest.TestCase):
    def test_marginal_rates_are_weighted_by_visits(self):
        # A 10% tile with n=10 and a 100% tile with n=1 cannot average to 55%.
        frame = pd.DataFrame(
            [dict(Severity_Level=1, Treatment_Delay_Minutes=10, Mortality_Flag=1)]
            + [dict(Severity_Level=1, Treatment_Delay_Minutes=10, Mortality_Flag=0)] * 9
            + [dict(Severity_Level=1, Treatment_Delay_Minutes=160, Mortality_Flag=1)]
            + [dict(Severity_Level=2, Treatment_Delay_Minutes=40, Mortality_Flag=0)]
        )
        matrix = make_mortality_matrix(frame)
        self.assertEqual(matrix.total_visits, 12)
        self.assertEqual(matrix.total_deaths, 2)
        self.assertEqual(matrix.visits.loc["≥ 160", 1], 1)
        self.assertEqual(matrix.visits.loc["40–<80", 2], 1)
        self.assertAlmostEqual(matrix.percentages.loc["< 40", 1], 10.0)
        self.assertAlmostEqual(matrix.percentages.loc["≥ 160", 1], 100.0)
        self.assertAlmostEqual(matrix.severity_percentages.loc[1], 200 / 11)
        self.assertAlmostEqual(matrix.delay_percentages.loc["< 40"], 10.0)
        self.assertTrue(np.isnan(matrix.percentages.loc["80–<120", 1]))

    def test_rejects_invalid_flag_and_delay_edges(self):
        frame = pd.DataFrame({
            "Severity_Level": [1], "Treatment_Delay_Minutes": [80], "Mortality_Flag": [2]
        })
        with self.assertRaisesRegex(ValueError, "0 or 1"):
            make_mortality_matrix(frame)
        frame["Mortality_Flag"] = 1
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            make_mortality_matrix(frame, delay_edges=(40, 40))

    def test_saves_png_svg_and_pdf(self):
        frame = pd.DataFrame({
            "Severity_Level": [1, 1, 2, 2, 3, 4, 5, 5],
            "Treatment_Delay_Minutes": [20, 40, 80, 120, 160, 39, 41, 200],
            "Mortality_Flag": [0, 1, 0, 0, 1, 0, 1, 0],
        })
        with tempfile.TemporaryDirectory() as tempdir:
            output = Path(tempdir) / "nested" / "heatmap.png"
            paths = save_mortality_heatmap(make_mortality_matrix(frame), output, dpi=80)
            self.assertEqual({p.suffix for p in paths}, {".png", ".svg", ".pdf"})
            self.assertTrue(all(p.exists() and p.stat().st_size > 500 for p in paths))


if __name__ == "__main__":
    unittest.main()
