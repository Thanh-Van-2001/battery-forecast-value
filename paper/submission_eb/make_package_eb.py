"""Submission package for Energy and Buildings (Elsevier).

Builds paper/submission_eb/package/ from paper/main.tex, its sections, paper/gen/macros.tex, paper/refs.bib and
paper/figures, plus the templates in this folder (highlights.md, title_page.md, cover_letter.md):

  manuscript.pdf, manuscript_anonymized.pdf   identified and anonymized builds of the same flat source
  latex_source.zip, latex_source_anonymized.zip   flat (no folders); each proved to compile on its own, in a fresh
                                              directory, from the included .bbl and again with bibtex
  title_page.pdf, title_page.docx, highlights.docx, cover_letter.docx
  abstract_plain.txt, keywords.txt, highlights.txt   text for the portal's typed fields
  build_info.json

No number is typed here: results come from paper/gen/macros.tex (written by code/make_macros.py); counts are
computed from the sources and the built PDFs. The anonymized source is made by resolving the \\ifdefined\\ANON
blocks, so the identifying branch is absent from it, not merely hidden. Exits non-zero on any failed check.

Run from the repository root:  python paper/submission_eb/make_package_eb.py [png_dir]
"""
import datetime
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

import fitz

PAPER = "paper"
HERE = os.path.join(PAPER, "submission_eb")
PKG = os.path.join(HERE, "package")
PNG = sys.argv[1] if len(sys.argv) > 1 else None
AE_COMMIT = "829fbfe"  # the Applied Energy submission
FORBIDDEN = [r"nguyen", r"thanh", r"tsinghua", r"gmail", r"github", r"felice", r"shenzhen", r"\bsigs\b",
             r"holy_grail", r"users[\\/]+admin", r"titan", r"van-2001"]
FAIL = []


def check(ok, msg):
    print(("ok    " if ok else "FAIL  ") + msg)
    if not ok:
        FAIL.append(msg)


def read(p):
    return io.open(p, encoding="utf-8").read().replace("\r\n", "\n")


def write(p, s):
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


def run(cmd, cwd, inp=None):
    return subprocess.run(cmd, cwd=cwd, input=inp, capture_output=True, text=True, encoding="utf-8", errors="replace")


M = dict(re.findall(r"res@([^\\]+)\\endcsname\{([^}]*)\}", read(os.path.join(PAPER, "gen", "macros.tex"))))


# ---------------------------------------------------------------- flat sources
def resolve_anon(s, anon):
    r"""keep the \ifdefined\ANON branch that applies; the blocks are not nested"""
    pat = re.compile(r"\\ifdefined\\ANON(?![a-zA-Z])(.*?)(?:\\else(?![a-zA-Z])(.*?))?\\fi(?![a-zA-Z])", re.S)
    return pat.sub(lambda m: (m.group(1) if anon else (m.group(2) or "")).strip("\n"), s)


def flatten(anon):
    s = read(os.path.join(PAPER, "main.tex"))
    s = re.sub(r"\\input\{sections/(\w+)\}", lambda m: read(os.path.join(PAPER, "sections", m.group(1) + ".tex")).rstrip("\n"), s)
    s = s.replace(r"\input{gen/macros.tex}", r"\input{macros}")
    s = re.sub(r"\\includegraphics(\[[^]]*\])?\{figures/", r"\\includegraphics\1{", s)
    s = resolve_anon(s, anon)
    s = "\n".join(ln for ln in s.split("\n") if not ln.lstrip().startswith("%"))
    s = re.sub(r"\n{3,}", "\n\n", s)
    assert "ANON" not in s and "sections/" not in s and "figures/" not in s and "gen/" not in s
    head = ("% Energy and Buildings submission, " + ("anonymized" if anon else "identified") + " manuscript.\n"
            "% Flat source: all numbers are in macros.tex (generated from the study's result files), figures are PDF.\n"
            "% Compile: pdflatex, bibtex, pdflatex, pdflatex (the .bbl is included, so bibtex is optional).\n")
    return head + s


FIGS = sorted(set(re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([\w.]+\.pdf)\}", flatten(False))))


def stage(d, job, anon):
    write(os.path.join(d, job + ".tex"), flatten(anon))
    shutil.copy2(os.path.join(PAPER, "gen", "macros.tex"), os.path.join(d, "macros.tex"))
    shutil.copy2(os.path.join(PAPER, "refs.bib"), os.path.join(d, "refs.bib"))
    for f in FIGS:
        shutil.copy2(os.path.join(PAPER, "figures", f), os.path.join(d, f))


def latex(d, job, bibtex=True):
    """pdflatex (+ bibtex) to a fixed point; returns the log text"""
    r = run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", job], d)
    assert r.returncode == 0, io.open(os.path.join(d, job + ".log"), encoding="latin-1").read()[-3000:]
    if bibtex:
        b = run(["bibtex", job], d)
        assert b.returncode in (0, 1), b.stdout[-2000:]
    for _ in range(3):
        r = run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", job], d)
        log = io.open(os.path.join(d, job + ".log"), encoding="latin-1").read()
        if "Rerun to get" not in log and "Label(s) may have changed" not in log:
            break
    assert r.returncode == 0 and os.path.exists(os.path.join(d, job + ".pdf")), log[-3000:]
    return log


def log_checks(log, name):
    warn = re.findall(r"(?:LaTeX|Package \w+) Warning: [^\n]*", log)
    undef = [w for w in warn if "undefined" in w] + (["undefined references"] if "There were undefined" in log else [])
    check(not undef, f"{name}: no undefined citations or references" + (f" -> {undef[:5]}" if undef else ""))
    check("multiply defined" not in log, f"{name}: no multiply defined labels")
    over = re.findall(r"Overfull \\hbox \((\d+\.\d+)pt too wide\)", log)
    check(not over, f"{name}: no overfull boxes" + (f" (found {over})" if over else ""))
    check("Undefined control sequence" not in log, f"{name}: no undefined control sequences")


def pdf_text(p):
    doc = fitz.open(p)
    return doc, "\n".join(pg.get_text() for pg in doc)


def forbidden_in(text):
    return [p for p in FORBIDDEN if re.search(p, text, flags=re.I)]


def anon_pdf(p):
    doc, text = pdf_text(p)
    meta = json.dumps(doc.metadata) + (doc.get_xml_metadata() or "")
    raw = open(p, "rb").read().decode("latin-1")
    doc.close()
    hits = forbidden_in(text) + forbidden_in(meta) + forbidden_in(raw)
    check(not hits, f"anonymous: {os.path.basename(p)} text, metadata and raw bytes" + (f" -> {hits}" if hits else ""))


def anon_zip(p, label):
    with zipfile.ZipFile(p) as z:
        hits = {n: forbidden_in(z.read(n).decode("latin-1")) for n in z.namelist()}
    hits = {k: v for k, v in hits.items() if v}
    check(not hits, f"anonymous: {label}" + (f" -> {hits}" if hits else ""))


# ---------------------------------------------------------------- text helpers
def expand(s):
    return re.sub(r"\\res\{([^}]+)\}", lambda m: M[m.group(1)], s)


def to_plain(tex):
    tex = expand(tex)
    tex = re.sub(r"\$\\tau=([^$]*)\$", lambda m: "τ = " + m.group(1).replace("-", "−"), tex)
    tex = re.sub(r"\$([0-9.,−-]+)\$", lambda m: m.group(1).replace("-", "−"), tex)
    r = run(["pandoc", "-f", "latex", "-t", "plain", "--wrap=none"], ".", inp=tex)
    assert r.returncode == 0, r.stderr
    return re.sub(r"\n{3,}", "\n\n", r.stdout).strip() + "\n"


def fill(t, cnt):
    t = re.sub(r"\{res:([^}]+)\}", lambda m: M[m.group(1)], t)
    t = re.sub(r"\{cnt:([^}]+)\}", lambda m: cnt[m.group(1)], t)
    assert "{res:" not in t and "{cnt:" not in t, t
    return t


def pandoc(src_text, out, extra=()):
    r = run(["pandoc", "-f", "markdown", "-o", out, *extra], ".", inp=src_text)
    assert r.returncode == 0, r.stderr


def cite_keys(tex):
    return {k.strip() for g in re.findall(r"\\cite[tp]?\{([^}]*)\}", tex) for k in g.split(",")}


def main():
    if os.path.exists(PKG):
        shutil.rmtree(PKG)
    os.makedirs(PKG)
    info = {}

    # ---- manuscripts: identified and anonymized, from the flat source, in fresh directories
    for job, anon in (("manuscript", False), ("manuscript_anonymized", True)):
        work = tempfile.mkdtemp(prefix="eb_build_")
        stage(work, job, anon)
        log = latex(work, job)
        log_checks(log, job)
        shutil.copy2(os.path.join(work, job + ".pdf"), os.path.join(PKG, job + ".pdf"))
        doc, text = pdf_text(os.path.join(PKG, job + ".pdf"))
        pages = doc.page_count
        doc.close()
        check("??" not in text, f"{job}: no '??' (missing macro or reference) in the PDF text")
        info[job + "_pages"] = pages
        bib = run(["bibtex", job], work).stdout
        print(f"{job}: {pages} pages; bibtex warnings: {sorted(set(re.findall(r'Warning--([^\n]*)', bib)))}")
        if PNG:
            os.makedirs(PNG, exist_ok=True)
            d = fitz.open(os.path.join(PKG, job + ".pdf"))
            for i, pg in enumerate(d):
                pg.get_pixmap(dpi=90).save(os.path.join(PNG, f"{job}_p{i + 1:02d}.png"))
            d.close()

        # flat zip, then prove it compiles on its own (from the .bbl, and with bibtex)
        zname = "latex_source.zip" if not anon else "latex_source_anonymized.zip"
        zpath = os.path.join(PKG, zname)
        members = [job + ".tex", job + ".bbl", "macros.tex", "refs.bib"] + FIGS
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for f in members:
                z.write(os.path.join(work, f), f)
        with zipfile.ZipFile(zpath) as z:
            names = z.namelist()
        check(all("/" not in n and "\\" not in n for n in names), f"{zname} is flat ({len(names)} files: {names})")
        for mode in ("bbl only", "with bibtex"):
            fresh = tempfile.mkdtemp(prefix="eb_zip_")
            with zipfile.ZipFile(zpath) as z:
                z.extractall(fresh)
            if mode == "with bibtex":
                os.remove(os.path.join(fresh, job + ".bbl"))
            zlog = latex(fresh, job, bibtex=(mode == "with bibtex"))
            zdoc, ztext = pdf_text(os.path.join(fresh, job + ".pdf"))
            check(zdoc.page_count == pages and ztext == text, f"{zname} compiles standalone ({mode}): same {pages} pages, same text")
            zdoc.close()
            log_checks(zlog, f"{zname} build ({mode})")
            shutil.rmtree(fresh, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)

    # ---- anonymity of everything a reviewer sees
    anon_pdf(os.path.join(PKG, "manuscript_anonymized.pdf"))
    anon_zip(os.path.join(PKG, "latex_source_anonymized.zip"), "latex_source_anonymized.zip (every member)")
    for f in FIGS:
        anon_pdf(os.path.join(PAPER, "figures", f))
    _, t_id = pdf_text(os.path.join(PKG, "manuscript.pdf"))
    check("Thanh Van Nguyen" in t_id and "github.com" in t_id.replace("\n", ""), "identified manuscript names the author and the repository")

    # ---- abstract, keywords, title
    main_tex = read(os.path.join(PAPER, "main.tex"))
    abs_tex = read(os.path.join(PAPER, "sections", "abstract.tex"))
    plain = to_plain(abs_tex)
    write(os.path.join(PKG, "abstract_plain.txt"), plain)
    n_abs = len(plain.split())
    check(n_abs <= 250, f"abstract {n_abs} words <= 250")
    kw = re.search(r"\\begin\{keyword\}(.*?)\\end\{keyword\}", main_tex, re.S).group(1)
    kws = [k.strip() for k in kw.split("\\sep") if k.strip()]
    write(os.path.join(PKG, "keywords.txt"), "\n".join(kws) + "\n")
    check(1 <= len(kws) <= 7, f"{len(kws)} keywords (1-7)")
    title = expand(re.search(r"\\title\{(.*?)\}\n", main_tex).group(1))
    info.update(abstract_words=n_abs, keywords=kws, title=title)

    # ---- highlights: 3-5 bullets of at most 85 characters including spaces
    hl_md = fill(read(os.path.join(HERE, "highlights.md")), {})
    hl = [ln[2:].strip() for ln in hl_md.split("\n") if ln.startswith("- ")]
    check(3 <= len(hl) <= 5, f"{len(hl)} highlights (3-5)")
    for h in hl:
        check(len(h) <= 85, f"highlight {len(h)} <= 85 characters: {h}")
    pandoc(hl_md, os.path.join(PKG, "highlights.docx"))
    write(os.path.join(PKG, "highlights.txt"), "\n".join(hl) + "\n")
    info["highlights"] = hl

    # ---- title page (docx and pdf), cover letter (docx)
    decl = read(os.path.join(PAPER, "sections", "declarations.tex"))
    ai = decl[decl.index("manuscript preparation process}") + len("manuscript preparation process}"):].strip()
    assert "\\" not in ai, ai
    old = set()
    for sec in ("abstract", "intro", "related", "model", "design", "results", "discussion", "conclusion", "declarations"):
        old |= cite_keys(run(["git", "show", f"{AE_COMMIT}:paper/sections/{sec}.tex"], ".").stdout)
    new = set()
    for sec in re.findall(r"\\input\{sections/(\w+)\}", main_tex):
        new |= cite_keys(read(os.path.join(PAPER, "sections", sec + ".tex")))
    added = sorted(new - old)
    today = datetime.date.today()
    cnt = {"title": title, "keywords": "; ".join(kws), "aiDeclaration": ai, "newRefs": str(len(added)),
           "date": f"{today.day} {today:%B} {today.year}"}
    tp = fill(read(os.path.join(HERE, "title_page.md")), cnt)
    pandoc(tp, os.path.join(PKG, "title_page.docx"))
    pandoc(tp, os.path.join(PKG, "title_page.pdf"), ["--pdf-engine=pdflatex"])
    cl = fill(read(os.path.join(HERE, "cover_letter.md")), cnt)
    pandoc(cl, os.path.join(PKG, "cover_letter.docx"))
    with zipfile.ZipFile(os.path.join(PKG, "title_page.docx")) as z:
        check("Thanh Van Nguyen" in z.read("word/document.xml").decode("utf-8"), "title page names the author")
    info.update(references_cited=len(new), references_added_since_AE=added, cover_letter_words=len(cl.split()))

    json.dump(info, io.open(os.path.join(PKG, "build_info.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("\n".join(sorted(os.listdir(PKG))))
    if FAIL:
        print(f"\n{len(FAIL)} check(s) failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
