"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createHybridIndex } from "./retrieval";

type Evidence = { label: string; evidence: string };
type Observation = {
  observationId: string; employer: string; title: string; location: string; sourceUrl: string;
  retrievedAt: string; sourceUpdatedAt?: string; contentHash: string; seniority: string; domain: string;
  compensation: { minimum: number; maximum: number } | null;
  entityResolution: { postingFamilyId: string; exactVariantGroupId: string; familySize: number; exactVariantGroupSize: number; repostCandidate: boolean; hasLocationVariants: boolean; reviewStatus: string; semantics: string };
  classifications: { aiRelationship: Evidence[]; systemLayer: Evidence[]; skills: Evidence[]; laborEffect: { label: string; inferred: boolean; basis: string }; humanRole: { label: string; inferred: boolean }; maturity: { label: string; inferred: boolean } };
};
type Term = { term: string; category: string; count: number; share: number; change: number | null; firstSeen: string; lastSeen: string };
type Dataset = { generatedAt: string; summary: { observations: number; employers: number; compensationCoverage: number; medianAdvertisedPayMidpoint: number; topSkills: [string, number][]; domains: Record<string, number> }; termIndex: Term[]; termTimeline: { date: string; terms: Record<string, number> }[]; payBenchmarks: { occupation: string; medianAnnualPay: number; sourceUrl: string }[]; observations: Observation[] };
type Metrics = { evaluation: { queries: number; judgmentPolicy: string }; aggregate: Record<string, Record<string, number>>; limitations: string[] };

const money = (value: number) => `$${Math.round(value / 1000)}K`;
export default function Observatory() {
  const [data, setData] = useState<Dataset | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("All domains");
  const [selected, setSelected] = useState<Observation | null>(null);
  const [termCategory, setTermCategory] = useState("All terms");
  const [selectedTerm, setSelectedTerm] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const lastFocus = useRef<HTMLElement | null>(null);

  const closeButton = useRef<HTMLButtonElement>(null);
  const drawer = useRef<HTMLElement>(null);
  const openObservation = (item: Observation) => { lastFocus.current = document.activeElement as HTMLElement; setSelected(item); };
  const closeObservation = () => { setSelected(null); requestAnimationFrame(() => lastFocus.current?.focus()); };
  useEffect(() => {
    fetch("/api/observatory.json").then(r => { if (!r.ok) throw new Error(String(r.status)); return r.json(); }).then((next: Dataset) => { setData(next); setSelectedTerm(next.termIndex?.[0]?.term || null); setSelectedDate(next.termTimeline?.at(-1)?.date || null); }).catch(() => setLoadError(true));
    fetch("/api/ml/retrieval-metrics.json").then(r => r.json()).then(setMetrics).catch(() => undefined);
  }, []);
  useEffect(() => { if (selected) closeButton.current?.focus(); }, [selected]);
  useEffect(() => {
    if (!selected) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { closeObservation(); return; }
      if (event.key !== "Tab") return;
      const focusable = Array.from(drawer.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])') || []).filter(element => !element.hasAttribute("hidden"));
      if (!focusable.length) { event.preventDefault(); return; }
      const first = focusable[0], last = focusable.at(-1)!;
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener("keydown", handleKey);
    return () => { window.removeEventListener("keydown", handleKey); document.body.style.overflow = previousOverflow; };
  }, [selected]);
  const domains = data ? Object.keys(data.summary.domains).sort() : [];
  const hybridIndex = useMemo(() => data ? createHybridIndex(data.observations) : null, [data]);
  const filtered = useMemo(() => {
    const ranked = query.trim() && hybridIndex ? hybridIndex.search(query).map(result => result.item as Observation) : (data?.observations || []);
    return ranked.filter(item => domain === "All domains" || item.domain === domain);
  }, [data, domain, hybridIndex, query]);
  const maxSkill = data?.summary.topSkills[0]?.[1] || 1;
  const termCategories = data ? Array.from(new Set(data.termIndex.map(item => item.category))) : [];
  const datedCounts = data?.termTimeline.find(item => item.date === selectedDate)?.terms || {};
  const visibleTerms = (data?.termIndex || []).filter(item => termCategory === "All terms" || item.category === termCategory).map(item => ({...item, count: datedCounts[item.term] ?? item.count})).filter(item => item.count > 0).slice(0, 34);
  const termMax = Math.max(...visibleTerms.map(item => item.count), 1);
  const selectedTermData = data?.termIndex.find(item => item.term === selectedTerm) || null;
  const termMatches = selectedTerm && data ? data.observations.filter(item => item.seniority === selectedTerm || item.domain === selectedTerm || [...item.classifications.skills,...item.classifications.systemLayer].some(hit => hit.label === selectedTerm)) : [];
  const termEmployers = Array.from(new Set(termMatches.map(item => item.employer))).slice(0, 4);

  return (
    <>
      <section className="dashboard" id="signals">
        <div className="section-head"><div><span>01 / CURRENT CORPUS</span><h2>What selected employers<br />ask for now.</h2></div><p>Every row is a dated observation—not a timeless job record. Revisions and removals become signal; unreviewed metadata families expose possible reposts and location variants.</p></div>
        <div className="kpi-grid">
          <article><span>Observed listings</span><strong>{data?.summary.observations ?? "—"}</strong><small>current curated slice</small></article>
          <article><span>Employers</span><strong>{data?.summary.employers ?? "—"}</strong><small>public career feeds</small></article>
          <article><span>Pay disclosed</span><strong>{data ? `${Math.round(data.summary.compensationCoverage * 100)}%` : "—"}</strong><small>of observations</small></article>
          <article><span>Median pay midpoint</span><strong>{data?.summary.medianAdvertisedPayMidpoint ? money(data.summary.medianAdvertisedPayMidpoint) : "—"}</strong><small>disclosed USD ranges</small></article>
        </div>
        <div className="signal-grid">
          <article className="skills-panel">
            <div className="panel-title"><span>OBSERVED TERM FREQUENCY</span><small>current curated corpus</small></div>
            <div className="skill-bars">{data?.summary.topSkills.map(([skill,count],i)=><div className="skill-row" key={skill}><b>{String(i+1).padStart(2,"0")}</b><span>{skill}</span><i><em style={{width:`${count/maxSkill*100}%`}} /></i><strong>{count}</strong></div>) || <p className="loading">Loading observation ledger…</p>}</div>
          </article>
          <article className="domain-panel">
            <div className="panel-title"><span>WHERE THE WORK SITS</span><small>listing count</small></div>
            <div className="domain-list">{data && Object.entries(data.summary.domains).sort((a,b)=>b[1]-a[1]).map(([name,count])=><button key={name} aria-label={`Show ${count} observations in ${name}`} onClick={()=>{setDomain(name); document.getElementById("ledger")?.scrollIntoView()}}><span>{name}</span><strong>{count}</strong><i style={{width:`${count/data.summary.observations*100}%`}} /></button>)}</div>
          </article>
        </div>
      </section>

      <section className="terms" id="terms">
        <div className="section-head"><div><span>02 / TERM MAP</span><h2>The language<br />of AI work.</h2></div><p>Normalized terms reveal what employers repeatedly ask for. Size shows listing frequency; color shows the kind of signal. Each daily observation becomes another frame in the longitudinal map.</p></div>
        <div className="term-controls"><div role="group" aria-label="Term family"><button className={termCategory==="All terms"?"active":""} onClick={()=>setTermCategory("All terms")}>All terms</button>{termCategories.map(category=><button className={termCategory===category?"active":""} key={category} onClick={()=>setTermCategory(category)}>{category}</button>)}</div><label><span>OBSERVATION DATE</span><select value={selectedDate || ""} onChange={e=>setSelectedDate(e.target.value)}>{data?.termTimeline.map(item=><option value={item.date} key={item.date}>{item.date}</option>)}</select></label></div>
        <div className="term-map-shell">
          <div className="word-map" aria-label="Map of recurring AI job terms">{visibleTerms.map(item=>{
            const size = 13 + Math.sqrt(item.count / termMax) * 45;
            return <button key={item.term} aria-pressed={selectedTerm===item.term} data-category={item.category} className={selectedTerm===item.term?"selected":""} style={{"--term-size":`${size}px`} as React.CSSProperties} onClick={()=>setSelectedTerm(item.term)}><span>{item.term}</span><small>{item.count}</small></button>;
          })}</div>
          <aside className="term-detail"><span>SELECTED TERM</span><h3>{selectedTerm || "Choose a term"}</h3>{selectedTermData && <><strong>{selectedTermData.count}<small> / {data?.summary.observations} listings</small></strong><div className="term-meter"><i style={{width:`${selectedTermData.share*100}%`}} /></div><dl><div><dt>FAMILY</dt><dd>{selectedTermData.category}</dd></div><div><dt>CHANGE</dt><dd>{selectedTermData.change === null ? "Baseline" : `${selectedTermData.change >= 0 ? "+" : ""}${selectedTermData.change}`}</dd></div><div><dt>EMPLOYERS</dt><dd>{termEmployers.join(", ") || "—"}</dd></div></dl></>}</aside>
        </div>
        <div className="term-time"><span>TIME</span>{data?.termTimeline.map((item,index)=><button key={item.date} className={selectedDate===item.date?"active":""} onClick={()=>setSelectedDate(item.date)}><i /><b>{index===0?"BASELINE":item.date.slice(5)}</b></button>)}<em>Daily frames accumulate automatically</em></div>
      </section>

      <section className="ledger" id="ledger">
        <div className="section-head light"><div><span>03 / EVIDENCE LEDGER</span><h2>Inspect the<br />observations.</h2></div><p>Open any listing to see source facts, evidence-bearing rule matches, and explicitly unreviewed inferences.</p></div>
        <div className="filters"><label><span>HYBRID SEARCH · BM25 + DENSE HASH + RRF</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Principal ML retrieval architecture, remote US…" /></label><label><span>DOMAIN</span><select value={domain} onChange={e=>setDomain(e.target.value)}><option>All domains</option>{domains.map(d=><option key={d}>{d}</option>)}</select></label><div className="result-count"><strong>{filtered.length}</strong><span>{query ? "ranked observations" : "observations"}</span></div></div>
        {loadError && <p className="data-error" role="alert">The observation corpus could not be loaded. Try again later or inspect the public JSON endpoint.</p>}
        <div className="table" role="table" aria-label="Job listing observations">
          <div className="tr table-head" role="row"><span role="columnheader">EMPLOYER / ROLE</span><span role="columnheader">DOMAIN</span><span role="columnheader">SENIORITY</span><span role="columnheader">PAY</span><span role="columnheader" /></div>
          {filtered.slice(0,30).map(item=><div className="tr" role="row" key={item.observationId}><span role="cell"><b>{item.employer}</b><button className="row-title" onClick={()=>openObservation(item)}>{item.title}</button><small>{item.location}</small></span><span role="cell"><i className="dot" />{item.domain}</span><span role="cell">{item.seniority}</span><span role="cell">{item.compensation ? `${money(item.compensation.minimum)}–${money(item.compensation.maximum)}` : "Not disclosed"}</span><span role="cell"><button className="open" aria-label={`Inspect ${item.title} at ${item.employer}`} onClick={()=>openObservation(item)}>↗</button></span></div>)}
        </div>
        {filtered.length > 30 && <p className="table-note">Showing 30 of {filtered.length} matches. Refine the filters to inspect the remaining records.</p>}
      </section>

      <section className="forecast" id="lab">
        <div className="section-head"><div><span>04 / RETRIEVAL LAB</span><h2>Measure relevance,<br />then improve it.</h2></div><p>The deployed search combines BM25, a fixed dense feature baseline, reciprocal-rank fusion, and transparent interaction reranking. Results are evaluated against committed graded judgments.</p></div>
        <div className="ml-metrics">{(["bm25", "dense_hash", "rrf", "interaction_rerank"] as const).map(name => <article key={name}><span>{name.replaceAll("_", " ")}</span><strong>{metrics ? metrics.aggregate[name]?.["ndcg@10"]?.toFixed(3) : "—"}</strong><small>nDCG@10</small><b>{metrics ? `${metrics.aggregate[name]?.["recall@10"]?.toFixed(3)} Recall@10` : "loading"}</b></article>)}</div>
        <div className="lab-note"><p><strong>Development evidence:</strong> {metrics?.evaluation.queries || "—"} single-reviewer queries. These figures are baselines, not production claims; the dense hash is not a learned semantic model and the interaction reranker is not a neural cross-encoder.</p><a href="/api/ml/retrieval-metrics.json">Inspect full metrics JSON ↗</a></div>
      </section>

      <section className="method" id="method">
        <div className="section-head light"><div><span>05 / PROVENANCE</span><h2>Evidence first.<br />Inference labeled.</h2></div><p>The corpus preserves only metadata, hashes, normalized facts, and short supporting excerpts unless republication rights permit more.</p></div>
        <div className="pipeline"><article><b>01</b><h3>Observe</h3><p>Retrieve public source metadata at a recorded time. Hash each version.</p></article><article><b>02</b><h3>Extract</h3><p>Normalize skills, AI methods, responsibilities, seniority, and compensation.</p></article><article><b>03</b><h3>Evidence</h3><p>Attach a short source span to each explicit classification. Mark all inference.</p></article><article><b>04</b><h3>Compare</h3><p>Detect edits, repostings, removals, co-occurrence, and movement over time.</p></article></div>
        <div className="apocalypso"><div><span>DOWNSTREAM FEED</span><h3>Apocalypso-ready.</h3><p>A compact versioned signal export can join the AI module as an indicator of organizational AI operationalization and labor-transition pressure.</p></div><a href="/api/apocalypso/jobs-signal.json" download>Download signal JSON <b>↓</b></a></div>
        <div className="sources"><span>REFERENCE SERIES</span><a href="https://www.census.gov/library/stories/2026/05/ai-use-businesses.html" target="_blank" rel="noreferrer">US Census BTOS ↗</a><a href="https://www.anthropic.com/research/economic-index-june-2026-report" target="_blank" rel="noreferrer">Anthropic Economic Index ↗</a><a href="https://www.pwc.com/gx/en/issues/artificial-intelligence/job-barometer/2026.html" target="_blank" rel="noreferrer">PwC AI Jobs Barometer ↗</a><a href="https://www.bls.gov/ooh/" target="_blank" rel="noreferrer">BLS Occupational Outlook ↗</a></div>
      </section>

      {selected && <div className="drawer-backdrop" role="presentation" onMouseDown={event=>{ if (event.target === event.currentTarget) closeObservation(); }}>
        <aside ref={drawer} className="drawer" role="dialog" aria-modal="true" aria-labelledby="observation-title" aria-describedby="observation-caution">
          <button ref={closeButton} className="close" onClick={closeObservation}>CLOSE ×</button>
          <span className="drawer-kicker">OBSERVATION · VERSIONED</span><h2 id="observation-title">{selected.title}</h2><h3>{selected.employer} · {selected.location}</h3>
          <div className="fact-grid"><div><span>DOMAIN</span><b>{selected.domain}</b></div><div><span>SENIORITY</span><b>{selected.seniority}</b></div><div><span>PAY</span><b>{selected.compensation?`${money(selected.compensation.minimum)}–${money(selected.compensation.maximum)}`:"Not disclosed"}</b></div><div><span>CONTENT HASH</span><b>{selected.contentHash.slice(7,19)}…</b></div><div><span>TITLE FAMILY</span><b>{selected.entityResolution.familySize} observation{selected.entityResolution.familySize===1?"":"s"}</b></div><div><span>EXACT VARIANT CANDIDATES</span><b>{selected.entityResolution.exactVariantGroupSize}</b></div></div>
          <h4>Evidence-backed signals</h4>{[...selected.classifications.aiRelationship,...selected.classifications.systemLayer,...selected.classifications.skills].slice(0,6).map((hit,i)=><blockquote key={`${hit.label}-${i}`}><b>{hit.label}</b><p>“{hit.evidence}”</p><small>RULE-DERIVED · SOURCE SPAN</small></blockquote>)}
          <h4>Unreviewed interpretation</h4><div className="inferences"><span>{selected.classifications.laborEffect.label}</span><span>{selected.classifications.humanRole.label}</span><span>{selected.classifications.maturity.label}</span></div><p className="caution" id="observation-caution">These labels are unreviewed hypotheses derived by versioned rules, not employer assertions or validated model outputs. {selected.entityResolution.semantics}</p><a className="source-button" href={selected.sourceUrl} target="_blank" rel="noreferrer">Open source listing ↗</a>
        </aside>
      </div>}
    </>
  );
}
