import { useRoute } from '@/core/router';
import { FileBrowser } from './FileBrowser';
import { FileEditor } from './FileEditor';

export function FilesPage() {
  const { params } = useRoute();
  const fileId = Number(params.file);
  return params.file && Number.isFinite(fileId) ? <FileEditor key={fileId} fileId={fileId} /> : <FileBrowser dir={params.dir ?? ''} />;
}
