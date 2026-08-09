import unittest

import numpy as np

from analysis import (
    cluster_robust_standard_error,
    effective_sample_size,
    standardized_mean_difference,
)


class AnalysisUtilityTests(unittest.TestCase):
    def test_effective_sample_size_equals_n_for_equal_weights(self):
        self.assertAlmostEqual(effective_sample_size(np.ones(8)), 8.0)

    def test_standardized_difference_is_zero_for_identical_groups(self):
        values = np.array([1.0, 2.0, 1.0, 2.0])
        treatment = np.array([1, 1, 0, 0])
        self.assertAlmostEqual(standardized_mean_difference(values, treatment), 0.0)

    def test_cluster_robust_se_is_nonnegative(self):
        influence = np.array([-0.2, 0.1, 0.3, -0.2])
        groups = np.array(["a", "a", "b", "c"])
        self.assertGreaterEqual(cluster_robust_standard_error(influence, groups), 0.0)


if __name__ == "__main__":
    unittest.main()

