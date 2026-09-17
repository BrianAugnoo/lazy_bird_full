import { request, requestBlob, downloadFileBlob } from '../client';
import type { FileItem, FileProcessResponse, DirectoryResponse, FilePatchIn } from '@/core/types/api';

/**
 * Upload one or multiple files
 * POST /files/upload?dir=...
 */
export async function uploadFiles(dir: string, files: File[]): Promise<FileItem[]> {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }

  const queryDir = encodeURIComponent(dir);
  return request<FileItem[]>(`/files/upload?dir=${queryDir}`, {
    method: 'POST',
    body: formData,
  });
}

/**
 * List all stored files
 * GET /files/
 */
export async function getFiles(): Promise<FileItem[]> {
  return request<FileItem[]>('/files/');
}

/**
 * Get file metadata by ID
 * GET /files/{file_id}
 */
export async function getFile(fileId: number): Promise<FileItem | null> {
  return request<FileItem | null>(`/files/${fileId}`);
}

/**
 * Get UTF-8 text content of a file
 * GET /files/{file_id}/content
 */
export async function getFileContent(fileId: number): Promise<string> {
  return request<string>(`/files/${fileId}/content`);
}

/**
 * Get the complete stored file as binary data and decode it as UTF-8 text
 * GET /files/{file_id}/full
 */
export async function getFullFileContent(fileId: number): Promise<string> {
  const blob = await requestBlob(`/files/${fileId}/full`);
  return blob.text();
}

/**
 * Update UTF-8 text content of a file
 * PUT /files/{file_id}/content
 */
export async function updateFileContent(fileId: number, content: string): Promise<FileItem> {
  return request<FileItem>(`/files/${fileId}/content`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  });
}

/**
 * Download a stored file as binary
 * GET /files/{file_id}/download
 */
export async function downloadFile(fileId: number, filename: string = 'file'): Promise<void> {
  return downloadFileBlob(`/files/${fileId}/download`, filename);
}

/**
 * Rename and/or move a file
 * PATCH /files/{file_id}
 */
export async function patchFile(fileId: number, data: FilePatchIn): Promise<FileItem> {
  return request<FileItem>(`/files/${fileId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * Create an empty directory
 * POST /files/directory?path=...
 */
export async function createDirectory(path: string): Promise<DirectoryResponse> {
  const queryPath = encodeURIComponent(path);
  return request<DirectoryResponse>(`/files/directory?path=${queryPath}`, {
    method: 'POST',
  });
}

/**
 * Move / rename a directory
 * PATCH /files/directory?source=...&destination=...
 */
export async function moveDirectory(source: string, destination: string): Promise<DirectoryResponse> {
  const querySource = encodeURIComponent(source);
  const queryDest = encodeURIComponent(destination);
  return request<DirectoryResponse>(`/files/directory?source=${querySource}&destination=${queryDest}`, {
    method: 'PATCH',
  });
}

/**
 * Delete a directory recursively
 * DELETE /files/directory?path=...
 */
export async function deleteDirectory(path: string): Promise<DirectoryResponse> {
  const queryPath = encodeURIComponent(path);
  return request<DirectoryResponse>(`/files/directory?path=${queryPath}`, {
    method: 'DELETE',
  });
}

/**
 * Trigger RAG processing (chunking & embedding) for an existing file
 * POST /files/{file_id}/process
 */
export async function processFile(fileId: number): Promise<FileProcessResponse> {
  return request<FileProcessResponse>(`/files/${fileId}/process`, {
    method: 'POST',
  });
}

/**
 * Delete selected files by ID
 * DELETE /files/ with a JSON array body: [1, 2]
 */
export async function deleteFiles(ids: number[]): Promise<{ message: string }> {
  if (ids.length === 0) {
    return { message: 'No files to delete.' };
  }
  return request<{ message: string }>('/files/', {
    method: 'DELETE',
    body: JSON.stringify(ids),
  });
}

/**
 * Delete all files
 * DELETE /files/delete_all
 */
export async function deleteAllFiles(): Promise<{ message: string }> {
  return request<{ message: string }>('/files/delete_all', {
    method: 'DELETE',
  });
}
