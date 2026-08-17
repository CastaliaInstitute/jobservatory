import Observatory from "./Observatory";

export default function Home() {
  return <main>
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <header className="masthead">
      <a className="wordmark" href="#main-content">JOBSERVATORY<span>/CASTALIA</span></a>
      <nav aria-label="Primary navigation"><a href="#signals">Signals</a><a href="#terms">Term map</a><a href="#ledger">Search</a><a href="#lab">ML lab</a><a href="#method">Method</a><a href="/annotation.html">Annotate</a></nav>
      <div className="live"><i /> OBSERVATORY ACTIVE</div>
    </header>
    <section className="hero" id="main-content">
      <div className="eyebrow">JOBSERVATORY · CASTALIA AI LABOR RESEARCH</div>
      <h1>Job listings are<br /><em>evidence of change.</em></h1>
      <div className="hero-bottom"><p className="lede">A longitudinal record of how selected organizations describe artificial-intelligence work—what they seek, what they value, and how roles are being redesigned.</p><a className="primary" href="#ledger">Inspect the evidence <span>↘</span></a></div>
      <div className="scope"><span>BUILDS</span><span>DEPLOYS</span><span>GOVERNS</span><span>EVALUATES</span><span>USES</span></div>
    </section>
    <Observatory />
    <footer><a className="wordmark" href="#main-content">JOBSERVATORY<span>/CASTALIA</span></a><p>AI labor intelligence for public understanding.</p><span>VERSION 0.2 · ML LAB BASELINE</span></footer>
  </main>;
}
