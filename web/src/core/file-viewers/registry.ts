import type { FileViewerModule } from './types';

/**
 * Registry extensible pour les modules de visualisation / édition de fichiers
 * Respecte le principe Open/Closed : tout nouveau format est un module qui s'enregistre
 * sans altérer le code existant.
 */
const registry: FileViewerModule[] = [];

/**
 * Enregistre un nouveau module de visualisation.
 * Retourne une fonction de désenregistrement utile pour les tests et le cycle de vie React.
 */
export const registerViewer = (viewer: FileViewerModule): (() => void) => {
  const existingIndex = registry.findIndex((v) => v.id === viewer.id);
  if (existingIndex >= 0) {
    registry[existingIndex] = viewer;
  } else {
    registry.push(viewer);
  }

  // Tri par priorité décroissante (la priorité la plus haute est testée en premier)
  registry.sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));

  return () => {
    const idx = registry.findIndex((v) => v.id === viewer.id);
    if (idx >= 0) {
      registry.splice(idx, 1);
    }
  };
};

/**
 * Résout le visualiseur le plus approprié pour une extension ou un type MIME donné.
 * Normalise l'extension (avec ou sans point initial, insensible à la casse).
 */
export const resolveViewer = (extension: string, mimeType?: string): FileViewerModule | undefined => {
  const cleanExt = extension.trim().toLowerCase().replace(/^\./, '');
  return registry.find((viewer) => viewer.canHandle(cleanExt, mimeType));
};

/**
 * Récupère l'ensemble des visualiseurs enregistrés.
 */
export const getAllViewers = (): readonly FileViewerModule[] => {
  return [...registry];
};

/**
 * Réinitialise le registre (essentiellement utilisé dans les tests unitaires).
 */
export const clearViewers = (): void => {
  registry.length = 0;
};
