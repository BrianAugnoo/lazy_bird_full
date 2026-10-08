import { request } from '../client';
import type { CompletionOut, EngineKind, EngineOut, PresetChanges, PresetOut } from '@/core/types/api';

/** Typed access to one engine family: `/{kind}-engines/` and `/{kind}-presets/`. */
export function engineApi(kind: EngineKind) {
  const route = kind.replace('_', '-');
  const engines = `/${route}-engines`;
  const presets = `/${route}-presets`;
  const engineKey = `${kind}_engine_id`;

  const body = (changes: PresetChanges) => {
    const { engine_id, ...rest } = changes;
    return JSON.stringify(engine_id === undefined ? rest : { ...rest, [engineKey]: engine_id });
  };

  return {
    engineIdOf: (preset: PresetOut): number => preset[engineKey as 'embedding_engine_id' | 'cross_encoder_engine_id' | 'inference_engine_id'] ?? -1,
    listEngines: () => request<EngineOut[]>(`${engines}/`),
    listPresets: () => request<PresetOut[]>(`${presets}/`),
    createPreset: (changes: Required<Pick<PresetChanges, 'name' | 'engine_id'>> & PresetChanges) =>
      request<PresetOut>(`${presets}/`, { method: 'POST', body: body(changes) }),
    updatePreset: (id: number, changes: PresetChanges) =>
      request<PresetOut>(`${presets}/${id}`, { method: 'PATCH', body: body(changes) }),
    deletePreset: (id: number) => request<void>(`${presets}/${id}`, { method: 'DELETE' }),
  };
}

/** One question, one answer with an inference preset (the default one when omitted). */
export const complete = (prompt: string, presetId?: number, instructions?: string) =>
  request<CompletionOut>('/inference/complete', {
    method: 'POST',
    body: JSON.stringify({ prompt, preset_id: presetId ?? null, instructions: instructions || null }),
  });
