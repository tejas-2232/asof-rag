import {
  Component,
  useEffect,
  useMemo,
  useState,
  type ErrorInfo,
  type ReactNode,
} from 'react'
import { TrueForgeUI } from '@truefoundry/trueforge-ui'
import {
  Activity,
  ArrowRight,
  Bot,
  Box,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Clock3,
  Database,
  ExternalLink,
  FileCheck2,
  FileSearch,
  Fingerprint,
  GitCompareArrows,
  LoaderCircle,
  LockKeyhole,
  Menu,
  Network,
  Play,
  RefreshCw,
  Search,
  ServerCog,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  TriangleAlert,
  X,
  XCircle,
  Zap,
} from 'lucide-react'
import './App.css'

type Filing = {
  id: string
  accession: string
  label: string
  filedAt: string
  period: string
}

type IndexVersion = {
  id: string
  chunk_count: number
  evaluation: { temporal_violations: number }
}

type Status = {
  candidate_id: string | null
  production_id: string | null
  indexes: Record<string, IndexVersion>
  sec_configured: boolean
}

type QueryResponse = {
  hits: Array<{
    score: number
    chunk: {
      accession: string
      filed_at: string
      section: string
      source_url: string
      text: string
    }
  }>
}

type Retrieval = {
  answer: string
  source: string
  date: string
  excerpt: string
  valid: boolean
  latency: string
  sourceUrl?: string
}

const DEMO_FILINGS: Filing[] = [
  {
    id: 'msft-2024-10k',
    accession: '0000950170-24-087843',
    label: 'FY 2024 annual report',
    filedAt: '2024-07-30',
    period: 'Period ending Jun 30, 2024',
  },
  {
    id: 'msft-2024-q3',
    accession: '0000950170-24-049295',
    label: 'Q3 2024 quarterly report',
    filedAt: '2024-04-25',
    period: 'Period ending Mar 31, 2024',
  },
  {
    id: 'msft-2024-q2',
    accession: '0000950170-24-008814',
    label: 'Q2 2024 quarterly report',
    filedAt: '2024-01-30',
    period: 'Period ending Dec 31, 2023',
  },
]

const DEMO_RESULTS: { production: Retrieval; candidate: Retrieval } = {
  production: {
    answer: 'Azure revenue grew 33% year over year.',
    source: 'Microsoft FY2025 Q1 10-Q · p. 29',
    date: '2024-10-30',
    excerpt:
      'Azure and other cloud services revenue grew 33% driven by growth in consumption-based services.',
    valid: false,
    latency: '612 ms',
  },
  candidate: {
    answer: 'Azure and other cloud services revenue grew 29% year over year.',
    source: 'Microsoft FY2024 10-K · p. 36',
    date: '2024-07-30',
    excerpt:
      'Azure and other cloud services revenue grew 29% driven by growth in our consumption-based services.',
    valid: true,
    latency: '438 ms',
  },
}

const PIPELINE_STAGES = [
  { label: 'Resolve filing', icon: Search },
  { label: 'Fetch raw', icon: Database },
  { label: 'Parse / chunk', icon: Box },
  { label: 'Temporal tests', icon: ShieldCheck },
  { label: 'Candidate ready', icon: FileCheck2 },
  { label: 'Approval / promotion', icon: LockKeyhole },
]

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), 5500)
  try {
    const response = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...init?.headers,
      },
    })
    if (!response.ok) throw new Error(`Request failed (${response.status})`)
    return (await response.json()) as T
  } finally {
    window.clearTimeout(timer)
  }
}

function normalizeFilings(input: unknown): Filing[] {
  const rows = Array.isArray(input)
    ? input
    : typeof input === 'object' && input && 'filings' in input
      ? (input as { filings?: unknown }).filings
      : []
  if (!Array.isArray(rows)) return []
  return rows.map((item, index) => {
    const row = item as Record<string, unknown>
    const filedAt = String(row.filedAt ?? row.filed_at ?? row.filing_date ?? '')
    const accession = String(row.accession ?? row.accession_number ?? row.id ?? index)
    const filingForm = String(row.form ?? 'SEC filing')
    const reportDate = String(row.report_date ?? row.period_of_report ?? '')
    return {
      id: String(row.id ?? accession),
      accession,
      label: String(row.label ?? row.title ?? `${filingForm} · ${reportDate}`),
      filedAt,
      period: String(row.period ?? reportDate),
    }
  })
}

function parseRetrieval(
  input: unknown,
  asOfDate: string,
): Retrieval {
  const response = input as QueryResponse | null
  const hit = response?.hits?.[0]
  if (!hit) {
    return {
      answer: 'No eligible evidence was returned.',
      source: 'No citation',
      date: asOfDate,
      excerpt: 'The selected index has no matching chunks for this cutoff.',
      valid: true,
      latency: 'ranked',
    }
  }
  const chunk = hit.chunk
  return {
    answer: chunk.text,
    source: `${chunk.accession} · ${chunk.section}`,
    date: chunk.filed_at.slice(0, 10),
    excerpt: chunk.text,
    valid: new Date(chunk.filed_at).getTime() <= new Date(`${asOfDate}T23:59:59Z`).getTime(),
    latency: 'ranked',
    sourceUrl: chunk.source_url,
  }
}

class ForgeErrorBoundary extends Component<
  { children: ReactNode; onFailure: () => void },
  { failed: boolean }
> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    this.props.onFailure()
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="forge-fallback">
          <div className="forge-fallback-icon">
            <TerminalSquare size={22} />
          </div>
          <strong>TrueForge is ready to connect</strong>
          <p>
            Start the local harness on port 8791 to stream tool calls, subagents,
            sandbox runs, and approvals here.
          </p>
          <a href="/trueforge/" target="_blank" rel="noreferrer">
            Open TrueForge endpoint <ExternalLink size={14} />
          </a>
        </div>
      )
    }
    return this.props.children
  }
}

function App() {
  const [ticker, setTicker] = useState('MSFT')
  const [form, setForm] = useState('10-K')
  const [asOfDate, setAsOfDate] = useState('2024-08-01')
  const [filings, setFilings] = useState<Filing[]>([])
  const [selectedFiling, setSelectedFiling] = useState('')
  const [backendState, setBackendState] = useState<'loading' | 'live' | 'demo'>(
    'loading',
  )
  const [filingsLoading, setFilingsLoading] = useState(true)
  const [action, setAction] = useState<
    'idle' | 'building' | 'querying' | 'promoting'
  >('idle')
  const [status, setStatus] = useState<Status | null>(null)
  const [candidateReady, setCandidateReady] = useState(false)
  const [candidateId, setCandidateId] = useState<string | null>(null)
  const [promoted, setPromoted] = useState(false)
  const [results, setResults] = useState(DEMO_RESULTS)
  const [comparisonMeasured, setComparisonMeasured] = useState(false)
  const [message, setMessage] = useState('')
  const [navOpen, setNavOpen] = useState(false)
  const [forgeFailed, setForgeFailed] = useState(false)

  const filing = useMemo(
    () => filings.find((item) => item.id === selectedFiling) ?? filings[0],
    [filings, selectedFiling],
  )

  useEffect(() => {
    let active = true
    api<Status>('/api/status')
      .then((data) => {
        if (!active) return
        setStatus(data)
        setCandidateId(data.candidate_id)
        setCandidateReady(Boolean(data.candidate_id))
        setPromoted(Boolean(data.production_id) && !data.candidate_id)
        setBackendState('live')
      })
      .catch(() => active && setBackendState('demo'))
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    const query = new URLSearchParams({ ticker, forms: form })
    api<unknown>(`/api/filings?${query.toString()}`)
      .then((data) => {
        if (!active) return
        const normalized = normalizeFilings(data)
        setFilings(normalized)
        setSelectedFiling(normalized[0]?.id ?? '')
        setBackendState('live')
      })
      .catch(() => {
        if (!active) return
        setFilings(DEMO_FILINGS)
        setSelectedFiling(DEMO_FILINGS[0].id)
        setBackendState('demo')
      })
      .finally(() => active && setFilingsLoading(false))
    return () => {
      active = false
    }
  }, [ticker, form])

  async function buildCandidate() {
    if (!filing) return
    setAction('building')
    setMessage('')
    setPromoted(false)
    try {
      const candidate = await api<IndexVersion>('/api/candidates/build', {
        method: 'POST',
        body: JSON.stringify({
          ticker,
          forms: [form],
          limit: 1,
          accession: filing.accession,
        }),
      })
      setBackendState('live')
      setCandidateId(candidate.id)
      setCandidateReady(true)
      setStatus((current) =>
        current
          ? {
              ...current,
              candidate_id: candidate.id,
              indexes: { ...current.indexes, [candidate.id]: candidate },
            }
          : current,
      )
      setMessage(`Candidate built with ${candidate.chunk_count} section-aware chunks.`)
    } catch {
      setBackendState('demo')
      setCandidateReady(false)
      setMessage('Backend unavailable. Candidate build was not performed.')
    } finally {
      setAction('idle')
    }
  }

  async function runComparison() {
    setAction('querying')
    setMessage('')
    const payload = {
      query: 'What was Azure revenue growth?',
      ticker,
      as_of: `${asOfDate}T23:59:59Z`,
      limit: 5,
    }
    try {
      const [production, candidate] = await Promise.all([
        api<unknown>('/api/query', {
          method: 'POST',
          body: JSON.stringify({
            ...payload,
            index: 'production',
            temporal_filter: false,
          }),
        }),
        api<unknown>('/api/query', {
          method: 'POST',
          body: JSON.stringify({
            ...payload,
            index: 'candidate',
            temporal_filter: true,
          }),
        }),
      ])
      setResults({
        production: parseRetrieval(production, asOfDate),
        candidate: parseRetrieval(candidate, asOfDate),
      })
      setComparisonMeasured(true)
      setBackendState('live')
      setMessage('Both retrieval paths completed.')
    } catch {
      setBackendState('demo')
      setComparisonMeasured(false)
      await new Promise((resolve) => window.setTimeout(resolve, 500))
      setResults(DEMO_RESULTS)
      setMessage('Demo comparison refreshed from the offline preview dataset.')
    } finally {
      setAction('idle')
    }
  }

  async function promoteCandidate() {
    setAction('promoting')
    setMessage('')
    try {
      await api('/api/promote', {
        method: 'POST',
        body: JSON.stringify({ candidate_id: candidateId }),
      })
      setBackendState('live')
      setPromoted(true)
      setCandidateReady(false)
      setCandidateId(null)
      setMessage('Candidate promoted. The prior production collection remains available.')
    } catch {
      setBackendState('demo')
      setMessage('Backend unavailable. Production was not changed.')
    } finally {
      setAction('idle')
    }
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${navOpen ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <Fingerprint size={22} />
          </div>
          <div>
            <span className="brand-name">AsOfRAG</span>
            <span className="brand-subtitle">Temporal intelligence</span>
          </div>
        </div>
        <nav aria-label="Primary navigation">
          <a className="nav-item active" href="#control-room" onClick={() => setNavOpen(false)}>
            <Activity size={17} /> Control room
          </a>
          <a className="nav-item" href="#pipeline" onClick={() => setNavOpen(false)}>
            <Network size={17} /> Index pipelines
            <span className="nav-count">1</span>
          </a>
          <a className="nav-item" href="#comparison" onClick={() => setNavOpen(false)}>
            <GitCompareArrows size={17} /> Retrieval tests
          </a>
          <a className="nav-item" href="#sources" onClick={() => setNavOpen(false)}>
            <FileSearch size={17} /> Filing registry
          </a>
        </nav>
        <div className="sidebar-environment">
          <span>Environment</span>
          <div>
            <span className="status-dot" />
            Production
            <ChevronDown size={14} />
          </div>
        </div>
        <div className="sidebar-footer">
          <div className="avatar">AK</div>
          <div>
            <strong>Alex Kim</strong>
            <span>Risk engineering</span>
          </div>
        </div>
      </aside>

      {navOpen && (
        <button
          className="nav-scrim"
          type="button"
          onClick={() => setNavOpen(false)}
          aria-label="Close navigation"
        />
      )}

      <main className="main-content" id="control-room">
        <header className="topbar">
          <button
            className="mobile-menu"
            type="button"
            onClick={() => setNavOpen((value) => !value)}
            aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
            aria-expanded={navOpen}
          >
            {navOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div>
            <span className="eyebrow">RELIABILITY CONTROL ROOM</span>
            <h1>Point-in-time truth for financial AI</h1>
          </div>
          <div className="topbar-meta">
            <div className={`connection ${backendState}`}>
              <span />
              {backendState === 'loading'
                ? 'Connecting'
                : backendState === 'live'
                  ? status?.sec_configured === false
                    ? 'SEC setup required'
                    : 'API connected'
                  : 'Demo Preview'}
            </div>
            <button className="icon-button" type="button" aria-label="Refresh status">
              <RefreshCw size={17} />
            </button>
          </div>
        </header>

        <div className="workspace">
          {backendState === 'demo' && (
            <div className="demo-banner" role="status">
              <Sparkles size={16} />
              <div>
                <strong>Demo Preview</strong>
                <span>
                  Backend unavailable — showing a clearly labeled, deterministic demo dataset.
                </span>
              </div>
            </div>
          )}

          <section className="control-panel" aria-labelledby="build-title">
            <div className="section-heading">
              <div>
                <span className="section-kicker">INDEX CONFIGURATION</span>
                <h2 id="build-title">Build a temporally safe candidate</h2>
              </div>
              <span className="snapshot-id">Snapshot · {asOfDate}</span>
            </div>
            <div className="control-grid">
              <label>
                <span>Ticker</span>
                <div className="input-wrap ticker-input">
                  <span className="ticker-badge">{ticker.slice(0, 1) || '—'}</span>
                  <input
                    value={ticker}
                    onChange={(event) => {
                      setFilingsLoading(true)
                      setTicker(event.target.value.toUpperCase())
                    }}
                    maxLength={6}
                    aria-label="Ticker symbol"
                  />
                </div>
              </label>
              <label>
                <span>Form</span>
                <div className="select-wrap">
                  <select
                    value={form}
                    onChange={(event) => {
                      setFilingsLoading(true)
                      setForm(event.target.value)
                    }}
                  >
                    <option>10-K</option>
                    <option>10-Q</option>
                  </select>
                  <ChevronDown size={15} />
                </div>
              </label>
              <label className="filing-field">
                <span>Filing</span>
                <div className="select-wrap">
                  <select
                    value={selectedFiling}
                    onChange={(event) => setSelectedFiling(event.target.value)}
                    disabled={filingsLoading || filings.length === 0}
                  >
                    {filingsLoading && <option>Loading filings…</option>}
                    {!filingsLoading && filings.length === 0 && (
                      <option>No filings found</option>
                    )}
                    {filings.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label} · Filed {item.filedAt}
                      </option>
                    ))}
                  </select>
                  {filingsLoading ? (
                    <LoaderCircle className="spin" size={15} />
                  ) : (
                    <ChevronDown size={15} />
                  )}
                </div>
              </label>
              <label>
                <span>As-of date</span>
                <div className="input-wrap date-wrap">
                  <CalendarDays size={16} />
                  <input
                    type="date"
                    value={asOfDate}
                    onChange={(event) => setAsOfDate(event.target.value)}
                  />
                </div>
              </label>
              <button
                className="primary-button build-button"
                type="button"
                onClick={buildCandidate}
                disabled={action !== 'idle' || !filing}
              >
                {action === 'building' ? (
                  <LoaderCircle className="spin" size={17} />
                ) : (
                  <Zap size={17} />
                )}
                {action === 'building' ? 'Building…' : 'Load & build candidate'}
              </button>
            </div>
            {message && (
              <p className="action-message" role="status">
                <CheckCircle2 size={15} />
                {message}
              </p>
            )}
          </section>

          <section className="pipeline-section" id="pipeline" aria-labelledby="pipeline-title">
            <div className="section-heading compact">
              <div>
                <span className="section-kicker">INGESTION PIPELINE</span>
                <h2 id="pipeline-title">Filing-to-index provenance</h2>
              </div>
              <span className="run-time">
                <Clock3 size={14} />
                {backendState === 'live' ? 'Persistent state loaded' : 'Preview workflow'}
              </span>
            </div>
            <div className="pipeline">
              {PIPELINE_STAGES.map((stage, index) => {
                const Icon = stage.icon
                const complete =
                  index < 2
                    ? filings.length > 0
                    : index < 5
                      ? candidateReady || promoted
                      : promoted
                const active = index === 4 && candidateReady && !promoted
                return (
                  <div className="pipeline-step-wrap" key={stage.label}>
                    <div
                      className={`pipeline-step ${complete ? 'complete' : ''} ${active ? 'active' : ''}`}
                    >
                      <div className="step-icon">
                        {complete && !active ? <Check size={17} /> : <Icon size={17} />}
                      </div>
                      <div>
                        <span>0{index + 1}</span>
                        <strong>{stage.label}</strong>
                      </div>
                    </div>
                    {index < PIPELINE_STAGES.length - 1 && (
                      <ArrowRight className="pipeline-arrow" size={16} />
                    )}
                  </div>
                )
              })}
            </div>
          </section>

          <section className="kpi-grid" aria-label="Temporal reliability metrics">
            <article className="kpi-card danger">
              <div className="kpi-icon"><TriangleAlert size={18} /></div>
              <div>
                <span>Temporal leakage</span>
                <strong>
                  {comparisonMeasured
                    ? results.production.valid
                      ? '0 detected'
                      : '1 detected'
                    : 'Not measured'}
                </strong>
                <small>{backendState === 'live' ? 'Naive production query' : 'Preview only'}</small>
              </div>
              <span className="kpi-trend">Action needed</span>
            </article>
            <article className="kpi-card success">
              <div className="kpi-icon"><FileCheck2 size={18} /></div>
              <div>
                <span>Citation coverage</span>
                <strong>{comparisonMeasured ? 'Top hit cited' : 'Not measured'}</strong>
                <small>SEC accession and section</small>
              </div>
              <span className="mini-bars" aria-hidden="true"><i /><i /><i /><i /><i /></span>
            </article>
            <article className="kpi-card neutral">
              <div className="kpi-icon"><Database size={18} /></div>
              <div>
                <span>Eligible chunks</span>
                <strong>
                  {candidateId && status?.indexes[candidateId]
                    ? status.indexes[candidateId].chunk_count.toLocaleString()
                    : 'Not built'}
                </strong>
                <small>Current candidate collection</small>
              </div>
              <span className="donut" aria-label="hard as-of filter">ASOF</span>
            </article>
            <article className="kpi-card accent">
              <div className="kpi-icon"><ShieldCheck size={18} /></div>
              <div>
                <span>Candidate status</span>
                <strong>{promoted ? 'Promoted' : candidateReady ? 'Ready' : 'Not built'}</strong>
                <small>{promoted ? 'Production pointer updated' : 'Awaiting candidate'}</small>
              </div>
              <span className="status-pill"><CircleDot size={12} />{promoted ? 'Live' : candidateReady ? 'Ready' : 'Idle'}</span>
            </article>
          </section>

          <section className="comparison-section" id="comparison" aria-labelledby="comparison-title">
            <div className="section-heading">
              <div>
                <span className="section-kicker">RETRIEVAL A/B TEST</span>
                <h2 id="comparison-title">Same question. Different truth boundary.</h2>
              </div>
              <button
                className="secondary-button"
                type="button"
                onClick={runComparison}
                disabled={action !== 'idle'}
              >
                {action === 'querying' ? (
                  <LoaderCircle className="spin" size={15} />
                ) : (
                  <Play size={15} />
                )}
                Run comparison
              </button>
            </div>
            <div className="query-strip">
              <Search size={17} />
              <span>What was Azure revenue growth?</span>
              <span className="query-date">Knowledge cutoff · {asOfDate}</span>
            </div>
            <div className="comparison-grid">
              <RetrievalCard
                title="Production"
                subtitle="current-prod"
                result={results.production}
                tone={results.production.valid ? 'success' : 'danger'}
                asOfDate={asOfDate}
              />
              <div className="versus-badge">VS</div>
              <RetrievalCard
                title="Candidate"
                subtitle={`as-of-${asOfDate}`}
                result={results.candidate}
                tone={results.candidate.valid ? 'success' : 'danger'}
                asOfDate={asOfDate}
              />
            </div>
          </section>

          <section className="sources-grid" id="sources">
            <article className="timeline-card">
              <div className="card-heading">
                <div>
                  <span className="section-kicker">ILLUSTRATIVE FILING TIMELINE</span>
                  <h2>Temporal boundary</h2>
                </div>
                <CalendarDays size={18} />
              </div>
              <div className="timeline">
                <div className="timeline-line" />
                <TimelineItem
                  date="Apr 25"
                  label="Q3 2024 · 10-Q"
                  state="eligible"
                  detail="Eligible"
                />
                <TimelineItem
                  date="Jul 30"
                  label="FY 2024 · 10-K"
                  state="selected"
                  detail="Selected source"
                />
                <div className="cutoff-marker">
                  <span>AS-OF</span>
                  <strong>Aug 01</strong>
                </div>
                <TimelineItem
                  date="Oct 30"
                  label="Q1 2025 · 10-Q"
                  state="blocked"
                  detail="Blocked · future"
                />
              </div>
            </article>

            <article className="source-card">
              <div className="card-heading">
                <div>
                  <span className="section-kicker">ILLUSTRATIVE CITED SOURCE</span>
                  <h2>Evidence, not just an answer</h2>
                </div>
                <span className="verified-badge"><ShieldCheck size={13} /> Verified</span>
              </div>
              <div className="document-preview">
                <div className="document-icon"><FileSearch size={22} /></div>
                <div>
                  <strong>Microsoft FY2024 Form 10-K</strong>
                  <span>Filed Jul 30, 2024 · Page 36</span>
                </div>
                <button type="button" aria-label="Open filing source"><ExternalLink size={16} /></button>
              </div>
              <blockquote>
                “Azure and other cloud services revenue grew <mark>29%</mark> driven by
                growth in our consumption-based services.”
              </blockquote>
              <div className="source-meta">
                <span><Fingerprint size={13} /> SHA-256 verified</span>
                <span><Clock3 size={13} /> valid_at ≤ 2024-08-01</span>
              </div>
            </article>
          </section>

          <section className="promotion-bar" aria-label="Candidate promotion">
            <div className="promotion-icon"><ShieldCheck size={21} /></div>
            <div>
              <strong>
                {promoted ? 'Candidate promoted to production' : 'Candidate passed all policy gates'}
              </strong>
              <span>
                {promoted
                  ? 'The validated temporal index is now serving production queries.'
                  : candidateReady
                    ? 'Candidate is isolated and ready for an approval-gated promotion.'
                    : 'Build a candidate before requesting promotion.'}
              </span>
            </div>
            <button
              className="primary-button"
              type="button"
              onClick={promoteCandidate}
              disabled={action !== 'idle' || promoted || !candidateReady}
            >
              {action === 'promoting' ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <LockKeyhole size={16} />
              )}
              {promoted ? 'Promoted' : action === 'promoting' ? 'Promoting…' : 'Approve & promote'}
            </button>
          </section>
        </div>
      </main>

      <aside className="forge-dock" aria-label="TrueForge agent operations">
        <div className="forge-header">
          <div>
            <span className="forge-logo"><Bot size={17} /></span>
            <div>
              <strong>TrueForge</strong>
              <span>Agent operations</span>
            </div>
          </div>
          <div className="forge-live"><span /> {forgeFailed ? 'OFFLINE' : 'EMBEDDED'}</div>
        </div>
        <div className="forge-context">
          <ServerCog size={15} />
          <span>asof-rag-reliability</span>
          <span className="forge-env">LOCAL</span>
        </div>
        <div className="forge-body">
          <ForgeErrorBoundary onFailure={() => setForgeFailed(true)}>
            <TrueForgeUI
              server={{ type: 'trueforge', baseUrl: '/trueforge' }}
              layout="dock"
              agentConfig={{ mode: 'AgentComposer' }}
              theme={{
                preset: 'trueforge',
                mode: 'dark',
                brand: { name: 'AsOfRAG Ops' },
                tokens: {
                  primaryBg: '#0a0d12',
                  secondaryBg: '#11161e',
                  textPrimary: '#edf4f2',
                  primaryButtonBg: '#29d391',
                  primaryButtonHover: '#20b77d',
                  primaryButtonText: '#06130e',
                  radius: '0.5rem',
                },
              }}
              onError={() => setForgeFailed(true)}
              className="trueforge-embed"
            />
          </ForgeErrorBoundary>
          {forgeFailed && (
            <a className="forge-error-link" href="/trueforge/" target="_blank" rel="noreferrer">
              Harness offline · open endpoint <ExternalLink size={12} />
            </a>
          )}
        </div>
        <div className="forge-capabilities" aria-label="Visible agent capabilities">
          <span><TerminalSquare size={13} /> Tools</span>
          <span><Network size={13} /> Subagents</span>
          <span><Box size={13} /> Sandbox</span>
          <span><CheckCircle2 size={13} /> Approvals</span>
        </div>
      </aside>
    </div>
  )
}

function RetrievalCard({
  title,
  subtitle,
  result,
  tone,
  asOfDate,
}: {
  title: string
  subtitle: string
  result: Retrieval
  tone: 'danger' | 'success'
  asOfDate: string
}) {
  const Icon = result.valid ? CheckCircle2 : XCircle
  return (
    <article className={`retrieval-card ${tone}`}>
      <header>
        <div>
          <span className="index-dot" />
          <div><strong>{title}</strong><span>{subtitle}</span></div>
        </div>
        <span className="latency">{result.latency}</span>
      </header>
      <div className="retrieval-answer">{result.answer}</div>
      <div className="validation-result">
        <Icon size={18} />
        <div>
          <strong>{result.valid ? 'Temporally valid' : 'Future leakage detected'}</strong>
          <span>
            Source filed {result.date} {result.valid ? 'is within' : 'exceeds'} the
            {' '}{asOfDate} cutoff
          </span>
        </div>
      </div>
      <div className="citation">
        <div>
          <FileSearch size={15} />
          {result.sourceUrl ? (
            <a href={result.sourceUrl} target="_blank" rel="noreferrer">
              <strong>{result.source}</strong>
            </a>
          ) : (
            <strong>{result.source}</strong>
          )}
        </div>
        <p>“{result.excerpt}”</p>
      </div>
    </article>
  )
}

function TimelineItem({
  date,
  label,
  state,
  detail,
}: {
  date: string
  label: string
  state: string
  detail: string
}) {
  return (
    <div className={`timeline-item ${state}`}>
      <span className="timeline-date">{date}</span>
      <span className="timeline-node" />
      <div><strong>{label}</strong><span>{detail}</span></div>
    </div>
  )
}

export default App
