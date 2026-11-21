"""POST-SUBMISSION EXPLORATORY ANALYSES (revision kit, 20 Nov 2026), part 2: summaries of code/revision_explore.py
(run on titan) plus a fixed-effects regression on out/panel.csv. Not pre-specified; nothing here changes a reported number.
Run from the repository root: python code/revision_analyze.py [dir with bills_revision.csv etc.; default out_revision/raw]  ->  out_revision/revision.json
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

RD = sys.argv[1] if len(sys.argv) > 1 else "out_revision/raw"


def R(name):
    """a raw output from titan, plain or gzipped (out_revision/raw keeps them gzipped)"""
    p = os.path.join(RD, name)
    return p if os.path.exists(p) else p + ".gz"

OUTD = "out_revision"
os.makedirs(OUTD, exist_ok=True)
MIN_GAIN = 0.005
REAL = ["F1", "F2", "F3", "F4", "F5"]
O = {}


def summary(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    t = stats.ttest_1samp(x, 0)
    half = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return dict(n=int(len(x)), mean=float(x.mean()), ci=[float(x.mean() - half), float(x.mean() + half)], p=float(t.pvalue),
                share_pos=float((x > 0).mean()))


base = pd.read_csv("out/bills_base.csv")
rev = pd.read_csv(R("bills_revision.csv"))
hind = pd.read_csv(R("hindsight.csv"))
pkw = pd.read_csv(R("pkw.csv")).set_index("building")
accb = pd.read_csv("out/accuracy.csv.gz")
accr = pd.read_csv(R("accuracy_revision.csv"))
O["f5_refit_max_rel_diff"] = float(pkw.f5_refit_maxabs_rel.max())

# reproduction check: daily perfect information and no battery equal the submitted run
B1 = base[base.tariff == "T1"].pivot_table(index=["building", "month"], columns="policy", values="bill")
R1 = rev.pivot_table(index=["building", "month"], columns="policy", values="bill")
O["check_max_abs_diff_PI"] = float((B1["PI"] - R1["PI"]).abs().max())
O["check_max_abs_diff_none"] = float((B1["none"] - R1["none"]).abs().max())
O["check_max_abs_diff_F5_vs_Q90"] = float((B1["F5"] - R1["Q90"]).abs().max())
O["check_max_abs_diff_GF5_vs_GQ90"] = float((B1["G_F5"] - R1["G_Q90"]).abs().max())
O["lp_failures"] = int(rev.groupby("building").lp_fail_building.first().sum())

# ---------------------------------------------------------------- R1 hindsight (non-myopic perfect information)
H = hind.pivot_table(index=["building", "tariff", "month"], values="bill_hindsight")["bill_hindsight"]
O["hindsight_failures"] = int((hind.ok == 0).sum())
BB = base.pivot_table(index=["building", "tariff", "month"], columns="policy", values="bill")
r1 = {}
for tf in ("T1", "T2"):
    b = BB.xs(tf, level="tariff")
    h = H.xs(tf, level="tariff").reindex(b.index)
    gain_h = b["none"] - h
    ann = b.groupby(level="building").sum()
    annh = h.groupby(level="building").sum()
    share_pi = (ann["none"] - ann["PI"]) / (ann["none"] - annh)
    pct_h = 100 * (ann["none"] - annh) / ann["none"]
    r1[tf] = dict(daily_PI_share_of_hindsight_saving_median=float(share_pi.median()),
                  daily_PI_share_q25=float(share_pi.quantile(0.25)), daily_PI_share_q75=float(share_pi.quantile(0.75)),
                  hindsight_saving_pct_of_bill_median=float(pct_h.median()),
                  daily_PI_saving_pct_of_bill_median=float((100 * (ann["none"] - ann["PI"]) / ann["none"]).median()),
                  hindsight_never_worse_than_daily_PI=bool(((b["PI"] - h) >= -1e-6 * b["none"]).all()),
                  months_hindsight_gain_below_0_5pct=int((gain_h < MIN_GAIN * b["none"]).sum()))
    if tf == "T1":
        pols = ["reactive"] + REAL + ["G_" + m for m in REAL] + ["S_scale", "S_under", "S_noise", "S_ar1", "S_shift"]
        r1[tf]["annual_share_of_hindsight_median"] = {p: float(((ann["none"] - ann[p]) / (ann["none"] - annh)).median())
                                                      for p in pols}
O["R1_hindsight"] = r1


# ---------------------------------------------------------------- shares, H1-style tau
def month_shares(bills, policies):
    gain = bills["none"] - bills["PI"]
    ok = gain >= MIN_GAIN * bills["none"]
    S = pd.DataFrame({p: (bills["none"] - bills[p]) / gain for p in policies})[ok]
    return S


def tau_h1(S, acc, models, prefix="", metric="mae"):
    """mean over buildings of the per-building mean over months of Kendall tau(-metric, share) across models"""
    s = S[[prefix + m for m in models]].copy()
    s.columns = models
    s = s.stack().rename("share").reset_index().rename(columns={"policy": "model", "level_2": "model"})
    a = acc[acc.model.isin(models)][["building", "month", "model", metric]]
    m = s.merge(a, on=["building", "month", "model"])
    taus = m.groupby(["building", "month"]).apply(lambda g: stats.kendalltau(-g[metric], g["share"]).statistic,
                                                  include_groups=False)
    return summary(taus.groupby(level="building").mean().dropna())


def annual(bills, policies):
    ann = bills.groupby(level="building").sum()
    sh = {p: (ann["none"] - ann[p]) / (ann["none"] - ann["PI"]) for p in policies}
    return {p: dict(median=float(sh[p].median()), q25=float(sh[p].quantile(0.25)), q75=float(sh[p].quantile(0.75)),
                    share_buildings_bill_up=float((ann[p] > ann["none"]).mean()),
                    pct_of_bill_median=float((100 * (ann["none"] - ann[p]) / ann["none"]).median()),
                    usd_per_kw_yr_median=float(((ann["none"] - ann[p]) / pkw.P_kw.reindex(ann.index)).median()))
            for p in policies}


acc_all = pd.concat([accb[["building", "month", "model", "mae", "rmse", "pinball09", "under"]],
                     accr[["building", "month", "model", "mae", "rmse", "pinball09", "under"]]], ignore_index=True)
ALLB = R1.join(B1[[c for c in B1.columns if c not in R1.columns]])

# reproduce the paper's H1 (v2, open loop) as a check of this code
S0 = month_shares(ALLB, REAL)
O["check_H1_open_reproduced"] = tau_h1(S0, acc_all, REAL)

# ---------------------------------------------------------------- R2 headroom
r2 = {}
for mm in ("H05", "H10"):
    pol_o = [f"{mm}_{f}" for f in REAL]
    pol_g = ["G_" + p for p in pol_o]
    S = month_shares(ALLB, pol_o + pol_g)
    So = S[pol_o].copy(); So.columns = REAL
    Sg = S[pol_g].copy(); Sg.columns = REAL
    r2[mm] = dict(H1_open=tau_h1(So, acc_all, REAL), H1_guarded=tau_h1(Sg, acc_all, REAL),
                  H1_open_pinball=tau_h1(So, acc_all, REAL, metric="pinball09"),
                  H1_open_F1toF4=tau_h1(So, acc_all, REAL[:4]),
                  annual=annual(ALLB, pol_o + pol_g))
O["R2_headroom"] = r2
O["R2_base_for_comparison"] = dict(annual=annual(ALLB, REAL + ["G_" + m for m in REAL] + ["reactive"]))

# ---------------------------------------------------------------- R3 quantile sweep
Q = ["Q50", "Q70", "Q80", "Q90", "Q95"]
NINE = ["F1", "F2", "F3", "F4"] + Q  # Q90 is F5 refitted (identical forecasts)
S = month_shares(ALLB, NINE + ["G_" + m for m in NINE])
So = S[NINE]
Sg = S[["G_" + m for m in NINE]].copy(); Sg.columns = NINE
rk = acc_all[acc_all.model.isin(NINE)].pivot_table(index=["building", "month"], columns="model", values="mae").rank(axis=1)
relb = accr.groupby("model").rel_bias.median()
r3 = dict(H1_nine_open=tau_h1(So, acc_all, NINE), H1_nine_guarded=tau_h1(Sg, acc_all, NINE),
          H1_nine_open_pinball=tau_h1(So, acc_all, NINE, metric="pinball09"),
          H1_nine_open_under=tau_h1(So, acc_all, NINE, metric="under"),
          H1_quantiles_only_open=tau_h1(So, acc_all, Q), H1_quantiles_only_guarded=tau_h1(Sg, acc_all, Q),
          mean_mae_rank_of_nine={m: float(rk[m].mean()) for m in NINE},
          median_monthly_rel_bias={m: float(relb[m]) for m in Q},
          median_monthly_mae_kwh={m: float(acc_all[acc_all.model == m].mae.median()) for m in NINE},
          annual=annual(ALLB, NINE + ["G_" + m for m in NINE]))
O["R3_quantiles"] = r3

# ---------------------------------------------------------------- R6 foundation-model forecaster (Chronos-Bolt)
ft = R("bills_tsfm.csv")
if os.path.exists(ft):
    BT = pd.read_csv(ft).pivot_table(index=["building", "month"], columns="policy", values="bill")
    acct = pd.read_csv(R("accuracy_tsfm.csv"))
    O["lp_failures_tsfm"] = int(pd.read_csv(ft).groupby("building").lp_fail_building.first().sum())
    ALLT = ALLB.join(BT)
    acc7 = pd.concat([acc_all, acct[["building", "month", "model", "mae", "rmse", "pinball09", "under"]]], ignore_index=True)
    SEVEN = REAL + ["B50", "B90"]
    S7 = month_shares(ALLT, SEVEN + ["G_" + m for m in SEVEN])
    S7o = S7[SEVEN]
    S7g = S7[["G_" + m for m in SEVEN]].copy(); S7g.columns = SEVEN
    rk7 = acc7[acc7.model.isin(SEVEN)].pivot_table(index=["building", "month"], columns="model", values="mae").rank(axis=1)
    rkb = acc7[acc7.model.isin(["F4", "B50"])].pivot_table(index=["building", "month"], columns="model", values="mae")
    r6 = dict(H1_seven_open=tau_h1(S7o, acc7, SEVEN), H1_seven_guarded=tau_h1(S7g, acc7, SEVEN),
              H1_seven_open_pinball=tau_h1(S7o, acc7, SEVEN, metric="pinball09"),
              mean_mae_rank_of_seven={m: float(rk7[m].mean()) for m in SEVEN},
              B50_more_accurate_than_F4_share_of_months=float((rkb["B50"] < rkb["F4"]).mean()),
              median_monthly_rel_bias={m: float(v) for m, v in acct.groupby("model").rel_bias.median().items()},
              median_monthly_mae_kwh={m: float(acc7[acc7.model == m].mae.median()) for m in ["F4", "F5", "B50", "B90"]},
              annual=annual(ALLT, ["B50", "B90", "G_B50", "G_B90"]))
    O["R6_tsfm"] = r6

# ---------------------------------------------------------------- R5 within-building regression (out/panel.csv)
P = pd.read_csv("out/panel.csv")
P = P[P.model.isin(REAL)].copy()
r5 = {}
for col in ("share_open", "share_guarded"):
    d = P[["building", "rel_mae", "rel_bias", col]].dropna()
    dm = d.groupby("building")[["rel_mae", "rel_bias", col]].transform(lambda x: x - x.mean())
    X = dm[["rel_mae", "rel_bias"]].to_numpy() * 100  # per percentage point
    y = dm[col].to_numpy()
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    XtX_inv = np.linalg.inv(X.T @ X)
    meat = np.zeros((2, 2))
    for _, idx in d.groupby("building").indices.items():
        s = X[idx].T @ e[idx]
        meat += np.outer(s, s)
    G = d.building.nunique()
    V = XtX_inv @ meat @ XtX_inv * G / (G - 1)
    se = np.sqrt(np.diag(V))
    r5[col] = dict(beta_rel_mae_per_pp=float(beta[0]), se_rel_mae=float(se[0]), beta_rel_bias_per_pp=float(beta[1]),
                   se_rel_bias=float(se[1]), n_obs=int(len(d)), n_buildings=int(G))
O["R5_fe_regression"] = r5

json.dump(O, open(os.path.join(OUTD, "revision.json"), "w"), indent=1, default=float)
print(json.dumps(O, indent=1, default=float)[:12000])
