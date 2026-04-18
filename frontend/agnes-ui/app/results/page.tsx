'use client'

import { useMemo, useState } from 'react'

type Alternative = {
  rank: number
  company: string
  product: string
  supplier: string
  similarity: string
  costImpact: string
  scoreClass: 'good' | 'warn'
  reasons: string[]
}

const alternatives: Alternative[] = [
  {
    rank: 1,
    company: 'EcoChem Supply',
    product: 'Sodium Sulfate Substitute',
    supplier: 'EcoChem Supply',
    similarity: '8.5',
    costImpact: '-32%',
    scoreClass: 'good',
    reasons: [
      'Lowest landed cost among validated options with strong margin upside.',
      'High functional similarity supports low-friction formulation transfer.',
      'Supplier has stable replenishment history and strong delivery adherence.',
      'Expected implementation effort is moderate and operationally manageable.',
    ],
  },
  {
    rank: 2,
    company: 'ValueChem Limited',
    product: 'Optimized Sulfate Blend',
    supplier: 'ValueChem Ltd.',
    similarity: '8.2',
    costImpact: '-28%',
    scoreClass: 'good',
    reasons: [
      'Strong cost reduction while preserving key performance characteristics.',
      'Blend profile aligns well with current quality acceptance thresholds.',
      'Vendor diversification improves resilience without major complexity.',
      'Good candidate for phased rollout across multiple product lines.',
    ],
  },
  {
    rank: 3,
    company: 'GreenMaterials Inc.',
    product: 'Sustainable Sulfate Option',
    supplier: 'GreenMaterials Inc.',
    similarity: '7.9',
    costImpact: '-22%',
    scoreClass: 'good',
    reasons: [
      'Balances savings and sustainability objectives for broader stakeholder buy-in.',
      'Operational fit is acceptable with manageable process adjustments.',
      'Improves ESG narrative while retaining economic viability.',
      'Suitable for premium SKUs where sustainability positioning is strategic.',
    ],
  },
  {
    rank: 4,
    company: 'CostSaver Solutions',
    product: 'Low-Cost Sulfate Mix',
    supplier: 'CostSaver Solutions',
    similarity: '7.7',
    costImpact: '-18%',
    scoreClass: 'warn',
    reasons: [
      'Attractive cost benefit, though qualification effort is slightly higher.',
      'Technical similarity is acceptable but warrants additional validation steps.',
      'Can reduce dependency on current supplier cluster.',
      'Recommended when speed-to-value is less critical than margin capture.',
    ],
  },
  {
    rank: 5,
    company: 'NordChem',
    product: 'Industrial Sulfate Alternative',
    supplier: 'NordChem',
    similarity: '7.4',
    costImpact: '-15%',
    scoreClass: 'warn',
    reasons: [
      'Moderate savings with robust supply footprint in key regions.',
      'Viable fallback option for continuity planning and dual-sourcing.',
      'Technical match is workable but not best-in-class.',
      'Best positioned as a risk-mitigation lane rather than primary source.',
    ],
  },
  { rank: 6, company: 'BlueCore Materials', product: 'Refined Sulfate Base', supplier: 'BlueCore', similarity: '8.1', costImpact: '-24%', scoreClass: 'good', reasons: ['Strong total-cost profile with low switching friction.', 'Reliable fill-rate history supports service-level continuity.', 'Good strategic fit for supplier consolidation initiatives.', 'Minimal expected impact on downstream manufacturing cadence.'] },
  { rank: 7, company: 'PureAxis Labs', product: 'Process-Stable Sulfate', supplier: 'PureAxis', similarity: '8.0', costImpact: '-21%', scoreClass: 'good', reasons: ['Stable process behavior lowers execution risk at plant level.', 'Cost improvement remains material at scale.', 'Supports standardized sourcing playbook across sites.', 'Recommended for fast pilot-to-scale transition.'] },
  { rank: 8, company: 'Synterra Inputs', product: 'Balanced Sulfate Compound', supplier: 'Synterra', similarity: '7.8', costImpact: '-20%', scoreClass: 'warn', reasons: ['Competitive economics with acceptable quality profile.', 'Requires tighter inbound quality monitoring initially.', 'Provides additional negotiation leverage across current vendors.', 'Good secondary lane for multi-supplier strategy.'] },
  { rank: 9, company: 'PrimeMatter Co.', product: 'Functional Sulfate Alternative', supplier: 'PrimeMatter', similarity: '7.6', costImpact: '-17%', scoreClass: 'warn', reasons: ['Useful value option for cost-sensitive product segments.', 'Qualification effort is moderate but contained.', 'Adds geographic balance to current supplier portfolio.', 'Appropriate where service flexibility outweighs max savings.'] },
  { rank: 10, company: 'IntegraChem', product: 'High-Purity Sulfate Mix', supplier: 'IntegraChem', similarity: '8.3', costImpact: '-25%', scoreClass: 'good', reasons: ['High purity profile supports quality-sensitive applications.', 'Strong savings case with low projected compliance risk.', 'Supplier capability aligns with long-term growth demand.', 'Good anchor candidate for strategic contract renegotiation.'] },
  { rank: 11, company: 'Luma Industrial', product: 'Standardized Sulfate Input', supplier: 'Luma', similarity: '7.5', costImpact: '-16%', scoreClass: 'warn', reasons: ['Delivers baseline savings with straightforward onboarding.', 'Useful optionality for seasonal demand spikes.', 'Requires moderate validation before broad deployment.', 'Best as tactical supplement to core suppliers.'] },
  { rank: 12, company: 'EverSource Materials', product: 'Efficient Sulfate Variant', supplier: 'EverSource', similarity: '7.9', costImpact: '-19%', scoreClass: 'good', reasons: ['Good blend of operational fit and cost performance.', 'Lower volatility in recent pricing benchmarks.', 'Supports near-term procurement optimization targets.', 'Suitable for staged substitution strategy.'] },
  { rank: 13, company: 'Vector Raw Inputs', product: 'Scalable Sulfate Option', supplier: 'Vector', similarity: '7.8', costImpact: '-18%', scoreClass: 'warn', reasons: ['Scalable supply model supports demand growth planning.', 'Cost benefit remains meaningful across volumes.', 'Needs tighter SLA controls at onboarding phase.', 'Strong candidate for regional rollout.'] },
  { rank: 14, company: 'AtlasChem Group', product: 'Commercial Sulfate Base', supplier: 'AtlasChem', similarity: '7.3', costImpact: '-14%', scoreClass: 'warn', reasons: ['Lower upside but useful for portfolio diversification.', 'Best used to strengthen continuity and negotiation posture.', 'Technical fit is adequate for non-critical SKUs.', 'Can serve as contingency source in disruption scenarios.'] },
  { rank: 15, company: 'NovaBulk Solutions', product: 'Bulk Sulfate Replacement', supplier: 'NovaBulk', similarity: '7.2', costImpact: '-13%', scoreClass: 'warn', reasons: ['Delivers incremental savings with broad availability.', 'Helps reduce concentration exposure to incumbent suppliers.', 'Requires more rigorous quality checks before scale-up.', 'Viable as reserve option within sourcing playbook.'] },
]

export default function ResultsPage() {
  const [selectedRank, setSelectedRank] = useState<number>(1)

  const selectedAlternative = useMemo(
    () => alternatives.find((item) => item.rank === selectedRank) ?? alternatives[0],
    [selectedRank],
  )

  return (
    <main className="pageShell">
      <section className="dashboard resultsDashboard">
        <header className="topbar">
          <div className="brandWrap">
            <span className="brandDot" />
            <span className="brandText">Spherecast</span>
          </div>

          <nav className="navLinks">
            <span>Solution</span>
            <span>Benefits</span>
            <span>Features</span>
            <span>Customers</span>
            <span>Blog</span>
            <span>Careers</span>
          </nav>

          <div className="actions">
            <button type="button" className="loginBtn">
              Log In
            </button>
            <button type="button" className="ghostBtn">
              Book a Demo
            </button>
          </div>
        </header>

        <section className="resultsHero">
          <div>
            <h1>Agnes</h1>
            <p>AI Supply Chain Manager</p>
            <a href="/" className="backLink">
              ← New Analysis
            </a>
          </div>
          <div className="heroActions">
            <span className="badge">Analysis completed • 21 products analyzed</span>
            <button type="button" className="ghostBtn">
              Download Results
            </button>
          </div>
        </section>

        <h2 className="resultsTitle">
          Results for: <span>Sulfate</span>
        </h2>

        <section className="kpiRow">
          <article className="statCard">
            <strong>15</strong>
            <small>Optimal Alternatives</small>
          </article>
          <article className="statCard">
            <strong>5</strong>
            <small>Suppliers Recommended</small>
          </article>
          <article className="statCard">
            <strong>28%</strong>
            <small>Avg. Cost Reduction</small>
          </article>
          <article className="statCard">
            <strong>EUR 68k</strong>
            <small>Estimated Annual Savings</small>
          </article>
        </section>

        <section className="resultsGrid">
          <article className="panel tablePanel">
            <h3>Top Alternatives</h3>
            <div className="altTableWrap">
              <table className="altTable">
                <thead>
                  <tr>
                    <th>Alternative</th>
                    <th>Supplier</th>
                    <th>Similarity</th>
                    <th>Est. Cost Impact</th>
                  </tr>
                </thead>
                <tbody>
                  {alternatives.map((item) => (
                    <tr
                      key={item.rank}
                      className={selectedRank === item.rank ? 'altRowSelected' : ''}
                      onClick={() => setSelectedRank(item.rank)}
                    >
                      <td>
                        <div className="altCell">
                          <span className="rank">{item.rank}</span>
                          <div>
                            <strong>{item.company}</strong>
                            <small>{item.product}</small>
                          </div>
                        </div>
                      </td>
                      <td>{item.supplier}</td>
                      <td>
                        <span className={`score ${item.scoreClass}`}>{item.similarity}</span>
                      </td>
                      <td className="impact">{item.costImpact}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </article>

          <aside className="resultsSide">
            <article className="panel">
              <h3>Selected Target</h3>
              <div className="miniBlock">
                <span>Ingredient</span>
                <strong>Sulfate</strong>
              </div>
              <div className="miniBlock">
                <span>Priority</span>
                <strong>Reduce Cost</strong>
              </div>
              <div className="miniBlock">
                <span>Selected supplier</span>
                <strong>{selectedAlternative.supplier}</strong>
              </div>
            </article>

            <article className="panel">
              <h3>Why This Alternative Is Better</h3>
              <ul className="reasoningList">
                {selectedAlternative.reasons.map((reason, index) => (
                  <li key={index}>{reason}</li>
                ))}
              </ul>
            </article>
          </aside>
        </section>
      </section>
    </main>
  )
}
