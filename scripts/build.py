"""Validate data/*.yaml and regenerate README.md and docs/data.js from it.

    python scripts/build.py          # validate + write
    python scripts/build.py --check  # validate only; non-zero exit on errors
"""
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SITE_URL = "https://mineself2016.github.io/biological_agents_survey/"
PAPER_URL = "https://academic.oup.com/bib/article/27/1/bbag075/8499367"
DIMENSIONS = ["task", "architecture", "interaction", "evaluation", "resources"]
RECENT_DAYS = 120
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


def is_recent(p, today):
    added = p.get("added")
    return bool(added) and (today - dt.date.fromisoformat(str(added))).days <= RECENT_DAYS


def paper_line(taxonomy, p, primary_task=None):
    venue = f" · *{p['venue']}*" if p.get("venue") else ""
    tags = [label(taxonomy, d, t) for d in DIMENSIONS for t in p.get(d) or []
            if not (d == "task" and t == primary_task)]
    tag_str = " " + " ".join(f"`{t}`" for t in tags) if tags else ""
    code = f" · [code]({p['code']})" if p.get("code") else ""
    dagger = " †" if p.get("in_survey") else ""
    out = [f"- **[{p['title']}]({p['url']})**{dagger} · {p['year']}{venue}{code}{tag_str}"]
    if p.get("summary"):
        out.append(f"  <details><summary>Summary</summary>\n\n  {p['summary']}\n\n  </details>\n")
    return "\n".join(out)


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


def build_readme(taxonomy, papers, resources, today):
    recent = sorted((p for p in papers if is_recent(p, today)),
                    key=lambda p: str(p["added"]), reverse=True)
    badge_date = today.isoformat().replace("-", "--")
    parts = [f"""# AI Agents in Biology

[![papers](https://img.shields.io/badge/papers-{len(papers)}-2a78d6)](#papers-by-biological-task)
[![updated](https://img.shields.io/badge/updated-{badge_date}-1baf7a)](#recently-added)
[![explorer](https://img.shields.io/badge/interactive-explorer-6250d6)]({SITE_URL})

Companion resource for

> **[Artificial Intelligence agents for biological research: a survey]({PAPER_URL})**
> Cong Qi\\*, Wenbo Wang\\*, Siqi Jiang, Qin Liu, Xun Song, Hanzhang Fang, Zhi Wei.
> *Briefings in Bioinformatics* 27(1), bbag075 (2026).

Every paper is tagged on all five dimensions of the survey's taxonomy — biological task,
system architecture, interaction mode, evaluation strategy and resource integration.
**[Open the interactive explorer]({SITE_URL})** to filter by any combination of tags,
see where the field is crowded or empty, and track growth over time.

This README is generated from [`data/`](data/) by `scripts/build.py`; please edit the
YAML rather than this file (see [Contributing](#contributing)).

![taxonomy](images/taxonomy_r1_sj.png)
"""]

    parts.append("## Recently added\n")
    if recent:
        parts += [paper_line(taxonomy, p) for p in recent]
    else:
        parts.append(f"_Nothing added in the last {RECENT_DAYS} days._")
    parts.append("")

    parts.append(f"""## Where the field is

Counts across all {len(papers)} papers; a paper can sit in more than one cell.
Empty cells (·) are combinations nobody has published yet.

**Task × architecture**

{coverage_table(taxonomy, papers, "architecture")}

**Task × resource integration**

{coverage_table(taxonomy, papers, "resources")}
""")

    parts.append("## Papers by biological task\n")
    parts.append("Each paper is listed once, under its first task tag; its other tags follow the title. † cited in the survey.\n")
    for tag, meta in taxonomy["task"]["categories"].items():
        group = [p for p in papers if (p.get("task") or [None])[0] == tag]
        if not group:
            continue
        group.sort(key=lambda p: (-p["year"], p["title"]))
        parts.append(f"### {meta['label']}\n\n_{meta['description']}_\n")
        parts += [paper_line(taxonomy, p, primary_task=tag) for p in group]
        parts.append("")
    untagged = [p for p in papers if not p.get("task")]
    if untagged:
        parts.append("### Not yet classified\n")
        parts += [paper_line(taxonomy, p) for p in untagged]
        parts.append("")

    parts.append("## Building blocks\n")
    parts.append("Benchmarks, libraries, knowledge sources and tools that biological agents are built on and evaluated with.\n")
    for key, title in RESOURCE_FILES:
        if resources[key]:
            parts.append(resource_section(title, resources[key]))

    parts.append("""## Contributing

New papers are welcome — open an issue with the **Add a paper** template, or send a pull
request that appends an entry to [`data/papers.yaml`](data/papers.yaml):

```yaml
- id: shortname-2026            # unique, lowercase
  title: "Full paper title"
  url: https://doi.org/...
  year: 2026
  venue: Nature Methods
  code: https://github.com/...   # optional
  summary: Two or three sentences on what the system does.
  task: [multi-omics]
  architecture: [multi-agent]
  interaction: [step-by-step]
  evaluation: [automated]
  resources: [tool-augmented]
  added: 2026-10-22
```

Allowed tag values are listed in [`data/taxonomy.yaml`](data/taxonomy.yaml).
Run `python scripts/build.py` to validate and regenerate this README and the explorer data.

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
    return "\n".join(parts)


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
    (ROOT / "README.md").write_text(build_readme(taxonomy, papers, resources, today))
    payload = {"generated": today.isoformat(), "taxonomy": taxonomy, "papers": papers,
               **resources}
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "data.js").write_text(
        "window.SURVEY = " + json.dumps(payload, ensure_ascii=False, default=str) + ";\n")
    print(f"wrote README.md and docs/data.js: {len(papers)} papers")


if __name__ == "__main__":
    main(check_only="--check" in sys.argv)
