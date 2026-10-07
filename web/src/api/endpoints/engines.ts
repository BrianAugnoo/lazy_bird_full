import { request } from '../client';
import type { EngineKind, EngineOut, PresetChanges, PresetOut } from '@/core/types/api';

/** Typed access to one engine family: `/{kind}-engines/` and `/{kind}-presets/`. */
export function engineApi(kind: EngineKind) {
  const engines = `/${kind}-engines`;
  const presets = `/${kind}-presets`;
  const engineKey = `${kind}_engine_id`;

  const body = (changes: PresetChanges) => {
    const { engine_id, ...rest } = changes;
    return JSON.stringify(engine_id === undefined ? rest : { ...rest, [engineKey]: engine_id });
  };

  return {
    engineIdOf: (preset: PresetOut): number => (kind === 'embedding' ? preset.embedding_engine_id : preset.inference_engine_id) ?? -1,
    listEngines: () => request<EngineOut[]>(`${engines}/`),
    listPresets: () => request<PresetOut[]>(`${presets}/`),
    createPreset: (changes: Required<Pick<PresetChanges, 'name' | 'engine_id'>> & PresetChanges) =>
      request<PresetOut>(`${presets}/`, { method: 'POST', body: body(changes) }),
    updatePreset: (id: number, changes: PresetChanges) =>
      request<PresetOut>(`${presets}/${id}`, { method: 'PATCH', body: body(changes) }),
    deletePreset: (id: number) => request<void>(`${presets}/${id}`, { method: 'DELETE' }),
  };
}
