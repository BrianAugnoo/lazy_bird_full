/**
 * Types partagés pour l'UI, les états de chargement / erreur / vide
 * Conformité Definition of Done §10 : États chargement / erreur / vide gérés
 */

export type StatusState = 'idle' | 'loading' | 'success' | 'error' | 'empty';

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  isEmpty: boolean;
}

export interface ApiErrorDetail {
  loc?: (string | number)[];
  msg?: string;
  type?: string;
}

export interface ApiErrorResponse {
  success?: boolean;
  error?: string;
  detail?: string | ApiErrorDetail[];
  invalid_keys?: string[];
  message?: string;
}

export type TabType = 
  | 'files' 
  | 'models' 
  | 'embeddings' 
  | 'databases' 
  | 'api-keys' 
  | 'search';
