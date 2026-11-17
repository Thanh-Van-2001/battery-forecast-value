"""Select BDG2 electricity meters per PLAN.md and build aligned load/temperature arrays.
Run: python prep.py <data_dir>  ->  <data_dir>/prep.npz, prep_log.json
"""
import json
import os
import sys

import numpy as np
import pandas as pd

D = sys.argv[1]
el = pd.read_csv(os.path.join(D, "electricity_cleaned.csv"), parse_dates=["timestamp"]).set_index("timestamp")
meta = pd.read_csv(os.path.join(D, "metadata.csv")).set_index("building_id")
wx = pd.read_csv(os.path.join(D, "weather.csv"), parse_dates=["timestamp"])
idx = pd.date_range("2016-01-01 00:00", "2017-12-31 23:00", freq="h")
el = el.reindex(idx)
LOG = {"meters": el.shape[1]}
keep, why, maxgap = [], {}, {}
for b in el.columns:
    x = el[b]
    ok = True
    for y in (2016, 2017):
        if x[str(y)].notna().mean() < 0.95:
            ok = False; why["missing>5%"] = why.get("missing>5%", 0) + 1; break
    if not ok:
        continue
    v = x.values
    run, best, prev = 1, 1, None
    for a in v:  # longest run of identical non-missing readings
        if prev is not None and a == prev and not np.isnan(a):
            run += 1; best = max(best, run)
        else:
            run = 1
        prev = a
    if best >= 72:
        why["flat>=72h"] = why.get("flat>=72h", 0) + 1; continue
    if np.nanmean(v) < 10:
        why["mean<10"] = why.get("mean<10", 0) + 1; continue
    gaps = x.isna().astype(int).groupby(x.notna().cumsum()).sum()
    if gaps.max() > 24:  # amendment 2: gaps of 4-24 h are filled from the same hour a week earlier
        why["gap>24h"] = why.get("gap>24h", 0) + 1; continue
    keep.append(b)
    maxgap[b] = int(gaps.max())
LOG["excluded"] = why
raw = el[keep]
L = raw.interpolate(limit=3, limit_area="inside")
for _ in range(4):  # seasonal fill for longer gaps: same hour one week earlier (then later), repeated if needed
    L = L.fillna(L.shift(168)).fillna(L.shift(-168))
L = L.bfill(limit=3).ffill(limit=3)
assert not L.isna().any().any(), "residual missing values"
filled = raw.isna() & L.notna()
LOG["filled_share_median"] = float(filled.mean().median())
LOG["buildings_with_seasonal_fill"] = int(sum(v > 3 for v in maxgap.values()))
seasonal = np.array([maxgap[b] > 3 for b in keep])
site = meta.loc[keep, "site_id"].values
temp = np.full(L.shape, np.nan)
for s in np.unique(site):
    t = wx[wx.site_id == s].set_index("timestamp")["airTemperature"].reindex(idx).interpolate(limit=6).bfill().ffill()
    temp[:, site == s] = t.values[:, None]
LOG["kept"] = len(keep)
LOG["temp_missing_after_fill"] = int(np.isnan(temp).sum())
np.savez_compressed(os.path.join(D, "prep.npz"), load=L.values.astype(np.float32), temp=temp.astype(np.float32),
                    hours=idx.values.astype("datetime64[h]").astype(np.int64), buildings=np.array(keep),
                    site=site, use=meta.loc[keep, "primaryspaceusage"].fillna("unknown").values, seasonal_fill=seasonal)
json.dump(LOG, open(os.path.join(D, "prep_log.json"), "w"), indent=1)
print(json.dumps(LOG, indent=1))
