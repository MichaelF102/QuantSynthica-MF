"""Unsupervised fund segmentation, run separately within each asset tier.

Funds in different tiers differ trivially (debt vs equity), so a single global clustering would just rediscover the
tier. Clusters are computed inside a tier and labelled from measured characteristics relative to that tier.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CLUSTER_VERSION = "cluster-1.0.0"
FEATURES = ["ret_3y", "vol_3y", "sharpe_3y", "max_dd_3y", "mom_12m", "downside_capture_3y", "info_ratio_3y"]
MIN_FUNDS = 25
SEED = 0


def _prepare(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    x = df[features].dropna()
    lo, hi = x.quantile(0.02), x.quantile(0.98)
    return x.clip(lo, hi, axis=1)  # winsorise so a single outlier fund cannot define a cluster


def _label(centroids: pd.DataFrame, tier_means: pd.Series, tier_std: pd.Series) -> dict[int, str]:
    """Plain-language labels from z-scores of each centroid against the tier."""
    z = (centroids - tier_means) / tier_std.replace(0, np.nan)
    out = {}
    for k, row in z.iterrows():
        parts = []
        if "ret_3y" in row and abs(row["ret_3y"]) >= 0.4:
            parts.append("high return" if row["ret_3y"] > 0 else "low return")
        if "vol_3y" in row and abs(row["vol_3y"]) >= 0.4:
            parts.append("high volatility" if row["vol_3y"] > 0 else "low volatility")
        if "max_dd_3y" in row and row["max_dd_3y"] <= -0.6:
            parts.append("deep drawdowns")
        if "mom_12m" in row and abs(row["mom_12m"]) >= 0.6:
            parts.append("strong momentum" if row["mom_12m"] > 0 else "weak momentum")
        out[int(k)] = ", ".join(parts[:3]) or "near tier average"
    return out


def _summ(name: str, X: np.ndarray, labels: np.ndarray, codes: list[str], feats: list[str], raw: pd.DataFrame) -> dict:
    from sklearn.metrics import silhouette_score

    uniq = sorted(set(labels) - {-1})
    sil = float(silhouette_score(X, labels)) if len(uniq) >= 2 and len(set(labels)) < len(labels) else None
    df = raw.loc[codes].assign(cluster=labels)
    cents = df[df.cluster >= 0].groupby("cluster")[feats].mean()
    names = _label(cents, raw[feats].mean(), raw[feats].std())
    sizes = df.cluster.value_counts().sort_index()
    return {
        "method": name, "clusters": len(uniq), "silhouette": sil, "noise_points": int((labels == -1).sum()),
        "sizes": {str(k): int(v) for k, v in sizes.items()},
        "centroids": [{"cluster": int(k), "label": names.get(int(k)), "size": int(sizes.get(k, 0)), **{f: float(v) for f, v in r.items()}}
                      for k, r in cents.iterrows()],
        "assignments": {c: int(l) for c, l in zip(codes, labels)},
    }


def cluster_tier(df: pd.DataFrame, features: list[str] = FEATURES) -> dict:
    # scikit-learn is imported here, not at module level: it adds ~100 MB to a process that never clusters (a small hosted API)
    from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
    from sklearn.decomposition import PCA
    from sklearn.mixture import GaussianMixture
    from sklearn.neighbors import NearestNeighbors
    from sklearn.preprocessing import StandardScaler

    x = _prepare(df, features)
    if len(x) < MIN_FUNDS:
        return {"available": False, "reason": f"fewer than {MIN_FUNDS} funds with all features", "funds": len(x)}
    X = StandardScaler().fit_transform(x)
    codes = list(x.index)
    pca = PCA(n_components=2, random_state=SEED).fit(X)
    pts = pca.transform(X)

    from sklearn.metrics import silhouette_score

    best_k, best_s = 2, -1.0
    for k in range(2, 7):
        lab = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit_predict(X)
        s = silhouette_score(X, lab)
        if s > best_s:
            best_k, best_s = k, s
    km = KMeans(n_clusters=best_k, n_init=10, random_state=SEED).fit_predict(X)
    hc = AgglomerativeClustering(n_clusters=best_k, linkage="ward").fit_predict(X)
    bics = {k: GaussianMixture(k, covariance_type="full", random_state=SEED, n_init=3).fit(X).bic(X) for k in range(2, 6)}
    kg = min(bics, key=bics.get)
    gm = GaussianMixture(kg, covariance_type="full", random_state=SEED, n_init=3).fit(X).predict(X)
    nn = NearestNeighbors(n_neighbors=5).fit(X)
    dist = np.sort(nn.kneighbors(X)[0][:, -1])
    eps = float(np.percentile(dist, 90))
    db = DBSCAN(eps=eps, min_samples=5).fit_predict(X)

    return {
        "available": True, "version": CLUSTER_VERSION, "funds": len(codes), "features": features,
        "pca": {"explained_variance": [float(v) for v in pca.explained_variance_ratio_],
                "loadings": {f: [float(pca.components_[0][i]), float(pca.components_[1][i])] for i, f in enumerate(features)},
                "points": {c: [float(p[0]), float(p[1])] for c, p in zip(codes, pts)}},
        "methods": [
            _summ("kmeans", X, km, codes, features, x), _summ("hierarchical", X, hc, codes, features, x),
            _summ("gmm", X, gm, codes, features, x), _summ("dbscan", X, db, codes, features, x),
        ],
        "notes": [f"K-Means and hierarchical use k={best_k} (best silhouette in 2-6); the mixture uses k={kg} (lowest BIC in 2-5).",
                  f"DBSCAN eps={eps:.2f} (90th percentile of 5th-neighbour distance); -1 marks outliers.",
                  "Features are winsorised at the 2nd and 98th percentile and standardised within the tier.",
                  "Cluster labels describe measured traits relative to the tier; they are not investment categories."],
    }
