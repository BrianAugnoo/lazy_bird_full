import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { SearchResult } from '@/core/types/api';
import { mockApi } from '@/test/http';
import { SearchPage } from './SearchPage';

const preset = (id: number, name: string, engineKey: string) => ({ id, name, [engineKey]: 1, kwargs: {}, default: id === 1, valid: true, errors: {} });

const result = (id: number, content: string, score: number | null): SearchResult => ({
  chunk: { id, file_id: id, position: 0, content, start_line: 1, end_line: 1, start_row: null, end_row: null, token_count: null, meta: {}, created_at: '2026-01-01T00:00:00Z' },
  file_name: `file${id}.md`,
  file_path: `/storage/file${id}.md`,
  distance: 0.5,
  score,
});

const routes = (crossEncoders = [preset(1, 'reranker', 'cross_encoder_engine_id')]) => ({
  'GET /embedding-presets/': [preset(1, 'minilm', 'embedding_engine_id')],
  'GET /cross-encoder-presets/': crossEncoders,
  'GET /files/': [],
});

async function openPage() {
  render(<SearchPage />);
  await screen.findByRole('tab', { name: 'Reranking' });
}

const ask = (question: string) => {
  fireEvent.change(screen.getByLabelText('Search'), { target: { value: question } });
};

describe('SearchPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('searches by embedding only by default and shows only the embedding options', async () => {
    const calls = mockApi({ ...routes(), 'POST /search/': [result(1, 'Green tea passage', null)] });
    await openPage();

    fireEvent.click(screen.getByText('Options'));
    expect(screen.getByLabelText('Embedding preset')).toBeTruthy();
    expect(screen.getByLabelText('Results')).toHaveProperty('value', '8');
    expect(screen.queryByLabelText('Cross-encoder preset')).toBeNull();
    expect(screen.queryByLabelText('Embedding candidates')).toBeNull();

    ask('green tea');
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByText('Green tea passage')).toBeTruthy();
    expect(calls('POST /search/')[0]).toEqual({ query: 'green tea', top_k: 8, preset_id: null, file_ids: null });
    expect(screen.queryByText(/score/)).toBeNull();
  });

  it('reranking exposes both presets and the candidate and result counts with their defaults', async () => {
    mockApi(routes());
    await openPage();

    fireEvent.click(screen.getByRole('tab', { name: 'Reranking' }));

    expect(screen.getByLabelText('Embedding preset')).toBeTruthy();
    expect(screen.getByLabelText('Cross-encoder preset')).toBeTruthy();
    expect(screen.getByLabelText('Embedding candidates')).toHaveProperty('value', '50');
    expect(screen.getByLabelText('Final results')).toHaveProperty('value', '10');
  });

  it('sends the reranking settings and shows results with their cross-encoder score', async () => {
    const calls = mockApi({ ...routes(), 'POST /search/': [result(2, 'Best passage', 7.5), result(1, 'Second passage', 1.25)] });
    await openPage();
    fireEvent.click(screen.getByRole('tab', { name: 'Reranking' }));
    fireEvent.change(screen.getByLabelText('Cross-encoder preset'), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('Embedding candidates'), { target: { value: '30' } });
    fireEvent.change(screen.getByLabelText('Final results'), { target: { value: '5' } });

    ask('green tea');
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByText('Best passage')).toBeTruthy();
    expect(calls('POST /search/')[0]).toEqual({
      query: 'green tea',
      top_k: 5,
      preset_id: null,
      file_ids: null,
      rerank: true,
      cross_encoder_preset_id: 1,
      top_n: 30,
    });
    expect(screen.getByText(/score 7\.500/)).toBeTruthy();
    expect(screen.getAllByRole('article').map((item) => item.textContent)).toEqual([expect.stringContaining('Best passage'), expect.stringContaining('Second passage')]);
  });

  it('refuses candidates that do not outnumber the final results', async () => {
    mockApi(routes());
    await openPage();
    fireEvent.click(screen.getByRole('tab', { name: 'Reranking' }));
    ask('green tea');

    fireEvent.change(screen.getByLabelText('Embedding candidates'), { target: { value: '10' } });

    expect(screen.getByText('Must be greater than the final results (10).')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Search' })).toHaveProperty('disabled', true);

    fireEvent.change(screen.getByLabelText('Embedding candidates'), { target: { value: '11' } });
    expect(screen.getByRole('button', { name: 'Search' })).toHaveProperty('disabled', false);
  });

  it('shows the field error the server returns for the candidates', async () => {
    mockApi({
      ...routes(),
      'POST /search/': { status: 422, body: { error: { code: 'invalid_request', message: 'The request is invalid.', details: { fields: { top_n: 'Must be greater than the final results (top_k = 10).' } } } } },
    });
    await openPage();
    fireEvent.click(screen.getByRole('tab', { name: 'Reranking' }));
    ask('green tea');

    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByText('Must be greater than the final results (top_k = 10).')).toBeTruthy();
    expect(screen.queryByText('The request is invalid.')).toBeNull();
  });

  it('explains how to get a cross-encoder when none exists', async () => {
    mockApi(routes([]));
    await openPage();

    fireEvent.click(screen.getByRole('tab', { name: 'Reranking' }));
    ask('green tea');

    await waitFor(() => expect(screen.getByText(/No cross-encoder preset yet/)).toBeTruthy());
    expect(screen.getByRole('button', { name: 'Search' })).toHaveProperty('disabled', true);
    fireEvent.click(screen.getByRole('tab', { name: 'Embedding only' }));
    expect(screen.getByRole('button', { name: 'Search' })).toHaveProperty('disabled', false);
  });
});
