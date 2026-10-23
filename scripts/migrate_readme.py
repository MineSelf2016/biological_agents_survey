"""One-time migration: parse the legacy README.md into structured YAML under data/.

Papers that appeared under several taxonomy sections are merged into one record;
their original placements are kept in `legacy_sections` and seed the dimension tags.
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

ENTRY = re.compile(
    r"^- \*\*\[(?P<title>.+?)\]\((?P<url>(?:[^()\s]|\([^()]*\))*)\)\s*\*\*"
    r"\s*(?:\(\*(?P<year>\d{4})\*\))?\s*(?:`(?P<venue>[^`]*)`)?"
)

# H2 heading (normalised) -> (kind, dimension)
H2_MAP = {
    "1. biological task domains": ("paper", "task"),
    "2. system architecture": ("paper", "architecture"),
    "3. evaluation strategy": ("paper", "evaluation"),
    "4. interaction mode": ("paper", "interaction"),
    "resource integration": ("paper", "resources"),
    "benchmark": ("benchmark", None),
    "2. libraries": ("library", None),
    "3. knowledge source": ("knowledge_source", None),
    "4. tools": ("tool", None),
}

H3_TO_TAG = {
    "clinical decision support": "clinical-decision-support",
    "knowledge discovery and hypothesis generation": "knowledge-discovery",
    "molecular and drug design": "molecular-drug-design",
    "multi-omics analysis": "multi-omics",
    "exploratory applications": "exploratory",
    "single-agent systems": "single-agent",
    "multi-agent systems": "multi-agent",
    "neuro-symbolic integration": "neuro-symbolic",
    "knowledge-augmented agents": "knowledge-augmented",
    "tool-augmented agents": "tool-augmented",
}


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


H2_KEYS = {norm(k): v for k, v in H2_MAP.items()}
H3_KEYS = {norm(k): v for k, v in H3_TO_TAG.items()}


def slug(title, year):
    head = re.split(r"[:\-–—]", title)[0]
    words = re.sub(r"[^A-Za-z0-9 ]+", "", head).lower().split()[:5]
    return "-".join(words) + (f"-{year}" if year else "")


def parse(lines):
    h2 = h3 = None
    entries, cur = [], None
    for line in lines:
        if line.startswith("## "):
            h2, h3, cur = norm(line[3:]), None, None
            continue
        if line.startswith("### "):
            h3, cur = norm(line[4:].replace("*", "")), None
            continue
        m = ENTRY.match(line.strip())
        if m and h2 in H2_KEYS:
            kind, dim = H2_KEYS[h2]
            cur = dict(kind=kind, dimension=dim, h3=h3, summary_lines=[], **m.groupdict())
            entries.append(cur)
            continue
        if cur is not None and line.lstrip().startswith(">"):
            cur["summary_lines"].append(line.lstrip()[1:].strip())
    for e in entries:
        e["summary"] = " ".join(e.pop("summary_lines")).strip()
        e["title"] = e["title"].strip()
        e["venue"] = (e["venue"] or "").strip() or None
        e["year"] = int(e["year"]) if e["year"] else None
    return entries


def build_papers(entries):
    papers, by_title = [], {}
    for e in (x for x in entries if x["kind"] == "paper"):
        key = norm(e["title"])
        if key not in by_title:
            rec = {
                "id": slug(e["title"], e["year"]),
                "title": e["title"],
                "url": e["url"],
                "year": e["year"],
                "venue": e["venue"],
                "summary": e["summary"],
                "task": [], "architecture": [], "evaluation": [],
                "interaction": [], "resources": [],
                "legacy_sections": [],
            }
            by_title[key] = rec
            papers.append(rec)
        rec = by_title[key]
        tag = H3_KEYS.get(e["h3"]) if e["h3"] else None
        rec["legacy_sections"].append(e["dimension"] + (f"/{tag}" if tag else ""))
        if tag and tag not in rec[e["dimension"]]:
            rec[e["dimension"]].append(tag)
        if len(e["summary"]) > len(rec["summary"]):
            rec["summary"] = e["summary"]
    seen = {}
    for p in papers:
        n = seen.get(p["id"], 0)
        seen[p["id"]] = n + 1
        if n:
            p["id"] += f"-{n + 1}"
    return papers


def build_resources(entries, kind):
    out = []
    for e in (x for x in entries if x["kind"] == kind):
        name, _, subtitle = e["title"].partition(":")
        rec = {"name": name.strip(), "subtitle": subtitle.strip() or None, "url": e["url"],
               "category": e["h3"]}
        if kind == "benchmark":
            rec["year"] = e["year"]
            rec["venue"] = e["venue"]
        else:
            rec["organization"] = e["venue"]
        rec["summary"] = e["summary"]
        out.append(rec)
    return out


def dump(obj, path):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w") as f:
        yaml.safe_dump(obj, f, sort_keys=False, allow_unicode=True, width=100)


def main(readme):
    entries = parse(Path(readme).read_text().splitlines())
    papers = build_papers(entries)
    dump(papers, ROOT / "data" / "papers.yaml")
    for kind, fname in [("benchmark", "benchmarks"), ("library", "libraries"),
                        ("knowledge_source", "knowledge_sources"), ("tool", "tools")]:
        dump(build_resources(entries, kind), ROOT / "data" / f"{fname}.yaml")
    counts = {k: sum(e["kind"] == k for e in entries) for k in
              ["paper", "benchmark", "library", "knowledge_source", "tool"]}
    print(counts, "unique papers:", len(papers))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: migrate_readme.py <legacy README.md>  (e.g. git show 0d1dc74:README.md > /tmp/old.md)")
    main(sys.argv[1])
