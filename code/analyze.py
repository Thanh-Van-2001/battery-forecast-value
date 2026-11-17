"""Pre-registered analysis (PLAN.md). Run: python analyze.py <data_dir> <results_dir>
Reads bills_base.csv (+ robustness files if present) and forecasts; writes results.json and prints tables.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

D, R = sys.argv[1], sys.argv[2]
Z = np.load(os.path.join(D, "prep.npz"), allow_pickle=True)
LOAD, HRS, USE = Z["load"].astype(np.float64), Z["hours"], Z["use"]
FZ = np.load(os.path.join(D, "forecasts.npz"), allow_pickle=True)
F, MODELS, TE = FZ["F"], list(FZ["models"]), FZ["te"]
NBF = F.shape[1]
LOAD = LOAD[:, :NBF]
USE = USE[:NBF]
REAL = ["F1", "F2", "F3", "F4", "F5"]
month = HRS.astype("datetime64[h]").astype("datetime64[M]").astype(int)[TE]
YT = LOAD[TE].T  # building x hour
NB = YT.shape[0]
MIN_GAIN = 0.005  # building-months where perfect information saves < 0.5% of the no-battery bill are excluded

# ---------------------------------------------------------------- accuracy metrics per model x building x month
days = np.arange(len(TE)) // 24
acc = []
for i, m in enumerate(MODELS):
    e = F[i] - YT
    for mo in np.unique(month):
        k = month == mo
        y, f = YT[:, k], F[i][:, k]
        ndays = k.sum() // 24
        yd, fd = y.reshape(NB, ndays, 24), f.reshape(NB, ndays, 24)
        pk_hour = yd.argmax(2)
        err_at_peak = np.abs(np.take_along_axis(fd - yd, pk_hour[..., None], 2)[..., 0]).mean(1)
        under = np.maximum(y - f, 0).mean(1)  # amendment 3 positive controls: under-forecast error, pinball(0.9)
        pin = np.where(y >= f, 0.9 * (y - f), 0.1 * (f - y)).mean(1)
        acc.append(pd.DataFrame(dict(model=m, month=mo, building=np.arange(NB), under=under, pinball09=pin,
                                     mae=np.abs(e[:, k]).mean(1), rmse=np.sqrt((e[:, k] ** 2).mean(1)),
                                     mape=np.nanmean(np.abs(e[:, k]) / np.where(y > 0, y, np.nan), 1),
                                     peak_hour_err=err_at_peak,
                                     peak_mag_err=np.abs(fd.max(2) - yd.max(2)).mean(1),
                                     peak_time_err=np.abs(fd.argmax(2) - pk_hour).mean(1))))
ACC = pd.concat(acc, ignore_index=True)


def shares(path):
    B = pd.read_csv(path)
    P = B.pivot_table(index=["building", "tariff", "month"], columns="policy", values="bill")
    gain = P["none"] - P["PI"]
    ok = gain >= MIN_GAIN * P["none"]
    pols = ["reactive"] + [c for c in P.columns if c in MODELS or c.startswith("G_")]
    S = {"PI": (P["none"] - P["PI"]) / gain}
    for pol in pols:
        S[pol] = (P["none"] - P[pol]) / gain
    S = pd.DataFrame(S)[ok]
    ann = P[ok].groupby(level=["building", "tariff"]).sum()
    A = pd.DataFrame({pol: (ann["none"] - ann[pol]) / (ann["none"] - ann["PI"]) for pol in pols})
    return S.reset_index(), A.reset_index(), int((~ok).sum()), int(len(ok))


def excl_by_tariff(path):
    B = pd.read_csv(path)
    P = B.pivot_table(index=["building", "tariff", "month"], columns="policy", values="bill")
    bad = (P["none"] - P["PI"]) < MIN_GAIN * P["none"]
    return bad.groupby(level="tariff").sum()


def h1(S, tariff, metric="mae", prefix="", models=None, months=None):
    """mean over months of Kendall tau(-metric, captured share) across F1-F5, per building
    (prefix "G_" = guarded execution of the same forecasts, amendment 2; models/months = subsets, amendment 3)"""
    models = models or REAL
    S = S if months is None else S[S.month.isin(months)]
    s = S[S.tariff == tariff].melt(id_vars=["building", "tariff", "month"], value_vars=[prefix + r for r in models],
                                   var_name="model", value_name="share")
    s["model"] = s.model.str.replace(prefix, "", regex=False) if prefix else s.model
    m = s.merge(ACC[ACC.model.isin(models)], on=["model", "month", "building"])
    taus = m.groupby(["building", "month"]).apply(lambda g: stats.kendalltau(-g[metric], g["share"]).statistic, include_groups=False)
    return taus.groupby(level="building").mean().dropna()


def rho_metric(S, tariff, metric):
    s = S[S.tariff == tariff].melt(id_vars=["building", "tariff", "month"], value_vars=REAL, var_name="model", value_name="share")
    m = s.merge(ACC[ACC.model.isin(REAL)], on=["model", "month", "building"])
    return m.groupby("building").apply(lambda g: stats.spearmanr(-g[metric], g["share"]).statistic, include_groups=False).dropna()


def summary(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    t = stats.ttest_1samp(x, 0)
    sign = stats.binomtest(int((x > 0).sum()), int((x != 0).sum()), 0.5)
    half = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return dict(n=len(x), mean=float(x.mean()), median=float(np.median(x)), share_pos=float((x > 0).mean()),
                t=float(t.statistic), p=float(t.pvalue), p_sign=float(sign.pvalue),
                ci_lo=float(x.mean() - half), ci_hi=float(x.mean() + half))


OUT = {}
for path in sorted(glob.glob(os.path.join(R, "bills_*.csv"))):
    tag = os.path.basename(path)[6:-4]
    S, A, nex, ntot = shares(path)
    res = {"excluded_building_months": nex, "building_months": ntot,
           "excluded_by_tariff": {tf: int(v) for tf, v in excl_by_tariff(path).items()}}
    t1, t2 = h1(S, "T1"), h1(S, "T2")
    res["H1_tau_T1"] = summary(t1)
    res["H1b_guarded_tau_T1"] = summary(h1(S, "T1", prefix="G_"))
    if tag == "base":
        res["H1_tau_T1_rmse"] = summary(h1(S, "T1", "rmse"))
        sf = Z["seasonal_fill"][:NBF] if "seasonal_fill" in Z.files else np.zeros(NBF, bool)
        res["H1_tau_T1_no_seasonal_fill"] = summary(t1[~sf[t1.index.values]])
        rm, rp = rho_metric(S, "T1", "mae"), rho_metric(S, "T1", "peak_mag_err")
        j = rm.index.intersection(rp.index)
        w2 = stats.wilcoxon(rp[j], rm[j])
        res["H2"] = dict(rho_mae=summary(rm[j]), rho_peakmag=summary(rp[j]), p=float(w2.pvalue),
                         share_peak_better=float((rp[j] > rm[j]).mean()))
        j3 = t1.index.intersection(t2.index)
        w3 = stats.wilcoxon(t2[j3], t1[j3])
        res["H3"] = dict(tau_T1=summary(t1[j3]), tau_T2=summary(t2[j3]), p=float(w3.pvalue))
        a1 = A[A.tariff == "T1"].set_index("building")
        best = a1[REAL].max(axis=1)
        k = int((a1["reactive"] >= best).sum())
        res["H4"] = dict(share_reactive_ge_best=float(k / len(a1)), n=int(len(a1)),
                         p=float(stats.binomtest(k, len(a1), 0.5, alternative="greater").pvalue))
        ps = {"H2": res["H2"]["p"], "H3": res["H3"]["p"], "H4": res["H4"]["p"]}
        order, run, adj = sorted(ps, key=ps.get), 0.0, {}
        for i, h in enumerate(order):
            run = max(run, min(1.0, (len(ps) - i) * ps[h])); adj[h] = run
        res["holm"] = adj
        for tf in ("T1", "T2"):
            a = A[A.tariff == tf]
            res[f"annual_share_{tf}"] = {p: dict(median=float(a[p].median()), mean=float(a[p].mean()),
                                                 share_negative=float((a[p] < 0).mean())) for p in A.columns if p not in ("building", "tariff")}
        # amendment 2 secondary: guarded execution
        g1 = h1(S, "T1", prefix="G_")
        res["H1b_guarded_tau_T1"] = summary(g1)
        ag = A[A.tariff == "T1"].set_index("building")
        bestg = ag[["G_" + r for r in REAL]].max(axis=1)
        kg = int((ag["reactive"] >= bestg).sum())
        res["H4b_guarded"] = dict(share_reactive_ge_best_guarded=float(kg / len(ag)), n=int(len(ag)),
                                  p=float(stats.binomtest(kg, len(ag), 0.5).pvalue),
                                  median_best_guarded=float(bestg.median()), median_reactive=float(ag["reactive"].median()))
        syng = ag[[c for c in ag.columns if c.startswith("G_S_")]]
        res["synthetic_T1_guarded"] = dict(median={c: float(syng[c].median()) for c in syng},
                                           friedman_p=float(stats.friedmanchisquare(*[syng[c] for c in syng]).pvalue))
        # amendment 3 (exploratory unless pre-listed)
        four = ["F1", "F2", "F3", "F4"]
        res["H1_F1toF4_open"] = summary(h1(S, "T1", models=four))
        res["H1_F1toF4_guarded"] = summary(h1(S, "T1", prefix="G_", models=four))
        for met in ("under", "pinball09"):
            res[f"H1_{met}_open"] = summary(h1(S, "T1", metric=met))
            res[f"H1_{met}_guarded"] = summary(h1(S, "T1", metric=met, prefix="G_"))
        months = sorted(S.month.unique())
        res["H1_first_half"] = summary(h1(S, "T1", months=months[:6]))  # pre-listed split of the test year
        res["H1_second_half"] = summary(h1(S, "T1", months=months[6:]))
        res["guarded_beats_reactive"] = {r: float((ag["G_" + r] > ag["reactive"]).mean()) for r in REAL}
        syn = A[A.tariff == "T1"].set_index("building")[[c for c in A.columns if c.startswith("S_")]]
        res["synthetic_T1"] = dict(median={c: float(syn[c].median()) for c in syn},
                                   friedman_p=float(stats.friedmanchisquare(*[syn[c] for c in syn]).pvalue))
        lf = YT.mean(1) / YT.max(1)
        daily = YT.reshape(NB, -1, 24).sum(2)
        cv = daily.std(1) / daily.mean(1)
        mod = pd.DataFrame(dict(best=best.values, lf=lf[best.index], cv=cv[best.index], use=USE[best.index]))
        res["moderators"] = dict(spearman_lf=float(stats.spearmanr(mod.best, mod.lf).statistic),
                                 spearman_cv=float(stats.spearmanr(mod.best, mod.cv).statistic),
                                 by_use={u: float(g.best.median()) for u, g in mod.groupby("use") if len(g) >= 20})
    OUT[tag] = res
    print(f"\n== {tag}: excluded {nex}/{ntot} building-months")
    print(json.dumps(res, indent=1)[:4000])
med_mae = ACC[ACC.model.isin(MODELS)].groupby("model").mae.median().to_dict()
OUT["accuracy_median_mae_kwh"] = med_mae
json.dump(OUT, open(os.path.join(R, "results.json"), "w"), indent=1)
ACC.to_csv(os.path.join(R, "accuracy.csv.gz"), index=False)
print("written", os.path.join(R, "results.json"))
