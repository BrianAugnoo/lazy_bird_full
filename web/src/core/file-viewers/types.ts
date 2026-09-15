import type React from 'react';
import type { FileItem } from '../types/api';

export interface FileViewerProps {
  file: FileItem;
  content?: string;
  onSave?: (nextContent: string) => Promise<void>;
  onClose: () => void;
  onProcess?: (fileId: number) => Promise<void>;
}

export interface FileViewerModule {
  id: string;
  name: string;
  icon?: string;
  canHandle: (extension: string, mimeType?: string) => boolean;
  Component: React.ComponentType<FileViewerProps>;
  priority?: number; // Permet de prioriser un visualiseur spécialisé sur un générique
}
