# Pre-analysis plan: when does a better load forecast lower a building's electricity bill?

Fixed on 2026-11-17, before any data are downloaded. Analyses not listed here are reported as exploratory.

## Question
For a behind-the-meter battery scheduled day-ahead from a load forecast, does a more accurate forecast (by the usual accuracy metrics) lead to a lower bill, across a large population of real buildings and two tariff structures? Which forecast errors matter, and when does forecasting beat a reactive rule that needs no forecast?

Related work trains forecasters on decision cost for a few buildings (about 20). This study does not propose a new learning method; it measures, on about 1,500 buildings, how well accuracy metrics rank forecasters by decision value.

## Data
Building Data Genome 2 (Miller et al., Scientific Data 2020; CC BY-SA 4.0): hourly whole-building electricity, 2016-2017, with site weather. Training year 2016, test year 2017.
Inclusion: electricity meters with at least 95% non-missing hours in each year, no run of 72 or more identical consecutive readings, and mean load at least 10 kWh/h. Missing hours are linearly interpolated for runs up to 3 h; buildings needing more are excluded.

## Decision model
- Battery: power rating P = 10% of the building's 2016 peak; energy capacity 2P (2 hours); round-trip efficiency 90% (charge and discharge 94.87% each); state of charge between 10% and 90%, starting each day at 50%, ending each day at 50%.
- Tariffs: (T1) time-of-use energy prices (0.20 $/kWh 12:00-18:00 on weekdays, 0.10 $/kWh otherwise) plus a monthly demand charge of 20 $/kW on the month's highest hourly net load; (T2) the same energy prices without a demand charge.
- Day-ahead schedule: at 00:00 the battery's 24 hourly powers are chosen by a linear program on the forecast load, minimising energy cost plus, under T1, the demand charge on the excess of the day's forecast peak net load over the month-to-date realised peak. The schedule is then executed against the actual load (open loop, clipped to state-of-charge limits).
- Benchmarks: no battery; the same daily program with the actual load (perfect information); and a reactive rule that needs no forecast (charge at the cheapest hours up to 90% SoC; discharge whenever the realised load exceeds the month-to-date peak, up to P).
- Decision value of a forecaster in a building-month = share of the perfect-information saving captured: (bill without battery - bill with forecaster) / (bill without battery - bill with perfect information).

## Forecasters (day-ahead, 24 hourly values, information up to 00:00)
F1 seasonal naive (same hour, previous day); F2 seasonal naive (same hour, previous week); F3 ridge regression on calendar features, loads lagged 24/48/168 h and temperature; F4 gradient-boosted trees (LightGBM) on the same features; F5 the same model trained on the 0.9 quantile (peak-conservative). Models are fitted per building on 2016 and not refitted. Temperature is the observed value (a perfect weather forecast), stated as a limitation. Synthetic forecasts for the mechanism analysis: actual load plus (a) Gaussian noise, (b) a +/-1 h timing shift, (c) a 5% scale error, at matched MAE.

## Accuracy metrics
MAE, RMSE, MAPE (on hours with load > 0), error at the hour of the actual daily peak, error of the forecast daily peak magnitude, and the daily-peak timing error (hours).

## Hypotheses and primary analysis
- H1 (primary): within a building, the ranking of F1-F5 by monthly MAE agrees with their ranking by decision value under T1. Measure: Kendall's tau between MAE (sign-reversed) and captured share across the five forecasters, per building and month, averaged over months; report its distribution over buildings and test its mean against zero (t-test over buildings, with a sign test).
- H2: under T1, peak-magnitude error predicts captured share better than MAE (paired comparison of per-building rank correlations, Wilcoxon signed-rank).
- H3: the agreement in H1 is higher under T2 than T1 (paired Wilcoxon over buildings).
- H4: the reactive rule captures at least as much of the perfect-information saving as the best forecaster under T1 in at least half of the buildings (sign test).
- H2-H4 are corrected with Holm's method.

## Moderators (descriptive)
Building primary use, load-factor (mean/peak), day-to-day variability, and site; regression of the best forecaster's captured share on these.

## Amendment 1 (2026-11-18, code written, before any data were loaded)
- Captured share is undefined when perfect information saves almost nothing. Building-months where the perfect-information saving is below 0.5% of the no-battery bill are excluded from share-based tests; their number is reported. Annual shares sum bills over the remaining months.
- The executed state of charge is not carried over: each day's schedule starts and ends at 50%, and energy left above 50% after open-loop clipping is forfeited (a small penalty on poor forecasts, the same rule for all forecasters).
- The reactive rule under T2 (no demand charge) discharges in the expensive hours and charges in the cheap hours; under T1 it also never charges above the month-to-date peak.

## Amendment 2 (2026-11-18, after a 6-building pipeline check, before the full run)
Disclosure: the pipeline was first run on the first 6 eligible buildings to check the code (outputs kept in `smoke/`). Its outcomes were seen: under T1 every forecaster, executed open loop, captured a negative share of the perfect-information saving, the reactive rule a positive one, and among the same-MAE synthetic forecasts the 1-hour shift was worst and the 5% scale error best. Two changes follow; the hypotheses H1-H4 and their tests are unchanged and are reported on the open-loop controller as registered.
- **Gap rule.** The 3-hour rule kept only 188 of 1,578 meters (543 excluded for one longer gap), far below the intended population. Gaps of 4-24 hours are now filled with the load at the same hour one week earlier (or later); meters with a gap above 24 hours, or more than 5% missing hours in a year, are still excluded. The pre-listed robustness check without such buildings is reported.
- **Guarded execution (secondary).** Open-loop execution ignores the realised load, which no operator does. A second controller uses the same day-ahead schedule but never charges above the month-to-date realised peak and discharges to hold the realised load at that peak when it is exceeded. H1 and H4 are repeated for it (H1b, H4b) and the synthetic error types are compared under it. These are secondary analyses, labelled as added after the pipeline check.

## Date correction
Amendments 1 and 2 are headed 2026-11-18 above; they were committed on 2026-11-17 at 23:45 and 23:53 (+07:00). The commit timestamps are authoritative.

## Amendment 3 (2026-11-18, after the full results and an independent review)
Disclosure: written after all v1 results (archived in `out/v1/`, code commit in `out/v1/CODE_COMMIT`) and a referee-style review were seen. The registered tests on v1 stay the primary results. A corrected simulation (v2) is reported alongside them:
- **Bug fix.** The guarded controller and the reactive rule reset the month-to-date peak to zero at each month start, which emptied the battery at 00:00 of day 1. The guard threshold is now max(month-to-date realised peak, the day's planned peak z); the reactive threshold is max(month-to-date realised peak, the previous month's realised peak).
- **State of charge carried over.** Each day starts from the state of charge left by the previous day (all policies); the day's schedule still ends at half charge. This removes both the forfeited and the free energy of the daily reset.
- **Reactive rule.** Charges only on weekday mornings (T1: never above its threshold); under T2 discharges only in weekday expensive hours.
- **Synthetic errors.** Two more same-MAE forecasts: a uniform under-forecast (mirror of the over-forecast) and hourly AR(1) noise (rho = 0.9). The multiplier of the one-hour lag error is reported.
- **Exploratory additions.** H1 among F1-F4 only; H1 with two asymmetric metrics (mean under-forecast error, 0.9 pinball loss); the pre-listed half-year split; the probability that the most accurate forecaster is the most valuable compared with its independence baseline (ties counted); within-building rank correlations; savings in % of the bill and $ per kW-year.

## Robustness (pre-listed)
Battery sizes of 5% and 20% of peak; demand charge of 10 and 30 $/kW; RMSE instead of MAE in H1; excluding buildings with interpolated hours; a second test year split (first half vs second half of 2017).
