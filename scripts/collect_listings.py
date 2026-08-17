#!/usr/bin/env python3
"""Collect public ATS listings as compact, versioned research observations.

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
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "sources.json").read_text())
ONET_SKILL_DATA = json.loads((ROOT / "data" / "ontology" / "onet_30_3_skill_profiles.json").read_text())
DB_PATH = ROOT / "data" / "observatory.sqlite"
PUBLIC_PATH = ROOT / "public" / "api" / "observatory.json"
APOCALYPSO_PATH = ROOT / "public" / "api" / "apocalypso" / "jobs-signal.json"
HISTORY_PATH = ROOT / "data" / "history.ndjson"
LEDGER_PATH = ROOT / "data" / "observation_versions.ndjson"
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
METHOD_VERSION = "jobservatory-rules-0.2.3"
ONTOLOGY_VERSION = "jobservatory-ontology-0.3.0"
ONET_VERSION = "30.3"

SKILLS = {
    "Python": ["python"], "PyTorch": ["pytorch"], "TensorFlow": ["tensorflow"],
    "Kubernetes": ["kubernetes", "k8s"], "AWS": ["aws", "amazon web services"],
    "LLMs": ["large language model", "llm", "foundation model"],
    "RAG": ["retrieval augmented", "retrieval-augmented", "rag"],
    "Agents": ["agentic ai", "ai agent", "agentic system", "agentic workflow"],
    "Evaluation": ["model evaluation", "evaluate models", "ai evaluation", "llm evaluation", "evals"],
    "Robotics": ["robotics", "autonomy", "perception"], "SQL": ["sql"],
    "C++": ["c++"], "Go": ["golang", "go programming language", "programming language go", "experience with go"], "TypeScript": ["typescript"],
    "Transformers": ["transformer"], "Vector search": ["vector search", "vector database", "vector embeddings", "semantic search", "embedding model"],
    "Safety": ["ai safety", "model safety", "red team"],
    "Governance": ["ai governance", "model governance", "responsible ai", "algorithmic accountability"]
}
LAYERS = {
    "data": ["data pipeline", "dataset", "data quality", "labeling"],
    "training": ["model training", "training models", "training pipeline", "fine-tun", "pretrain", "pre-train", "post-training"],
    "evaluation": ["evaluation", "evals", "benchmark", "red team"],
    "serving": ["inference", "serving", "latency", "deployment"],
    "product": ["ai product", "ml product", "model product", "customer-facing ai", "user experience"],
    "infrastructure": ["infrastructure", "distributed system", "cluster", "kubernetes"],
    "safety": ["ai safety", "model safety", "alignment", "model governance", "responsible ai"]
}
RELATIONSHIPS = {
    "builds": ["build ai", "build ml", "develop ai", "develop machine learning", "train models", "model research"],
    "deploys": ["deploy models", "model deployment", "production inference", "integrate ai", "implement ai"],
    "governs": ["ai governance", "model governance", "ai policy", "responsible ai"],
    "evaluates": ["model evaluation", "evaluate models", "ai evaluation", "model benchmark", "evals"],
    "uses": ["use ai", "ai-enabled", "leverage ai"]
}

AI_ROLE_TERMS = [
    "artificial intelligence", "machine learning", "deep learning", "generative ai", "genai",
    "large language model", "llm", "foundation model", "model serving", "model inference",
    "computer vision", "robotics", "autonomy", "autonomous", "retrieval", "ranking",
]
TITLE_TERMS = [
    " ai ", "machine learning", " ml ", "model", "research scientist", "data scientist",
    "robot", "autonomy", "perception", "inference", "search", "retrieval", "ranking",
    "ai safety", "model safety", "alignment", "eval", "red team", "intelligence systems",
]
EVIDENCE_EXCLUSIONS = [
    "equal opportunity", "data privacy", "personal information", "recruitment efforts",
    "scammer", "salary offer may vary", "minimum education", "about the company",
]

def clean_html(value: str) -> str:
    value = html.unescape(html.unescape(value or ""))
    value = re.sub(r"<(br|/p|/li|/h\d)[^>]*>\s*", ". ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def focused_role_text(text: str) -> str:
    """Trim recurring employer/EEO boilerplate before rule-based extraction."""
    lowered = text.lower()
    starts = [lowered.find(marker) for marker in (
        "what you'll do", "what you’ll do", "about the role", "responsibilities",
        "the role", "you will", "in this role",
    )]
    starts = [position for position in starts if position >= 0]
    start = min(starts) if starts else 0
    focused = text[start: start + 9000]
    lowered_focused = focused.lower()
    ends = [lowered_focused.find(marker, 500) for marker in (
        "equal opportunity", "compensation", "salary range", "annual salary",
        "benefits", "data privacy", "minimum education", "apply for this job",
    )]
    ends = [position for position in ends if position >= 0]
    return focused[:min(ends)] if ends else focused

def contains(text: str, term: str) -> bool:
    if len(term.strip()) <= 4:
        return bool(re.search(r"(?<![a-z0-9])" + re.escape(term.strip()) + r"(?![a-z0-9])", text, re.I))
    return term.lower() in text.lower()

def evidence(text: str, terms: list[str]) -> str | None:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sentence in sentences:
        lowered = sentence.lower()
        if any(contains(sentence, term) for term in terms) and not any(term in lowered for term in EVIDENCE_EXCLUSIONS):
            return sentence[:280].strip()
    return None

def matches(text: str, ontology: dict[str, list[str]]) -> list[dict]:
    found = []
    for label, terms in ontology.items():
        quote = evidence(text, terms)
        if any(contains(text, term) for term in terms) and quote:
            found.append({"label": label, "evidence": quote})
    return found

def role_relevance(title: str, text: str) -> dict:
    padded_title = f" {title.lower()} "
    title_hits = sorted({term.strip() for term in TITLE_TERMS if contains(padded_title, term)})
    body_hits = sorted({term for term in AI_ROLE_TERMS if evidence(text, [term])})
    tier = "direct" if title_hits else "applied" if len(body_hits) >= 2 else "contextual"
    return {
        "tier": tier,
        "titleHits": title_hits,
        "bodyHits": body_hits[:8],
        "method": METHOD_VERSION,
        "inferred": True,
    }

def seniority(title: str) -> str:
    t = title.lower()
    if any(x in t for x in ["chief", "vp", "vice president", "director", "head of"]): return "Leadership"
    if any(x in t for x in ["principal", "staff", "fellow"]): return "Staff+"
    if any(x in t for x in ["senior", "sr.", "lead"]): return "Senior"
    if any(x in t for x in ["intern", "new grad", "associate", "junior"]): return "Early career"
    return "Mid-level / unspecified"

def onet_occupation(title: str) -> dict | None:
    """Conservative title normalization; an O*NET-backed candidate, not ground truth."""
    lowered = title.lower()
    candidates = [
        (["robotics engineer", "robotics software"], "17-2199.08", "Robotics Engineers"),
        (["data scientist"], "15-2051.00", "Data Scientists"),
        (["research scientist", "research engineer"], "15-1221.00", "Computer and Information Research Scientists"),
        (["engineering manager", "director of engineering", "head of engineering"], "11-3021.00", "Computer and Information Systems Managers"),
        (["software engineer", "software developer", "ml engineer", "machine learning engineer", "infrastructure engineer"], "15-1252.00", "Software Developers"),
        (["technical program manager", "program manager"], "13-1082.00", "Project Management Specialists"),
    ]
    for terms, code, name in candidates:
        if any(term in lowered for term in terms):
            return {"code": code, "title": name, "taxonomy": f"O*NET-SOC {ONET_VERSION}", "inferred": True, "reviewStatus": "unreviewed", "sourceUrl": "https://www.onetcenter.org/database.html"}
    return None

def normalize_onet_software_skills(skill_hits: list[dict], occupation: dict | None) -> list[dict]:
    """Attach exact O*NET software examples without turning occupation profiles into listing facts."""
    if not occupation:
        return skill_hits
    profile = ONET_SKILL_DATA["profiles"].get(occupation["code"], {})
    official = {item["name"]: item for item in profile.get("softwareSkills", [])}
    crosswalk = ONET_SKILL_DATA.get("softwareCrosswalk", {})
    normalized = []
    for hit in skill_hits:
        result = dict(hit)
        match = next((official[name] for name in crosswalk.get(hit["label"], []) if name in official), None)
        if match:
            result["onetSoftwareSkill"] = {
                **match, "onetVersion": ONET_VERSION, "occupationCode": occupation["code"],
                "normalizationBasis": "listing evidence plus occupation-linked exact crosswalk",
                "inferred": True, "reviewStatus": "unreviewed",
            }
        normalized.append(result)
    return normalized

def domain(title: str, text: str) -> str:
    t, v = title.lower(), text[:1800].lower()
    if any(x in t for x in ["robot", "autonomy", "perception", "embedded", "guidance", "flight"]): return "Robotics & embedded"
    if any(x in t for x in ["safety", "policy", "governance", "alignment", "red team", "trust"]): return "Safety & governance"
    if any(x in t for x in ["scientist", "research", "biology", "science"]): return "Scientific AI"
    if any(x in t for x in ["product", "program manager", "business", "director", "head of", "manager"]): return "Product & leadership"
    if any(x in t for x in ["education", "learning", "training", "curriculum"]): return "Education & training"
    if any(x in v for x in ["robotics", "autonomous vehicle", "embedded system"]): return "Robotics & embedded"
    if any(x in v for x in ["ai safety", "responsible ai", "model governance"]): return "Safety & governance"
    if any(x in t for x in ["software", "machine learning", " ml ", "data", "infrastructure", "systems engineer", " ai ", "model"]): return "ML engineering"
    return "AI-adjacent operations"

def compensation(text: str) -> dict | None:
    candidates = re.findall(r"\$([1-9]\d{1,2}(?:,\d{3})+)(?:\.\d+)?\s*(?:-|–|—|to)\s*\$?([1-9]\d{1,2}(?:,\d{3})+)", text, re.I)
    for low, high in candidates:
        lo, hi = int(low.replace(",", "")), int(high.replace(",", ""))
        if 20_000 <= lo <= hi <= 1_000_000:
            return {"currency": "USD", "minimum": lo, "maximum": hi, "period": "annual", "explicit": True}
    return None

def fetch_board(board: str) -> tuple[list[dict], dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Jobservatory/0.1 (+https://jobservatory.castalia.institute)"})
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=40) as response:
        payload = response.read()
        metadata = {
            "url": url, "httpStatus": response.status,
            "etag": response.headers.get("ETag"), "lastModified": response.headers.get("Last-Modified"),
            "responseHash": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "responseBytes": len(payload), "latencyMs": round((time.perf_counter() - started) * 1000),
            "feedSchemaVersion": "greenhouse-job-board-v1",
        }
        return json.loads(payload).get("jobs", []), metadata

def fetch_lever(site: str) -> tuple[list[dict], dict]:
    url = f"https://api.lever.co/v0/postings/{site}?mode=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Jobservatory/0.1 (+https://jobservatory.castalia.institute)"})
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=40) as response:
        payload = response.read()
        metadata = {
            "url": url, "httpStatus": response.status,
            "etag": response.headers.get("ETag"), "lastModified": response.headers.get("Last-Modified"),
            "responseHash": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "responseBytes": len(payload), "latencyMs": round((time.perf_counter() - started) * 1000),
            "feedSchemaVersion": "lever-postings-v0",
        }
        jobs = json.loads(payload)
        if not isinstance(jobs, list):
            raise ValueError("Lever response is not a list")
        return jobs, metadata

def fetch_ashby(board: str) -> tuple[list[dict], dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
    req = urllib.request.Request(url, headers={"User-Agent": "Jobservatory/0.1 (+https://jobservatory.castalia.institute)"})
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=40) as response:
        payload = response.read()
        parsed = json.loads(payload)
        jobs = parsed.get("jobs", [])
        if not isinstance(jobs, list):
            raise ValueError("Ashby response jobs field is not a list")
        jobs = [job for job in jobs if job.get("isListed") is True]
        metadata = {
            "url": url, "httpStatus": response.status,
            "etag": response.headers.get("ETag"), "lastModified": response.headers.get("Last-Modified"),
            "responseHash": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "responseBytes": len(payload), "latencyMs": round((time.perf_counter() - started) * 1000),
            "feedSchemaVersion": f"ashby-posting-api-{parsed.get('apiVersion', 'unknown')}",
        }
        return jobs, metadata

def structured_compensation(ats: str, job: dict) -> dict | None:
    """Normalize explicitly structured annual salary ranges; do not annualize other units."""
    if ats == "lever":
        value = job.get("salaryRange") or {}
        interval = str(value.get("interval", "")).lower()
        if interval not in {"year", "annual", "annually", "1 year"}:
            return None
        minimum, maximum = value.get("min"), value.get("max")
        currency = value.get("currency")
    elif ats == "ashby":
        components = (job.get("compensation") or {}).get("summaryComponents") or []
        value = next((item for item in components if item.get("compensationType") == "Salary" and str(item.get("interval", "")).upper() == "1 YEAR"), {})
        minimum, maximum = value.get("minValue"), value.get("maxValue")
        currency = value.get("currencyCode")
    else:
        return None
    if not isinstance(minimum, (int, float)) or not isinstance(maximum, (int, float)) or minimum > maximum:
        return None
    return {"currency": currency or "unspecified", "minimum": minimum, "maximum": maximum, "period": "annual", "explicit": True, "source": "structured-ats-field"}

def normalize_job(ats: str, job: dict) -> dict:
    if ats == "greenhouse":
        return {
            "id": str(job["id"]), "title": job.get("title", ""), "content": job.get("content", ""),
            "location": (job.get("location") or {}).get("name", "Remote / unspecified"),
            "url": job.get("absolute_url"), "sourceUpdatedAt": job.get("updated_at"), "sourcePublishedAt": None,
            "structuredCompensation": structured_compensation(ats, job),
        }
    if ats == "ashby":
        locations = [job.get("location", "")] + [item.get("location", "") for item in job.get("secondaryLocations", [])]
        return {
            "id": str(job["id"]), "title": job.get("title", ""), "content": job.get("descriptionPlain", ""),
            "location": " · ".join(dict.fromkeys(value for value in locations if value)) or "Remote / unspecified",
            "url": job.get("jobUrl"), "sourceUpdatedAt": None, "sourcePublishedAt": job.get("publishedAt"),
            "structuredCompensation": structured_compensation(ats, job),
        }
    categories = job.get("categories") or {}
    list_content = " ".join(f"{item.get('text', '')}. {item.get('content', '')}" for item in job.get("lists", []))
    created = job.get("createdAt")
    return {
        "id": str(job["id"]), "title": job.get("text", ""),
        "content": " ".join((job.get("descriptionPlain", ""), list_content, job.get("additionalPlain", ""))),
        "location": categories.get("location", "Remote / unspecified"), "url": job.get("hostedUrl"),
        "sourceUpdatedAt": None,
        "sourcePublishedAt": datetime.fromtimestamp(created / 1000, timezone.utc).isoformat() if isinstance(created, (int, float)) else None,
        "structuredCompensation": structured_compensation(ats, job),
    }

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
      CREATE TABLE IF NOT EXISTS analyses (
        analysis_id TEXT PRIMARY KEY, observation_id TEXT NOT NULL, source_id TEXT NOT NULL,
        method_version TEXT NOT NULL, ontology_version TEXT NOT NULL, created_at TEXT NOT NULL,
        payload_json TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_analyses_observation ON analyses(observation_id);
    """)

def main() -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    previous_export = json.loads(PUBLIC_PATH.read_text()) if PUBLIC_PATH.exists() else {"observations": []}
    ledger = []
    if LEDGER_PATH.exists():
        ledger = [json.loads(line) for line in LEDGER_PATH.read_text().splitlines() if line.strip()]
    previous = {}
    for item in ledger:
        current = previous.get(item["sourceId"])
        if not current or int(item.get("version", 1)) >= int(current.get("version", 1)):
            previous[item["sourceId"]] = item
    candidates = []
    retrieval = []
    failures = []
    configured_sources = [("greenhouse", source) for source in CONFIG.get("greenhouse", [])] + [("lever", source) for source in CONFIG.get("lever", [])] + [("ashby", source) for source in CONFIG.get("ashby", [])]
    for ats, source in configured_sources:
        source_key = source.get("board") or source.get("site")
        try:
            if ats == "greenhouse":
                jobs, fetch_metadata = fetch_board(source_key)
            elif ats == "lever":
                jobs, fetch_metadata = fetch_lever(source_key)
            else:
                jobs, fetch_metadata = fetch_ashby(source_key)
        except Exception as exc:
            print(f"warning: {source['employer']}: {exc}", file=sys.stderr)
            failures.append({"employer": source["employer"], "ats": ats, "sourceKey": source_key, "errorType": type(exc).__name__})
            continue
        source_eligible = 0
        for raw_job in jobs:
            job = normalize_job(ats, raw_job)
            body = clean_html(job.get("content", ""))
            title = clean_html(job.get("title", ""))
            role_text = focused_role_text(body)
            haystack = (title + " " + role_text).lower()
            relevance = role_relevance(title, role_text)
            if relevance["tier"] == "contextual":
                continue
            source_eligible += 1
            source_id = f"{ats}:{source_key}:{job['id']}"
            digest = hashlib.sha256((title + "\n" + body).encode()).hexdigest()
            analysis_id = "analysis:" + hashlib.sha256(f"{source_id}:{digest}:{METHOD_VERSION}:{ONTOLOGY_VERSION}".encode()).hexdigest()[:20]
            occupation = onet_occupation(title)
            skill_hits = normalize_onet_software_skills(matches(f"{title}. {role_text}", SKILLS), occupation)
            layer_hits = matches(f"{title}. {role_text}", LAYERS)
            relationship_hits = matches(f"{title}. {role_text}", RELATIONSHIPS)
            record = {
                "observationId": f"{source_id}:{digest[:12]}", "sourceId": source_id,
                "analysisId": analysis_id,
                "employer": source["employer"], "title": title,
                "location": clean_html(job.get("location", "Remote / unspecified")),
                "sourceUrl": job.get("url"), "retrievedAt": now,
                "sourceUpdatedAt": job.get("sourceUpdatedAt"), "sourcePublishedAt": job.get("sourcePublishedAt"), "contentHash": f"sha256:{digest}",
                "seniority": seniority(title), "domain": domain(title, role_text),
                "onetOccupation": occupation,
                "compensation": job.get("structuredCompensation") or compensation(body),
                "roleRelevance": relevance,
                "classifications": {
                    "aiRelationship": relationship_hits[:3], "systemLayer": layer_hits[:3],
                    "skills": skill_hits[:8],
                    "laborEffect": {"label": "unclassified", "inferred": True, "basis": "Requires validated task-level evidence; no default effect is assigned."},
                    "humanRole": {"label": "accountable leader" if seniority(title) == "Leadership" else "technical decision-maker" if seniority(title) == "Staff+" else "unclassified", "inferred": True},
                    "maturity": {"label": "production scaling" if any(evidence(role_text, [x]) for x in ["production inference", "production deployment", "serving latency", "at scale"]) else "unclassified", "inferred": True}
                },
                "extraction": {"methodVersion": METHOD_VERSION, "ontologyVersion": ONTOLOGY_VERSION, "reviewStatus": "unreviewed"},
                "descriptionPolicy": "metadata-and-evidence-only",
                "duplicateGroup": hashlib.sha256(f"{source['employer']}|{title.lower()}|{clean_html(job.get('location', ''))}".encode()).hexdigest()[:16]
            }
            candidates.append(record)
        policy = CONFIG.get("atsPolicies", {}).get(ats, {})
        retrieval.append({"employer": source["employer"], "ats": ats, "sourceKey": source_key, "sector": source.get("sector", "unspecified"), "retrieved": len(jobs), "eligible": source_eligible, "status": "ok", "rightsReviewStatus": source.get("rightsReviewStatus", "pending"), "retentionPolicy": source.get("retentionPolicy", "metadata-hash-short-evidence"), **policy, **fetch_metadata})

    if failures and os.environ.get("JOBSERVATORY_ALLOW_PARTIAL") != "1":
        raise RuntimeError(f"refusing partial publication; {len(failures)} source feed(s) failed")
    minimum = int(CONFIG.get("minimumRecordsPerSource", 1))
    thin = [item for item in retrieval if item["eligible"] < minimum]
    if thin and os.environ.get("JOBSERVATORY_ALLOW_PARTIAL") != "1":
        raise RuntimeError(f"refusing publication; source(s) below {minimum} eligible records: {thin}")

    candidates.sort(key=lambda x: (x.get("sourceUpdatedAt") or "", x["title"]), reverse=True)
    maximum = int(CONFIG["maximumObservations"])
    if len(candidates) <= maximum:
        records = candidates
    else:
        by_employer: dict[str, list[dict]] = defaultdict(list)
        for record in candidates:
            by_employer[record["employer"]].append(record)
        floor = min(25, maximum // max(len(by_employer), 1))
        allocations = {
            employer: min(len(items), max(floor, int(maximum * len(items) / len(candidates))))
            for employer, items in by_employer.items()
        }
        while sum(allocations.values()) > maximum:
            employer = max((name for name in allocations if allocations[name] > floor), key=lambda name: allocations[name], default=None)
            if employer is None: break
            allocations[employer] -= 1
        while sum(allocations.values()) < maximum:
            employer = max((name for name, items in by_employer.items() if allocations[name] < len(items)), key=lambda name: len(by_employer[name]) - allocations[name], default=None)
            if employer is None: break
            allocations[employer] += 1
        records = [record for employer in sorted(by_employer) for record in by_employer[employer][:allocations[employer]]]
        records.sort(key=lambda x: (x.get("sourceUpdatedAt") or "", x["title"]), reverse=True)
    for record in records:
        prior = previous.get(record["sourceId"])
        same = prior and prior.get("contentHash") == record["contentHash"]
        same_analysis = prior and prior.get("analysisId") == record["analysisId"]
        record["version"] = int(prior.get("version", 1)) if same else int(prior.get("version", 0)) + 1 if prior else 1
        record["firstSeen"] = prior.get("firstSeen", prior.get("retrievedAt")) if prior else now
        record["lastSeen"] = now
        record["changeType"] = "unchanged" if same else "revised" if prior else "new"
        record["analysisChangeType"] = "unchanged" if same_analysis else "reanalyzed" if prior else "new"
        record["previousObservationId"] = prior.get("observationId") if prior and not same else None
    new_versions = [r for r in records if r["changeType"] in ("new", "revised") or r["analysisChangeType"] == "reanalyzed"]
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a") as handle:
        for record in new_versions:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    for r in records:
        conn.execute("INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?)", (
            r["observationId"], r["sourceId"], r["employer"], r["title"], r["sourceUrl"],
            r["location"], r["retrievedAt"], r["sourceUpdatedAt"], r["contentHash"], json.dumps(r, separators=(",", ":"))))
        conn.execute("INSERT OR IGNORE INTO analyses VALUES (?,?,?,?,?,?,?)", (
            r["analysisId"], r["observationId"], r["sourceId"], METHOD_VERSION,
            ONTOLOGY_VERSION, now, json.dumps(r, separators=(",", ":"))))
    conn.execute("PRAGMA optimize")
    conn.commit()

    skill_counts = Counter(hit["label"] for r in records for hit in r["classifications"]["skills"])
    term_counts = Counter()
    term_categories = {}
    for record in records:
        for key, category in (("skills", "Skill"), ("systemLayer", "System layer")):
            for hit in record["classifications"][key]:
                term_counts[hit["label"]] += 1
                term_categories[hit["label"]] = category
        term_counts[record["seniority"]] += 1
        term_categories[record["seniority"]] = "Seniority"
        term_counts[record["domain"]] += 1
        term_categories[record["domain"]] = "Job domain"
    domains = Counter(r["domain"] for r in records)
    employers = Counter(r["employer"] for r in records)
    employer_shares = {employer: count / len(records) for employer, count in employers.items()} if records else {}
    source_concentration = {
        "largestEmployerShare": round(max(employer_shares.values()), 4) if employer_shares else None,
        "herfindahlHirschmanIndex": round(sum(share * share for share in employer_shares.values()), 4),
        "interpretation": "Published-record concentration diagnostic; not a labor-market estimate.",
    }
    changes = Counter(r["changeType"] for r in records)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    prior_snapshots = sorted(path for path in SNAPSHOT_DIR.glob("*.json") if path.stem < now[:10])
    prior_presence = set()
    if prior_snapshots:
        prior_presence = set(json.loads(prior_snapshots[-1].read_text()).get("eligibleSourceIds", []))
    current_presence = {r["sourceId"] for r in candidates}
    changes["disappeared"] = len(prior_presence - current_presence) if prior_presence else 0
    snapshot = {"date": now[:10], "generatedAt": now, "eligibleSourceIds": sorted(current_presence), "contentHashes": {r["sourceId"]: r["contentHash"] for r in candidates}}
    (SNAPSHOT_DIR / f"{now[:10]}.json").write_text(json.dumps(snapshot, separators=(",", ":")) + "\n")
    compensated = [r for r in records if r["compensation"]]
    usd_annual_compensated = [r for r in compensated if r["compensation"].get("currency") == "USD" and r["compensation"].get("period") == "annual"]
    midpoint = sorted((r["compensation"]["minimum"] + r["compensation"]["maximum"]) / 2 for r in usd_annual_compensated)
    median_pay = int(midpoint[len(midpoint)//2]) if midpoint else None
    previous_terms = {item["term"]: item.get("count", 0) for item in previous_export.get("termIndex", [])}
    term_index = [{
        "term": term, "category": term_categories[term], "count": count,
        "share": round(count / len(records), 4) if records else 0,
        "change": count - previous_terms[term] if term in previous_terms else None,
        "firstSeen": previous_export.get("generatedAt", now) if term in previous_terms else now,
        "lastSeen": now
    } for term, count in term_counts.most_common()]
    export = {
        "schemaVersion": "0.2.0", "generatedAt": now, "scope": f"All listings meeting versioned direct-or-applied AI rules within {len(retrieval)} selected public employer feeds across declared sectors and ATS providers; global, curated, and not labor-market representative",
        "methodNote": "Listings are timestamped observations, not unique jobs. Rule-derived labels are unreviewed hypotheses; evidence excerpts remain linked to sources.",
        "methods": {"extraction": METHOD_VERSION, "ontology": ONTOLOGY_VERSION, "sampling": CONFIG.get("samplingPolicy"), "labelReview": "unreviewed"},
        "onet": {
            "version": ONET_SKILL_DATA["onetVersion"], "license": ONET_SKILL_DATA["license"],
            "licenseUrl": ONET_SKILL_DATA["licenseUrl"], "sourceUrl": ONET_SKILL_DATA["sourceUrl"],
            "attribution": ONET_SKILL_DATA["attribution"],
            "skillProfiles": {
                code: {key: value for key, value in profile.items() if key != "softwareSkills"}
                for code, profile in ONET_SKILL_DATA["profiles"].items()
            },
            "profileSemantics": "Occupation-inherited profiles are context, not listing-stated requirements. Record-level software mappings require listing evidence and an exact occupation-linked crosswalk.",
        },
        "coverage": {"sourceRegistryVersion": CONFIG.get("registryVersion"), "definition": CONFIG.get("coverageDefinition"), "sourcesConfigured": len(configured_sources), "sourcesSuccessful": len(retrieval), "sourceFailures": failures, "atsProviders": dict(Counter(item["ats"] for item in retrieval)), "sectors": dict(Counter(item["sector"] for item in retrieval)), "retrieval": retrieval, "eligibleObservations": len(candidates), "publishedObservations": len(records), "publicationCap": int(CONFIG["maximumObservations"])},
        "summary": {"observations": len(records), "employers": len(employers), "employerMix": employers, "sourceConcentration": source_concentration, "changes": changes, "compensationCoverage": round(len(compensated)/len(records), 3) if records else 0, "usdAnnualCompensationObservations": len(usd_annual_compensated), "medianAdvertisedPayMidpoint": median_pay, "medianAdvertisedPayCurrency": "USD" if median_pay is not None else None, "medianAdvertisedPayPeriod": "annual" if median_pay is not None else None, "topSkills": skill_counts.most_common(8), "domains": domains},
        "payBenchmarks": [
          {"occupation":"Data scientists","medianAnnualPay":112590,"year":2024,"source":"BLS OEWS","sourceUrl":"https://www.bls.gov/ooh/math/data-scientists.htm"},
          {"occupation":"Software developers","medianAnnualPay":133080,"year":2024,"source":"BLS OOH","sourceUrl":"https://www.bls.gov/ooh/computer-and-information-technology/software-developers.htm"},
          {"occupation":"Computer and information research scientists","medianAnnualPay":140910,"year":2024,"source":"BLS OOH","sourceUrl":"https://www.bls.gov/ooh/computer-and-information-technology/computer-and-information-research-scientists.htm"}
        ],
        "termIndex": term_index,
        "termTimeline": [],
        "observations": records
    }
    PUBLIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_PATH.write_text(json.dumps(export, indent=2) + "\n")
    APOCALYPSO_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if HISTORY_PATH.exists():
        history = [json.loads(line) for line in HISTORY_PATH.read_text().splitlines() if line.strip()]
    retrieved_total = sum(item["retrieved"] for item in retrieval)
    daily = {"date": now[:10], "generatedAt": now, **export["summary"], "termCounts": dict(term_counts), "retrieval": retrieval, "eligibleObservations": len(candidates), "retrievedObservations": retrieved_total, "aiRelatedShare": round(len(candidates) / retrieved_total, 6) if retrieved_total else None}
    history = [item for item in history if item.get("date") != daily["date"]] + [daily]
    HISTORY_PATH.write_text("".join(json.dumps(item, separators=(",", ":")) + "\n" for item in history[-730:]))
    export["termTimeline"] = [{"date": item["date"], "terms": item.get("termCounts", {})} for item in history[-365:]]
    PUBLIC_PATH.write_text(json.dumps(export, indent=2) + "\n")
    usable_history = [item for item in history if item.get("aiRelatedShare") is not None]
    enough_history = len(usable_history) >= 30
    signal_value = None
    if enough_history:
        current = sum(item["aiRelatedShare"] for item in usable_history[-7:]) / 7
        prior = sum(item["aiRelatedShare"] for item in usable_history[-14:-7]) / 7
        signal_value = round((current - prior) * 100, 3)
    apocalypso = {
        "schemaVersion": "apocalypso.signal.v2", "generatedAt": now, "module": "AI", "source": "jobservatory.castalia.institute",
        "signal": {"id": "labor.ai_related_listing_share_change", "name": "7-day change in direct-or-applied AI listing share", "status": "available" if enough_history else "insufficient_history", "value": signal_value, "unit": "percentage_points", "minimumHistoryDays": 30, "observedHistoryDays": len(usable_history), "comparison": "latest_7_day_mean_minus_prior_7_day_mean", "direction": "higher_means_a_larger_share_of_source_listings_meet_the_versioned_ai_relevance_rules"},
        "context": {**export["summary"], "coverage": export["coverage"], "warning": "Selected employer feeds are not representative of the labor market."}, "sourceUrl": "https://jobservatory.castalia.institute/api/observatory.json"
    }
    APOCALYPSO_PATH.write_text(json.dumps(apocalypso, indent=2) + "\n")
    print(f"exported {len(records)} observations from {len(employers)} employers")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
