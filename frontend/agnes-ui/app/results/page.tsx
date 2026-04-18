'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

type ClusterCandidate = {
  sku: string
  name: string
  hybridSimilarity: number
}

type Substitute = {
  name: string
  sku: string | null
  confidenceScore: number
  reasoning: string
  hybridSimilarity: number | null
}

type AnalysisResult = {
  product: {
    id: number
    sku: string
    label: string
    companyName: string
  }
  targetIngredient: {
    sku: string
    name: string
  }
  priority: string
  bomIngredientNames: string[]
  clusterCandidates: ClusterCandidate[]
  substitutes: Substitute[]
  usedFallback: boolean
  llmError: string | null
}

const priorityLabels: Record<string, string> = {
  cost: 'Reduce Cost',
  suppliers: 'Reduce Supplier Count',
  risk: 'Reduce Risk / Improve Reliability',
  sustainability: 'Improve Sustainability',
}

function formatPriority(priority: string) {
  return priorityLabels[priority] ?? priority
}

function scorePercent(value: number | null | undefined) {
  if (value == null) return 'n/a'
  return `${Math.round(value * 100)}%`
}

export default function ResultsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const productId = searchParams.get('productId')
  const targetSku = searchParams.get('targetSku')
  const priority = searchParams.get('priority') ?? 'cost'
  const missingSelection = !productId || !targetSku

  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (missingSelection) {
      return
    }

    let cancelled = false

    async function loadAnalysis() {
      try {
        setLoading(true)
        const params = new URLSearchParams({
          productId,
          targetSku,
          priority,
        })
        const response = await fetch(`/api/analyze?${params.toString()}`, { cache: 'no-store' })
        const data = (await response.json()) as AnalysisResult & { error?: string }

        if (!response.ok) {
          throw new Error(data.error ?? 'Failed to run substitution analysis.')
        }

        if (!cancelled) {
          setResult(data)
          setError(null)
        }
      } catch (err) {
        console.error(err)
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to run substitution analysis.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadAnalysis()
    return () => {
      cancelled = true
    }
  }, [missingSelection, priority, productId, targetSku])

  const topSubstitutes = useMemo(() => result?.substitutes ?? [], [result])

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
            <button
              type="button"
              className="ghostBtn"
              onClick={() => window.open('/api/cluster-visualization', '_blank', 'noopener,noreferrer')}
            >
              View Clusters
            </button>
            <button type="button" className="ghostBtn" onClick={() => router.push('/')}>
              Back
            </button>
          </div>
        </header>

        <section className="agentRunCard">
          <div className="agentRunMeta">
            <span className="runChip">● Live Analysis</span>
            <span>{loading ? 'Running clustering and LLM validation...' : 'Analysis complete'}</span>
          </div>

          <h1>
            Finding substitutes for <span>{result?.targetIngredient.name ?? 'selected ingredient'}</span>
          </h1>
          <p>
            This run combines hybrid substitute discovery, profile enrichment, and contextual LLM
            validation for the selected finished good.
          </p>

          <div className="runInfoGrid">
            <article className="runInfoTile">
              <small>Company</small>
              <strong>{result?.product.companyName ?? 'Loading...'}</strong>
              <span>Customer context from the SQLite catalog</span>
            </article>
            <article className="runInfoTile">
              <small>Product</small>
              <strong>{result?.product.label ?? 'Loading...'}</strong>
              <span>{result?.product.sku ?? 'Waiting for product info'}</span>
            </article>
            <article className="runInfoTile">
              <small>Target Ingredient</small>
              <strong>{result?.targetIngredient.name ?? 'Loading...'}</strong>
              <span>{result?.targetIngredient.sku ?? 'Waiting for ingredient info'}</span>
            </article>
            <article className="runInfoTile">
              <small>Priority</small>
              <strong>{formatPriority(priority)}</strong>
              <span>{result ? `${result.bomIngredientNames.length} BOM ingredients in context` : 'Preparing context'}</span>
            </article>
          </div>
        </section>

        {loading && (
          <section className="panel liveResultsPanel">
            <h2>Running Analysis</h2>
            <p className="muted">
              Agnes is computing hybrid similarity candidates, building ingredient profiles, and asking the
              LLM to validate which substitutes work in this BOM.
            </p>
          </section>
        )}

        {missingSelection && (
          <section className="panel liveResultsPanel errorPanel">
            <h2>Missing Selection</h2>
            <p className="muted">Go back and choose a product plus an ingredient before running the analysis.</p>
          </section>
        )}

        {error && !loading && !missingSelection && (
          <section className="panel liveResultsPanel errorPanel">
            <h2>Analysis Failed</h2>
            <p className="muted">{error}</p>
          </section>
        )}

        {!loading && result && !missingSelection && (
          <>
            {result.usedFallback && (
              <section className="panel liveResultsPanel warningPanel">
                <h2>Fallback Mode</h2>
                <p className="muted">
                  The live LLM response was unavailable, so the shortlist is currently based on hybrid
                  similarity candidates. {result.llmError ? `Reason: ${result.llmError}` : ''}
                </p>
              </section>
            )}

            <section className="recHeader">
              <div>
                <h2>Validated Substitutes</h2>
                <p>Shortlisted after hybrid clustering and contextual LLM validation</p>
              </div>
              <div className="recHeaderActions">
                <span className="updatedNow">● {topSubstitutes.length} substitutes returned</span>
              </div>
            </section>

            {topSubstitutes.length === 0 ? (
              <section className="panel liveResultsPanel">
                <h2>No Viable Substitutes</h2>
                <p className="muted">
                  The pipeline did not find any substitutes that passed the current similarity threshold and
                  contextual validation for this BOM.
                </p>
              </section>
            ) : (
              <section className="substituteResultsGrid">
                {topSubstitutes.map((substitute, index) => (
                  <article key={`${substitute.name}-${index}`} className="substituteResultCard">
                    <div className="substituteCardTop">
                      <div>
                        <small>Option {index + 1}</small>
                        <h3>{substitute.name}</h3>
                      </div>
                      <div className="substituteConfidence">
                        <span>Confidence</span>
                        <strong>{substitute.confidenceScore}</strong>
                      </div>
                    </div>

                    <div className="substituteMetricRow">
                      <div className="substituteMetricChip">
                        <span>Hybrid Similarity</span>
                        <strong>{scorePercent(substitute.hybridSimilarity)}</strong>
                      </div>
                      <div className="substituteMetricChip">
                        <span>SKU</span>
                        <strong>{substitute.sku ?? 'Not resolved'}</strong>
                      </div>
                    </div>

                    <p className="substituteReasoning">{substitute.reasoning}</p>
                  </article>
                ))}
              </section>
            )}

          </>
        )}
      </section>
    </main>
  )
}
