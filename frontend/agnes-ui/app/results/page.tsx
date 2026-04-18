'use client'

import { useEffect, useMemo, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

type Substitute = {
  name: string
  sku: string | null
  confidenceScore: number
  reasoning: string
  hybridSimilarity: number | null
  pricePerKg?: number | null
  supplierCount?: number
  rank: number
  rankingReasoning?: string | null
  recommendedSupplier?: {
    id: number
    name: string
    pricePerKg: number
    distanceKm: number
  } | null
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
  priorityLabel: string
  bomIngredientNames: string[]
  substitutes: Substitute[]
  usedFallback: boolean
  substitutionLlmError: string | null
  recommendationLlmError: string | null
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

function summarizeFallbackReason(message: string | null) {
  if (!message) return null
  if (message.includes('RESOURCE_EXHAUSTED') || message.includes('429')) {
    return 'The live model hit a temporary rate limit, so fallback ranking was used.'
  }
  if (message.includes('GEMINI_API_KEY') || message.includes('VERTEX_PROJECT_ID')) {
    return 'Live model credentials are not configured, so fallback ranking was used.'
  }
  return message
}

function capitalizeFirstLetter(str: string) {
  if (!str) return str;
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// 1. Rename your original component to ResultsContent (or similar)
function ResultsContent() {
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
          productId: productId ?? '',
          targetSku: targetSku ?? '',
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
  const fallbackReasons = useMemo(
      () =>
          [result?.substitutionLlmError, result?.recommendationLlmError]
              .map((message) => summarizeFallbackReason(message ?? null))
              .filter((message, index, all) => Boolean(message) && all.indexOf(message) === index) as string[],
      [result],
  )

  return (
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
            Finding substitutes for <span>{capitalizeFirstLetter(result?.targetIngredient.name ?? 'selected ingredient')}</span>
          </h1>
          <p>
            This run combines hybrid substitute discovery, profile enrichment, and contextual LLM
            validation and then sorts the viable substitutes based on the selected business priority.
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
              <strong>{capitalizeFirstLetter(result?.targetIngredient.name ?? 'Loading...')}</strong>
              <span>{result?.targetIngredient.sku ?? 'Waiting for ingredient info'}</span>
            </article>
            <article className="runInfoTile">
              <small>Priority</small>
              <strong>{formatPriority(priority)}</strong>
              <span>{result ? `${result.bomIngredientNames.length} BOM ingredients in context` : 'Preparing context'}</span>
            </article>
          </div>
        </section>

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
                    <div className="warningPanelHeader">
                <span className="warningPanelIcon" aria-hidden="true">
                  ▲
                </span>
                      <h2>Fallback Mode</h2>
                    </div>
                    <p className="muted">
                      Part of the live LLM flow was unavailable, so the app used fallback ranking for this run.
                    </p>
                    {fallbackReasons.length > 0 && (
                        <div className="warningReasonList">
                          {fallbackReasons.map((reason) => (
                              <span key={reason} className="warningReasonChip">
                      {reason}
                    </span>
                          ))}
                        </div>
                    )}
                  </section>
              )}

              <section className="recHeader">
                <div>
                  <h2>Validated Substitutes</h2>
                  <p>Sorted by the backend using the selected business priority</p>
                </div>
                <div className="recHeaderActions">
                  <span className="updatedNow">● {topSubstitutes.length} substitutes returned</span>
                </div>
              </section>

              {topSubstitutes.length === 0 ? (
                  <section className="panel liveResultsPanel emptyStatePanel">
                    <div className="emptyStateHeader">
                <span className="emptyStateIcon" aria-hidden="true">
                  ◌
                </span>
                      <h2>No Validated Substitutes</h2>
                    </div>
                    <p className="muted">
                      The pipeline did not find any substitutes that passed validation strongly enough to rank.
                    </p>
                  </section>
              ) : (
                  <section className="substituteResultsGrid">
                    {topSubstitutes.map((substitute, index) => (
                        <article key={`${substitute.name}-${index}`} className="substituteResultCard">
                          <div className="substituteCardTop">
                            <div>
                              <small>{substitute.rank ? `Rank ${substitute.rank}` : `Option ${index + 1}`}</small>
                              <h3>
                                {capitalizeFirstLetter(substitute.name)}
                                {substitute.recommendedSupplier && (
                                  <span className="recommendedSupplierHighlight">
                                    {' '}— by {capitalizeFirstLetter(substitute.recommendedSupplier.name)}
                                  </span>
                                )}
                              </h3>
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
                              <span>Price / kg</span>
                              <strong>
                                {substitute.pricePerKg != null ? substitute.pricePerKg.toFixed(2) : 'n/a'}
                              </strong>
                            </div>
                            <div className="substituteMetricChip">
                              <span>Supplier Options</span>
                              <strong>
                                {substitute.supplierCount ?? 0}
                              </strong>
                            </div>
                            {substitute.recommendedSupplier && (
                                <div className="substituteMetricChip">
                                  <span>Recommended Supplier</span>
                                  <strong>{substitute.recommendedSupplier.name}</strong>
                                </div>
                            )}
                          </div>

                          <p className="substituteReasoning">
                            {substitute.rankingReasoning ?? substitute.reasoning}
                          </p>
                        </article>
                    ))}
                  </section>
              )}
            </>
        )}
      </section>
  )
}

// 2. Create a new default export that wraps the content in Suspense
export default function ResultsPage() {
  return (
      <main className="pageShell">
        <Suspense fallback={<div>Loading interface...</div>}>
          <ResultsContent />
        </Suspense>
      </main>
  )
}