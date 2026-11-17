"""Figures from out/panel.csv and out/results.json. Run: python make_figures.py <repo_root>"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = sys.argv[1]
FIG = os.path.join(ROOT, "paper", "figures")
os.makedirs(FIG, exist_ok=True)
P = pd.read_csv(os.path.join(ROOT, "out", "panel.csv"))
plt.rcParams.update({"font.size": 9, "font.family": "serif", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6, "axes.axisbelow": True})
BLUE, ORANGE, GREEN, PINK, GOLD, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#e87ba4", "#eda100", "#52514e"
REAL = ["F4", "F3", "F1", "F2", "F5"]  # ordered by median MAE (most accurate first)
LAB = {"F1": "Naive 24 h", "F2": "Naive 168 h", "F3": "Ridge", "F4": "LightGBM", "F5": "LightGBM q0.9",
       "S_noise": "Noise", "S_shift": "1-h shift", "S_scale": "Uniform over-forecast"}


def med_iqr(x):
    return np.median(x), np.percentile(x, 25), np.percentile(x, 75)


# Figure 1: annual captured share by forecaster (ordered by accuracy), open loop vs guarded; reactive rule as a band
fig, ax = plt.subplots(figsize=(5.6, 3.0))
xs = np.arange(len(REAL))
for j, (col, c, mk, off, lab) in enumerate([("share_open", ORANGE, "o", -0.12, "Open-loop schedule"),
                                             ("share_guarded", BLUE, "s", 0.12, "Guarded schedule")]):
    st = [med_iqr(P[P.model == m][col]) for m in REAL]
    ax.errorbar(xs + off, [s[0] for s in st], yerr=[[s[0] - s[1] for s in st], [s[2] - s[0] for s in st]],
                fmt=mk, color=c, ms=6, lw=1.5, capsize=0, label=lab)
r = P[P.model == "F4"].share_reactive
m_, lo, hi = med_iqr(r)
ax.axhspan(lo, hi, color=GREY, alpha=0.10, lw=0)
ax.axhline(m_, color=GREY, lw=1.2, ls="--", label="Reactive rule (no forecast)")
ax.axhline(0, color="black", lw=0.8)
acc = pd.read_csv(os.path.join(ROOT, "out", "accuracy.csv.gz"))
rk = acc[acc.model.isin(REAL)].pivot_table(index=["building", "month"], columns="model", values="mae").rank(axis=1).mean()
assert list(rk.sort_values().index) == REAL, rk
ax.set_xticks(xs, [f"{LAB[m]}\nrank {rk[m]:.2f}" for m in REAL])
ax.set_ylabel("Share of perfect-information saving")
ax.set_xlabel("Forecaster, from most to least accurate (mean MAE rank over building-months)")
ax.legend(frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_share_by_forecaster.pdf"))
plt.close(fig)

# Figure 2: same-MAE synthetic errors
fig, ax = plt.subplots(figsize=(4.6, 2.8))
SYN = ["S_scale", "S_noise", "S_shift"]
xs = np.arange(len(SYN))
for col, c, mk, off, lab in [("share_open", ORANGE, "o", -0.12, "Open-loop schedule"), ("share_guarded", BLUE, "s", 0.12, "Guarded schedule")]:
    st = [med_iqr(P[P.model == m][col]) for m in SYN]
    ax.errorbar(xs + off, [s[0] for s in st], yerr=[[s[0] - s[1] for s in st], [s[2] - s[0] for s in st]],
                fmt=mk, color=c, ms=6, lw=1.5, capsize=0, label=lab)
ax.axhline(0, color="black", lw=0.8)
ax.set_xticks(xs, [LAB[m] for m in SYN])
ax.set_ylabel("Share of perfect-information saving")
ax.set_xlabel("Error type (all with the MAE of LightGBM, month by month)")
ax.legend(frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_synthetic.pdf"))
plt.close(fig)

# Figure 3: accuracy vs value per building and forecaster (guarded); bias as a second panel
fig, axs = plt.subplots(1, 2, figsize=(6.6, 2.9), sharey=True)
COL = {"F1": GOLD, "F2": PINK, "F3": GREEN, "F4": BLUE, "F5": ORANGE}
MK = {"F1": "^", "F2": "v", "F3": "D", "F4": "s", "F5": "o"}
for m in REAL:
    d = P[P.model == m]
    axs[0].scatter(100 * d.rel_mae, d.share_guarded, s=6, color=COL[m], marker=MK[m], alpha=0.45, lw=0, label=LAB[m])
    axs[1].scatter(100 * d.rel_bias, d.share_guarded, s=6, color=COL[m], marker=MK[m], alpha=0.45, lw=0)
axs[0].set_xlabel("Relative MAE (%)")
axs[1].set_xlabel("Relative bias (%, positive = over-forecast)")
axs[0].set_ylabel("Share of perfect-information\nsaving (guarded)")
axs[0].set_xlim(0, np.percentile(100 * P[P.model.isin(REAL)].rel_mae, 99))
axs[1].set_xlim(np.percentile(100 * P[P.model.isin(REAL)].rel_bias, 1), np.percentile(100 * P[P.model.isin(REAL)].rel_bias, 99))
axs[0].set_ylim(-0.2, 1.0)
axs[0].legend(frameon=False, fontsize=7, markerscale=2.5, loc="upper right")
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_accuracy_vs_value.pdf"))
plt.close(fig)
print("figures written")
