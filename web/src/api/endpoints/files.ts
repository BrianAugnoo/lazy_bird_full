import { request } from '../client';
import type { FileItem, FileProcessResponse } from '@/core/types/api';

/**
 * Upload d'un ou plusieurs fichiers
 * POST /files/upload?dir=...
 */
export async function uploadFiles(dir: string, files: File[]): Promise<FileItem[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }

  const queryDir = encodeURIComponent(dir || 'documents');
  return request<FileItem[]>(`/files/upload?dir=${queryDir}`, {
    method: 'POST',
    body: formData,
  });
}

/**
 * Liste l'ensemble des fichiers stockés
 * GET /files/
 */
export async function getFiles(): Promise<FileItem[]> {
  return request<FileItem[]>('/files/');
}

/**
 * Récupère les métadonnées d'un fichier par son ID
 * GET /files/{file_id}
 */
export async function getFile(fileId: number): Promise<FileItem | null> {
  return request<FileItem | null>(`/files/${fileId}`);
}

/**
 * Déclenche le traitement (chunking / embedding) d'un fichier existant
 * POST /files/{file_id}/process
 */
export async function processFile(fileId: number): Promise<FileProcessResponse> {
  return request<FileProcessResponse>(`/files/${fileId}/process`, {
    method: 'POST',
  });
}

/**
 * Supprime les fichiers sélectionnés
 * DELETE /files/?ids=1&ids=2
 */
export async function deleteFiles(ids: number[]): Promise<{ message: string }> {
  if (ids.length === 0) {
    return { message: 'No files to delete.' };
  }
  const queryString = ids.map((id) => `ids=${encodeURIComponent(id)}`).join('&');
  return request<{ message: string }>(`/files/?${queryString}`, {
    method: 'DELETE',
  });
}

/**
 * Supprime la totalité des fichiers
 * DELETE /files/delete_all
 */
export async function deleteAllFiles(): Promise<{ message: string }> {
  return request<{ message: string }>('/files/delete_all', {
    method: 'DELETE',
  });
}
