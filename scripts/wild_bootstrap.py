"""Wild cluster bootstrap p-value for the difference-in-differences term.

With few clusters (43 states here), state-clustered standard errors can be too small.
The wild cluster bootstrap imposes the null (no effect), then for each replication
flips the sign of the restricted residuals by state, using one random +1/-1 draw per
state, and re-estimates. The p-value is how often the bootstrap |t| exceeds the
observed |t|.

Uses Rademacher weights (+1/-1). With very few clusters, Webb six-point weights are
the usual alternative; 43 states is enough for Rademacher.

The t-statistic uses the same small-sample correction as statsmodels' cluster option,
(G/(G-1)) * ((N-1)/(N-K)) applied to the covariance. The correction is constant across
replications, so it rescales every t* and t_obs by the same factor and leaves the
bootstrap p-value unchanged; it is applied so the printed t matches statsmodels.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

import event_study as es

B = 9999
SEED = 20261110
TERM = "treated_x_post"


def wls_cluster(X: np.ndarray, y: np.ndarray, w: np.ndarray, codes: np.ndarray, n_groups: int):
    """WLS with a cluster-robust covariance, small-sample corrected as in statsmodels."""
    n, k = X.shape
    sw = np.sqrt(w)
    Xw = X * sw[:, None]
    beta, *_ = np.linalg.lstsq(Xw, y * sw, rcond=None)
    resid = y - X @ beta
    bread = np.linalg.inv(Xw.T @ Xw)
    scores = np.zeros((n_groups, k))
    np.add.at(scores, codes, X * (w * resid)[:, None])
    meat = scores.T @ scores
    correction = (n_groups / (n_groups - 1)) * ((n - 1) / (n - k))
    V = correction * (bread @ meat @ bread)
    return beta, V, resid


def main() -> None:
    rates = pd.read_csv(es.RATES)
    panel = es.build_panel(rates)
    panel["post"] = (panel["year"] >= es.EXPANSION_YEAR).astype(float)

    X_df = es.design_matrix(panel, event_study=False)
    X = X_df.to_numpy(dtype=float)
    y = panel["uninsured_rate"].to_numpy(dtype=float)
    w = panel["pop_sample"].to_numpy(dtype=float)
    codes_raw = panel["state"].astype("category").cat.codes.to_numpy()
    n_groups = int(codes_raw.max()) + 1
    j = list(X_df.columns).index(TERM)

    beta, V, _ = wls_cluster(X, y, w, codes_raw, n_groups)
    t_obs = beta[j] / np.sqrt(V[j, j])

    keep = [k for k in range(X.shape[1]) if k != j]
    _, _, resid_r = wls_cluster(X[:, keep], y, w, codes_raw, n_groups)
    fitted_r = y - resid_r

    rng = np.random.default_rng(SEED)
    t_star = np.empty(B)
    for b in range(B):
        signs = rng.choice([-1.0, 1.0], size=n_groups)
        y_star = fitted_r + resid_r * signs[codes_raw]
        beta_b, V_b, _ = wls_cluster(X, y_star, w, codes_raw, n_groups)
        t_star[b] = beta_b[j] / np.sqrt(V_b[j, j])

    p_boot = (np.sum(np.abs(t_star) >= abs(t_obs)) + 1) / (B + 1)
    p_asym = 2 * (1 - stats.norm.cdf(abs(t_obs)))
    print(f"DiD estimate: {beta[j]:.4f}")
    print(f"cluster-robust t (small-sample corrected): {t_obs:.3f}")
    print(f"wild cluster bootstrap p-value: {p_boot:.4f}  (B = {B}, {n_groups} states)")
    print(f"asymptotic normal p-value:      {p_asym:.4f}")


if __name__ == "__main__":
    main()
