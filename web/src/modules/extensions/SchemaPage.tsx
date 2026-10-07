import { getApiBaseUrl } from '@/api/client';

/** The data model diagram served by the backend (pan by dragging, zoom with the wheel). */
export function SchemaPage() {
  return <iframe className="schema-frame" title="Data model" src={`${getApiBaseUrl().replace(/\/$/, '')}/schemas`} />;
}
