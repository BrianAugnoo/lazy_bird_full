# Context Module — file-explorer

## Objectif
Interface d'exploration, d'organisation, d'upload multiple par glisser-déposer, d'édition et de traitement RAG des fichiers stockés dans lazy_bird.

## API publique exposée
- `FileExplorer` : composant principal React du gestionnaire de fichiers.

## Dépendances
- `src/api/endpoints/files.ts` (`getFiles`, `uploadFiles`, `deleteFiles`, `deleteAllFiles`, `processFile`)
- `src/api/ws.ts` (`progressWs`) pour le suivi en temps réel
- `src/modules/file-viewers/` (`FileViewerModal`)
- `src/core/types/api.ts` (`FileItem`, `FileProgressItem`)

## Comment l'étendre
- Pour ajouter des filtres (par statut, taille, type), étendre les états de filtrage dans `FileExplorer.tsx`.
- Pour connecter un nouvel endpoint backend (ex: renommage ou déplacement), ajouter la méthode correspondante dans `src/api/endpoints/files.ts` et ajouter le bouton d'action dans la table.

## Limitations connues / TODO
- L'arborescence des dossiers est actuellement virtuelle et calculée à partir des chemins de fichiers.
