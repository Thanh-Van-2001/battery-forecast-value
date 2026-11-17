# When is a load forecast worth its accuracy? Battery scheduling in 462 buildings

Replication package for the manuscript *Asymmetric errors, not accuracy, decide what a load forecast is worth for battery peak shaving: a pre-specified study of 462 buildings* (Thanh Van Nguyen, Tsinghua Shenzhen International Graduate School).

## Pre-specification
`PLAN.md` holds the analysis plan and its three amendments. The git history shows that the plan was committed before any data were downloaded (commit `5e849c8`), and when each amendment was made. Amendment 3 was written after the results and an independent review; the registered test is reported on both the registered simulation (v1, archived in `out/v1/`, code commit in `out/v1/CODE_COMMIT`) and the corrected one (v2).

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
| paper numbers and figures | `code/make_macros.py .`, `code/make_figures.py .` | `paper/gen/macros.tex`, `paper/figures/` |

`code/run_v2.sh` is the exact batch used for the reported (v2) run, including the robustness settings; `code/run_all.sh` the v1 batch. The result files used in the paper are in `out/`; `paper/gen/manifest.json` records their sha256. Every number in the manuscript is a macro generated from these files.

## Licence
Code: MIT (see `LICENSE`). Data: CC BY-SA 4.0, by the Building Data Genome 2 authors.
