import Observatory from "./Observatory";

export default function Home() {
  return <main>
    <header className="masthead">
      <a className="wordmark" href="#top">JOBS<span>/CASTALIA</span></a>
      <nav aria-label="Primary navigation"><a href="#signals">Signals</a><a href="#terms">Term map</a><a href="#ledger">Ledger</a><a href="#forecast">Forecast</a><a href="#method">Method</a></nav>
      <div className="live"><i /> OBSERVATORY ACTIVE</div>
    </header>
    <section className="hero" id="top">
      <div className="eyebrow">CASTALIA AI LABOR OBSERVATORY · OPEN RESEARCH</div>
      <h1>Job listings are<br /><em>evidence of change.</em></h1>
      <div className="hero-bottom"><p className="lede">A longitudinal record of how organizations operationalize artificial intelligence—what they fund, what they value, and how human work is being redesigned.</p><a className="primary" href="#ledger">Inspect the evidence <span>↘</span></a></div>
      <div className="scope"><span>BUILDS</span><span>DEPLOYS</span><span>GOVERNS</span><span>EVALUATES</span><span>USES</span></div>
    </section>
    <Observatory />
    <footer><a className="wordmark" href="#top">JOBS<span>/CASTALIA</span></a><p>AI labor intelligence for public understanding.</p><span>VERSION 0.1 · EVIDENCE LEDGER</span></footer>
  </main>;
}
