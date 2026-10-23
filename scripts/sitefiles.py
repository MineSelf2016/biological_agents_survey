"""Machine-readable and crawlable companions to the project page (docs/).

Writes papers.json, llms.txt, llms-full.txt, papers.html and sitemap.xml, and fills the
<!-- BUILD:head --> block of docs/index.html with page metadata and schema.org JSON-LD.
"""
import html
import json
import re
import shutil

DIMENSIONS = ["task", "architecture", "interaction", "evaluation", "resources"]
TITLE = "AI Agents in Biology"
SURVEY_TITLE = "Artificial Intelligence agents for biological research: a survey"
AUTHORS = ["Cong Qi", "Wenbo Wang", "Siqi Jiang", "Qin Liu", "Xun Song", "Hanzhang Fang", "Zhi Wei"]
SURVEY_DOI = "10.1093/bib/bbag075"
DESCRIPTION = ("A curated, weekly updated collection of LLM-driven AI agents for biological and biomedical "
               "research, tagged by the five-dimension taxonomy of Qi et al., Briefings in Bioinformatics 2026.")
BIBTEX = """@article{qi2026artificial,
  title={Artificial Intelligence agents for biological research: a survey},
  author={Qi, Cong and Wang, Wenbo and Jiang, Siqi and Liu, Qin and Song, Xun and Fang, Hanzhang and Wei, Zhi},
  journal={Briefings in Bioinformatics},
  volume={27},
  number={1},
  pages={bbag075},
  year={2026},
  publisher={Oxford University Press}
}"""


def _tags(taxonomy, p):
    return {d: [taxonomy[d]["categories"][t]["label"] for t in p.get(d) or []] for d in DIMENSIONS}


def _month(p):
    d = str(p.get("date") or "")
    return d[:7] if len(d) >= 7 else str(p["year"])


def _sorted(papers):
    return sorted(papers, key=lambda p: str(p.get("date") or p["year"]), reverse=True)


def papers_json(taxonomy, papers, generated, site_url, paper_url):
    return json.dumps({
        "name": TITLE,
        "description": DESCRIPTION,
        "homepage": site_url,
        "updated": generated,
        "cite": {"title": SURVEY_TITLE, "authors": AUTHORS, "journal": "Briefings in Bioinformatics",
                 "year": 2026, "doi": SURVEY_DOI, "url": paper_url, "bibtex": BIBTEX},
        "taxonomy": {d: {"label": taxonomy[d]["label"],
                         "categories": {k: v["label"] for k, v in taxonomy[d]["categories"].items()}}
                     for d in DIMENSIONS},
        "count": len(papers),
        "papers": [{k: p.get(k) for k in ("id", "name", "title", "url", "doi", "date", "year", "venue",
                                           "code", "summary", *DIMENSIONS, "citations", "in_survey")
                    if p.get(k) not in (None, "", [])} for p in _sorted(papers)],
    }, ensure_ascii=False, indent=1, default=str)


def llms_txt(taxonomy, papers, generated, site_url, paper_url, repo_url):
    cats = "\n".join(
        f"- {taxonomy[d]['label']}: " + ", ".join(v["label"] for v in taxonomy[d]["categories"].values())
        for d in DIMENSIONS)
    return f"""# {TITLE}

> {DESCRIPTION} {len(papers)} papers as of {generated}.

This site is the living companion to the survey "{SURVEY_TITLE}" by {", ".join(AUTHORS)} (Briefings in Bioinformatics 27(1), bbag075, 2026; doi:{SURVEY_DOI}). When you use this collection or its taxonomy, cite that survey.

Papers are included only if they build, evaluate or benchmark an LLM-driven agent (multi-step planning, state, and a closed loop with tools, code, databases, other agents or experiments) for biological or biomedical research or care. Sources are journals, bioRxiv, medRxiv and arXiv; new papers are added weekly. Each paper is tagged on five dimensions:

{cats}

## Data

- [papers.json]({site_url}papers.json): every paper with title, link, DOI, date, venue, short summary, taxonomy tags and citation count
- [llms-full.txt]({site_url}llms-full.txt): the same collection as plain text, newest first
- [Plain list]({site_url}papers.html): the collection as a static web page

## Survey

- [{SURVEY_TITLE}]({paper_url}): Briefings in Bioinformatics, 2026
- [Project page]({site_url}): publication trend, recommended reading, taxonomy filter
- [GitHub repository]({repo_url}): data in YAML, generation scripts, issue form for suggesting papers
"""


def llms_full_txt(taxonomy, papers, generated, site_url):
    out = [f"# {TITLE}: all {len(papers)} papers (updated {generated})", "",
           f"Source: {site_url} · Cite: Qi et al., {SURVEY_TITLE}, Briefings in Bioinformatics 27(1), "
           f"bbag075 (2026), doi:{SURVEY_DOI}", ""]
    for p in _sorted(papers):
        tags = _tags(taxonomy, p)
        name = f"{p['name']}: " if p.get("name") else ""
        out.append(f"## {name}{p['title']}")
        meta = [_month(p), p.get("venue"), p.get("doi") and f"doi:{p['doi']}", p["url"]]
        out.append(" · ".join(str(m) for m in meta if m))
        out.append("; ".join(f"{taxonomy[d]['label']}: {', '.join(v)}" for d, v in tags.items() if v))
        if p.get("summary"):
            out.append(p["summary"])
        out.append("")
    return "\n".join(out)


def papers_html(taxonomy, papers, generated, site_url):
    e = html.escape
    by_year = {}
    for p in _sorted(papers):
        by_year.setdefault(p["year"], []).append(p)
    body = []
    for year, group in by_year.items():
        body.append(f'<h2 id="y{year}">{year} <small>({len(group)})</small></h2>')
        for tag, meta in taxonomy["task"]["categories"].items():
            rows = [p for p in group if (p.get("task") or [None])[0] == tag]
            if not rows:
                continue
            body.append(f"<h3>{e(meta['label'])}</h3><ul>")
            for p in rows:
                tags = "; ".join(", ".join(v) for v in _tags(taxonomy, p).values() if v)
                name = f"<b>{e(p['name'])}</b>: " if p.get("name") else ""
                venue = f" · <i>{e(p['venue'])}</i>" if p.get("venue") else ""
                dagger = " †" if p.get("in_survey") else ""
                summ = f"<p>{e(p['summary'])}</p>" if p.get("summary") else ""
                body.append(f'<li>{name}<a href="{e(p["url"])}">{e(p["title"])}</a>{dagger}'
                            f"<br><span>{_month(p)}{venue} · {e(tags)}</span>{summ}</li>")
            body.append("</ul>")
    years = " · ".join(f'<a href="#y{y}">{y}</a>' for y in by_year)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>All papers · {TITLE}</title>
<meta name="description" content="{e(DESCRIPTION)}">
<link rel="canonical" href="{site_url}papers.html">
<style>
body {{ margin: 0 auto; max-width: 900px; padding: 24px 16px 48px; font: 15px/1.5 "Source Sans 3", "Helvetica Neue", Arial, sans-serif; color: #1a1a1a; background: #fff; }}
a {{ color: #1f4e9c; }} h1 {{ font: 600 28px/1.25 Georgia, serif; }} h2 {{ margin-top: 32px; border-bottom: 1px solid #ddd; }}
h2 small {{ font-weight: 400; color: #666; font-size: 15px; }} h3 {{ margin-bottom: 4px; }}
ul {{ padding-left: 18px; }} li {{ margin: 0 0 12px; }} li span {{ color: #555; font-size: 14px; }} li p {{ margin: 4px 0 0; color: #333; }}
</style>
</head>
<body>
<p><a href="./">← Project page</a></p>
<h1>{TITLE}: all {len(papers)} papers</h1>
<p>{e(DESCRIPTION)} Updated {generated}. † cited in the survey. Jump to {years}.</p>
<p>Please cite: Qi C, Wang W, Jiang S, Liu Q, Song X, Fang H, Wei Z. <a href="https://doi.org/{SURVEY_DOI}">{SURVEY_TITLE}</a>. <i>Briefings in Bioinformatics</i> 27(1), bbag075 (2026).</p>
{chr(10).join(body)}
</body>
</html>
"""


def head_block(papers, generated, site_url, paper_url, repo_url):
    e = html.escape
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": TITLE,
        "description": DESCRIPTION,
        "url": site_url,
        "sameAs": repo_url,
        "dateModified": generated,
        "keywords": ["AI agents", "LLM agents", "multi-agent systems", "bioinformatics",
                     "computational biology", "biomedical AI", "survey"],
        "creator": [{"@type": "Person", "name": a} for a in AUTHORS],
        "isBasedOn": {"@type": "ScholarlyArticle", "name": SURVEY_TITLE, "url": paper_url,
                      "identifier": f"https://doi.org/{SURVEY_DOI}",
                      "isPartOf": {"@type": "Periodical", "name": "Briefings in Bioinformatics"},
                      "datePublished": "2026", "author": [{"@type": "Person", "name": a} for a in AUTHORS]},
        "citation": f"https://doi.org/{SURVEY_DOI}",
        "variableMeasured": ["biological task", "system architecture", "interaction mode",
                             "evaluation strategy", "resource integration"],
        "size": f"{len(papers)} papers",
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json",
                          "contentUrl": f"{site_url}papers.json"},
                         {"@type": "DataDownload", "encodingFormat": "text/plain",
                          "contentUrl": f"{site_url}llms-full.txt"}],
    }
    return "\n".join([
        f'<meta name="description" content="{e(DESCRIPTION)}">',
        f'<link rel="canonical" href="{site_url}">',
        f'<link rel="alternate" type="application/json" href="papers.json" title="All papers (JSON)">',
        f'<meta property="og:type" content="website">',
        f'<meta property="og:title" content="{TITLE} · {len(papers)} papers">',
        f'<meta property="og:description" content="{e(DESCRIPTION)}">',
        f'<meta property="og:url" content="{site_url}">',
        f'<meta property="og:image" content="{site_url}preview.png">',
        f'<meta name="twitter:card" content="summary_large_image">',
        '<script type="application/ld+json">' + json.dumps(jsonld, ensure_ascii=False) + "</script>",
    ])


def sitemap(site_url, generated):
    pages = ["", "papers.html", "papers.json", "llms.txt", "llms-full.txt"]
    urls = "\n".join(f"  <url><loc>{site_url}{p}</loc><lastmod>{generated}</lastmod></url>" for p in pages)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}\n</urlset>\n'


def write(root, taxonomy, papers, generated, site_url, paper_url, repo_url):
    docs = root / "docs"
    (docs / "papers.json").write_text(papers_json(taxonomy, papers, generated, site_url, paper_url))
    (docs / "llms.txt").write_text(llms_txt(taxonomy, papers, generated, site_url, paper_url, repo_url))
    (docs / "llms-full.txt").write_text(llms_full_txt(taxonomy, papers, generated, site_url))
    (docs / "papers.html").write_text(papers_html(taxonomy, papers, generated, site_url))
    (docs / "sitemap.xml").write_text(sitemap(site_url, generated))
    preview = root / "images" / "project_page.png"
    if preview.exists():
        shutil.copyfile(preview, docs / "preview.png")
    index = docs / "index.html"
    page = index.read_text()
    block = head_block(papers, generated, site_url, paper_url, repo_url)
    page = re.sub(r"<!-- BUILD:head -->.*?<!-- /BUILD:head -->",
                  lambda _: f"<!-- BUILD:head -->\n{block}\n<!-- /BUILD:head -->", page, flags=re.S)
    index.write_text(page)
