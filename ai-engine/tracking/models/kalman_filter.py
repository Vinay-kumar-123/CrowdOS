from typing import Tuple
import numpy as np


class KalmanFilter:
    """
    8D Kalman Filter for bounding box tracking in 2D image space.
    State vector: [cx, cy, a, h, v_cx, v_cy, v_a, v_h]
    where (cx, cy) is box center, 'a' is aspect ratio (w/h), 'h' is height,
    and (v_cx, v_cy, v_a, v_h) are their respective velocities.
    """
    def __init__(self):
        ndim = 4
        dt = 1.0

        # Motion matrix (8x8)
        self._motion_mat = np.eye(2 * ndim, dtype=np.float32)
        for i in range(ndim):
            self._motion_mat[i, ndim + i] = dt

        # Update / Measurement matrix (4x8)
        self._update_mat = np.eye(ndim, 2 * ndim, dtype=np.float32)

        # Standard deviation weights
        self._std_weight_position = 1.0 / 20.0
        self._std_weight_velocity = 1.0 / 160.0

    def initiate(self, measurement: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create track state mean (8D) and covariance matrix (8x8) from unobserved measurement [cx, cy, a, h].
        """
        mean_pos = measurement
        mean_vel = np.zeros_like(mean_pos)
        mean = np.r_[mean_pos, mean_vel]

        std = [
            2 * self._std_weight_position * measurement[3],
            2 * self._std_weight_position * measurement[3],
            1e-2,
            2 * self._std_weight_position * measurement[3],
            10 * self._std_weight_velocity * measurement[3],
            10 * self._std_weight_velocity * measurement[3],
            1e-5,
            10 * self._std_weight_velocity * measurement[3]
        ]
        covariance = np.diag(np.square(std)).astype(np.float32)
        return mean, covariance

    def predict(self, mean: np.ndarray, covariance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run Kalman filter prediction step to update state mean and covariance.
        """
        std_pos = [
            self._std_weight_position * mean[3],
            self._std_weight_position * mean[3],
            1e-2,
            self._std_weight_position * mean[3]
        ]
        std_vel = [
            self._std_weight_velocity * mean[3],
            self._std_weight_velocity * mean[3],
            1e-5,
            self._std_weight_velocity * mean[3]
        ]
        motion_cov = np.diag(np.square(np.r_[std_pos, std_vel])).astype(np.float32)

        mean = np.dot(self._motion_mat, mean)
        covariance = np.linalg.multi_dot((self._motion_mat, covariance, self._motion_mat.T)) + motion_cov
        return mean, covariance

    def project(self, mean: np.ndarray, covariance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Project state distribution to measurement space [cx, cy, a, h].
        """
        std = [
            self._std_weight_position * mean[3],
            self._std_weight_position * mean[3],
            1e-1,
            self._std_weight_position * mean[3]
        ]
        innovation_cov = np.diag(np.square(std)).astype(np.float32)

        mean_projected = np.dot(self._update_mat, mean)
        covariance_projected = np.linalg.multi_dot((self._update_mat, covariance, self._update_mat.T)) + innovation_cov
        return mean_projected, covariance_projected

    def update(
        self,
        mean: np.ndarray,
        covariance: np.ndarray,
        measurement: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run Kalman filter update step given state mean, covariance, and observed measurement.
        """
        projected_mean, projected_cov = self.project(mean, covariance)

        chol_factor = np.linalg.cholesky(projected_cov)
        kalman_gain = np.linalg.solve(
            chol_factor.T,
            np.linalg.solve(chol_factor, np.dot(self._update_mat, covariance.T))
        ).T

        innovation = measurement - projected_mean
        new_mean = mean + np.dot(innovation, kalman_gain.T)
        new_covariance = covariance - np.linalg.multi_dot((kalman_gain, projected_cov, kalman_gain.T))

        return new_mean, new_covariance
