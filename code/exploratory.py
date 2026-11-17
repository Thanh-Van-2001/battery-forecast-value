"""Exploratory, labelled as such in the paper: (1) how often the most accurate forecaster is also the most valuable
in a building-month; (2) forecast bias versus captured share; (3) a compact per building x forecaster table for figures.
Run: python exploratory.py <data_dir> <results_dir>  ->  <results_dir>/exploratory.json, panel.csv
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

D, R = sys.argv[1], sys.argv[2]
Z = np.load(os.path.join(D, "prep.npz"), allow_pickle=True)
FZ = np.load(os.path.join(D, "forecasts.npz"), allow_pickle=True)
F, MODELS, TE = FZ["F"], list(FZ["models"]), FZ["te"]
NB = F.shape[1]
YT = Z["load"][TE][:, :NB].T.astype(np.float64)
REAL = ["F1", "F2", "F3", "F4", "F5"]
month = Z["hours"].astype("datetime64[h]").astype("datetime64[M]").astype(int)[TE]

B = pd.read_csv(os.path.join(R, "bills_base.csv"))
P = B.pivot_table(index=["building", "tariff", "month"], columns="policy", values="bill")
gain = P["none"] - P["PI"]
ok = gain >= 0.005 * P["none"]
P = P[ok]
gain = gain[ok]
OUT = {}
acc = pd.read_csv(os.path.join(R, "accuracy.csv.gz"))
for ctl, pre in (("open", ""), ("guarded", "G_")):
    S = pd.DataFrame({m: (P["none"] - P[pre + m]) / gain for m in REAL}).xs("T1", level="tariff")
    a = acc[acc.model.isin(REAL)].pivot_table(index=["building", "month"], columns="model", values="mae")
    a = a.loc[S.index]
    best_acc = a.eq(a.min(axis=1), axis=0)          # ties counted as matches (amendment 3)
    best_val = S.eq(S.max(axis=1), axis=0)
    same = (best_acc & best_val).any(axis=1).mean()
    pa = best_acc.div(best_acc.sum(axis=1), axis=0).mean()  # marginal frequencies
    pv_ = best_val.div(best_val.sum(axis=1), axis=0).mean()
    OUT[f"most_accurate_is_most_valuable_{ctl}"] = float(same)
    OUT[f"independence_baseline_{ctl}"] = float((pa * pv_).sum())
    OUT[f"most_valuable_share_{ctl}"] = {m: float(v) for m, v in pv_.items()}
OUT["most_accurate_share"] = {m: float(v) for m, v in pa.items()}
OUT["shift_kappa"] = dict(zip(["median", "q25", "q75"], np.percentile(FZ["shift_kappa"], [50, 25, 75]).round(3).tolist())) \
    if "shift_kappa" in FZ.files else None
# annual bias (mean error / mean load) and annual captured share per building x forecaster
ann = B[B.tariff == "T1"].pivot_table(index=["building", "month"], columns="policy", values="bill")
ann = ann.loc[ok.xs("T1", level="tariff")[ok.xs("T1", level="tariff")].index].groupby(level="building").sum()
rows = []
for i, m in enumerate(MODELS):
    bias = (F[i].astype(np.float64) - YT).mean(1) / YT.mean(1)
    mae = np.abs(F[i].astype(np.float64) - YT).mean(1) / YT.mean(1)
    for b in ann.index:
        den = ann.loc[b, "none"] - ann.loc[b, "PI"]
        rows.append(dict(building=b, model=m, rel_bias=bias[b], rel_mae=mae[b],
                         share_open=(ann.loc[b, "none"] - ann.loc[b, m]) / den,
                         share_guarded=(ann.loc[b, "none"] - ann.loc[b, "G_" + m]) / den,
                         share_reactive=(ann.loc[b, "none"] - ann.loc[b, "reactive"]) / den))
panel = pd.DataFrame(rows)
panel.to_csv(os.path.join(R, "panel.csv"), index=False)
real = panel[panel.model.isin(REAL)]
for ctl in ("open", "guarded"):
    # within-building rank correlations across the five forecasters, averaged over buildings (amendment 3)
    wb = real.groupby("building").apply(lambda g: pd.Series({
        "bias": stats.spearmanr(g.rel_bias, g[f"share_{ctl}"]).statistic,
        "mae": stats.spearmanr(-g.rel_mae, g[f"share_{ctl}"]).statistic}), include_groups=False)
    OUT[f"within_spearman_bias_share_{ctl}"] = float(wb["bias"].mean())
    OUT[f"within_spearman_mae_share_{ctl}"] = float(wb["mae"].mean())
    OUT[f"spearman_bias_share_{ctl}"] = float(stats.spearmanr(real.rel_bias, real[f"share_{ctl}"]).statistic)
    OUT[f"spearman_mae_share_{ctl}"] = float(stats.spearmanr(-real.rel_mae, real[f"share_{ctl}"]).statistic)
# money (amendment 3): annual saving as % of the no-battery bill and in $ per kW of battery power per year
LOADALL = Z["load"][:, :NB].astype(np.float64)
TRm = Z["hours"].astype("datetime64[h]").astype("datetime64[Y]").astype(int) + 1970 == 2016
Pkw = 0.10 * LOADALL[TRm].max(0)
money = {}
for tf in ("T1", "T2"):
    bb = B[B.tariff == tf].pivot_table(index=["building", "month"], columns="policy", values="bill").groupby(level="building").sum()
    for pol in ["PI", "reactive", "F4", "F5", "G_F4", "G_F5"]:
        pct = 100 * (bb["none"] - bb[pol]) / bb["none"]
        kw = (bb["none"] - bb[pol]) / Pkw[bb.index]
        money[f"{tf}_{pol}"] = dict(pct_median=float(pct.median()), usd_per_kw_yr_median=float(kw.median()))
    money[f"{tf}_bill_none_median_usd"] = float(bb["none"].median())
OUT["money"] = money
OUT["median_rel_bias"] = real.groupby("model").rel_bias.median().round(4).to_dict()
OUT["median_rel_mae"] = panel.groupby("model").rel_mae.median().round(4).to_dict()
json.dump(OUT, open(os.path.join(R, "exploratory.json"), "w"), indent=1)
print(json.dumps(OUT, indent=1))
