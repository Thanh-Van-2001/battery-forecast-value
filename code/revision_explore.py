"""POST-SUBMISSION EXPLORATORY ANALYSES (20 Nov 2026). Not in PLAN.md and not pre-specified; written
after the manuscript was first submitted, in response to referee-style comments.

(1) hindsight  - the battery LP solved over each whole calendar month with the actual load (non-myopic perfect
                 information), T1 and T2. The daily perfect-information schedule is feasible for it, so it bounds the
                 daily benchmark from below.
(2) headroom   - the day-ahead LP with the planned grid draw kept m x forecast load below the planned peak
                 (g_t + m * Lhat_t <= z, z >= month-to-date peak), m = 0.05 and 0.10, F1-F5, open loop and guarded, T1.
(3) quantiles  - LightGBM quantile forecasters with F4/F5's features and settings, alpha = 0.5, 0.7, 0.8, 0.9, 0.95,
                 open loop and guarded, T1 (alpha 0.9 refits F5 and checks that it is reproduced).
The daily perfect-information bill is recomputed as a check against bills_base.csv.

Run on titan from the repository root: python code/revision_explore.py data results_revision 6
Writes <out>/bills_revision.csv, hindsight.csv, accuracy_revision.csv, pkw.csv, f5_check.json
"""
import json
import os
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
D, OUTD = sys.argv[1], sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 6
sys.argv = [sys.argv[0], D, os.path.join(OUTD, "unused.csv"), str(W)]  # simulate.py parses argv at import
import simulate as S  # noqa: E402  (loads prep.npz and forecasts.npz; base settings: P = 10% of peak, 20 $/kW)

import lightgbm as lgb  # noqa: E402
import numpy as np  # noqa: E402
from scipy.optimize import linprog  # noqa: E402
from scipy.sparse import coo_matrix  # noqa: E402

os.makedirs(OUTD, exist_ok=True)
LOAD, TE, F, MODELS, month, PRICE = S.LOAD, S.TE, S.F, S.MODELS, S.month, S.PRICE
TEMP = S.Z["temp"].astype(np.float64)
HRS = S.HRS
T = LOAD.shape[0]
hod, dow = HRS % 24, ((HRS // 24) + 4) % 7
year = HRS.astype("datetime64[h]").astype("datetime64[Y]").astype(int) + 1970
TRF = np.where((year == 2016) & (np.arange(T) >= 168))[0]  # training rows of forecasts.py
REAL = ["F1", "F2", "F3", "F4", "F5"]
MARGINS = [0.05, 0.10]
ALPHAS = [0.5, 0.7, 0.8, 0.9, 0.95]
QN = {a: f"Q{int(round(a * 100))}" for a in ALPHAS}


def features(b):
    """identical to code/forecasts.py"""
    y = LOAD[:, b]
    lag = lambda k: np.concatenate([np.full(k, np.nan), y[:-k]])
    l24, l48, l168 = lag(24), lag(48), lag(168)
    t = TEMP[:, b]
    return np.column_stack([np.eye(24)[hod], np.eye(7)[dow], l24, l48, l168, t, t ** 2, np.maximum(t - 18, 0),
                            np.maximum(12 - t, 0)])


def quantile_forecasts(b):
    X = features(b)
    y = LOAD[:, b]
    p = dict(n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=40, subsample=0.8, subsample_freq=1,
             colsample_bytree=0.9, verbose=-1, n_jobs=1, random_state=b)
    out = {}
    for a in ALPHAS:
        q = lgb.LGBMRegressor(objective="quantile", alpha=a, **p).fit(X[TRF], y[TRF])
        out[QN[a]] = np.maximum(q.predict(X[TE]).astype(np.float32), 0).astype(np.float64)
    return out


def schedule_h(Lhat, price, peak_so_far, lam, lp, E, s0, m):
    """the day-ahead LP of simulate.schedule with headroom: g_t + m * Lhat_t <= z. Returns c, d, planned g, ok."""
    Aeq, Aub, bounds = lp
    beq = np.concatenate([np.zeros(24), Lhat, [s0, 0.5 * E]])
    c = np.zeros(S.NV); c[S.ig:S.ig + 24] = price; c[S.iz] = lam
    bnd = list(bounds); bnd[S.iz] = (peak_so_far, None)
    r = linprog(c, A_ub=Aub, b_ub=-m * np.asarray(Lhat), A_eq=Aeq, b_eq=beq, bounds=bnd, method="highs")
    if r.status != 0:
        return np.zeros(24), np.zeros(24), np.asarray(Lhat, float), False
    return r.x[S.ic:S.ic + 24], r.x[S.idd:S.idd + 24], r.x[S.ig:S.ig + 24], True


def hindsight_month(L, price, lam, E, P):
    """whole-month LP with the actual load; variables [c(n), d(n), s(n+1), g(n), z]; s starts and ends at 0.5E."""
    n = len(L)
    ic, idd, isx, ig, iz = 0, n, 2 * n, 3 * n + 1, 4 * n + 1
    nv = 4 * n + 2
    t = np.arange(n)
    r1 = np.concatenate([t, t, t, t]); c1 = np.concatenate([isx + t + 1, isx + t, ic + t, idd + t])
    v1 = np.concatenate([np.ones(n), -np.ones(n), -S.ETA * np.ones(n), np.ones(n) / S.ETA])
    r2 = np.concatenate([n + t] * 3); c2 = np.concatenate([ig + t, ic + t, idd + t])
    v2 = np.concatenate([np.ones(n), -np.ones(n), np.ones(n)])
    r3 = np.array([2 * n, 2 * n + 1]); c3 = np.array([isx, isx + n]); v3 = np.ones(2)
    Aeq = coo_matrix((np.concatenate([v1, v2, v3]), (np.concatenate([r1, r2, r3]), np.concatenate([c1, c2, c3]))),
                     shape=(2 * n + 2, nv)).tocsr()
    beq = np.concatenate([np.zeros(n), L, [0.5 * E, 0.5 * E]])
    Aub = coo_matrix((np.concatenate([np.ones(n), -np.ones(n)]), (np.concatenate([t, t]), np.concatenate([ig + t, np.full(n, iz)]))),
                     shape=(n, nv)).tocsr()
    bounds = [(0, P)] * (2 * n) + [(0.1 * E, 0.9 * E)] * (n + 1) + [(0, None)] * n + [(0, None)]
    cost = np.zeros(nv); cost[ig:ig + n] = price; cost[iz] = lam
    r = linprog(cost, A_ub=Aub, b_ub=np.zeros(n), A_eq=Aeq, b_eq=beq, bounds=bounds, method="highs")
    if r.status != 0:
        return np.nan, False
    g = r.x[ig:ig + n]
    return float((price * g).sum() + lam * g.max()), True


def one(b):
    t0 = time.time()
    L = LOAD[:, b]
    P = S.SHARE * L[S.TR].max()
    E = 2 * P
    lp = S.build_lp(E, P)
    lam = S.DC
    Q = quantile_forecasts(b)
    f5_maxabs = float(np.max(np.abs(Q["Q90"] - F[MODELS.index("F5"), b].astype(np.float64))))
    f5_rel = f5_maxabs / float(L[TE].mean())
    fc = {m: F[MODELS.index(m), b].astype(np.float64) for m in REAL}
    fc.update(Q)
    open_pols = [f"H{int(m * 100):02d}_{f}" for m in MARGINS for f in REAL] + list(Q)
    names = ["none", "PI"] + open_pols + ["G_" + p for p in open_pols]
    G = {n: np.empty(len(TE)) for n in names}
    peaks = {n: 0.0 for n in names}
    soc = {n: 0.5 * E for n in names}
    cur_m, fails = None, 0
    for k0 in range(0, len(TE), 24):
        h = TE[k0:k0 + 24]
        mo = month[h[0]]
        if mo != cur_m:
            peaks = {n: 0.0 for n in names}; cur_m = mo
        Ld, pr = L[h], PRICE[h]
        G["none"][k0:k0 + 24] = Ld
        c, d, z, ok = S.schedule(Ld, pr, peaks["PI"], lam, lp, E, soc["PI"]); fails += not ok
        G["PI"][k0:k0 + 24], soc["PI"] = S.execute(Ld, c, d, E, soc["PI"])
        for pol in open_pols:
            if pol.startswith("H"):
                m = int(pol[1:3]) / 100.0
                Lh = fc[pol[4:]][k0:k0 + 24]
                c, d, gp, ok = schedule_h(Lh, pr, peaks[pol], lam, lp, E, soc[pol], m); fails += not ok
                G[pol][k0:k0 + 24], soc[pol] = S.execute(Ld, c, d, E, soc[pol])
                gn = "G_" + pol
                c, d, gp, ok = schedule_h(Lh, pr, peaks[gn], lam, lp, E, soc[gn], m); fails += not ok
                thr = max(peaks[gn], float(np.max(gp)))  # same threshold definition as the base guard
            else:
                Lh = fc[pol][k0:k0 + 24]
                c, d, z, ok = S.schedule(Lh, pr, peaks[pol], lam, lp, E, soc[pol]); fails += not ok
                G[pol][k0:k0 + 24], soc[pol] = S.execute(Ld, c, d, E, soc[pol])
                gn = "G_" + pol
                c, d, z, ok = S.schedule(Lh, pr, peaks[gn], lam, lp, E, soc[gn]); fails += not ok
                thr = max(peaks[gn], z)
            G[gn][k0:k0 + 24], soc[gn] = S.execute_guarded(Ld, c, d, E, P, thr, lam, soc[gn])
        for n in names:
            peaks[n] = max(peaks[n], G[n][k0:k0 + 24].max())
    rows = []
    mt = month[TE]
    for mo in np.unique(mt):
        k = mt == mo
        for n in names:
            g = G[n][k]
            rows.append((b, "T1", int(mo), n, float((PRICE[TE][k] * g).sum() + lam * g.max()), fails))
    hind = []
    for lam_, tf in ((lam, "T1"), (0.0, "T2")):
        for mo in np.unique(mt):
            k = mt == mo
            bill, ok = hindsight_month(L[TE][k], PRICE[TE][k], lam_, E, P)
            hind.append((b, tf, int(mo), bill, int(ok)))
    acc = []
    y = L[TE]
    for mname, f in Q.items():
        for mo in np.unique(mt):
            k = mt == mo
            e = f[k] - y[k]
            acc.append((b, int(mo), mname, float(np.abs(e).mean()), float(np.sqrt((e ** 2).mean())),
                        float(np.where(e <= 0, -0.9 * e, 0.1 * e).mean()), float(np.maximum(-e, 0).mean()),
                        float(e.mean() / y[k].mean())))
    return rows, hind, acc, (b, P, f5_maxabs, f5_rel), time.time() - t0


if __name__ == "__main__":
    NB = int(os.environ.get("SMOKE", F.shape[1]))
    t0 = time.time()
    with Pool(W) as pool:
        res = pool.map(one, range(NB), chunksize=1)
    with open(os.path.join(OUTD, "bills_revision.csv.part"), "w") as fh:
        fh.write("building,tariff,month,policy,bill,lp_fail_building\n")
        for r in res:
            for row in r[0]:
                fh.write(",".join(map(str, row)) + "\n")
    os.replace(os.path.join(OUTD, "bills_revision.csv.part"), os.path.join(OUTD, "bills_revision.csv"))
    with open(os.path.join(OUTD, "hindsight.csv"), "w") as fh:
        fh.write("building,tariff,month,bill_hindsight,ok\n")
        for r in res:
            for row in r[1]:
                fh.write(",".join(map(str, row)) + "\n")
    with open(os.path.join(OUTD, "accuracy_revision.csv"), "w") as fh:
        fh.write("building,month,model,mae,rmse,pinball09,under,rel_bias\n")
        for r in res:
            for row in r[2]:
                fh.write(",".join(map(str, row)) + "\n")
    with open(os.path.join(OUTD, "pkw.csv"), "w") as fh:
        fh.write("building,P_kw,f5_refit_maxabs,f5_refit_maxabs_rel\n")
        for r in res:
            fh.write(",".join(map(str, r[3])) + "\n")
    chk = np.array([r[3][3] for r in res])
    json.dump(dict(n=int(NB), f5_refit_max_rel_diff=float(chk.max()), f5_refit_median_rel_diff=float(np.median(chk)),
                   seconds=time.time() - t0, per_building_seconds_median=float(np.median([r[4] for r in res]))),
              open(os.path.join(OUTD, "f5_check.json"), "w"), indent=1)
    print("done", NB, "buildings in", round(time.time() - t0), "s")
