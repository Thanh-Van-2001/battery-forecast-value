"""Small descriptive facts for the paper -> <out>/facts.json. Run: python facts.py <data_dir> <out_json>"""
import json
import os
import sys

import numpy as np
import pandas as pd

D, OUT = sys.argv[1], sys.argv[2]
m = pd.read_csv(os.path.join(D, "metadata.csv"))
Z = np.load(os.path.join(D, "prep.npz"), allow_pickle=True)
F = np.load(os.path.join(D, "forecasts.npz"), allow_pickle=True)
L = Z["load"][F["te"]].T.astype(float)
models = list(F["models"])
s = F["F"][models.index("S_scale")].astype(float)
r = s / np.where(L > 0, L, np.nan) - 1
uses = pd.Series(Z["use"]).value_counts()
facts = dict(bdg2_buildings=int(m.building_id.nunique()), bdg2_sites=int(m.site_id.nunique()),
             kept_sites=int(len(set(Z["site"]))), scale_median_pct=float(np.nanmedian(r) * 100),
             scale_q25_pct=float(np.nanpercentile(r, 25) * 100), scale_q75_pct=float(np.nanpercentile(r, 75) * 100),
             top_uses={k: int(v) for k, v in uses.head(4).items()}, mean_load_median=float(np.median(L.mean(1))))
json.dump(facts, open(OUT, "w"), indent=1)
print(facts)
