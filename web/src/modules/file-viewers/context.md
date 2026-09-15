# Context Module — file-viewers

## Objectif
Fournit le système de visualisation et d'édition de fichiers de lazy_bird, articulé autour d'un contrat extensible Open/Closed (`registry.ts`).

## API publique exposée
- `registerAllBuiltinViewers()` : enregistre les modules natifs (Markdown, Texte/Code, Métadonnées universelles).
- `FileViewerModal` : modale d'affichage dynamique qui résout automatiquement le meilleur visualiseur selon l'extension du fichier.
- Types : `FileViewerProps`, `FileViewerModule` exportés depuis `@/core/file-viewers/types`.

## Dépendances
- `src/core/file-viewers/registry.ts`
- `src/core/types/api.ts` (`FileItem`)

## Comment l'étendre
Pour ajouter la prise en charge d'un nouveau format de fichier (ex: visualiseur PDF ou images) :
1. Créez un nouveau sous-dossier dans `src/modules/file-viewers/<nouveau-format>/`.
2. Développez le composant respectant l'interface `FileViewerProps`.
3. Appelez `registerViewer({ id, name, canHandle: (ext) => ext === 'pdf', Component })` dans son point d'entrée ou lors de l'initialisation de l'application.

## Limitations connues / TODO
- La lecture du contenu textuel de fichiers existants stockés sur le serveur dépend de la capacité du navigateur à lire les fichiers locaux ou d'un futur endpoint backend de streaming de contenu brut.
