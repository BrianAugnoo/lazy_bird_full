import { useState } from 'react'
import { searchChunks } from '@/api/endpoints/search'
import type { SearchResultChunk } from '@/core/types/api'

export function SemanticSearch() {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState(5)
  const [results, setResults] = useState<SearchResultChunk[]>([])
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setHasSearched(true)
    try {
      setResults(await searchChunks(query, topK))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'La recherche a échoué.')
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="content-container">
      <section className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">Recherche sémantique</h2>
            <p className="card-description">Retrouvez les passages les plus proches dans votre index vectoriel.</p>
          </div>
          <span className="badge badge-info">POST /search/</span>
        </div>
        <div className="card-body">
          <form onSubmit={handleSearch} style={{ display: 'grid', gridTemplateColumns: '1fr 140px auto', gap: '12px', alignItems: 'end' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="search-query">Question ou expression</label>
              <input
                id="search-query"
                className="form-input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ex. comment fonctionne l'indexation ?"
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="search-top-k">Résultats: {topK}</label>
              <input
                id="search-top-k"
                type="range"
                min="1"
                max="100"
                value={topK}
                onChange={(event) => setTopK(Number(event.target.value))}
                style={{ width: '100%' }}
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
              {loading ? 'Recherche...' : 'Rechercher'}
            </button>
          </form>

          {error && (
            <div className="alert alert-error" style={{ marginTop: '20px' }}>
              <span aria-hidden="true">!</span>
              <span style={{ flex: 1 }}>{error}</span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setError(null)}>Fermer</button>
            </div>
          )}

          {loading && (
            <div className="state-loading" aria-live="polite">
              <span className="spinner" />
              <div className="state-title">Interrogation de l'index...</div>
            </div>
          )}

          {!loading && hasSearched && !error && results.length === 0 && (
            <div className="state-empty">
              <span style={{ fontSize: '2rem' }} aria-hidden="true">⌕</span>
              <div className="state-title">Aucun passage trouvé</div>
              <p className="state-desc">Essayez une formulation plus générale ou vérifiez que des documents sont indexés.</p>
            </div>
          )}

          {!loading && results.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '24px' }}>
              {results.map((result, index) => (
                <article className="card" key={`${result.embedded_id}-${result.start_line}-${index}`}>
                  <div className="card-header">
                    <span className="badge badge-muted">Résultat {index + 1}</span>
                    <span className="badge badge-info">
                      {result.distance === undefined ? 'Distance indisponible' : `Distance ${result.distance.toFixed(4)}`}
                    </span>
                  </div>
                  <div className="card-body">
                    <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{result.content}</p>
                    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '14px', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                      <span>Lignes {result.start_line}-{result.end_line}</span>
                      <span>Chunk #{result.embedded_id}</span>
                      {result.meta_data && <span>{JSON.stringify(result.meta_data)}</span>}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
