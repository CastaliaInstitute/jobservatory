"use client";

import { useEffect, useMemo, useState } from "react";

type Evidence = { label: string; evidence: string };
type Observation = {
  observationId: string; employer: string; title: string; location: string; sourceUrl: string;
  retrievedAt: string; sourceUpdatedAt?: string; contentHash: string; seniority: string; domain: string;
  compensation: { minimum: number; maximum: number } | null;
  classifications: { aiRelationship: Evidence[]; systemLayer: Evidence[]; skills: Evidence[]; laborEffect: { label: string; inferred: boolean; basis: string }; humanRole: { label: string; inferred: boolean }; maturity: { label: string; inferred: boolean } };
};
type Term = { term: string; category: string; count: number; share: number; change: number | null; firstSeen: string; lastSeen: string };
type Dataset = { generatedAt: string; summary: { observations: number; employers: number; compensationCoverage: number; medianAdvertisedPayMidpoint: number; topSkills: [string, number][]; domains: Record<string, number> }; termIndex: Term[]; termTimeline: { date: string; terms: Record<string, number> }[]; payBenchmarks: { occupation: string; medianAnnualPay: number; sourceUrl: string }[]; observations: Observation[] };

const money = (value: number) => `$${Math.round(value / 1000)}K`;
const scenarios = {
  measured: { name: "Measured", autonomy: 8, skills: 11, churn: 7, note: "Current adoption continues; governance and evaluation capacity catches up." },
  acceleration: { name: "Acceleration", autonomy: 19, skills: 24, churn: 16, note: "Agent deployment expands quickly and redesigns knowledge-work roles." },
  friction: { name: "Friction", autonomy: 3, skills: 6, churn: 4, note: "Reliability, regulation, and integration costs slow operational change." }
};

export default function Observatory() {
  const [data, setData] = useState<Dataset | null>(null);
  const [query, setQuery] = useState("");
  const [domain, setDomain] = useState("All domains");
  const [selected, setSelected] = useState<Observation | null>(null);
  const [scenario, setScenario] = useState<keyof typeof scenarios>("measured");
  const [termCategory, setTermCategory] = useState("All terms");
  const [selectedTerm, setSelectedTerm] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  useEffect(() => { fetch("/api/observatory.json").then(r => r.json()).then((next: Dataset) => { setData(next); setSelectedTerm(next.termIndex?.[0]?.term || null); setSelectedDate(next.termTimeline?.at(-1)?.date || null); }).catch(() => setData(null)); }, []);
  const domains = data ? Object.keys(data.summary.domains).sort() : [];
  const filtered = useMemo(() => (data?.observations || []).filter(item => {
    const haystack = `${item.title} ${item.employer} ${item.location} ${item.classifications.skills.map(s => s.label).join(" ")}`.toLowerCase();
    return (domain === "All domains" || item.domain === domain) && haystack.includes(query.toLowerCase());
  }), [data, domain, query]);
  const maxSkill = data?.summary.topSkills[0]?.[1] || 1;
  const model = scenarios[scenario];
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
        <div className="section-head"><div><span>01 / CURRENT CORPUS</span><h2>What employers are<br />funding now.</h2></div><p>Every row is a dated observation—not a timeless job record. Revisions, removals, and repostings become signal.</p></div>
        <div className="kpi-grid">
          <article><span>Observed listings</span><strong>{data?.summary.observations ?? "—"}</strong><small>current curated slice</small></article>
          <article><span>Employers</span><strong>{data?.summary.employers ?? "—"}</strong><small>public career feeds</small></article>
          <article><span>Pay disclosed</span><strong>{data ? `${Math.round(data.summary.compensationCoverage * 100)}%` : "—"}</strong><small>of observations</small></article>
          <article><span>Median pay midpoint</span><strong>{data?.summary.medianAdvertisedPayMidpoint ? money(data.summary.medianAdvertisedPayMidpoint) : "—"}</strong><small>disclosed USD ranges</small></article>
        </div>
        <div className="signal-grid">
          <article className="skills-panel">
            <div className="panel-title"><span>SKILL EMERGENCE INDEX</span><small>current corpus frequency</small></div>
            <div className="skill-bars">{data?.summary.topSkills.map(([skill,count],i)=><div className="skill-row" key={skill}><b>{String(i+1).padStart(2,"0")}</b><span>{skill}</span><i><em style={{width:`${count/maxSkill*100}%`}} /></i><strong>{count}</strong></div>) || <p className="loading">Loading observation ledger…</p>}</div>
          </article>
          <article className="domain-panel">
            <div className="panel-title"><span>WHERE THE WORK SITS</span><small>listing count</small></div>
            <div className="domain-list">{data && Object.entries(data.summary.domains).sort((a,b)=>b[1]-a[1]).map(([name,count])=><button key={name} onClick={()=>{setDomain(name); document.getElementById("ledger")?.scrollIntoView()}}><span>{name}</span><strong>{count}</strong><i style={{width:`${count/data.summary.observations*100}%`}} /></button>)}</div>
          </article>
        </div>
      </section>

      <section className="terms" id="terms">
        <div className="section-head"><div><span>02 / TERM MAP</span><h2>The language<br />of AI work.</h2></div><p>Normalized terms reveal what employers repeatedly ask for. Size shows listing frequency; color shows the kind of signal. Each daily observation becomes another frame in the longitudinal map.</p></div>
        <div className="term-controls"><div role="group" aria-label="Term family"><button className={termCategory==="All terms"?"active":""} onClick={()=>setTermCategory("All terms")}>All terms</button>{termCategories.map(category=><button className={termCategory===category?"active":""} key={category} onClick={()=>setTermCategory(category)}>{category}</button>)}</div><label><span>OBSERVATION DATE</span><select value={selectedDate || ""} onChange={e=>setSelectedDate(e.target.value)}>{data?.termTimeline.map(item=><option value={item.date} key={item.date}>{item.date}</option>)}</select></label></div>
        <div className="term-map-shell">
          <div className="word-map" aria-label="Map of recurring AI job terms">{visibleTerms.map(item=>{
            const size = 13 + Math.sqrt(item.count / termMax) * 45;
            return <button key={item.term} data-category={item.category} className={selectedTerm===item.term?"selected":""} style={{fontSize:`${size}px`}} onClick={()=>setSelectedTerm(item.term)}><span>{item.term}</span><small>{item.count}</small></button>;
          })}</div>
          <aside className="term-detail"><span>SELECTED TERM</span><h3>{selectedTerm || "Choose a term"}</h3>{selectedTermData && <><strong>{selectedTermData.count}<small> / {data?.summary.observations} listings</small></strong><div className="term-meter"><i style={{width:`${selectedTermData.share*100}%`}} /></div><dl><div><dt>FAMILY</dt><dd>{selectedTermData.category}</dd></div><div><dt>CHANGE</dt><dd>{selectedTermData.change === null ? "Baseline" : `${selectedTermData.change >= 0 ? "+" : ""}${selectedTermData.change}`}</dd></div><div><dt>EMPLOYERS</dt><dd>{termEmployers.join(", ") || "—"}</dd></div></dl></>}</aside>
        </div>
        <div className="term-time"><span>TIME</span>{data?.termTimeline.map((item,index)=><button key={item.date} className={selectedDate===item.date?"active":""} onClick={()=>setSelectedDate(item.date)}><i /><b>{index===0?"BASELINE":item.date.slice(5)}</b></button>)}<em>Daily frames accumulate automatically</em></div>
      </section>

      <section className="ledger" id="ledger">
        <div className="section-head light"><div><span>03 / EVIDENCE LEDGER</span><h2>Inspect the<br />observations.</h2></div><p>Open any listing to see evidence-backed classifications, explicit facts, and model-derived inferences.</p></div>
        <div className="filters"><label><span>SEARCH</span><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Title, employer, place, or skill" /></label><label><span>DOMAIN</span><select value={domain} onChange={e=>setDomain(e.target.value)}><option>All domains</option>{domains.map(d=><option key={d}>{d}</option>)}</select></label><div className="result-count"><strong>{filtered.length}</strong><span>matching observations</span></div></div>
        <div className="table" role="table" aria-label="Job listing observations">
          <div className="tr table-head" role="row"><span>EMPLOYER / ROLE</span><span>DOMAIN</span><span>SENIORITY</span><span>PAY</span><span /></div>
          {filtered.slice(0,30).map(item=><button className="tr" role="row" key={item.observationId} onClick={()=>setSelected(item)}><span><b>{item.employer}</b><strong>{item.title}</strong><small>{item.location}</small></span><span><i className="dot" />{item.domain}</span><span>{item.seniority}</span><span>{item.compensation ? `${money(item.compensation.minimum)}–${money(item.compensation.maximum)}` : "Not disclosed"}</span><span className="open">↗</span></button>)}
        </div>
        {filtered.length > 30 && <p className="table-note">Showing 30 of {filtered.length} matches. Refine the filters to inspect the remaining records.</p>}
      </section>

      <section className="forecast" id="forecast">
        <div className="section-head"><div><span>04 / SCENARIO ENGINE</span><h2>Forecast pressure,<br />not fate.</h2></div><p>Directional 12-month scenarios combine listing mix, responsibility language, skill concentration, and observed AI adoption. They are hypotheses to test.</p></div>
        <div className="scenario-tabs" role="group" aria-label="Forecast scenario">{Object.entries(scenarios).map(([key,value])=><button key={key} className={scenario===key?"active":""} onClick={()=>setScenario(key as keyof typeof scenarios)}>{value.name}</button>)}</div>
        <div className="forecast-body"><div className="dial"><span>12-MONTH SIGNAL</span><strong>+{model.autonomy}%</strong><small>AI autonomy language</small><i style={{"--dial":`${model.autonomy*3.2}deg`} as React.CSSProperties} /></div><div className="forecast-bars"><div><span>Emerging skill churn</span><i><em style={{width:`${model.skills*3}%`}} /></i><strong>+{model.skills}%</strong></div><div><span>Role redesign pressure</span><i><em style={{width:`${model.churn*4}%`}} /></i><strong>+{model.churn}%</strong></div><p>{model.note}</p></div><aside><span>MODEL DISCIPLINE</span><p>No single listing predicts displacement. Signals are revised as versions accumulate and compared against BLS employment, pay, and occupation outcomes.</p></aside></div>
      </section>

      <section className="method" id="method">
        <div className="section-head light"><div><span>05 / PROVENANCE</span><h2>Evidence first.<br />Inference labeled.</h2></div><p>The corpus preserves only metadata, hashes, normalized facts, and short supporting excerpts unless republication rights permit more.</p></div>
        <div className="pipeline"><article><b>01</b><h3>Observe</h3><p>Retrieve public source metadata at a recorded time. Hash each version.</p></article><article><b>02</b><h3>Extract</h3><p>Normalize skills, AI methods, responsibilities, seniority, and compensation.</p></article><article><b>03</b><h3>Evidence</h3><p>Attach a short source span to each explicit classification. Mark all inference.</p></article><article><b>04</b><h3>Compare</h3><p>Detect edits, repostings, removals, co-occurrence, and movement over time.</p></article></div>
        <div className="apocalypso"><div><span>DOWNSTREAM FEED</span><h3>Apocalypso-ready.</h3><p>A compact versioned signal export can join the AI module as an indicator of organizational AI operationalization and labor-transition pressure.</p></div><a href="/api/apocalypso/jobs-signal.json" download>Download signal JSON <b>↓</b></a></div>
        <div className="sources"><span>REFERENCE SERIES</span><a href="https://www.census.gov/library/stories/2026/05/ai-use-businesses.html" target="_blank">US Census BTOS ↗</a><a href="https://www.anthropic.com/research/economic-index-june-2026-report" target="_blank">Anthropic Economic Index ↗</a><a href="https://www.pwc.com/gx/en/issues/artificial-intelligence/job-barometer/2026.html" target="_blank">PwC AI Jobs Barometer ↗</a><a href="https://www.bls.gov/ooh/" target="_blank">BLS Occupational Outlook ↗</a></div>
      </section>

      {selected && <div className="drawer-backdrop" onMouseDown={()=>setSelected(null)}><aside className="drawer" onMouseDown={e=>e.stopPropagation()} aria-label="Observation detail"><button className="close" onClick={()=>setSelected(null)}>CLOSE ×</button><span className="drawer-kicker">OBSERVATION · VERSIONED</span><h2>{selected.title}</h2><h3>{selected.employer} · {selected.location}</h3><div className="fact-grid"><div><span>DOMAIN</span><b>{selected.domain}</b></div><div><span>SENIORITY</span><b>{selected.seniority}</b></div><div><span>PAY</span><b>{selected.compensation?`${money(selected.compensation.minimum)}–${money(selected.compensation.maximum)}`:"Not disclosed"}</b></div><div><span>CONTENT HASH</span><b>{selected.contentHash.slice(7,19)}…</b></div></div><h4>Evidence-backed signals</h4>{[...selected.classifications.aiRelationship,...selected.classifications.systemLayer,...selected.classifications.skills].slice(0,6).map((hit,i)=><blockquote key={`${hit.label}-${i}`}><b>{hit.label}</b><p>“{hit.evidence}”</p><small>EXPLICIT · SOURCE SPAN</small></blockquote>)}<h4>Model-derived interpretation</h4><div className="inferences"><span>{selected.classifications.laborEffect.label}</span><span>{selected.classifications.humanRole.label}</span><span>{selected.classifications.maturity.label}</span></div><p className="caution">These labels are hypotheses derived from listing language, not employer assertions.</p><a className="source-button" href={selected.sourceUrl} target="_blank" rel="noreferrer">Open source listing ↗</a></aside></div>}
    </>
  );
}
