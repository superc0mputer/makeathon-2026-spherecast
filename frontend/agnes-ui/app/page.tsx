'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'

const priorities = [
  { key: 'cost', label: 'Reduce Cost', hint: 'Maximize price savings' },
  { key: 'suppliers', label: 'Reduce Supplier Count', hint: 'Consolidate fragmented buying' },
  { key: 'risk', label: 'Reduce Risk / Improve Reliability', hint: 'Protect service and lead times' },
  { key: 'sustainability', label: 'Improve Sustainability', hint: 'Lower environmental impact' },
] as const

type PriorityKey = (typeof priorities)[number]['key']

type Company = {
  id: number
  name: string
  productCount: number
}

type Product = {
  id: number
  sku: string
  label: string
  ingredientCount: number
}

type Ingredient = {
  id: number
  sku: string
  name: string
}

type SelectedProduct = {
  id: number
  sku: string
  label: string
  companyId: number
  companyName: string
  ingredients: Ingredient[]
}

export default function Home() {
  const router = useRouter()
  const [companies, setCompanies] = useState<Company[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [selectedCompanyId, setSelectedCompanyId] = useState('')
  const [selectedProductId, setSelectedProductId] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<SelectedProduct | null>(null)
  const [selectedIngredientId, setSelectedIngredientId] = useState<number | null>(null)
  const [priority, setPriority] = useState<PriorityKey>('cost')
  const [status, setStatus] = useState('Choose a company and product to begin.')
  const [loadingCompanies, setLoadingCompanies] = useState(true)
  const [loadingProducts, setLoadingProducts] = useState(false)
  const [loadingProductDetails, setLoadingProductDetails] = useState(false)

  const selectedPriority = useMemo(
    () => priorities.find((item) => item.key === priority)?.label ?? 'Reduce Cost',
    [priority],
  )

  const selectedIngredient = useMemo(
    () => selectedProduct?.ingredients.find((ingredient) => ingredient.id === selectedIngredientId) ?? null,
    [selectedIngredientId, selectedProduct],
  )

  useEffect(() => {
    let cancelled = false

    async function loadCompanies() {
      try {
        const response = await fetch('/api/catalog')
        const data = (await response.json()) as { companies?: Company[] }
        if (!cancelled) {
          setCompanies(data.companies ?? [])
        }
      } catch (error) {
        console.error(error)
        if (!cancelled) {
          setStatus('Could not load companies from the database.')
        }
      } finally {
        if (!cancelled) {
          setLoadingCompanies(false)
        }
      }
    }

    void loadCompanies()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!selectedCompanyId) {
      return
    }

    let cancelled = false

    async function loadProducts() {
      try {
        const response = await fetch(`/api/catalog?companyId=${selectedCompanyId}`)
        const data = (await response.json()) as { products?: Product[] }
        if (!cancelled) {
          setProducts(data.products ?? [])
        }
      } catch (error) {
        console.error(error)
        if (!cancelled) {
          setStatus('Could not load products for that company.')
        }
      } finally {
        if (!cancelled) {
          setLoadingProducts(false)
        }
      }
    }

    void loadProducts()
    return () => {
      cancelled = true
    }
  }, [selectedCompanyId])

  useEffect(() => {
    if (!selectedProductId) {
      return
    }

    let cancelled = false

    async function loadProductDetails() {
      try {
        const params = new URLSearchParams({
          companyId: selectedCompanyId,
          productId: selectedProductId,
        })
        const response = await fetch(`/api/catalog?${params.toString()}`)
        const data = (await response.json()) as { selectedProduct?: SelectedProduct | null }
        if (!cancelled) {
          setSelectedProduct(data.selectedProduct ?? null)
          setSelectedIngredientId(null)
          setStatus('Product ready. Select one ingredient from the BOM to run substitution analysis.')
        }
      } catch (error) {
        console.error(error)
        if (!cancelled) {
          setStatus('Could not load the selected product details.')
        }
      } finally {
        if (!cancelled) {
          setLoadingProductDetails(false)
        }
      }
    }

    void loadProductDetails()
    return () => {
      cancelled = true
    }
  }, [selectedCompanyId, selectedProductId])

  return (
    <main className="pageShell">
      <section className="dashboard">
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
          <div className="agnesOverviewTag">AI Supply Chain Manager</div>
          <h1>
            Meet <span>Agnes</span>
          </h1>
          <p>
            <strong>Agnes</strong> is an AI Supply Chain Manager built for <strong>CPG sourcing teams</strong>.
            It connects fragmented BOM and supplier data, identifies credible substitute ingredients, and
            prioritizes options based on business goals such as <strong>cost</strong>,{' '}
            <strong>resilience</strong>, and <strong>sustainability</strong>.
          </p>
          <p>
            Instead of only giving a score, Agnes provides <strong>transparent reasoning</strong> for each
            recommendation so procurement, quality, and operations teams can make <strong>confident
            decisions faster</strong>.
          </p>
        </section>

        <section className="inputOnlyGrid">
          <article className="panel leftPanel inputPanelLarge">
            <h2>Substitution Input</h2>
            <p className="muted">
              Pick a company, choose one of its finished goods, and review the BOM ingredients available
              for substitution.
            </p>

            <label className="fieldLabel" htmlFor="company">
              Company
            </label>
            <select
              id="company"
              value={selectedCompanyId}
              onChange={(event) => {
                const nextCompanyId = event.target.value
                setLoadingProducts(Boolean(nextCompanyId))
                setSelectedCompanyId(nextCompanyId)
                setProducts([])
                setSelectedProductId('')
                setSelectedProduct(null)
                setSelectedIngredientId(null)
                setLoadingProductDetails(false)
                setStatus(
                  nextCompanyId
                    ? 'Company selected. Choose one of its products.'
                    : 'Choose a company and product to begin.',
                )
              }}
              className="textInput selectInput"
              disabled={loadingCompanies}
            >
              <option value="">
                {loadingCompanies ? 'Loading companies...' : 'Select a company'}
              </option>
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name} ({company.productCount} products)
                </option>
              ))}
            </select>

            <label className="fieldLabel" htmlFor="product">
              Product
            </label>
            <select
              id="product"
              value={selectedProductId}
              onChange={(event) => {
                const nextProductId = event.target.value
                setLoadingProductDetails(Boolean(nextProductId))
                setStatus(
                  nextProductId
                    ? 'Loading BOM ingredients for the selected product.'
                    : 'Company selected. Choose one of its products.',
                )
                setSelectedProductId(nextProductId)
                setSelectedProduct(null)
                setSelectedIngredientId(null)
              }}
              className="textInput selectInput"
              disabled={!selectedCompanyId || loadingProducts}
            >
              <option value="">
                {!selectedCompanyId
                  ? 'Select a company first'
                  : loadingProducts
                    ? 'Loading products...'
                    : 'Select a product'}
              </option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.label} ({product.ingredientCount} BOM ingredients)
                </option>
              ))}
            </select>

            {selectedProduct && (
              <section className="selectedProductCard">
                <div className="selectedProductHeader">
                  <div>
                    <p className="selectedProductEyebrow">Selected Product</p>
                    <h3>{selectedProduct.label}</h3>
                  </div>
                  <span className="selectedProductBadge">{selectedProduct.ingredients.length} ingredients</span>
                </div>

                <div className="selectedProductMeta">
                  <div className="miniBlock">
                    <span>Company</span>
                    <strong>{selectedProduct.companyName}</strong>
                  </div>
                  <div className="miniBlock">
                    <span>Product SKU</span>
                    <strong>{selectedProduct.sku}</strong>
                  </div>
                </div>

                <div className="ingredientOptions">
                  <p className="fieldLabel ingredientSectionLabel">Ingredients available for substitution</p>
                  <p className="ingredientHelperText">
                    Tap one ingredient to choose the substitution target for this product.
                  </p>
                  <div className="ingredientChipGrid">
                    {selectedProduct.ingredients.map((ingredient) => (
                      <button
                        key={ingredient.id}
                        type="button"
                        className={`ingredientChip ${selectedIngredientId === ingredient.id ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedIngredientId(ingredient.id)
                          setStatus(
                            `Selected ${ingredient.name} as the substitution target for ${selectedProduct.label}.`,
                          )
                        }}
                      >
                        <strong>{ingredient.name}</strong>
                        <span>{ingredient.sku}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </section>
            )}

            <p className="fieldLabel">Priority</p>
            <div className="priorityGrid">
              {priorities.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setPriority(item.key)}
                  className={`priorityCard ${priority === item.key ? 'active' : ''}`}
                >
                  <strong>{item.label}</strong>
                  <small>{item.hint}</small>
                </button>
              ))}
            </div>

            <div className="runSection">
              <button
                type="button"
                className="runBtn"
                disabled={!selectedIngredient || loadingProductDetails}
                onClick={() => {
                  if (!selectedProduct || !selectedIngredient) {
                    setStatus('Please choose a company, product, and ingredient before running the analysis.')
                    return
                  }

                  setStatus(
                    `Running analysis for ${selectedIngredient.name} in ${selectedProduct.label} with ${selectedPriority}.`,
                  )
                  const params = new URLSearchParams({
                    productId: String(selectedProduct.id),
                    targetSku: selectedIngredient.sku,
                    priority,
                  })
                  router.push(`/results?${params.toString()}`)
                }}
              >
                Run Analysis
              </button>
              <p className="runStatus">
                {loadingProductDetails ? 'Loading product ingredients...' : status}
              </p>
            </div>
          </article>
        </section>
      </section>
    </main>
  )
}
