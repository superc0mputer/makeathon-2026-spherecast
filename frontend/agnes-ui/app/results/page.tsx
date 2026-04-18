'use client'

import { useMemo, useState } from 'react'

type Recommendation = {
  id: string
  name: string
  cas: string
  formula: string
  tags: string[]
  score: number
  supplier: string
  supplierLocation: string
  distanceKm: number
  transitDays: number
  landedCost: number
  savingsPct: number
  confidence: number
  scores: {
    substitutability: number
    supplyChain: number
    bomMatch: number
    sustainability: number
  }
  aiRecommendation: string
}

const recommendations: Recommendation[] = [
  {
    id: 'potassium-sorbate',
    name: 'Potassium Sorbate',
    cas: '24634-61-5',
    formula: 'C6H7KO2',
    tags: ['FDA Approved', 'EU Compliant', 'Drop-in'],
    score: 94,
    supplier: 'Nordic BioChem AS',
    supplierLocation: 'Hamburg, DE',
    distanceKm: 412,
    transitDays: 4,
    landedCost: 3.85,
    savingsPct: 8.3,
    confidence: 96,
    scores: {
      substitutability: 96,
      supplyChain: 95,
      bomMatch: 92,
      sustainability: 88,
    },
    aiRecommendation:
      'Strongest preservative match with near-identical pH activity range. Hamburg-based supplier provides 4-day transit and measurable sourcing savings versus current baseline.',
  },
  {
    id: 'calcium-propionate',
    name: 'Calcium Propionate',
    cas: '4075-81-4',
    formula: 'C6H10CaO4',
    tags: ['EU Compliant', 'Bakery Proven', 'Low Risk'],
    score: 91,
    supplier: 'GreenMaterials Inc.',
    supplierLocation: 'Munich, DE',
    distanceKm: 186,
    transitDays: 2,
    landedCost: 3.96,
    savingsPct: 6.9,
    confidence: 93,
    scores: {
      substitutability: 92,
      supplyChain: 93,
      bomMatch: 90,
      sustainability: 89,
    },
    aiRecommendation:
      'High-confidence substitute with strong regional supplier reliability. Best fit when balancing cost improvement with smooth implementation across existing production lines.',
  },
  {
    id: 'sodium-acetate',
    name: 'Sodium Acetate',
    cas: '127-09-3',
    formula: 'C2H3NaO2',
    tags: ['Drop-in', 'EU Compliant', 'High Availability'],
    score: 88,
    supplier: 'ValueChem Ltd.',
    supplierLocation: 'Rotterdam, NL',
    distanceKm: 617,
    transitDays: 5,
    landedCost: 4.02,
    savingsPct: 5.4,
    confidence: 90,
    scores: {
      substitutability: 89,
      supplyChain: 90,
      bomMatch: 87,
      sustainability: 86,
    },
    aiRecommendation:
      'Operationally practical option with broad supplier depth. Recommended as a resilient dual-source lane for categories with volatile demand.',
  },
  {
    id: 'natamycin',
    name: 'Natamycin',
    cas: '7681-93-8',
    formula: 'C33H47NO13',
    tags: ['Label Friendly', 'Premium SKU Fit', 'EU Compliant'],
    score: 86,
    supplier: 'PureAxis Labs',
    supplierLocation: 'Zurich, CH',
    distanceKm: 302,
    transitDays: 3,
    landedCost: 4.18,
    savingsPct: 4.1,
    confidence: 89,
    scores: {
      substitutability: 87,
      supplyChain: 88,
      bomMatch: 85,
      sustainability: 90,
    },
    aiRecommendation:
      'Best suited for premium formulations where clean-label positioning matters. Provides moderate savings with positive sustainability impact and limited rollout friction.',
  },
]

function MetricBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="recMetricRow">
      <div className="recMetricTop">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <div className="recMetricTrack">
        <div className="recMetricFill" style={{ width: `${value}%` }} />
      </div>
    </div>
  )
}

export default function ResultsPage() {
  const [openIds, setOpenIds] = useState<string[]>([])

  const openRecommendations = useMemo(
    () =>
      openIds
        .map((id) => recommendations.find((item) => item.id === id))
        .filter((item): item is Recommendation => Boolean(item)),
    [openIds],
  )

  const closedRecommendations = useMemo(
    () => recommendations.filter((item) => !openIds.includes(item.id)),
    [openIds],
  )

  function openRecommendation(id: string) {
    setOpenIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
  }

  function closeRecommendation(id: string) {
    setOpenIds((prev) => prev.filter((item) => item !== id))
  }

  function closeAllRecommendations() {
    setOpenIds([])
  }

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

        <section className="agentRunCard">
          <div className="agentRunMeta">
            <span className="runChip">● Substitution Run</span>
            <span>Initiated 2 min ago • 23.3s total runtime</span>
          </div>

          <h1>
            Finding substitutes for <span>Sodium Benzoate (E211)</span>
          </h1>
          <p>
            Ranked by chemical viability, supply chain risk, sustainability, and total landed cost
            across Beverage Concentrate v3.4.
          </p>

          <div className="agentRunActions">
            <button type="button" className="ghostBtn altGhost">
              Adjust Weights
            </button>
            <button type="button" className="runBtn darkRunBtn">
              Export Report
            </button>
          </div>

          <div className="runInfoGrid">
            <article className="runInfoTile">
              <small>CAS Number</small>
              <strong>532-32-1</strong>
              <span>C7H5NaO2</span>
            </article>
            <article className="runInfoTile">
              <small>BOM</small>
              <strong>Beverage Concentrate v3.4</strong>
              <span>1,240 kg / batch</span>
            </article>
            <article className="runInfoTile">
              <small>Origin</small>
              <strong>Munich, DE</strong>
              <span>48.1351° N, 11.5820° E</span>
            </article>
            <article className="runInfoTile">
              <small>Current Cost</small>
              <strong>$4.20/kg</strong>
              <span>ChemPro Industries</span>
            </article>
          </div>
        </section>

        <section className="recHeader">
          <div>
            <h2>Top Recommendations</h2>
            <p>Ranked by the multi-criteria decision engine</p>
          </div>
          <div className="recHeaderActions">
            <span className="updatedNow">● Updated just now</span>
            {openIds.length > 0 && (
              <button type="button" className="collapseAllBtn" onClick={closeAllRecommendations}>
                Back to all substitutes
              </button>
            )}
          </div>
        </section>

        {openRecommendations.length > 0 && (
          <section className="expandedStack">
            {openRecommendations.map((selected) => (
              <article key={selected.id} className="detailCard">
                <div className="detailCardTopActions">
                  <button
                    type="button"
                    className="closePopupBtn"
                    onClick={() => closeRecommendation(selected.id)}
                  >
                    Close
                  </button>
                </div>
                <div className="detailHead">
                  <div>
                    <h3>{selected.name}</h3>
                    <p>
                      CAS {selected.cas} • {selected.formula}
                    </p>
                  </div>
                  <div className="recScoreBlock detailScore">
                    <span>Score</span>
                    <strong>{selected.score}</strong>
                  </div>
                </div>

                <div className="recTags detailTags">
                  {selected.tags.map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>

                <div className="detailMetrics">
                  <MetricBar label="Substitutability" value={selected.scores.substitutability} />
                  <MetricBar label="BOM Match" value={selected.scores.bomMatch} />
                  <MetricBar label="Supply Chain" value={selected.scores.supplyChain} />
                  <MetricBar label="Sustainability" value={selected.scores.sustainability} />
                </div>

                <div className="supplierRow">
                  <div>
                    <strong>{selected.supplier}</strong>
                    <span>{selected.supplierLocation}</span>
                  </div>
                  <div className="supplierMeta">
                    <strong>{selected.distanceKm} km</strong>
                    <span>{selected.transitDays}d transit</span>
                  </div>
                </div>

                <div className="costRow">
                  <div>
                    <small>Landed Cost</small>
                    <strong>
                      ${selected.landedCost.toFixed(2)} <span>/kg</span>
                    </strong>
                    <em>↓ {selected.savingsPct}%</em>
                  </div>
                  <div>
                    <small>Confidence</small>
                    <strong>{selected.confidence}%</strong>
                  </div>
                </div>

                <div className="aiRecommendationBox">
                  <small>AI Recommendation</small>
                  <p>{selected.aiRecommendation}</p>
                </div>

                <button type="button" className="runBtn selectBtn">
                  Select Substitute →
                </button>
              </article>
            ))}
          </section>
        )}

        {closedRecommendations.length > 0 && (
          <section className="recGrid">
            {closedRecommendations.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`recCard ${openIds.includes(item.id) ? 'active' : ''}`}
                onClick={() => openRecommendation(item.id)}
              >
                <div className="recCardTop">
                  <div>
                    <h3>{item.name}</h3>
                    <p>
                      CAS {item.cas} • {item.formula}
                    </p>
                  </div>
                  <div className="recScoreBlock">
                    <span>Score</span>
                    <strong>{item.score}</strong>
                  </div>
                </div>

                <div className="recTags">
                  {item.tags.map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>

                <div className="recCardBottom">
                  <span>
                    {item.supplier} • {item.supplierLocation}
                  </span>
                  <strong>
                    ${item.landedCost.toFixed(2)}/kg • ↓ {item.savingsPct}%
                  </strong>
                </div>
              </button>
            ))}
          </section>
        )}
      </section>
    </main>
  )
}
