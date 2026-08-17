#!/usr/bin/env python3
"""Collect public Greenhouse listings as compact, versioned research observations.

Full descriptions are never republished. The public export contains source metadata,
derived classifications, hashes, and short evidence spans linked to the original.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "sources.json").read_text())
DB_PATH = ROOT / "data" / "observatory.sqlite"
PUBLIC_PATH = ROOT / "public" / "api" / "observatory.json"
APOCALYPSO_PATH = ROOT / "public" / "api" / "apocalypso" / "jobs-signal.json"
HISTORY_PATH = ROOT / "data" / "history.ndjson"

SKILLS = {
    "Python": ["python"], "PyTorch": ["pytorch"], "TensorFlow": ["tensorflow"],
    "Kubernetes": ["kubernetes", "k8s"], "AWS": ["aws", "amazon web services"],
    "LLMs": ["large language model", "llm", "foundation model"],
    "RAG": ["retrieval augmented", "retrieval-augmented", "rag"],
    "Agents": ["agentic", " ai agent", "agents"], "Evaluation": ["evaluation", "evals"],
    "Robotics": ["robotics", "autonomy", "perception"], "SQL": ["sql"],
    "C++": ["c++"], "Go": ["golang", " go "], "TypeScript": ["typescript"],
    "Transformers": ["transformer"], "Vector search": ["vector search", "embedding"],
    "Safety": ["ai safety", "model safety", "red team"], "Governance": ["governance", "compliance"]
}
LAYERS = {
    "data": ["data pipeline", "dataset", "data quality", "labeling"],
    "training": ["training", "fine-tun", "pretrain"],
    "evaluation": ["evaluation", "evals", "benchmark", "red team"],
    "serving": ["inference", "serving", "latency", "deployment"],
    "product": ["product", "customer", "user experience"],
    "infrastructure": ["infrastructure", "distributed system", "cluster", "kubernetes"],
    "safety": ["safety", "alignment", "governance", "responsible ai"]
}
RELATIONSHIPS = {
    "builds": ["build", "develop", "train", "research"],
    "deploys": ["deploy", "production", "integrate", "implement"],
    "governs": ["govern", "compliance", "policy", "responsible ai"],
    "evaluates": ["evaluat", "benchmark", "test", "quality"],
    "uses": ["use ai", "ai-enabled", "leverage ai"]
}

def clean_html(value: str) -> str:
    value = re.sub(r"<(br|/p|/li|/h\d)>\s*", ". ", value or "", flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()

def contains(text: str, term: str) -> bool:
    if len(term.strip()) <= 4:
        return bool(re.search(r"(?<![a-z0-9])" + re.escape(term.strip()) + r"(?![a-z0-9])", text, re.I))
    return term.lower() in text.lower()

def evidence(text: str, terms: list[str]) -> str | None:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        if any(contains(sentence, term) for term in terms):
            return sentence[:280].strip()
    return None

def matches(text: str, ontology: dict[str, list[str]]) -> list[dict]:
    found = []
    for label, terms in ontology.items():
        quote = evidence(text, terms)
        if any(contains(text, term) for term in terms) and quote:
            found.append({"label": label, "evidence": quote})
    return found

def seniority(title: str) -> str:
    t = title.lower()
    if any(x in t for x in ["chief", "vp", "vice president", "director", "head of"]): return "Leadership"
    if any(x in t for x in ["principal", "staff", "fellow"]): return "Staff+"
    if any(x in t for x in ["senior", "sr.", "lead"]): return "Senior"
    if any(x in t for x in ["intern", "new grad", "associate", "junior"]): return "Early career"
    return "Mid-level / unspecified"

def domain(title: str, text: str) -> str:
    t, v = title.lower(), text[:1800].lower()
    if any(x in t for x in ["robot", "autonomy", "perception", "embedded", "guidance", "flight"]): return "Robotics & embedded"
    if any(x in t for x in ["safety", "policy", "governance", "alignment", "red team", "trust"]): return "Safety & governance"
    if any(x in t for x in ["scientist", "research", "biology", "science"]): return "Scientific AI"
    if any(x in t for x in ["product", "program manager", "business", "director", "head of", "manager"]): return "Product & leadership"
    if any(x in t for x in ["education", "learning", "training", "curriculum"]): return "Education & training"
    if any(x in v for x in ["robotics", "autonomous vehicle", "embedded system"]): return "Robotics & embedded"
    if any(x in v for x in ["ai safety", "responsible ai", "model governance"]): return "Safety & governance"
    return "ML engineering"

def compensation(text: str) -> dict | None:
    candidates = re.findall(r"\$([1-9]\d{1,2}(?:,\d{3})+)(?:\.\d+)?\s*(?:-|–|to)\s*\$?([1-9]\d{1,2}(?:,\d{3})+)", text, re.I)
    for low, high in candidates:
        lo, hi = int(low.replace(",", "")), int(high.replace(",", ""))
        if 20_000 <= lo <= hi <= 1_000_000:
            return {"currency": "USD", "minimum": lo, "maximum": hi, "period": "annual", "explicit": True}
    return None

def fetch_board(board: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Castalia-AI-Labor-Observatory/0.1 (+https://jobs.castalia.institute)"})
    with urllib.request.urlopen(req, timeout=40) as response:
        return json.load(response).get("jobs", [])

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS observations (
        observation_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, employer TEXT NOT NULL,
        title TEXT NOT NULL, url TEXT NOT NULL, location TEXT, retrieved_at TEXT NOT NULL,
        source_updated_at TEXT, content_hash TEXT NOT NULL, payload_json TEXT NOT NULL
      );
      CREATE UNIQUE INDEX IF NOT EXISTS idx_observations_source_hash ON observations(source_id, content_hash);
      CREATE INDEX IF NOT EXISTS idx_observations_retrieved_at ON observations(retrieved_at);
      CREATE INDEX IF NOT EXISTS idx_observations_employer ON observations(employer);
    """)

def main() -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    previous_export = json.loads(PUBLIC_PATH.read_text()) if PUBLIC_PATH.exists() else {"observations": []}
    previous = {item["sourceId"]: item for item in previous_export.get("observations", [])}
    candidates = []
    for source in CONFIG["greenhouse"]:
        try:
            jobs = fetch_board(source["board"])
        except Exception as exc:
            print(f"warning: {source['employer']}: {exc}", file=sys.stderr)
            continue
        for job in jobs:
            body = clean_html(job.get("content", ""))
            title = clean_html(job.get("title", ""))
            haystack = (title + " " + body).lower()
            if not any(k in haystack for k in ["artificial intelligence", "machine learning", " ai ", "llm", "language model", "robot", "autonomy"]):
                continue
            source_id = f"greenhouse:{source['board']}:{job['id']}"
            digest = hashlib.sha256((title + "\n" + body).encode()).hexdigest()
            skill_hits = matches(body, SKILLS)
            layer_hits = matches(body, LAYERS)
            relationship_hits = matches(body, RELATIONSHIPS)
            record = {
                "observationId": f"{source_id}:{digest[:12]}", "sourceId": source_id,
                "employer": source["employer"], "title": title,
                "location": clean_html((job.get("location") or {}).get("name", "Remote / unspecified")),
                "sourceUrl": job.get("absolute_url"), "retrievedAt": now,
                "sourceUpdatedAt": job.get("updated_at"), "contentHash": f"sha256:{digest}",
                "seniority": seniority(title), "domain": domain(title, body),
                "compensation": compensation(body),
                "classifications": {
                    "aiRelationship": relationship_hits[:3], "systemLayer": layer_hits[:3],
                    "skills": skill_hits[:8],
                    "laborEffect": {"label": "augmentation", "inferred": True, "basis": "Role language describes humans using or building AI; verify longitudinally."},
                    "humanRole": {"label": "decision-maker" if seniority(title) in ["Leadership", "Staff+"] else "builder / operator", "inferred": True},
                    "maturity": {"label": "production scaling" if any(x in haystack for x in ["production", "scale", "reliability", "latency"]) else "productization", "inferred": True}
                },
                "descriptionPolicy": "metadata-and-evidence-only",
                "duplicateGroup": hashlib.sha256(f"{source['employer']}|{title.lower()}|{clean_html((job.get('location') or {}).get('name', ''))}".encode()).hexdigest()[:16]
            }
            candidates.append(record)

    candidates.sort(key=lambda x: (x.get("sourceUpdatedAt") or "", x["title"]), reverse=True)
    by_employer: dict[str, list[dict]] = defaultdict(list)
    for record in candidates:
        by_employer[record["employer"]].append(record)
    records = []
    while len(records) < int(CONFIG["maximumObservations"]):
        added = False
        for employer in sorted(by_employer):
            if by_employer[employer] and len(records) < int(CONFIG["maximumObservations"]):
                records.append(by_employer[employer].pop(0))
                added = True
        if not added: break
    for record in records:
        prior = previous.get(record["sourceId"])
        same = prior and prior.get("contentHash") == record["contentHash"]
        record["version"] = int(prior.get("version", 1)) if same else int(prior.get("version", 0)) + 1 if prior else 1
        record["firstSeen"] = prior.get("firstSeen", prior.get("retrievedAt")) if prior else now
        record["lastSeen"] = now
        record["changeType"] = "unchanged" if same else "revised" if prior else "new"
        record["previousObservationId"] = prior.get("observationId") if prior and not same else None
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    for r in records:
        conn.execute("INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?)", (
            r["observationId"], r["sourceId"], r["employer"], r["title"], r["sourceUrl"],
            r["location"], r["retrievedAt"], r["sourceUpdatedAt"], r["contentHash"], json.dumps(r, separators=(",", ":"))))
    conn.execute("PRAGMA optimize")
    conn.commit()

    skill_counts = Counter(hit["label"] for r in records for hit in r["classifications"]["skills"])
    domains = Counter(r["domain"] for r in records)
    employers = Counter(r["employer"] for r in records)
    changes = Counter(r["changeType"] for r in records)
    changes["disappeared"] = len(set(previous) - {r["sourceId"] for r in records})
    compensated = [r for r in records if r["compensation"]]
    midpoint = sorted((r["compensation"]["minimum"] + r["compensation"]["maximum"]) / 2 for r in compensated)
    median_pay = int(midpoint[len(midpoint)//2]) if midpoint else None
    export = {
        "schemaVersion": "0.1.0", "generatedAt": now, "scope": "Curated public US-focused AI job listings",
        "methodNote": "Listings are observations, not unique jobs. Inferences are labeled and retain evidence where available.",
        "summary": {"observations": len(records), "employers": len(employers), "employerMix": employers, "changes": changes, "compensationCoverage": round(len(compensated)/len(records), 3) if records else 0, "medianAdvertisedPayMidpoint": median_pay, "topSkills": skill_counts.most_common(8), "domains": domains},
        "payBenchmarks": [
          {"occupation":"Data scientists","medianAnnualPay":112590,"year":2024,"source":"BLS OEWS","sourceUrl":"https://www.bls.gov/ooh/math/data-scientists.htm"},
          {"occupation":"Software developers","medianAnnualPay":133080,"year":2024,"source":"BLS OOH","sourceUrl":"https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm"},
          {"occupation":"Computer and information research scientists","medianAnnualPay":140910,"year":2024,"source":"BLS OOH","sourceUrl":"https://www.bls.gov/ooh/computer-and-information-technology/computer-and-information-research-scientists.htm"}
        ],
        "observations": records
    }
    PUBLIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_PATH.write_text(json.dumps(export, indent=2) + "\n")
    APOCALYPSO_PATH.parent.mkdir(parents=True, exist_ok=True)
    apocalypso = {
        "schemaVersion": "apocalypso.signal.v1", "generatedAt": now, "module": "AI", "source": "jobs.castalia.institute",
        "signal": {"id": "labor.ai_job_design", "name": "AI job-design pressure", "value": min(1, round((domains.get("ML engineering", 0) + domains.get("Product & leadership", 0)) / max(len(records), 1), 3)), "unit": "index_0_1", "direction": "higher_means_more_operationalization"},
        "context": export["summary"], "sourceUrl": "https://jobs.castalia.institute/api/observatory.json"
    }
    APOCALYPSO_PATH.write_text(json.dumps(apocalypso, indent=2) + "\n")
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if HISTORY_PATH.exists():
        history = [json.loads(line) for line in HISTORY_PATH.read_text().splitlines() if line.strip()]
    daily = {"date": now[:10], "generatedAt": now, **export["summary"]}
    history = [item for item in history if item.get("date") != daily["date"]] + [daily]
    HISTORY_PATH.write_text("".join(json.dumps(item, separators=(",", ":")) + "\n" for item in history[-730:]))
    print(f"exported {len(records)} observations from {len(employers)} employers")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
