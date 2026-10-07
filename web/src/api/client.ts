/**
 * Typed HTTP client: the single place where the frontend calls the backend.
 *
 * Every backend error has the shape `{"error": {"code", "message", "details"}}`;
 * it is surfaced as an `ApiError` carrying the same fields.
 */

export const getApiBaseUrl = (): string => {
  const configuredUrl = typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL;
  if (configuredUrl) return configuredUrl;
  if (typeof import.meta !== 'undefined' && import.meta.env?.DEV) return '/api';
  return 'http://localhost:8000';
};

export class ApiError extends Error {
  public status: number;
  public code: string;
  public details: Record<string, unknown>;

  constructor(message: string, status: number, code = 'error', details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Messages per field for `invalid_settings` / `invalid_request` errors. */
  get fieldErrors(): Record<string, string> {
    const fields = this.details.fields;
    return fields && typeof fields === 'object' ? (fields as Record<string, string>) : {};
  }
}

const unreachable = (baseUrl: string, cause: unknown) =>
  new ApiError(`Unable to connect to Lazy Bird server (${baseUrl}). Check that it is running.`, 0, 'network_error', {
    cause: String(cause),
  });

function buildUrl(path: string): string {
  const baseUrl = getApiBaseUrl();
  return `${baseUrl.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`;
}

/** Turn an error response body into an `ApiError`. */
export function toApiError(status: number, statusText: string, data: unknown): ApiError {
  const body = data as { error?: unknown; detail?: unknown; message?: unknown } | null;
  const error = body && typeof body === 'object' ? body.error : undefined;
  if (error && typeof error === 'object') {
    const { code, message, details } = error as { code?: string; message?: string; details?: Record<string, unknown> };
    return new ApiError(message || `Request failed (${status}).`, status, code || 'error', details || {});
  }
  if (typeof error === 'string') return new ApiError(error, status);
  if (typeof body?.detail === 'string') return new ApiError(body.detail, status);
  if (typeof data === 'string' && data.length > 0) return new ApiError(data, status);
  return new ApiError(`Request failed (${status}${statusText ? ` ${statusText}` : ''}).`, status);
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const defaultHeaders: Record<string, string> = {};
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path), { ...options, headers: { ...defaultHeaders, ...options.headers } });
  } catch (networkError) {
    throw unreachable(getApiBaseUrl(), networkError);
  }

  const contentType = response.headers.get('content-type') || '';
  let data: unknown = null;
  try {
    data = contentType.includes('application/json') ? await response.json() : await response.text();
  } catch {
    data = null;
  }

  if (!response.ok) throw toApiError(response.status, response.statusText, data);
  if (response.status === 204) return undefined as T;
  return data as T;
}

export async function downloadFileBlob(path: string, filename: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path));
  } catch (networkError) {
    throw unreachable(getApiBaseUrl(), networkError);
  }

  if (!response.ok) {
    throw new ApiError(`Could not download the file (${response.status}).`, response.status);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(objectUrl);
}

export async function requestBlob(path: string): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(buildUrl(path));
  } catch (networkError) {
    throw unreachable(getApiBaseUrl(), networkError);
  }

  if (!response.ok) {
    throw new ApiError(`Could not fetch the file content (${response.status}).`, response.status);
  }

  return response.blob();
}

/**
 * Send a file as the raw body of a request, reporting upload progress (fetch cannot).
 * `onProgress` receives the bytes sent so far; aborting `signal` cancels the upload.
 */
export function uploadBody<T>(
  path: string,
  body: Blob,
  { method = 'PUT', onProgress, signal }: { method?: string; onProgress?: (sent: number) => void; signal?: AbortSignal } = {},
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, buildUrl(path));
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.upload.onprogress = (event) => onProgress?.(event.loaded);
    xhr.onload = () => {
      let data: unknown = xhr.responseText;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        // Not JSON: keep the text.
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as T);
      else reject(toApiError(xhr.status, xhr.statusText, data));
    };
    xhr.onerror = () => reject(unreachable(getApiBaseUrl(), 'upload failed'));
    xhr.onabort = () => reject(new ApiError('The upload was cancelled.', 0, 'upload_cancelled'));
    signal?.addEventListener('abort', () => xhr.abort());
    xhr.send(body);
  });
}
