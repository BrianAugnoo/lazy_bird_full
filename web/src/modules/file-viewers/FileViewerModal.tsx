import React from 'react';
import type { FileItem } from '@/core/types/api';
import { resolveViewer } from '@/core/file-viewers/registry';

interface FileViewerModalProps {
  file: FileItem | null;
  content?: string;
  onSave?: (nextContent: string) => Promise<void>;
  onClose: () => void;
  onProcess?: (fileId: number) => Promise<void>;
}

export const FileViewerModal: React.FC<FileViewerModalProps> = ({
  file,
  content,
  onSave,
  onClose,
  onProcess,
}) => {
  if (!file) return null;

  const viewer = resolveViewer(file.extension);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-window"
        style={{ maxWidth: '860px', height: '80vh' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-body" style={{ height: '100%', padding: '24px' }}>
          {viewer ? (
            <viewer.Component
              file={file}
              content={content}
              onSave={onSave}
              onClose={onClose}
              onProcess={onProcess}
            />
          ) : (
            <div className="state-empty">
              <span style={{ fontSize: '2rem' }}>⚠️</span>
              <div className="state-title">No compatible viewer</div>
              <p className="state-desc">
                Format {file.extension} is not supported by installed viewer modules.
              </p>
              <button type="button" className="btn btn-secondary" onClick={onClose}>
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
