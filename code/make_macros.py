"""Every number in the paper comes from here: out/{results,exploratory,prep_log}.json -> paper/gen/macros.tex (\res{key}).
Run: python make_macros.py <repo_root>"""
import hashlib
import json
import os
import sys

ROOT = sys.argv[1]
O = lambda f: json.load(open(os.path.join(ROOT, "out", f)))
R, X, P = O("results.json"), O("exploratory.json"), O("prep_log.json")
b = R["base"]
M = {}


def pv(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def pc(x, d=0):
    return f"{100 * x:.{d}f}"


def sgn(x, d=3):
    return f"{x:+.{d}f}".replace("+", "+").replace("-", "-")


M["nMeters"] = P["meters"]; M["nKept"] = P["kept"]
M["nExclMissing"] = P["excluded"]["missing>5%"]; M["nExclFlat"] = P["excluded"]["flat>=72h"]
M["nExclGap"] = P["excluded"]["gap>24h"]; M["nExclMean"] = P["excluded"]["mean<10"]
M["nSeasonal"] = P["buildings_with_seasonal_fill"]; M["filledMedPct"] = f"{100 * P['filled_share_median']:.2f}"
M["nBM"] = f"{b['building_months']:,}"; M["nBMexcl"] = b["excluded_building_months"]
M["nBMexclPct"] = pc(b["excluded_building_months"] / b["building_months"], 1)
M["nBMused"] = f"{b['building_months'] - b['excluded_building_months']:,}"
for k, tag in [("H1_tau_T1", "hone"), ("H1_tau_T1_rmse", "honermse"), ("H1_tau_T1_no_seasonal_fill", "honenofill"),
               ("H1b_guarded_tau_T1", "honeb")]:
    s = b[k]
    M[tag + "Mean"] = f"{s['mean']:.3f}"; M[tag + "Median"] = f"{s['median']:.3f}"
    M[tag + "Pos"] = pc(s["share_pos"]); M[tag + "T"] = f"{s['t']:.2f}"; M[tag + "P"] = pv(s["p"])
    M[tag + "Psign"] = pv(s["p_sign"]); M[tag + "N"] = s["n"]
h2 = b["H2"]
M["htwoRhoMae"] = f"{h2['rho_mae']['mean']:.3f}"; M["htwoRhoPeak"] = f"{h2['rho_peakmag']['mean']:.3f}"
M["htwoP"] = pv(h2["p"]); M["htwoShare"] = pc(h2["share_peak_better"])
h3 = b["H3"]
M["hthreeN"] = h3["tau_T1"]["n"]; M["hthreeTauOne"] = f"{h3['tau_T1']['mean']:.3f}"
M["hthreeTauTwo"] = f"{h3['tau_T2']['mean']:.3f}"; M["hthreeP"] = pv(h3["p"])
M["hfourShare"] = pc(b["H4"]["share_reactive_ge_best"]); M["hfourP"] = pv(b["H4"]["p"])
M["hfourbShare"] = pc(b["H4b_guarded"]["share_reactive_ge_best_guarded"]); M["hfourbP"] = pv(b["H4b_guarded"]["p"])
M["hfourbBest"] = f"{b['H4b_guarded']['median_best_guarded']:.2f}"; M["hfourbReactive"] = f"{b['H4b_guarded']['median_reactive']:.2f}"
M["hfourbBeatPct"] = pc(1 - b["H4b_guarded"]["share_reactive_ge_best_guarded"])
for h, p in b["holm"].items():
    M["holm" + h] = pv(p)
for tf in ("T1", "T2"):
    for pol, v in b["annual_share_" + tf].items():
        k = pol.replace("_", "")
        M[f"sh{tf}{k}"] = f"{v['median']:.2f}"
        M[f"neg{tf}{k}"] = pc(v["share_negative"])
neg_open = [b["annual_share_T1"][m]["share_negative"] for m in ["F1", "F2", "F3", "F4", "F5"]]
M["negOpenLo"] = pc(min(neg_open)); M["negOpenHi"] = pc(max(neg_open))
neg_open4 = [b["annual_share_T1"][m]["share_negative"] for m in ["F1", "F2", "F3", "F4"]]
M["negOpenFourLo"] = pc(min(neg_open4)); M["negOpenFourHi"] = pc(max(neg_open4))
g = [b["annual_share_T1"]["G_" + m]["median"] for m in ["F1", "F2", "F3", "F4", "F5"]]
M["shGuardLo"] = f"{min(g):.2f}"; M["shGuardHi"] = f"{max(g):.2f}"
o = [b["annual_share_T1"][m]["median"] for m in ["F1", "F2", "F3", "F4", "F5"]]
M["shOpenLo"] = f"{min(o):.2f}"; M["shOpenHi"] = f"{max(o):.2f}"
M["synFriedP"] = pv(b["synthetic_T1"]["friedman_p"]); M["synFriedPg"] = pv(b["synthetic_T1_guarded"]["friedman_p"])
M["modLF"] = f"{b['moderators']['spearman_lf']:.2f}"; M["modCV"] = f"{b['moderators']['spearman_cv']:.2f}"
for m, v in R["accuracy_median_mae_kwh"].items():
    M["mae" + m.replace("_", "")] = f"{v:.2f}"
for m, v in X["median_rel_mae"].items():
    M["relmae" + m.replace("_", "")] = pc(v, 1)
for m, v in X["median_rel_bias"].items():
    M["relbias" + m.replace("_", "")] = f"{100 * v:+.1f}"
M["mostAccOpen"] = pc(X["most_accurate_is_most_valuable_open"]); M["mostAccGuard"] = pc(X["most_accurate_is_most_valuable_guarded"])
M["rhoBiasOpen"] = f"{X['spearman_bias_share_open']:.2f}"; M["rhoBiasGuard"] = f"{X['spearman_bias_share_guarded']:.2f}"
M["rhoMaeOpen"] = f"{X['spearman_mae_share_open']:.2f}"; M["rhoMaeGuard"] = f"{X['spearman_mae_share_guarded']:.2f}"
for t in ("b05", "b20", "dc10", "dc30"):
    s = R[t]["H1_tau_T1"]
    M["rob" + t + "Mean"] = f"{s['mean']:+.3f}"; M["rob" + t + "P"] = pv(s["p"]); M["rob" + t + "Pos"] = pc(s["share_pos"])
    M["rob" + t + "Excl"] = R[t]["excluded_building_months"]
robs = [abs(R[t]["H1_tau_T1"]["mean"]) for t in ("base", "b05", "b20", "dc10", "dc30")] + [abs(b["H1b_guarded_tau_T1"]["mean"])]
M["robMaxAbsTau"] = f"{max(robs):.2f}"
Fa = O("facts.json")
M["bdgBuildings"] = f"{Fa['bdg2_buildings']:,}"; M["bdgSites"] = Fa["bdg2_sites"]; M["keptSites"] = Fa["kept_sites"]
M["scaleMed"] = f"{Fa['scale_median_pct']:.1f}"; M["scaleLo"] = f"{Fa['scale_q25_pct']:.1f}"; M["scaleHi"] = f"{Fa['scale_q75_pct']:.1f}"
M["meanLoadMed"] = f"{Fa['mean_load_median']:.0f}"
for k, v in Fa["top_uses"].items():
    M["use" + "".join(w[0] for w in k.replace("/", " ").split())] = v
import pandas as pd
acc = pd.read_csv(os.path.join(ROOT, "out", "accuracy.csv.gz"))
rk = acc[acc.model.isin(["F1", "F2", "F3", "F4", "F5"])].pivot_table(index=["building", "month"], columns="model", values="mae").rank(axis=1)
for m in rk.columns:
    M["rank" + m] = f"{rk[m].mean():.2f}"; M["worst" + m] = pc((rk[m] == 5).mean()); M["best" + m] = pc((rk[m] == 1).mean())
S3 = json.load(open(os.path.join(ROOT, "smoke", "prep_log_3h_rule.json")))
M["nKeptThreeH"] = S3["kept"]; M["nExclThreeH"] = S3["excluded"]["gap>3h"]

os.makedirs(os.path.join(ROOT, "paper", "gen"), exist_ok=True)
with open(os.path.join(ROOT, "paper", "gen", "macros.tex"), "w") as fh:
    fh.write("% generated by code/make_macros.py - do not edit\n\\makeatletter\n")
    for k, v in sorted(M.items()):
        fh.write(f"\\expandafter\\def\\csname res@{k}\\endcsname{{{v}}}\n")
    fh.write("\\makeatother\n\\newcommand{\\res}[1]{\\ifcsname res@#1\\endcsname\\csname res@#1\\endcsname\\else\\textbf{??#1??}\\fi}\n")
man = {f: hashlib.sha256(open(os.path.join(ROOT, "out", f), "rb").read()).hexdigest()
       for f in ["results.json", "exploratory.json", "prep_log.json", "panel.csv", "facts.json", "accuracy.csv.gz"]}
json.dump(man, open(os.path.join(ROOT, "paper", "gen", "manifest.json"), "w"), indent=1)
print(len(M), "macros")
