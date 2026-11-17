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
    same = (a.idxmin(axis=1) == S.idxmax(axis=1)).mean()
    OUT[f"most_accurate_is_most_valuable_{ctl}"] = float(same)
OUT["chance"] = 0.2
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
    OUT[f"spearman_bias_share_{ctl}"] = float(stats.spearmanr(real.rel_bias, real[f"share_{ctl}"]).statistic)
    OUT[f"spearman_mae_share_{ctl}"] = float(stats.spearmanr(-real.rel_mae, real[f"share_{ctl}"]).statistic)
OUT["median_rel_bias"] = real.groupby("model").rel_bias.median().round(4).to_dict()
OUT["median_rel_mae"] = panel.groupby("model").rel_mae.median().round(4).to_dict()
json.dump(OUT, open(os.path.join(R, "exploratory.json"), "w"), indent=1)
print(json.dumps(OUT, indent=1))
