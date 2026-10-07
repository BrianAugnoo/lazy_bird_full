import { useState } from 'react';
import { engineApi } from '@/api/endpoints/engines';
import { files as filesApi, search } from '@/api/endpoints/files';
import { buildHash } from '@/core/router';
import type { SearchResult } from '@/core/types/api';
import { useResource } from '@/core/useResource';
import { Icon } from '@/ui/Icon';
import { MultiSelect } from '@/ui/MultiSelect';
import { PageHeader } from '@/ui/PageHeader';

const embedding = engineApi('embedding');

function loadOptions() {
  return Promise.all([embedding.listPresets(), filesApi.list()]).then(([presets, files]) => ({ presets, files }));
}

export function SearchPage() {
  const options = useResource(loadOptions, []);
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(8);
  const [presetId, setPresetId] = useState<number | ''>('');
  const [fileIds, setFileIds] = useState<string[]>([]);
  const [showFilters, setShowFilters] = useState(false);
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const files = options.data?.files ?? [];
  const presets = options.data?.presets ?? [];

  const run = async () => {
    if (!query.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setResults(
        await search({
          query: query.trim(),
          top_k: topK,
          preset_id: presetId === '' ? null : presetId,
          file_ids: fileIds.length ? fileIds.map(Number) : null,
        }),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
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
            <button type="submit" className="btn btn-primary" disabled={busy || !query.trim()}>
              {busy ? 'Searching…' : 'Search'}
            </button>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" style={{ alignSelf: 'flex-start' }} onClick={() => setShowFilters(!showFilters)} aria-expanded={showFilters}>
            <Icon name={showFilters ? 'chevronDown' : 'chevronRight'} /> Options
            {(presetId !== '' || fileIds.length > 0) && <span className="chip chip-accent">active</span>}
          </button>
          {showFilters && (
            <div className="search-options">
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
              <div className="form-group">
                <label className="form-label" htmlFor="search-count">
                  Results
                </label>
                <input id="search-count" type="number" min={1} max={50} className="form-input" value={topK} onChange={(event) => setTopK(Math.max(1, Number(event.target.value) || 1))} />
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
