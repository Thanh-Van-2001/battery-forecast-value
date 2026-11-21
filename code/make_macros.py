"""Every number in the paper comes from here: out/{results,exploratory,prep_log}.json -> paper/gen/macros.tex (\res{key}).
Run: python make_macros.py <repo_root>"""
import hashlib
import json
import os
import sys

ROOT = sys.argv[1]
O = lambda f: json.load(open(os.path.join(ROOT, "out", f)))
R, X, P = O("results.json"), O("exploratory.json"), O("prep_log.json")  # v2 (amendment 3)
R1 = O("v1/results.json")  # v1: the simulation exactly as registered
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
def ci(s):
    """95% CI of a summary; v1 summaries lack it, so it is rebuilt from mean and t"""
    if "ci_lo" in s:
        return s["ci_lo"], s["ci_hi"]
    from scipy import stats as _st
    se = abs(s["mean"] / s["t"]) if s["t"] else float("nan")
    h = _st.t.ppf(0.975, s["n"] - 1) * se
    return s["mean"] - h, s["mean"] + h


def tau_macros(tag, s):
    M[tag + "Mean"] = f"{s['mean']:.3f}"; M[tag + "Median"] = f"{s['median']:.3f}"
    M[tag + "Pos"] = pc(s["share_pos"]); M[tag + "T"] = f"{s['t']:.2f}"; M[tag + "P"] = pv(s["p"])
    M[tag + "Psign"] = pv(s["p_sign"]); M[tag + "N"] = s["n"]
    lo, hi = ci(s)
    M[tag + "Lo"] = f"{lo:.3f}"; M[tag + "Hi"] = f"{hi:.3f}"


b1 = R1["base"]
tau_macros("vone", b1["H1_tau_T1"])  # registered test on the registered simulation
tau_macros("voneb", b1["H1b_guarded_tau_T1"])
for k, tag in [("H1_F1toF4_open", "fourOpen"), ("H1_F1toF4_guarded", "fourGuard"), ("H1_under_open", "underOpen"),
               ("H1_under_guarded", "underGuard"), ("H1_pinball09_open", "pinOpen"), ("H1_pinball09_guarded", "pinGuard"),
               ("H1_first_half", "halfOne"), ("H1_second_half", "halfTwo")]:
    tau_macros(tag, b[k])
for r, v in b["guarded_beats_reactive"].items():
    M["beatReact" + r] = pc(v)
gb = list(b["guarded_beats_reactive"].values())
M["beatReactLo"] = pc(min(gb)); M["beatReactHi"] = pc(max(gb))
M["exclTOne"] = b["excluded_by_tariff"].get("T1", 0); M["exclTTwo"] = b["excluded_by_tariff"].get("T2", 0)
M["indepOpen"] = pc(X["independence_baseline_open"]); M["indepGuard"] = pc(X["independence_baseline_guarded"])
M["mostValFfiveOpen"] = pc(X["most_valuable_share_open"]["F5"]); M["mostValFfiveGuard"] = pc(X["most_valuable_share_guarded"]["F5"])
M["mostAccFfour"] = pc(X["most_accurate_share"]["F4"])
M["kappaMed"] = f"{X['shift_kappa']['median']:.1f}"; M["kappaLo"] = f"{X['shift_kappa']['q25']:.1f}"; M["kappaHi"] = f"{X['shift_kappa']['q75']:.1f}"
M["wRhoBiasOpen"] = f"{X['within_spearman_bias_share_open']:.2f}"; M["wRhoBiasGuard"] = f"{X['within_spearman_bias_share_guarded']:.2f}"
M["wRhoMaeOpen"] = f"{X['within_spearman_mae_share_open']:+.2f}"; M["wRhoMaeGuard"] = f"{X['within_spearman_mae_share_guarded']:+.2f}"
mo = X["money"]
for k, v in mo.items():
    if isinstance(v, dict):
        kk = k.replace("_", "")
        M["pct" + kk] = f"{v['pct_median']:.2f}"; M["usd" + kk] = f"{v['usd_per_kw_yr_median']:.0f}"
M["billTOne"] = f"{mo['T1_bill_none_median_usd'] / 1000:.0f}"; M["billTTwo"] = f"{mo['T2_bill_none_median_usd'] / 1000:.0f}"
for t in [t for t in ("b05", "b20", "dc10", "dc30") if t in R]:
    s = R[t]["H1b_guarded_tau_T1"]
    M["robg" + t + "Mean"] = f"{s['mean']:+.3f}"; M["robg" + t + "P"] = pv(s["p"])
M["nBM"] = f"{b['building_months']:,}"; M["nBMexcl"] = b["excluded_building_months"]
M["nBMexclPct"] = pc(b["excluded_building_months"] / b["building_months"], 1)
M["nBMused"] = f"{b['building_months'] - b['excluded_building_months']:,}"
for k, tag in [("H1_tau_T1", "hone"), ("H1_tau_T1_rmse", "honermse"), ("H1_tau_T1_no_seasonal_fill", "honenofill"),
               ("H1b_guarded_tau_T1", "honeb")]:
    tau_macros(tag, b[k])
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
for t in [t for t in ("b05", "b20", "dc10", "dc30") if t in R]:
    s = R[t]["H1_tau_T1"]
    M["rob" + t + "Mean"] = f"{s['mean']:+.3f}"; M["rob" + t + "P"] = pv(s["p"]); M["rob" + t + "Pos"] = pc(s["share_pos"])
    M["rob" + t + "Excl"] = R[t].get("excluded_by_tariff", {}).get("T1", R[t]["excluded_building_months"])
robs = [abs(R[t]["H1_tau_T1"]["mean"]) for t in ("base", "b05", "b20", "dc10", "dc30") if t in R]
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

# ---------------------------------------------------------------- post-submission exploratory analyses (prefix rv)
# out_revision/revision.json, written by code/revision_analyze.py from the titan runs of revision_explore.py and
# revision_tsfm.py. Not pre-specified; reported in the section "Exploratory analyses added after the pre-specified study".
RVF = os.path.join(ROOT, "out_revision", "revision.json")
if os.path.exists(RVF):
    V = json.load(open(RVF))
    NAME = {"F1": "Fone", "F2": "Ftwo", "F3": "Fthree", "F4": "Ffour", "F5": "Ffive", "Q50": "Qfifty", "Q70": "Qseventy",
            "Q80": "Qeighty", "Q90": "Qninety", "Q95": "Qninetyfive", "B50": "Bfifty", "B90": "Bninety"}

    def rv_tau(tag, s):
        M["rv" + tag] = f"{s['mean']:.3f}"; M["rv" + tag + "Lo"] = f"{s['ci'][0]:.3f}"
        M["rv" + tag + "Hi"] = f"{s['ci'][1]:.3f}"; M["rv" + tag + "Pos"] = pc(s["share_pos"]); M["rv" + tag + "P"] = pv(s["p"])

    def rv_annual(prefix, a):
        """median annual share (and IQR), % of buildings with a higher bill, saving in % of bill and $/kW-yr"""
        M[prefix + "Sh"] = f"{a['median']:.2f}"; M[prefix + "Up"] = pc(a["share_buildings_bill_up"])
        M[prefix + "Pct"] = f"{a['pct_of_bill_median']:.2f}"; M[prefix + "Usd"] = f"{a['usd_per_kw_yr_median']:.0f}"
        if "q25" in a:
            M[prefix + "ShLo"] = f"{a['q25']:.2f}"; M[prefix + "ShHi"] = f"{a['q75']:.2f}"

    # reproduction checks of the new code against the submitted run
    chk = max(V[k] for k in ("check_max_abs_diff_PI", "check_max_abs_diff_none", "check_max_abs_diff_F5_vs_Q90",
                             "check_max_abs_diff_GF5_vs_GQ90"))
    M["rvCheckMaxDiff"] = f"{chk:.1f}"; M["rvCheckHone"] = f"{V['check_H1_open_reproduced']['mean']:.3f}"
    M["rvLpFail"] = V["lp_failures"] + V.get("lp_failures_tsfm", 0) + V["hindsight_failures"]
    # R1 monthly hindsight benchmark
    h1, h2 = V["R1_hindsight"]["T1"], V["R1_hindsight"]["T2"]
    M["rvHindCapt"] = pc(h1["daily_PI_share_of_hindsight_saving_median"], 1)
    M["rvHindCaptLo"] = pc(h1["daily_PI_share_q25"], 1); M["rvHindCaptHi"] = pc(h1["daily_PI_share_q75"], 1)
    M["rvHindCaptTtwo"] = pc(h2["daily_PI_share_of_hindsight_saving_median"], 0)
    M["rvHindPct"] = f"{h1['hindsight_saving_pct_of_bill_median']:.2f}"
    M["rvHindDailyPct"] = f"{h1['daily_PI_saving_pct_of_bill_median']:.2f}"
    hs = h1["annual_share_of_hindsight_median"]
    for pol, v in hs.items():
        M["rvHindSh" + pol.replace("_", "")] = f"{v:.2f}"
    pols = ["reactive"] + [m for m in ("F1", "F2", "F3", "F4", "F5")] + ["G_" + m for m in ("F1", "F2", "F3", "F4", "F5")]
    M["rvHindMaxDiff"] = f"{max(abs(hs[p] - b['annual_share_T1'][p]['median']) for p in pols):.2f}"
    # R2 headroom margin in the day-ahead program
    for mm, tag in (("H05", "Hfive"), ("H10", "Hten")):
        r = V["R2_headroom"][mm]
        rv_tau(tag + "Open", r["H1_open"]); rv_tau(tag + "Guard", r["H1_guarded"])
        rv_tau(tag + "Pin", r["H1_open_pinball"]); rv_tau(tag + "Four", r["H1_open_F1toF4"])
        for f in ("F1", "F2", "F3", "F4", "F5"):
            rv_annual("rv" + tag + NAME[f], r["annual"][f"{mm}_{f}"])
            rv_annual("rv" + tag + "G" + NAME[f], r["annual"][f"G_{mm}_{f}"])
        up = [r["annual"][f"{mm}_{f}"]["share_buildings_bill_up"] for f in ("F1", "F2", "F3", "F4")]
        M["rv" + tag + "UpFourLo"] = pc(min(up)); M["rv" + tag + "UpFourHi"] = pc(max(up))
        gp = [r["annual"][f"G_{mm}_{f}"]["pct_of_bill_median"] for f in ("F1", "F2", "F3", "F4", "F5")]
        M["rv" + tag + "GPctLo"] = f"{min(gp):.2f}"; M["rv" + tag + "GPctHi"] = f"{max(gp):.2f}"
        osh = [r["annual"][f"{mm}_{f}"]["median"] for f in ("F1", "F2", "F3", "F4")]
        M["rv" + tag + "ShFourLo"] = f"{min(osh):.2f}"; M["rv" + tag + "ShFourHi"] = f"{max(osh):.2f}"
    # R3 quantile sweep (LightGBM, F4/F5 features; Q90 is F5 refitted)
    r3 = V["R3_quantiles"]
    for f in ("F1", "F2", "F3", "F4", "Q50", "Q70", "Q80", "Q90", "Q95"):
        M["rvRankNine" + NAME[f]] = f"{r3['mean_mae_rank_of_nine'][f]:.2f}"
        M["rvMae" + NAME[f]] = f"{r3['median_monthly_mae_kwh'][f]:.2f}"
        rv_annual("rvQ" + NAME[f], r3["annual"][f]); rv_annual("rvQG" + NAME[f], r3["annual"]["G_" + f])
    for f, v in r3["median_monthly_rel_bias"].items():
        M["rvBias" + NAME[f]] = f"{100 * v:+.1f}"
    rv_tau("QonlyOpen", r3["H1_quantiles_only_open"]); rv_tau("QonlyGuard", r3["H1_quantiles_only_guarded"])
    rv_tau("NineOpen", r3["H1_nine_open"]); rv_tau("NineGuard", r3["H1_nine_guarded"])
    rv_tau("NinePin", r3["H1_nine_open_pinball"]); rv_tau("NineUnder", r3["H1_nine_open_under"])
    # R5 within-building regression with building fixed effects, cluster-robust standard errors
    for col, tag in (("share_open", "Open"), ("share_guarded", "Guard")):
        r = V["R5_fe_regression"][col]
        M["rvFeMae" + tag] = f"{r['beta_rel_mae_per_pp']:+.4f}"; M["rvFeMaeSe" + tag] = f"{r['se_rel_mae']:.4f}"
        M["rvFeBias" + tag] = f"{r['beta_rel_bias_per_pp']:+.4f}"; M["rvFeBiasSe" + tag] = f"{r['se_rel_bias']:.4f}"
        M["rvFeN"] = f"{r['n_obs']:,}"
    # R6 zero-shot foundation-model forecaster (Chronos-Bolt small): B50 median, B90 0.9 quantile
    r6 = V["R6_tsfm"]
    rv_tau("SevenOpen", r6["H1_seven_open"]); rv_tau("SevenGuard", r6["H1_seven_guarded"])
    rv_tau("SevenPin", r6["H1_seven_open_pinball"])
    for f, v in r6["mean_mae_rank_of_seven"].items():
        M["rvRankSeven" + NAME[f]] = f"{v:.2f}"
    for f, v in r6["median_monthly_mae_kwh"].items():
        M["rvMaeSeven" + NAME[f]] = f"{v:.2f}"
    for f, v in r6["median_monthly_rel_bias"].items():
        M["rvBias" + NAME[f]] = f"{100 * v:+.1f}"
    M["rvBfiftyBeatsFfour"] = pc(r6["B50_more_accurate_than_F4_share_of_months"])
    for f in ("B50", "B90"):
        rv_annual("rv" + NAME[f], r6["annual"][f]); rv_annual("rvG" + NAME[f], r6["annual"]["G_" + f])

os.makedirs(os.path.join(ROOT, "paper", "gen"), exist_ok=True)
with open(os.path.join(ROOT, "paper", "gen", "macros.tex"), "w") as fh:
    fh.write("% generated by code/make_macros.py - do not edit\n\\makeatletter\n")
    for k, v in sorted(M.items()):
        fh.write(f"\\expandafter\\def\\csname res@{k}\\endcsname{{{v}}}\n")
    fh.write("\\makeatother\n\\newcommand{\\res}[1]{\\ifcsname res@#1\\endcsname\\csname res@#1\\endcsname\\else\\textbf{??#1??}\\fi}\n")
man = {f: hashlib.sha256(open(os.path.join(ROOT, "out", f), "rb").read()).hexdigest()
       for f in ["results.json", "exploratory.json", "prep_log.json", "panel.csv", "facts.json", "accuracy.csv.gz"]}
if os.path.exists(RVF):
    man["../out_revision/revision.json"] = hashlib.sha256(open(RVF, "rb").read()).hexdigest()
json.dump(man, open(os.path.join(ROOT, "paper", "gen", "manifest.json"), "w"), indent=1)
print(len(M), "macros")
