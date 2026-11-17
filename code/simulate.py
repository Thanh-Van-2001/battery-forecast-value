"""Battery scheduling and monthly bills per PLAN.md.
For each building, tariff, battery size and demand charge: daily day-ahead LP on a forecast, open-loop execution on
the actual load, monthly bill. Benchmarks: no battery, perfect information (same LP on the actual load), reactive rule.
Run: python simulate.py <data_dir> <out_csv> [workers] [battery_share] [demand_charge]
"""
import os
import sys
from multiprocessing import Pool

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import lil_matrix

D, OUT = sys.argv[1], sys.argv[2]
W = int(sys.argv[3]) if len(sys.argv) > 3 else 8
SHARE = float(sys.argv[4]) if len(sys.argv) > 4 else 0.10
DC = float(sys.argv[5]) if len(sys.argv) > 5 else 20.0
ETA = np.sqrt(0.90)
Z = np.load(os.path.join(D, "prep.npz"), allow_pickle=True)
LOAD = Z["load"].astype(np.float64)
HRS = Z["hours"]
FZ = np.load(os.path.join(D, "forecasts.npz"), allow_pickle=True)
F, MODELS, TE = FZ["F"], list(FZ["models"]), FZ["te"]  # float32 to halve memory (titan is shared)
hod = HRS % 24
dow = ((HRS // 24) + 4) % 7
month = HRS.astype("datetime64[h]").astype("datetime64[M]").astype(int)
PRICE = np.where((dow < 5) & (hod >= 12) & (hod < 18), 0.20, 0.10)
YEAR = (HRS.astype("datetime64[h]").astype("datetime64[Y]").astype(int) + 1970)
TR = YEAR == 2016

# LP in variables x = [c(24), d(24), s(25), g(24), z(1)]; s is state of charge, g grid draw, z peak
NV = 24 + 24 + 25 + 24 + 1
ic, idd, isx, ig, iz = 0, 24, 48, 73, 97


def build_lp(E, P):
    Aeq = lil_matrix((24 + 24 + 2, NV))
    for t in range(24):  # s[t+1] - s[t] - eta c + d/eta = 0
        Aeq[t, isx + t + 1] = 1; Aeq[t, isx + t] = -1; Aeq[t, ic + t] = -ETA; Aeq[t, idd + t] = 1 / ETA
    for t in range(24):  # g - c + d = L  (rhs set per day)
        Aeq[24 + t, ig + t] = 1; Aeq[24 + t, ic + t] = -1; Aeq[24 + t, idd + t] = 1
    Aeq[48, isx] = 1; Aeq[49, isx + 24] = 1
    Aub = lil_matrix((24, NV))
    for t in range(24):  # g - z <= 0
        Aub[t, ig + t] = 1; Aub[t, iz] = -1
    bounds = [(0, P)] * 48 + [(0.1 * E, 0.9 * E)] * 25 + [(0, None)] * 24 + [(0, None)]
    return Aeq.tocsr(), Aub.tocsr(), bounds


def schedule(Lhat, price, peak_so_far, lam, lp, E, s0):
    """day-ahead LP; amendment 3: starts from the carried-over state of charge s0, ends at half charge.
    Returns charge, discharge, planned peak z and a success flag."""
    Aeq, Aub, bounds = lp
    beq = np.concatenate([np.zeros(24), Lhat, [s0, 0.5 * E]])
    c = np.zeros(NV); c[ig:ig + 24] = price; c[iz] = lam
    bnd = list(bounds); bnd[iz] = (peak_so_far, None)  # demand cost lam*(z - peak) up to a constant
    r = linprog(c, A_ub=Aub, b_ub=np.zeros(24), A_eq=Aeq, b_eq=beq, bounds=bnd, method="highs")
    if r.status != 0:
        return np.zeros(24), np.zeros(24), peak_so_far, False
    return r.x[ic:ic + 24], r.x[idd:idd + 24], r.x[iz], True


def execute(L, c, d, E, s0):
    """open loop: scheduled powers, clipped so that SoC stays in bounds and there is no export; returns (g, SoC)"""
    s, g = s0, np.empty(24)
    for t in range(24):
        ct = min(c[t], max(0.0, (0.9 * E - s) / ETA))
        dt = min(d[t], max(0.0, (s - 0.1 * E) * ETA), L[t] + ct)
        s += ETA * ct - dt / ETA
        g[t] = L[t] + ct - dt
    return g, s


def execute_guarded(L, c, d, E, P, threshold, lam, s0):
    """the day-ahead schedule, but never charge above the threshold and discharge to hold the realised grid draw at it.
    Amendment 3: threshold = max(month-to-date realised peak, the day's planned peak), which fixes the month start."""
    if lam == 0:
        return execute(L, c, d, E, s0)
    s, g, pk = s0, np.empty(24), threshold
    for t in range(24):
        ct = min(c[t], max(0.0, (0.9 * E - s) / ETA))
        dt = min(d[t], max(0.0, (s - 0.1 * E) * ETA), L[t] + ct)
        if L[t] + ct - dt > pk:
            ct = max(0.0, min(ct, pk - L[t] + dt))
            if L[t] + ct - dt > pk:
                dt = min(P, max(0.0, (s - 0.1 * E) * ETA), max(dt, L[t] + ct - pk))
        s += ETA * ct - dt / ETA
        g[t] = L[t] + ct - dt
        pk = max(pk, g[t])
    return g, s


def reactive(L, hours, threshold, lam, E, P, s0):
    """forecast-free rule (amendment 3): T1 - shave above max(month-to-date peak, previous month's peak) and charge only
    on weekday mornings without exceeding that threshold; T2 - charge on weekday mornings, discharge in expensive hours."""
    s, g, pk = s0, np.empty(24), threshold
    for t in range(24):
        h = hours[t]
        weekday = dow[h] < 5
        room = max(0.0, (0.9 * E - s) / ETA)
        avail = max(0.0, (s - 0.1 * E) * ETA)
        ct = dt = 0.0
        if lam > 0:
            if L[t] > pk:
                dt = min(P, L[t] - pk, avail)
            elif weekday and hod[h] < 12:
                ct = min(P, room, max(0.0, pk - L[t]))
        else:
            if weekday and PRICE[h] >= 0.2:
                dt = min(P, L[t], avail)
            elif weekday and hod[h] < 12:
                ct = min(P, room)
        s += ETA * ct - dt / ETA
        g[t] = L[t] + ct - dt
        pk = max(pk, g[t])
    return g, s


def one(b):
    L = LOAD[:, b]
    P = SHARE * L[TR].max()
    E = 2 * P
    lp = build_lp(E, P)
    rows = []
    first_m = month[TE[0]]
    for lam, tariff in ((DC, "T1"), (0.0, "T2")):
        names = ["none", "PI", "reactive"] + MODELS + ["G_" + m for m in MODELS]
        G = {n: np.empty(len(TE)) for n in names}
        peaks = {n: 0.0 for n in names}
        soc = {n: 0.5 * E for n in names}
        prev_peak_reactive = float(L[month == first_m - 1].max())  # December 2016 peak (no battery)
        fails = 0
        cur_m = None
        for k0 in range(0, len(TE), 24):
            h = TE[k0:k0 + 24]
            m = month[h[0]]
            if m != cur_m:
                if cur_m is not None:
                    prev_peak_reactive = peaks["reactive"]
                peaks = {n: 0.0 for n in names}; cur_m = m
            Ld, pr = L[h], PRICE[h]
            G["none"][k0:k0 + 24] = Ld
            c, d, z, ok = schedule(Ld, pr, peaks["PI"], lam, lp, E, soc["PI"]); fails += not ok
            G["PI"][k0:k0 + 24], soc["PI"] = execute(Ld, c, d, E, soc["PI"])
            thr = max(peaks["reactive"], prev_peak_reactive) if lam > 0 else 0.0
            G["reactive"][k0:k0 + 24], soc["reactive"] = reactive(Ld, h, thr, lam, E, P, soc["reactive"])
            for i, mname in enumerate(MODELS):
                c, d, z, ok = schedule(F[i, b, k0:k0 + 24], pr, peaks[mname], lam, lp, E, soc[mname]); fails += not ok
                G[mname][k0:k0 + 24], soc[mname] = execute(Ld, c, d, E, soc[mname])
                gn = "G_" + mname
                if lam > 0:  # guarded execution plans from its own state and month-to-date peak
                    c, d, z, ok = schedule(F[i, b, k0:k0 + 24], pr, peaks[gn], lam, lp, E, soc[gn]); fails += not ok
                    thr = max(peaks[gn], z)
                else:
                    thr = 0.0
                G[gn][k0:k0 + 24], soc[gn] = execute_guarded(Ld, c, d, E, P, thr, lam, soc[gn])
            for n in names:
                peaks[n] = max(peaks[n], G[n][k0:k0 + 24].max())
        mt = month[TE]
        for m in np.unique(mt):
            k = mt == m
            for n in names:
                g = G[n][k]
                bill = float((PRICE[TE][k] * g).sum() + lam * g.max())
                rows.append((b, tariff, int(m), n, bill, fails))
    return rows


if __name__ == "__main__":
    NB = F.shape[1]  # equals the number of buildings forecast (fewer in a SMOKE run)
    with Pool(W) as pool:
        res = pool.map(one, range(NB), chunksize=2)
    with open(OUT + ".part", "w") as fh:
        fh.write("building,tariff,month,policy,bill,lp_fail_building\n")
        for rows in res:
            for r in rows:
                fh.write(",".join(map(str, r)) + "\n")
    os.replace(OUT + ".part", OUT)
    print("written", OUT)
