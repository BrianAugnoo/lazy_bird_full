import type { CallableItem } from '@/core/types/api';

/** A tool or hook as `GET /tools/` or `GET /hooks/` lists it. */
export function callable(extension: string, module: string, name: string, description = ''): CallableItem {
  return {
    id: `${extension}-${module}-${name}`,
    name,
    description,
    extension,
    module,
    file_path: `${extension}/${module}.py`,
    class_name: null,
    needs_settings: false,
    meta_params: [],
    required_meta: [],
    accepts_any_meta: false,
    parameters: null,
  };
}
