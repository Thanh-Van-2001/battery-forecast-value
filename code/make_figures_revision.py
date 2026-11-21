"""Figure for the post-submission exploratory analyses (not pre-specified): value and accuracy against the quantile
level of the forecast, LightGBM quantile models (R3) and the zero-shot Chronos-Bolt forecaster (R6).
Reads out_revision/revision.json only. Run: python make_figures_revision.py <repo_root>"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = sys.argv[1]
FIG = os.path.join(ROOT, "paper", "figures")
V = json.load(open(os.path.join(ROOT, "out_revision", "revision.json")))
plt.rcParams.update({"font.size": 9, "font.family": "serif", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e6e6e6", "grid.linewidth": 0.6, "axes.axisbelow": True})
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#52514e"
Q = ["Q50", "Q70", "Q80", "Q90", "Q95"]
A = [0, 1, 2, 3, 4]  # equally spaced positions for the five levels
ALAB = ["0.5", "0.7", "0.8", "0.9", "0.95"]
r3, r6 = V["R3_quantiles"]["annual"], V["R6_tsfm"]["annual"]

fig, axs = plt.subplots(1, 2, figsize=(6.6, 3.2), gridspec_kw={"width_ratios": [1.45, 1]})
ax = axs[0]
for pre, c, mk, off, lab in [("", ORANGE, "o", -0.08, "Open loop"), ("G_", BLUE, "s", 0.08, "Guarded")]:
    med = [r3[pre + q]["median"] for q in Q]
    lo = [r3[pre + q]["median"] - r3[pre + q]["q25"] for q in Q]
    hi = [r3[pre + q]["q75"] - r3[pre + q]["median"] for q in Q]
    ax.errorbar([a + off for a in A], med, yerr=[lo, hi], fmt=mk + "-", color=c, ms=5, lw=1.3, capsize=0,
                label="LightGBM quantile, " + lab.lower())
    for b, a in (("B50", 0), ("B90", 3)):
        s = r6[pre + b]
        ax.errorbar([a + 3 * off], [s["median"]], yerr=[[s["median"] - s["q25"]], [s["q75"] - s["median"]]], fmt="D",
                    mfc="white", mec=c, color=c, ms=5.5, lw=1.0, capsize=0,
                    label=("Chronos-Bolt, " + lab.lower()) if b == "B50" else None)
ax.axhline(0, color="black", lw=0.8)
ax.set_xticks(A, ALAB)
ax.set_xlabel("Quantile level of the forecast")
ax.set_ylabel("Share of perfect-information saving")
ax.set_title("(a) Value", fontsize=9, loc="left")
ax.legend(frameon=False, fontsize=6.8, loc="lower center", bbox_to_anchor=(0.5, 1.08), ncol=2)

ax = axs[1]
mae = V["R3_quantiles"]["median_monthly_mae_kwh"]
ax.plot(A, [mae[q] for q in Q], "o-", color=GREY, ms=5, lw=1.3, label="LightGBM quantile")
m6 = V["R6_tsfm"]["median_monthly_mae_kwh"]
ax.plot([0, 3], [m6["B50"], m6["B90"]], "D", mfc="white", mec=GREY, color=GREY, ms=5.5, label="Chronos-Bolt")
ax.axhline(mae["F4"], color=GREY, lw=0.9, ls="--", label="LightGBM (squared error)")
ax.set_xticks(A, ALAB)
ax.set_xlabel("Quantile level of the forecast")
ax.set_ylabel("Median monthly MAE (kWh per hour)")
ax.set_title("(b) Accuracy", fontsize=9, loc="left")
ax.legend(frameon=False, fontsize=6.8, loc="lower center", bbox_to_anchor=(0.5, 1.08), ncol=1)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_quantile_value.pdf"))
plt.close(fig)
print("figure written")
