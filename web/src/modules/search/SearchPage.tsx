import { useState } from 'react';
import { ApiError } from '@/api/client';
import { engineApi } from '@/api/endpoints/engines';
import { files as filesApi, search } from '@/api/endpoints/files';
import { buildHash } from '@/core/router';
import type { SearchResult } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { Icon } from '@/ui/Icon';
import { MultiSelect } from '@/ui/MultiSelect';
import { PageHeader } from '@/ui/PageHeader';
import { candidatesError, DEFAULT_CANDIDATES, DEFAULT_RESULTS, MAX_CANDIDATES, MAX_RESULTS, toPayload, type SearchMode } from './searchRequest';

const embedding = engineApi('embedding');
const crossEncoder = engineApi('cross_encoder');

const MODES: { id: SearchMode; label: string; hint: string }[] = [
  { id: 'embedding', label: 'Embedding only', hint: 'Finds the passages closest in meaning to the question.' },
  { id: 'rerank', label: 'Reranking', hint: 'Finds candidates by meaning, then a cross-encoder reads each one with the question and keeps the best.' },
];

function loadOptions() {
  return Promise.all([embedding.listPresets(), crossEncoder.listPresets(), filesApi.list()]).then(([presets, crossEncoderPresets, files]) => ({
    presets,
    crossEncoderPresets,
    files,
  }));
}

export function SearchPage() {
  const options = useResource(loadOptions, []);
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<SearchMode>('embedding');
  const [embeddingResults, setEmbeddingResults] = useState<number>(DEFAULT_RESULTS.embedding);
  const [rerankResults, setRerankResults] = useState<number>(DEFAULT_RESULTS.rerank);
  const [candidates, setCandidates] = useState(DEFAULT_CANDIDATES);
  const [presetId, setPresetId] = useState<number | ''>('');
  const [crossEncoderPresetId, setCrossEncoderPresetId] = useState<number | ''>('');
  const [fileIds, setFileIds] = useState<string[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const files = options.data?.files ?? [];
  const presets = options.data?.presets ?? [];
  const crossEncoderPresets = options.data?.crossEncoderPresets ?? [];
  const reranking = mode === 'rerank';
  const resultCount = reranking ? rerankResults : embeddingResults;
  const form = { mode, query, presetId, crossEncoderPresetId, results: resultCount, candidates, fileIds };
  const candidatesProblem = candidatesError(form);
  const missingCrossEncoder = reranking && options.data !== undefined && crossEncoderPresets.length === 0;
  const canSearch = !busy && query.trim() !== '' && !candidatesProblem && !missingCrossEncoder;

  const chooseMode = (next: SearchMode) => {
    setMode(next);
    if (next === 'rerank') setShowFilters(true);
  };

  const run = async () => {
    if (!canSearch) return;
    setBusy(true);
    setError(null);
    setFieldErrors({});
    try {
      setResults(await search(toPayload(form)));
    } catch (reason) {
      if (reason instanceof ApiError && Object.keys(reason.fieldErrors).length > 0) setFieldErrors(reason.fieldErrors);
      else setError(reason instanceof Error ? reason.message : String(reason));
      setResults(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="Search" description="Find the passages of your files closest in meaning to a question, the way agents do." />
      <form
        className="card"
        onSubmit={(event) => {
          event.preventDefault();
          void run();
        }}
      >
        <div className="card-body stack">
          <div className="search-bar">
            <Icon name="search" />
            <input className="search-input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ask something about your files…" aria-label="Search" autoFocus />
            <button type="submit" className="btn btn-primary" disabled={!canSearch}>
              {busy ? 'Searching…' : 'Search'}
            </button>
          </div>
          <div className="tabs" role="tablist" aria-label="Search mode" style={{ marginBottom: 0 }}>
            {MODES.map((item) => (
              <button key={item.id} type="button" role="tab" aria-selected={mode === item.id} className={`tab ${mode === item.id ? 'is-active' : ''}`} onClick={() => chooseMode(item.id)}>
                {item.label}
              </button>
            ))}
          </div>
          <div className="form-hint">{MODES.find((item) => item.id === mode)?.hint}</div>
          <button type="button" className="btn btn-ghost btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => setShowFilters(!showFilters)} aria-expanded={showFilters}>
            <Icon name={showFilters ? 'chevronDown' : 'chevronRight'} /> Options
            {(presetId !== '' || fileIds.length > 0 || (reranking && crossEncoderPresetId !== '')) && <span className="chip chip-accent">active</span>}
          </button>
          {showFilters && (
            <div className={`search-options ${reranking ? 'search-options-rerank' : ''}`}>
              <div className="form-group">
                <label className="form-label" htmlFor="search-preset">
                  Embedding preset
                </label>
                <select id="search-preset" className="form-input" value={presetId} onChange={(event) => setPresetId(event.target.value ? Number(event.target.value) : '')}>
                  <option value="">Default</option>
                  {presets.map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.name}
                    </option>
                  ))}
                </select>
                <div className="form-hint">Only files embedded with this preset's model are found.</div>
              </div>
              {reranking && (
                <div className="form-group">
                  <label className="form-label" htmlFor="search-cross-encoder">
                    Cross-encoder preset
                  </label>
                  <select
                    id="search-cross-encoder"
                    className="form-input"
                    value={crossEncoderPresetId}
                    onChange={(event) => setCrossEncoderPresetId(event.target.value ? Number(event.target.value) : '')}
                  >
                    <option value="">Default</option>
                    {crossEncoderPresets.map((preset) => (
                      <option key={preset.id} value={preset.id}>
                        {preset.name}
                      </option>
                    ))}
                  </select>
                  {missingCrossEncoder ? (
                    <div className="form-error">
                      No cross-encoder preset yet. <a href={buildHash('cross-encoder')}>Create one</a> to rerank.
                    </div>
                  ) : (
                    <div className="form-hint">Scores each candidate against the question.</div>
                  )}
                  {fieldErrors.cross_encoder_preset_id && <div className="form-error">{fieldErrors.cross_encoder_preset_id}</div>}
                </div>
              )}
              {reranking && (
                <div className="form-group">
                  <label className="form-label" htmlFor="search-candidates">
                    Embedding candidates
                  </label>
                  <input
                    id="search-candidates"
                    type="number"
                    min={1}
                    max={MAX_CANDIDATES}
                    className="form-input"
                    value={candidates}
                    onChange={(event) => setCandidates(Math.max(1, Number(event.target.value) || 1))}
                    aria-invalid={Boolean(candidatesProblem || fieldErrors.top_n)}
                  />
                  {candidatesProblem || fieldErrors.top_n ? (
                    <div className="form-error">{candidatesProblem ?? fieldErrors.top_n}</div>
                  ) : (
                    <div className="form-hint">Passages the cross-encoder reads.</div>
                  )}
                </div>
              )}
              <div className="form-group">
                <label className="form-label" htmlFor="search-count">
                  {reranking ? 'Final results' : 'Results'}
                </label>
                <input
                  id="search-count"
                  type="number"
                  min={1}
                  max={MAX_RESULTS}
                  className="form-input"
                  value={resultCount}
                  onChange={(event) => (reranking ? setRerankResults : setEmbeddingResults)(Math.max(1, Number(event.target.value) || 1))}
                />
                {reranking && <div className="form-hint">Best passages kept after reranking.</div>}
              </div>
              <div className="form-group search-files">
                <label className="form-label">Only in these files</label>
                <MultiSelect
                  options={files.map((file) => ({ value: String(file.id), label: `${file.name}${file.extension}`, description: file.directory || undefined }))}
                  value={fileIds}
                  onChange={setFileIds}
                  emptyText="No file yet."
                />
              </div>
            </div>
          )}
        </div>
      </form>

      {error && <div className="alert alert-error">{error}</div>}
      {results && results.length === 0 && (
        <div className="state-empty">
          <div className="state-title">Nothing found</div>
          <p className="state-desc">Files must be embedded (state “Ready” on the Files page) to be found.</p>
        </div>
      )}
      {results && results.length > 0 && (
        <div className="search-results">
          {results.map((result) => (
            <article key={result.chunk.id} className="search-result">
              <header className="row-between">
                <a href={buildHash('files', { file: result.chunk.file_id })} className="search-result-file">
                  <Icon name="file" size={15} /> {result.file_name}
                </a>
                <span className="muted small">
                  lines {result.chunk.start_line}–{result.chunk.end_line}
                  {result.score !== null && ` · score ${result.score.toFixed(3)}`}
                  {result.distance !== null && ` · distance ${result.distance.toFixed(3)}`}
                </span>
              </header>
              <pre className="search-result-text">{result.chunk.content}</pre>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
