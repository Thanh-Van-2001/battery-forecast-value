"""Day-ahead forecasts for 2017 per PLAN.md: F1 lag-24, F2 lag-168, F3 ridge, F4 LightGBM, F5 LightGBM q0.9,
plus synthetic forecasts with the same monthly MAE as F4 but one error type each: S_noise, S_shift, S_scale.
Every feature of target hour t uses loads at t-24 or earlier, so all are known at 00:00 of the target day.
Run: python forecasts.py <data_dir> [workers]  ->  <data_dir>/forecasts.npz
"""
import os
import sys
from multiprocessing import Pool

import lightgbm as lgb
import numpy as np
from sklearn.linear_model import Ridge

D = sys.argv[1]
W = int(sys.argv[2]) if len(sys.argv) > 2 else 8
Z = np.load(os.path.join(D, "prep.npz"), allow_pickle=True)
LOAD, TEMP = Z["load"].astype(np.float64), Z["temp"].astype(np.float64)
HRS = Z["hours"]  # hours since epoch
T, NB = LOAD.shape
hod = HRS % 24
dow = ((HRS // 24) + 4) % 7  # 1970-01-01 was a Thursday -> 0 = Monday
year = (HRS.astype("datetime64[h]").astype("datetime64[Y]").astype(int) + 1970)
month = HRS.astype("datetime64[h]").astype("datetime64[M]").astype(int)
TR = np.where((year == 2016) & (np.arange(T) >= 168))[0]
TE = np.where(year == 2017)[0]
MODELS = ["F1", "F2", "F3", "F4", "F5", "S_noise", "S_shift", "S_scale", "S_under", "S_ar1"]  # amendment 3 adds the last two


def features(b):
    y = LOAD[:, b]
    lag = lambda k: np.concatenate([np.full(k, np.nan), y[:-k]])
    l24, l48, l168 = lag(24), lag(48), lag(168)
    t = TEMP[:, b]
    X = np.column_stack([np.eye(24)[hod], np.eye(7)[dow], l24, l48, l168, t, t ** 2, np.maximum(t - 18, 0), np.maximum(12 - t, 0)])
    return X, l24, l168


def one(b):
    rng = np.random.default_rng(1000 + b)
    y = LOAD[:, b]
    X, l24, l168 = features(b)
    out = np.empty((len(MODELS), len(TE)), np.float32)
    out[0], out[1] = l24[TE], l168[TE]
    sc = y[TR].mean()
    r = Ridge(alpha=1.0).fit(X[TR] / 1.0, y[TR] / sc)
    out[2] = r.predict(X[TE]) * sc
    p = dict(n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=40, subsample=0.8, subsample_freq=1,
             colsample_bytree=0.9, verbose=-1, n_jobs=1, random_state=b)
    g = lgb.LGBMRegressor(**p).fit(X[TR], y[TR])
    out[3] = g.predict(X[TE])
    q = lgb.LGBMRegressor(objective="quantile", alpha=0.9, **p).fit(X[TR], y[TR])
    out[4] = q.predict(X[TE])
    # synthetic forecasts matched to F4's MAE month by month
    yt, f4 = y[TE], out[3].astype(np.float64)
    shift = np.concatenate([[yt[0]], yt[:-1]])  # forecast hour t with the actual of t-1 (peak predicted 1 h late)
    s_noise, s_shift, s_scale = np.empty_like(yt), np.empty_like(yt), np.empty_like(yt)
    s_under, s_ar1 = np.empty_like(yt), np.empty_like(yt)
    kappas = []
    for m in np.unique(month[TE]):
        k = month[TE] == m
        target = np.abs(f4[k] - yt[k]).mean()
        z = rng.standard_normal(k.sum())
        s_noise[k] = yt[k] + z * target / np.mean(np.abs(z))
        base = np.abs(shift[k] - yt[k]).mean()
        kappa = target / base if base > 0 else 0.0
        kappas.append(kappa)
        s_shift[k] = yt[k] + kappa * (shift[k] - yt[k])
        r = target / yt[k].mean()
        s_scale[k] = yt[k] * (1 + r)
        s_under[k] = np.maximum(yt[k] * (1 - r), 0)  # amendment 3: the mirror image of S_scale
        a = np.empty(k.sum()); a[0] = rng.standard_normal()  # amendment 3: hourly AR(1) noise, rho = 0.9
        e = rng.standard_normal(k.sum()) * np.sqrt(1 - 0.81)
        for t in range(1, len(a)):
            a[t] = 0.9 * a[t - 1] + e[t]
        s_ar1[k] = yt[k] + a * target / np.mean(np.abs(a))
    out[5], out[6], out[7], out[8], out[9] = s_noise, s_shift, s_scale, s_under, s_ar1
    return np.maximum(out, 0), np.array(kappas)


if __name__ == "__main__":
    NB = int(os.environ.get("SMOKE", NB))  # SMOKE=k runs the first k buildings only (pipeline check)
    with Pool(W) as pool:
        res = pool.map(one, range(NB), chunksize=4)
    F = np.stack([r[0] for r in res], axis=1)  # model x building x hour
    K = np.stack([r[1] for r in res])  # building x month: multiplier of the one-hour lag error in S_shift
    np.savez_compressed(os.path.join(D, "forecasts.npz.part.npz"), F=F, models=np.array(MODELS), te=TE, shift_kappa=K)
    print("S_shift kappa: median %.2f, IQR %.2f-%.2f" % (np.median(K), *np.percentile(K, [25, 75])))
    os.replace(os.path.join(D, "forecasts.npz.part.npz"), os.path.join(D, "forecasts.npz"))
    mae = np.abs(F - LOAD[TE][:, :NB].T[None]).mean(axis=2) / LOAD[TE][:, :NB].mean(0)[None]
    for i, m in enumerate(MODELS):
        print(f"{m:8s} median relative MAE {np.median(mae[i]):.3f}")
