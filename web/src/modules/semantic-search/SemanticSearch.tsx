import { useState } from 'react';
import { searchChunks } from '@/api/endpoints/search';
import type { SearchResult } from '@/core/types/api';

export function SemanticSearch() {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setHasSearched(true);
    try {
      setResults(await searchChunks(query, topK));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search request failed.');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-container">
      <section className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">Semantic Search</h2>
            <p className="card-description">Find the most relevant passages in your vector index.</p>
          </div>
          <span className="badge badge-info">POST /search/</span>
        </div>
        <div className="card-body">
          <form onSubmit={handleSearch} style={{ display: 'grid', gridTemplateColumns: '1fr 140px auto', gap: '12px', alignItems: 'end' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="search-query">Query or Question</label>
              <input
                id="search-query"
                className="form-input"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="e.g. How does document chunking work?"
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label" htmlFor="search-top-k">Results: {topK}</label>
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
              {loading ? 'Searching...' : 'Search'}
            </button>
          </form>

          {error && (
            <div className="alert alert-error" style={{ marginTop: '20px' }}>
              <span aria-hidden="true">!</span>
              <span style={{ flex: 1 }}>{error}</span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setError(null)}>Close</button>
            </div>
          )}

          {loading && (
            <div className="state-loading" aria-live="polite">
              <span className="spinner" />
              <div className="state-title">Querying vector index...</div>
            </div>
          )}

          {!loading && hasSearched && !error && results.length === 0 && (
            <div className="state-empty">
              <span style={{ fontSize: '2rem' }} aria-hidden="true">⌕</span>
              <div className="state-title">No matching passages found</div>
              <p className="state-desc">Try rephrasing your search query or verify that documents have been processed into the active vector database.</p>
            </div>
          )}

          {!loading && results.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '24px' }}>
              {results.map((result, index) => (
                <article className="card" key={result.chunk.id}>
                  <div className="card-header">
                    <span className="badge badge-muted">#{index + 1} · {result.file_name}</span>
                    <span className="badge badge-info">
                      {result.distance == null ? 'Distance N/A' : `Distance: ${result.distance.toFixed(4)}`}
                    </span>
                  </div>
                  <div className="card-body">
                    <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{result.chunk.content}</p>
                    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', marginTop: '14px', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                      <span>Lines {result.chunk.start_line}-{result.chunk.end_line}</span>
                      <span>Chunk #{result.chunk.position + 1}</span>
                      <span title={result.file_path}>{result.file_path}</span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
