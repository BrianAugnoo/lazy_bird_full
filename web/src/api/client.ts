/**
 * Client HTTP centralisé et typé pour Lazy Bird
 * Conforme à AGENTS.md :
 * - Aucune URL codée en dur (configurable via VITE_API_URL avec fallback)
 * - Gestion explicite des erreurs 503 (startup failure) et 422 (validation FastAPI)
 */

export const getApiBaseUrl = (): string => {
  const configuredUrl = typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL;
  if (configuredUrl) return configuredUrl;
  if (typeof import.meta !== 'undefined' && import.meta.env?.DEV) return '/api';
  return 'http://localhost:8000';
};

export class ApiError extends Error {
  public status: number;
  public details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

export async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`;

  const defaultHeaders: Record<string, string> = {};
  if (!(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const mergedOptions: RequestInit = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  let response: Response;
  try {
    response = await fetch(url, mergedOptions);
  } catch (networkErr) {
    throw new ApiError(
      `Impossible de joindre le serveur Lazy Bird (${baseUrl}). Vérifiez qu'il est bien démarré.`,
      0,
      networkErr
    );
  }

  // Traitement du corps de la réponse (JSON si possible)
  const contentType = response.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  let data: any = null;

  if (isJson) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      data = await response.text();
    } catch {
      data = null;
    }
  }

  // Gestion des erreurs HTTP
  if (!response.ok) {
    // 503 : Startup failure
    if (response.status === 503) {
      const errorMessage = data?.error || 'Le serveur backend est en cours d’initialisation ou la base de données est indisponible.';
      throw new ApiError(errorMessage, 503, data);
    }

    // 422 : Validation FastAPI
    if (response.status === 422) {
      const detail = data?.detail;
      const formattedDetail = Array.isArray(detail)
        ? detail.map((d: any) => `${d.loc ? d.loc.join('.') + ': ' : ''}${d.msg}`).join(', ')
        : (typeof detail === 'string' ? detail : 'Paramètres de requête invalides (erreur 422).');
      throw new ApiError(formattedDetail, 422, data);
    }

    // 400 : Erreur métier (ex: clé API déjà existante)
    if (response.status === 400) {
      const msg = data?.detail || data?.message || 'Requête invalide (400).';
      throw new ApiError(msg, 400, data);
    }

    // 404 : Introuvable
    if (response.status === 404) {
      const msg = data?.detail || 'Ressource demandée introuvable (404).';
      throw new ApiError(msg, 404, data);
    }

    // Autres erreurs (500, etc.)
    const fallbackMsg = (typeof data === 'string' && data.length > 0)
      ? data
      : (data?.error || data?.message || `Erreur serveur (${response.status} ${response.statusText}).`);
    throw new ApiError(fallbackMsg, response.status, data);
  }

  return data as T;
}

export async function downloadFileBlob(path: string, filename: string): Promise<void> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`;

  let response: Response;
  try {
    response = await fetch(url);
  } catch (networkErr) {
    throw new ApiError(
      `Impossible de joindre le serveur Lazy Bird (${baseUrl}). Vérifiez qu'il est bien démarré.`,
      0,
      networkErr
    );
  }

  if (!response.ok) {
    throw new ApiError(`Impossible de télécharger le fichier (${response.status}).`, response.status);
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
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`;

  let response: Response;
  try {
    response = await fetch(url);
  } catch (networkErr) {
    throw new ApiError(
      `Impossible de joindre le serveur Lazy Bird (${baseUrl}). Vérifiez qu'il est bien démarré.`,
      0,
      networkErr
    );
  }

  if (!response.ok) {
    throw new ApiError(`Impossible de récupérer le contenu du fichier (${response.status}).`, response.status);
  }

  return response.blob();
}
