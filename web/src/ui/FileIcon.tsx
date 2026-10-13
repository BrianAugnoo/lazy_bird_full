import { fileIconAsset } from '@/file_icon/registry';

export function FileIcon({ extension = '', folder = false }: { extension?: string; folder?: boolean }) {
  if (folder) return <svg className="finder-folder" width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path className="folder-back" d="M2 7a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v9H2z" /><path className="folder-front" d="M2 9h20v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z" /></svg>;
  return <span className="registered-file-icon" aria-hidden="true" style={{ maskImage: `url("${fileIconAsset(extension)}")` }} />;
}
