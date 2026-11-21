"""POST-SUBMISSION EXPLORATORY ANALYSIS (revision kit, 20 Nov 2026; not in PLAN.md): a 2024-2026 time-series
foundation model as a sixth and seventh forecaster. Chronos-Bolt (amazon/chronos-bolt-small), zero-shot, univariate on
the building's own hourly load up to midnight before the target day (context CTX hours; no temperature, no fitting).
B50 = its median forecast (the accuracy-optimal choice), B90 = its 0.9 quantile (the peak-conservative choice), both from
the same model run. Each is scheduled with the base LP and executed open loop and guarded (tariff T1, base battery).

Two steps on titan, from the repository root:
  forecast:  /mnt/data1/thanh/tsfm/.venv/bin/python code/revision_tsfm.py forecast data results_revision [threads]
  simulate:  .venv/bin/python code/revision_tsfm.py simulate data results_revision [workers]
Writes <out>/tsfm_bolt.npz, then <out>/bills_tsfm.csv and accuracy_tsfm.csv."""
import os
import sys
import time

import numpy as np

MODE, D, OUTD = sys.argv[1], sys.argv[2], sys.argv[3]
CTX = 512
os.makedirs(OUTD, exist_ok=True)
FN = os.path.join(OUTD, "tsfm_bolt.npz")
NL = chr(10)


def forecast():
    import torch
    from chronos import BaseChronosPipeline
    torch.set_num_threads(int(sys.argv[4]) if len(sys.argv) > 4 else 6)
    Z = np.load(os.path.join(D, "prep.npz"), allow_pickle=True)
    TE = np.load(os.path.join(D, "forecasts.npz"), allow_pickle=True)["te"]
    L = Z["load"].astype(np.float32)
    nb = int(os.environ.get("SMOKE", L.shape[1]))  # prep.npz holds exactly the kept buildings
    pipe = BaseChronosPipeline.from_pretrained("amazon/chronos-bolt-small", device_map="cpu", torch_dtype=torch.float32)
    i_sh, n_sh = map(int, os.environ.get("SHARD", "0/1").split("/"))  # SHARD=i/n: buildings i, i+n, ...
    bs = list(range(i_sh, nb, n_sh))
    out = np.empty((2, len(bs), len(TE)), np.float32)
    t0 = time.time()
    starts = TE[0] + 24 * np.arange(len(TE) // 24)
    for j, b in enumerate(bs):
        ctx = torch.tensor(np.stack([L[s - CTX:s, b] for s in starts]))
        q, _ = pipe.predict_quantiles(ctx, prediction_length=24, quantile_levels=[0.5, 0.9])
        q = np.maximum(q.detach().cpu().numpy(), 0)  # (days, 24, 2)
        out[0, j] = q[:, :, 0].reshape(-1)
        out[1, j] = q[:, :, 1].reshape(-1)
        if j % 20 == 0:
            print(i_sh, j, len(bs), round(time.time() - t0), "s", flush=True)
    fn = FN if n_sh == 1 else FN.replace(".npz", f"_shard{i_sh}of{n_sh}.npz")
    np.savez_compressed(fn + ".part.npz", F=out, models=np.array(["B50", "B90"]), ctx=CTX, buildings=np.array(bs))
    os.replace(fn + ".part.npz", fn)
    print("forecast done", out.shape, round(time.time() - t0), "s")


def merge():
    import glob
    parts = sorted(glob.glob(FN.replace(".npz", "_shard*of*.npz")))
    if not parts:
        return
    G = [np.load(p) for p in parts]
    nb = sum(len(g["buildings"]) for g in G)
    F = np.empty((2, nb, G[0]["F"].shape[2]), np.float32)
    for g in G:
        F[:, g["buildings"]] = g["F"]
    np.savez_compressed(FN, F=F, models=G[0]["models"], ctx=CTX, buildings=np.arange(nb))


S = FB = NAMES = None  # set by simulate() before the worker pool forks


def one(b):
    L = S.LOAD[:, b]
    P = S.SHARE * L[S.TR].max()
    E = 2 * P
    lp = S.build_lp(E, P)
    lam = S.DC
    names = NAMES + ["G_" + n for n in NAMES]
    Gd = {n: np.empty(len(S.TE)) for n in names}
    peaks = {n: 0.0 for n in names}
    soc = {n: 0.5 * E for n in names}
    cur_m, fails = None, 0
    for k0 in range(0, len(S.TE), 24):
        h = S.TE[k0:k0 + 24]
        mo = S.month[h[0]]
        if mo != cur_m:
            peaks = {n: 0.0 for n in names}; cur_m = mo
        Ld, pr = L[h], S.PRICE[h]
        for i, n in enumerate(NAMES):
            Lh = FB[i, b, k0:k0 + 24]
            c, d, z, ok = S.schedule(Lh, pr, peaks[n], lam, lp, E, soc[n]); fails += not ok
            Gd[n][k0:k0 + 24], soc[n] = S.execute(Ld, c, d, E, soc[n])
            gn = "G_" + n
            c, d, z, ok = S.schedule(Lh, pr, peaks[gn], lam, lp, E, soc[gn]); fails += not ok
            Gd[gn][k0:k0 + 24], soc[gn] = S.execute_guarded(Ld, c, d, E, P, max(peaks[gn], z), lam, soc[gn])
        for n in names:
            peaks[n] = max(peaks[n], Gd[n][k0:k0 + 24].max())
    rows, acc = [], []
    mt = S.month[S.TE]
    y = L[S.TE]
    for mo in np.unique(mt):
        k = mt == mo
        for n in names:
            g = Gd[n][k]
            rows.append((b, "T1", int(mo), n, float((S.PRICE[S.TE][k] * g).sum() + lam * g.max()), fails))
        for i, n in enumerate(NAMES):
            e = FB[i, b][k] - y[k]
            acc.append((b, int(mo), n, float(np.abs(e).mean()), float(np.sqrt((e ** 2).mean())),
                        float(np.where(e <= 0, -0.9 * e, 0.1 * e).mean()), float(np.maximum(-e, 0).mean()),
                        float(e.mean() / y[k].mean())))
    return rows, acc


def simulate():
    global S, FB, NAMES
    from multiprocessing import Pool
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    W = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    sys.argv = [sys.argv[0], D, os.path.join(OUTD, "unused.csv"), str(W)]
    import simulate as sim
    S = sim
    if not os.path.exists(FN):
        merge()
    G = np.load(FN)
    FB, NAMES = G["F"].astype(np.float64), list(G["models"])
    nb = FB.shape[1]
    with Pool(W) as pool:
        res = pool.map(one, range(nb), chunksize=1)
    with open(os.path.join(OUTD, "bills_tsfm.csv"), "w") as fh:
        fh.write("building,tariff,month,policy,bill,lp_fail_building" + NL)
        for r in res:
            for row in r[0]:
                fh.write(",".join(map(str, row)) + NL)
    with open(os.path.join(OUTD, "accuracy_tsfm.csv"), "w") as fh:
        fh.write("building,month,model,mae,rmse,pinball09,under,rel_bias" + NL)
        for r in res:
            for row in r[1]:
                fh.write(",".join(map(str, row)) + NL)
    print("simulate done", nb)


if __name__ == "__main__":
    forecast() if MODE == "forecast" else simulate()
