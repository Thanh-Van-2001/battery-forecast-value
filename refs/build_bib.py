"""Build refs.bib from Crossref BibTeX for verified DOIs (fails loudly if a DOI does not resolve), plus three
non-DOI entries checked by hand against arXiv / the NeurIPS proceedings. Run: python build_bib.py <out.bib>"""
import re
import sys
import time
import urllib.request

DOIS = {
    "miller2020bdg2": "10.1038/s41597-020-00712-x",
    "elmachtoub2022spo": "10.1287/mnsc.2020.3922",
    "mandi2024dfl": "10.1613/jair.1.15320",
    "sadana2025survey": "10.1016/j.ejor.2024.03.020",
    "soman2020peak": "10.1145/3396851.3397751",
    "ghafoori2023v2b": "10.1016/j.apenergy.2023.121052",
    "mary2025rmpc": "10.1016/j.jobe.2025.112445",
    "leadbetter2012battery": "10.1016/j.enbuild.2012.09.035",
    "hong2016probabilistic": "10.1016/j.ijforecast.2015.11.011",
    "gneiting2011point": "10.1198/jasa.2011.r10138",
    "hanna2014dispatch": "10.1016/j.solener.2014.02.020",
    "oudalov2007sizing": "10.1109/pct.2007.4538388",
    "wang2019smartmeter": "10.1109/tsg.2018.2818167",
    "jiang2026v2b": "10.1016/j.enbuild.2025.116863",
    "kim2025neural": "10.1109/tii.2025.3597951",
    "stratigakos2021value": "10.1109/powertech46648.2021.9494832",
    "papadopoulos2020peak": "10.3390/en13051183",
    "murphy1993good": "10.1175/1520-0434(1993)008<0281:wiagfa>2.0.co;2",
    "hyndman2006another": "10.1016/j.ijforecast.2006.03.001",
    "gneiting2007scoring": "10.1198/016214506000001437",
    "pinson2007trading": "10.1109/tpwrs.2007.901117",
    "miller2020gepiii": "10.1080/23744731.2020.1795514",
    "vazquez2019citylearn": "10.1145/3360322.3360998",
}
EXTRA = r"""
@misc{depoortere2026dfl,
  author = {Depoortere, Joris and Kazmi, Hussain and Driesen, Johan},
  title = {Decision-focused learning for optimal {PV}-battery scheduling},
  year = {2026},
  eprint = {2605.28340},
  archivePrefix = {arXiv},
  note = {arXiv preprint arXiv:2605.28340}
}
@inproceedings{emami2023buildingsbench,
  author = {Emami, Patrick and Sahu, Abhijeet and Graf, Peter},
  title = {{BuildingsBench}: A large-scale dataset of 900{K} buildings and benchmark for short-term load forecasting},
  booktitle = {Advances in Neural Information Processing Systems 36 (Datasets and Benchmarks Track)},
  year = {2023},
  note = {arXiv:2307.00142}
}
@inproceedings{donti2017task,
  author = {Donti, Priya L. and Amos, Brandon and Kolter, J. Zico},
  title = {Task-based end-to-end model learning in stochastic optimization},
  booktitle = {Advances in Neural Information Processing Systems 30},
  year = {2017},
  note = {arXiv:1703.04529}
}
@inproceedings{ke2017lightgbm,
  author = {Ke, Guolin and Meng, Qi and Finley, Thomas and Wang, Taifeng and Chen, Wei and Ma, Weidong and Ye, Qiwei and Liu, Tie-Yan},
  title = {{LightGBM}: A highly efficient gradient boosting decision tree},
  booktitle = {Advances in Neural Information Processing Systems 30},
  pages = {3146--3154},
  year = {2017}
}
"""
out = []
for key, doi in DOIS.items():
    url = f"https://api.crossref.org/works/{doi}/transform/application/x-bibtex"
    req = urllib.request.Request(url, headers={"User-Agent": "ref-check/0.1"})
    bib = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
    bib = re.sub(r"^@(\w+)\{[^,]+,", lambda m: "@" + m.group(1) + "{" + key + ",", bib.strip(), count=1)
    bib = re.sub(r"\s*url=\{[^}]*\},", "", bib)  # the DOI is printed; long URLs overflow the margin
    out.append(bib)
    time.sleep(0.5)
open(sys.argv[1], "w", encoding="utf-8").write("\n\n".join(out) + "\n" + EXTRA)
print(len(out) + 3, "entries written")
