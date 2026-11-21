# When is a load forecast worth its accuracy? Battery scheduling in 462 buildings

Replication package for the manuscript *The most accurate load forecast is not the most valuable: a pre-specified study of battery peak shaving under demand charges in 462 buildings* (Thanh Van Nguyen, Tsinghua Shenzhen International Graduate School). An earlier version was titled *Asymmetric errors, not accuracy, decide what a load forecast is worth for battery peak shaving: a pre-specified study of 462 buildings*.

## Pre-specification
`PLAN.md` holds the analysis plan and its three amendments. The git history shows that the plan was committed before any data were downloaded (commit `5e849c8`), and when each amendment was made. Amendment 3 was written after the results and an independent review; the registered test is reported on both the registered simulation (v1, archived in `out/v1/`, code commit in `out/v1/CODE_COMMIT`) and the corrected one (v2).

The analyses in the manuscript's section "Exploratory analyses added after the pre-specified study" are in neither the plan nor its amendments: they were run after the manuscript was first submitted (code: `code/revision_explore.py`).

## Data
Building Data Genome 2 (Miller et al., *Scientific Data* 7, 2020; CC BY-SA 4.0). It is not redistributed: `code/download_bdg2.sh` downloads the three files from GitHub LFS and checks their sha256 against the LFS pointers.

## Pipeline (Python 3.12; numpy, pandas, scipy, scikit-learn, lightgbm)
| Step | Script | Output |
|---|---|---|
| download | `code/download_bdg2.sh data` | `data/*.csv` (hash-checked) |
| selection, gap filling | `code/prep.py data` | `data/prep.npz`, `prep_log.json` |
| forecasts F1-F5 and synthetic errors | `code/forecasts.py data 6` | `data/forecasts.npz` |
| battery schedules and bills | `code/simulate.py data results/bills_base.csv 6 0.10 20` | bills per building, tariff, month, policy |
| pre-specified tests | `code/analyze.py data results` | `results.json`, `accuracy.csv.gz` |
| exploratory analyses | `code/exploratory.py data results` | `exploratory.json`, `panel.csv` |
| post-submission analyses: hindsight, headroom, quantile sweep | `code/revision_explore.py data results_revision 6` (`code/run_revision.sh`) | `out_revision/raw/` |
| post-submission analysis: Chronos-Bolt (needs `chronos-forecasting`, torch) | `code/revision_tsfm.py forecast ...`, then `simulate ...` (`code/run_revision_tsfm.sh`) | `out_revision/raw/` |
| summaries of the post-submission analyses | `code/revision_analyze.py` | `out_revision/revision.json` |
| paper numbers and figures | `code/make_macros.py .`, `code/make_figures.py .`, `code/make_figures_revision.py .` | `paper/gen/macros.tex`, `paper/figures/` |
| references (Crossref, fails loudly) | `refs/build_bib.py paper/refs.bib` | `paper/refs.bib` |
| Energy and Buildings package | `paper/submission_eb/make_package_eb.py` | `paper/submission_eb/package/` |

`code/run_v2.sh` is the exact batch used for the reported (v2) run, including the robustness settings; `code/run_all.sh` the v1 batch. The result files used in the paper are in `out/` and `out_revision/`; `paper/gen/manifest.json` records their sha256. Every number in the manuscript is a macro generated from these files.

## Licence
Code: MIT (see `LICENSE`). Data: CC BY-SA 4.0, by the Building Data Genome 2 authors.
