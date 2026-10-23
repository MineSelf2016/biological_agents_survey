"""Validate data/*.yaml and regenerate README.md and docs/data.js from it.

    python scripts/build.py          # validate + write
    python scripts/build.py --check  # validate only; non-zero exit on errors
"""
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE_URL = "https://mineself2016.github.io/biological_agents_survey/"
PAPER_URL = "https://academic.oup.com/bib/article/27/1/bbag075/8499367"
DIMENSIONS = ["task", "architecture", "interaction", "evaluation", "resources"]
LATEST_N = 20
READING_N = 15
FIRST_YEAR_PAGE = 2025
TOP_VENUE = re.compile(r"^(nature|science|cell\b|the new england|nejm|the lancet|lancet)", re.I)
RESOURCE_FILES = [
    ("benchmarks", "Benchmarks"),
    ("libraries", "Libraries"),
    ("knowledge_sources", "Knowledge Sources"),
    ("tools", "Tools"),
]


def load(name):
    with open(DATA / f"{name}.yaml") as f:
        return yaml.safe_load(f) or []


def validate(taxonomy, papers):
    errors, ids = [], Counter(p.get("id") for p in papers)
    errors += [f"duplicate id: {i}" for i, n in ids.items() if n > 1]
    for p in papers:
        pid = p.get("id", "<missing id>")
        for field in ("id", "title", "url", "year"):
            if not p.get(field):
                errors.append(f"{pid}: missing {field}")
        for dim in DIMENSIONS:
            allowed = taxonomy[dim]["categories"]
            for tag in p.get(dim) or []:
                if tag not in allowed:
                    errors.append(f"{pid}: unknown {dim} tag '{tag}'")
        if p.get("added"):
            try:
                dt.date.fromisoformat(str(p["added"]))
            except ValueError:
                errors.append(f"{pid}: added is not YYYY-MM-DD")
    return errors


def label(taxonomy, dim, tag):
    return taxonomy[dim]["categories"][tag]["label"]


def anchor(text):
    keep = "".join(c for c in text.lower() if c.isalnum() or c in " -")
    return keep.replace(" ", "-")


def coverage_table(taxonomy, papers, col_dim):
    cols = list(taxonomy[col_dim]["categories"])
    head = ["Task \\ " + taxonomy[col_dim]["label"]] + [label(taxonomy, col_dim, c) for c in cols]
    rows = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for t in taxonomy["task"]["categories"]:
        cells = []
        for c in cols:
            n = sum(t in (p.get("task") or []) and c in (p.get(col_dim) or []) for p in papers)
            cells.append(str(n) if n else "·")
        rows.append(f"| {label(taxonomy, 'task', t)} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def resource_section(title, items):
    out = [f"### {title}\n"]
    by_cat = {}
    for r in items:
        by_cat.setdefault(r.get("category") or "other", []).append(r)
    for cat, rs in by_cat.items():
        if len(by_cat) > 1:
            out.append(f"**{cat.title()}**\n")
        for r in rs:
            sub = f" — {r['subtitle']}" if r.get("subtitle") else ""
            meta = [str(x) for x in (r.get("organization"), r.get("venue"), r.get("year")) if x]
            meta_str = f" · {' '.join(meta)}" if meta else ""
            out.append(f"- **[{r['name']}]({r['url']})**{sub}{meta_str}")
            if r.get("summary"):
                out.append(f"  <details><summary>Summary</summary>\n\n  {r['summary']}\n\n  </details>\n")
        out.append("")
    return "\n".join(out)


def compact_line(taxonomy, p):
    venue = f" · *{p['venue']}*" if p.get("venue") else ""
    tags = [label(taxonomy, d, t) for d in DIMENSIONS for t in p.get(d) or []]
    tag_str = " " + " ".join(f"`{t}`" for t in tags) if tags else ""
    dagger = " †" if p.get("in_survey") else ""
    name = f"**{p['name']}**: " if p.get("name") else ""
    return f"- {name}[{p['title']}]({p['url']}){dagger} · {pub_month(p)}{venue}{tag_str}"


def pub_month(p):
    d = str(p.get("date") or "")
    if len(d) >= 7:
        return dt.date(int(d[:4]), int(d[5:7]), 1).strftime("%b %Y")
    return str(p["year"])


def score(p, today):
    d = str(p.get("date") or "")
    months = 12
    if len(d) >= 7:
        months = max(1, (today.year - int(d[:4])) * 12 + today.month - int(d[5:7]) + 1)
    top = bool(TOP_VENUE.match(p.get("venue") or ""))
    return (1e6 if p.get("featured") else 0) + 10 * (p.get("citations") or 0) / months + 5 * top


def year_file(year):
    return f"papers/{year}.md" if year >= FIRST_YEAR_PAGE else "papers/earlier.md"


def build_year_page(taxonomy, papers, title):
    parts = [f"# {title}\n", f"[← Back to the main page](../README.md) · {len(papers)} papers · "
             "† cited in the survey\n"]
    for tag, meta in taxonomy["task"]["categories"].items():
        group = [p for p in papers if (p.get("task") or [None])[0] == tag]
        if not group:
            continue
        group.sort(key=lambda p: (str(p.get("date") or p["year"])), reverse=True)
        parts.append(f"## {meta['label']} ({len(group)})\n")
        parts += [compact_line(taxonomy, p) for p in group]
        parts.append("")
    return "\n".join(parts)


def build_resources_page(resources):
    parts = ["# Building blocks\n", "[← Back to the main page](README.md)\n",
             "Benchmarks, libraries, knowledge sources and tools that biological agents are built on and evaluated with.\n"]
    for key, title in RESOURCE_FILES:
        if resources[key]:
            parts.append(resource_section(title, resources[key]))
    return "\n".join(parts)


def build_readme(taxonomy, papers, resources, today):
    badge_date = today.isoformat().replace("-", "--")
    latest = sorted((p for p in papers if p.get("date")), key=lambda p: str(p["date"]), reverse=True)[:LATEST_N]
    picks = sorted(papers, key=lambda p: score(p, today), reverse=True)[:READING_N]
    years = sorted({p["year"] for p in papers}, reverse=True)
    pages = {}
    for p in papers:
        pages.setdefault(year_file(p["year"]), []).append(p)
    page_links = " · ".join(
        f"[{f[7:-3].title()}]({f}) ({len(pages[f])})" for f in sorted(pages, key=lambda f: f if f[7:-3].isdigit() else "", reverse=True))
    parts = [f"""# AI Agents in Biology

<p align="center">
  <a href="{SITE_URL}"><img src="images/project_page.png" width="860" alt="Project page: monthly publication trend and recommended reading"></a>
</p>
<p align="center">
  <b><a href="{SITE_URL}">Open the project page →</a></b><br>
  <sub>Filter all {len(papers)} papers by the five taxonomy dimensions, follow the monthly trend, and find recommended reading.</sub>
</p>

[![papers](https://img.shields.io/badge/papers-{len(papers)}-2a78d6)](#all-papers)
[![updated](https://img.shields.io/badge/updated-{badge_date}-1baf7a)](#latest-papers)
[![website](https://img.shields.io/badge/project-page-6250d6)]({SITE_URL})

Companion resource for

> **[Artificial Intelligence agents for biological research: a survey]({PAPER_URL})**
> Cong Qi\\*, Wenbo Wang\\*, Siqi Jiang, Qin Liu, Xun Song, Hanzhang Fang, Zhi Wei.
> *Briefings in Bioinformatics* 27(1), bbag075 (2026).

A curated, weekly updated list of LLM-driven AI agents for biological and biomedical research,
from journals, bioRxiv, medRxiv and arXiv. Every paper is tagged on the survey's five dimensions:
biological task, system architecture, interaction mode, evaluation strategy and resource integration.
**[Browse it on the project page]({SITE_URL})** to filter by any combination of tags and see
how the field grows month by month.

![taxonomy](images/taxonomy_r1_sj.png)
"""]

    parts.append("## Recommended reading\n")
    parts.append("Most-cited papers per month since publication (citation counts from OpenAlex).\n")
    for p in picks:
        cites = f" · {p['citations']} citations" if p.get("citations") else ""
        parts.append(compact_line(taxonomy, p) + cites)
    parts.append("")

    parts.append(f"## Latest papers\n")
    parts += [compact_line(taxonomy, p) for p in latest]
    parts.append(f"\nSee the [{years[0]} list]({year_file(years[0])}) for more.\n")

    parts.append(f"""## Where the field is

Counts across all {len(papers)} papers; a paper can sit in more than one cell.

**Task × architecture**

{coverage_table(taxonomy, papers, "architecture")}

**Task × resource integration**

{coverage_table(taxonomy, papers, "resources")}
""")

    parts.append(f"""## All papers

Grouped by year, then by biological task: {page_links}.

Benchmarks, agent libraries, knowledge sources and bioinformatics tools are listed in [resources.md](resources.md).
""")

    parts.append("""## Contributing

Missing a paper? Open an issue with the **Add a paper** template, or send a pull request that
appends an entry to [`data/papers.yaml`](data/papers.yaml):

```yaml
- id: shortname-2026            # unique, lowercase
  name: ShortName               # optional
  title: "Full paper title"
  url: https://doi.org/...
  date: 2026-05-14
  year: 2026
  venue: Nature Methods
  code: https://github.com/...   # optional
  summary: Two or three sentences on what the system does.
  task: [multi-omics]
  architecture: [multi-agent]
  interaction: [step-by-step]
  evaluation: [automated]
  resources: [tool-augmented]
```

Allowed tag values are listed in [`data/taxonomy.yaml`](data/taxonomy.yaml).
`python scripts/build.py` validates the data and regenerates this README, the year pages and the project page data.

## Citation

```bibtex
@article{qi2026artificial,
  title={Artificial Intelligence agents for biological research: a survey},
  author={Qi, Cong and Wang, Wenbo and Jiang, Siqi and Liu, Qin and Song, Xun and Fang, Hanzhang and Wei, Zhi},
  journal={Briefings in Bioinformatics},
  volume={27},
  number={1},
  pages={bbag075},
  year={2026},
  publisher={Oxford University Press}
}
```
""")
    return "\n".join(parts), pages


def main(check_only=False):
    taxonomy = load("taxonomy")
    papers = load("papers")
    resources = {k: load(k) for k, _ in RESOURCE_FILES}
    errors = validate(taxonomy, papers)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        sys.exit(1)
    if check_only:
        print(f"ok: {len(papers)} papers")
        return
    today = dt.date.today()
    readme, pages = build_readme(taxonomy, papers, resources, today)
    (ROOT / "README.md").write_text(readme)
    (ROOT / "papers").mkdir(exist_ok=True)
    for f, group in pages.items():
        title = f"Papers from {f[7:-3]}" if f[7:-3].isdigit() else f"Papers before {FIRST_YEAR_PAGE}"
        (ROOT / f).write_text(build_year_page(taxonomy, group, title))
    (ROOT / "resources.md").write_text(build_resources_page(resources))
    payload = {"generated": today.isoformat(), "taxonomy": taxonomy, "papers": papers,
               **resources}
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "data.js").write_text(
        "window.SURVEY = " + json.dumps(payload, ensure_ascii=False, default=str) + ";\n")
    print(f"wrote README.md, {len(pages)} year pages, resources.md and docs/data.js: {len(papers)} papers")


if __name__ == "__main__":
    main(check_only="--check" in sys.argv)
