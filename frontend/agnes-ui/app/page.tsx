'use client'

import { useMemo, useState } from 'react'

const priorities = [
  { key: 'cost', label: 'Reduce Cost', hint: 'Maximize price savings' },
  { key: 'suppliers', label: 'Reduce Supplier Count', hint: 'Consolidate fragmented buying' },
  { key: 'risk', label: 'Reduce Risk / Improve Reliability', hint: 'Protect service and lead times' },
  { key: 'sustainability', label: 'Improve Sustainability', hint: 'Lower environmental impact' },
] as const

type PriorityKey = (typeof priorities)[number]['key']

export default function Home() {
  const [ingredient, setIngredient] = useState('')
  const [priority, setPriority] = useState<PriorityKey>('cost')
  const [status, setStatus] = useState('Ready')

  const selectedPriority = useMemo(
    () => priorities.find((item) => item.key === priority)?.label ?? 'Reduce Cost',
    [priority],
  )

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

        <section className="hero">
          <h1>Agnes</h1>
          <p>AI Supply Chain Manager</p>
        </section>

        {/* <section className="statGrid">
          <article className="statCard">
            <strong>21</strong>
            <small>Products analyzed</small>
          </article>
          <article className="statCard">
            <strong>39</strong>
            <small>Substitute options</small>
          </article>
          <article className="statCard">
            <strong>12</strong>
            <small>Supplier consolidations</small>
          </article>
          <article className="statCard">
            <strong>EUR 241k</strong>
            <small>Estimated annual savings</small>
          </article>
        </section> */}

        <section className="contentGrid">
          <article className="panel leftPanel">
            <h2>Substitution Input</h2>
            <p className="muted">Enter one ingredient and choose the main optimization objective.</p>

            <label className="fieldLabel" htmlFor="ingredient">
              Ingredient Type
            </label>
            <input
              id="ingredient"
              value={ingredient}
              onChange={(event) => setIngredient(event.target.value)}
              placeholder="e.g. sulfate"
              className="textInput"
            />

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
          </article>

          <aside className="panel rightPanel">
            <h3>Selected Target</h3>
            <p className="ingredientValue">{ingredient.trim() || 'No ingredient entered yet'}</p>

            <div className="miniBlock">
              <span>Priority</span>
              <strong>{selectedPriority}</strong>
            </div>

            <div className="miniBlock">
              <span>Next Step</span>
              <strong>Run matching and compliance checks</strong>
            </div>

            <div className="runSection">
              <button
                type="button"
                className="runBtn"
                onClick={() =>
                  setStatus(
                    `Running analysis for ${ingredient.trim() || 'selected ingredient'} with ${selectedPriority}.`,
                  )
                }
              >
                Run Analysis
              </button>
              <p className="runStatus">{status}</p>
            </div>
          </aside>
        </section>
      </section>
    </main>
  )
}
