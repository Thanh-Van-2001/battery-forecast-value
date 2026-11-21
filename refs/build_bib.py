"""Build refs.bib from Crossref BibTeX for verified DOIs (fails loudly if a DOI does not resolve), plus
non-DOI entries checked by hand against arXiv / the NeurIPS proceedings (arXiv entries: arXiv API, 22 Nov 2026). Run: python build_bib.py <out.bib>"""
import re
import sys
import time
import unicodedata
import urllib.request

# accented Latin letters as LaTeX accents, so that BibTeX can abbreviate a first name such as Angel with an acute
# accent to its initial (a raw UTF-8 letter is cut in half and breaks pdflatex)
ACC = {"́": "'", "̀": "`", "̂": "^", "̈": '"', "̃": "~", "̧": "c", "̌": "v",
       "̄": "=", "̊": "r", "̆": "u", "̋": "H"}


def accent(ch):
    if ord(ch) < 128:
        return ch
    d = unicodedata.normalize("NFD", ch)
    if len(d) == 2 and d[0].isascii() and d[0].isalpha() and d[1] in ACC:
        a = ACC[d[1]]
        return "{\\" + a + d[0] + "}" if not a.isalpha() else "{\\" + a + "{" + d[0] + "}}"
    return ch

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
    # revision kit (20 Nov 2026): prior work found by the post-submission OpenAlex sweep, checked against Crossref
    "putz2023truevalue": "10.1016/j.segan.2022.100983",
    "valle2027riskaware": "10.1016/j.apenergy.2026.128975",
    "sesay2026quantile": "10.1016/j.ijepes.2026.112076",
    # the arXiv preprint 2605.28340 cited at submission is now published (Journal of Energy Storage)
    "depoortere2026dfl": "10.1016/j.est.2026.121152",
    # Energy and Buildings version (22 Nov 2026): references added for the 2024-2026 literature,
    # each DOI checked against Crossref on 22 Nov 2026 (title, authors, venue and year as printed)
    "katholnigg2025impact": "10.1145/3736425.3772098",
    "hossen2026ptoev": "10.1016/j.jer.2026.11.019",
    "smets2025valueprice": "10.1016/j.energy.2025.137112",
    "zhang2025valueoriented": "10.1109/tsg.2024.3503554",
    "paredes2025dflreserve": "10.1016/j.segan.2025.101677",
    "cortesaguirre2025empc": "10.1109/tsg.2025.3600047",
    "perezpineiro2026tiered": "10.1007/s11081-026-10103-7",
    "langtry2024data": "10.1016/j.enbuild.2024.114605",
    "park2025tsfmbuildings": "10.1016/j.enbuild.2025.116446",
    "liao2025timegpt": "10.1016/j.apenergy.2024.124973",
}
EXTRA = r"""
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
@misc{ansari2024chronos,
  author = {Ansari, Abdul Fatir and Stella, Lorenzo and Turkmen, Caner and others},
  title = {Chronos: Learning the language of time series},
  year = {2024},
  howpublished = {arXiv preprint arXiv:2403.07815}
}
@misc{ansari2025chronos2,
  author = {Ansari, Abdul Fatir and Shchur, Oleksandr and K{\"u}ken, Jaris and others},
  title = {Chronos-2: From univariate to universal forecasting},
  year = {2025},
  howpublished = {arXiv preprint arXiv:2510.15821}
}
@misc{das2024timesfm,
  author = {Das, Abhimanyu and Kong, Weihao and Sen, Rajat and Zhou, Yichen},
  title = {A decoder-only foundation model for time-series forecasting},
  year = {2023},
  howpublished = {arXiv preprint arXiv:2310.10688}
}
@misc{woo2024moirai,
  author = {Woo, Gerald and Liu, Chenghao and Kumar, Akshat and Xiong, Caiming and Savarese, Silvio and Sahoo, Doyen},
  title = {Unified training of universal time series forecasting transformers},
  year = {2024},
  howpublished = {arXiv preprint arXiv:2402.02592}
}
@misc{saleptsis2026dfl,
  author = {Saleptsis, Marios and Lesage-Landry, Antoine and Mussetta, Marco and Leva, Sonia},
  title = {Decision-focused learning for optimal battery scheduling under load and photovoltaic power uncertainty in microgrids},
  year = {2026},
  howpublished = {arXiv preprint arXiv:2610.14782}
}
"""
out = []
for key, doi in DOIS.items():
    url = f"https://api.crossref.org/works/{doi}/transform/application/x-bibtex"
    req = urllib.request.Request(url, headers={"User-Agent": "ref-check/0.1"})
    for attempt in range(6):  # Crossref rate-limits bursts (HTTP 429): back off and retry
        try:
            bib = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 5:
                raise
            time.sleep(10 * (attempt + 1))
    bib = re.sub(r"^@(\w+)\{[^,]+,", lambda m: "@" + m.group(1) + "{" + key + ",", bib.strip(), count=1)
    bib = re.sub(r"\s*url=\{[^}]*\},", "", bib)  # the DOI is printed; long URLs overflow the margin
    bib = bib.replace("&amp;", r"\&")  # Crossref returns an HTML entity in some journal names
    bib = "".join(accent(ch) for ch in bib)
    # keep acronyms and camel-case names upper case in the title (the style lower-cases titles): EV, MPC, PV-BESS, TimeGPT
    bib = re.sub(r"(\btitle=\{)([^}]*)\}", lambda m: m.group(1) + re.sub(
        r"(?<![{\w])([A-Za-z]*[A-Z][A-Za-z0-9]*[A-Z0-9][A-Za-z0-9]*)(?![\w}])",
        lambda w: "{" + w.group(1) + "}" if sum(c.isupper() for c in w.group(1)) >= 2 or w.group(1)[1:2].isupper() else w.group(1),
        m.group(2)) + "}", bib, count=1)
    out.append(bib)
    time.sleep(0.5)
open(sys.argv[1], "w", encoding="utf-8").write("\n\n".join(out) + "\n" + EXTRA)
print(len(out) + EXTRA.count("@"), "entries written")
