18 November 2026

The Editor
Applied Energy

Dear Editor,

Please consider the enclosed manuscript, "Asymmetric errors, not accuracy, decide what a load forecast is worth for battery peak shaving: a pre-specified study of 462 buildings", for publication in Applied Energy as a research article.

Behind-the-meter batteries in commercial and institutional buildings are scheduled from load forecasts, and those forecasts are chosen almost everywhere by accuracy metrics such as the mean absolute error. The manuscript tests, on 462 real buildings from the Building Data Genome 2 data set, whether accuracy predicts the money a forecast saves under a demand-charge tariff. It does not: ranking five standard forecasters by MAE does not agree with ranking them by bill savings. The study shows why. Under-forecasts at charging hours set new monthly peaks, while over-forecasts of the same size only keep charge in reserve, so a 0.9-quantile forecaster, the least accurate on average, saved the most, and an asymmetric score (the 0.9 pinball loss) agrees with value where the MAE does not. It also shows that executing a cost-minimising day-ahead schedule open loop raises the bill in most buildings, whereas a simple real-time peak guard turns every forecaster into a saving. Without a demand charge, accuracy does not matter at all.

We believe the paper will interest Applied Energy readers who design forecasting and control for building storage: its recommendations (choose forecasters by asymmetric scores, guard schedules in real time, check the bill rather than the error) are simple to apply, and it supplies two baselines that studies of decision-focused forecasting for storage should include. The analysis plan was fixed in version control before the data were downloaded; all amendments are disclosed, and the code, plan history and result files are available at https://github.com/Thanh-Van-2001/battery-forecast-value.

The manuscript is original, has not been published elsewhere and is not under consideration by another journal. The use of generative AI tools is disclosed in the manuscript, as the journal's policy requires. The author declares no competing interests and received no specific funding.

Sincerely,

Thanh Van Nguyen
Tsinghua Shenzhen International Graduate School, Tsinghua University
felicenguyen2001@gmail.com
