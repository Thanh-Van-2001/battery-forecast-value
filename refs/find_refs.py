"""Look up candidate references on Crossref by title and print DOI, venue, year, authors for manual confirmation."""
import json
import time
import urllib.parse
import urllib.request

Q = [
    "The Building Data Genome 2 data-set, an open dataset of hourly building energy meters",
    "Smart Predict, then Optimize",
    "Decision-focused learning: Foundations, state of the art, benchmark and future opportunities",
    "A survey of contextual optimization methods for decision-making under uncertainty",
    "Peak Forecasting for Battery-based Energy Optimizations in Campus Microgrids",
    "Electricity peak shaving for commercial buildings using machine learning and vehicle to building (V2B) system",
    "Robust model predictive control of battery energy storage with neural network forecasting for peak shaving in university campus",
    "Battery storage system for residential electricity peak demand shaving",
    "Probabilistic electric load forecasting: A tutorial review",
    "Making and evaluating point forecasts",
    "LightGBM: A highly efficient gradient boosting decision tree",
    "Energy dispatch schedule optimization for demand charge reduction using a photovoltaic-battery storage system with solar forecasting",
    "Sizing and optimal operation of battery energy storage system for peak load shaving application",
    "Review of smart meter data analytics: applications, methodologies, and challenges",
    "Optimizing electric vehicle chargers allocation in a V2B office building with dynamic user participation",
    "neural optimizer decision-focused learning energy storage demand charge monthly peak transformer",
    "Value-oriented forecasting renewable energy decision cost",
    "Model predictive control for demand charge management building battery",
]
UA = {"User-Agent": "ref-check/0.1 (academic citation verification)"}
for q in Q:
    u = "https://api.crossref.org/works?rows=3&query.bibliographic=" + urllib.parse.quote(q)
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
    except Exception as e:
        print("ERR", q[:60], e)
        continue
    print("\n#", q[:100])
    for it in d["message"]["items"]:
        au = ", ".join((a.get("given", "") + " " + a.get("family", "")).strip() for a in it.get("author", [])[:6])
        print("  ", it.get("DOI"), "|", (it.get("title") or [""])[0][:95], "|", (it.get("container-title") or [""])[0][:35],
              "|", it.get("issued", {}).get("date-parts", [[None]])[0][0], "|", au[:110])
    time.sleep(1)
