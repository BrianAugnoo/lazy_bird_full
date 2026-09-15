# Questions bloquantes / Points d'attention pour l'équipe Backend

Conformément à la section 7 de `AGENTS.md`, voici les questions et incohérences identifiées lors de l'analyse initiale :

## 1. Commande de démarrage du backend
- **Constat** : Le serveur en cours d'exécution sur le port 8000 a été lancé avec la commande `uvicorn.exe --reload lazy_bird:main`. Or, `lazy_bird:main` pointe sur la fonction `def main(): print(...)` dans `lazy_bird/__init__.py`. Résultat : toutes les requêtes HTTP (y compris `GET /`) renvoient `500 Internal Server Error`.
- **Solution recommandée** : Relancer le serveur avec :
  ```bash
  uv run uvicorn lazy_bird.main:app --reload
  ```
  (comme documenté dans `lazy_bird/README.md`).

## 2. Absence de `id` dans `FileOut` (`GET /files/` et `POST /files/upload`)
- **Constat** : Les endpoints de gestion de fichiers requièrent un identifiant numérique :
  - `GET /files/{file_id}`
  - `POST /files/{file_id}/process`
  - `DELETE /files/?ids=1&ids=2`
  Cependant, `GET /files/` et `POST /files/upload` renvoient le schéma Pydantic `FileOut` qui ne contient que `name`, `size`, `extension`, `path`, `status` (pas de champ `id`).
  Le seul endroit où `id` apparaît est dans le flux WebSocket `/ws/upload-progress`.
- **Question** : Le backend doit-il ajouter `id: int` dans `FileOut` (recommandé pour une API REST cohérente), ou le frontend doit-il s'appuyer sur la réconciliation avec le flux WebSocket / nom de fichier ?

## 3. Lecture, téléchargement et édition de contenu de fichier
- **Constat** : `AGENTS.md` (§4) demande :
  > "création et édition de fichiers texte directement dans l'interface, actions standard (renommer, déplacer, supprimer, télécharger)"
  Cependant, dans `endpoint.md` :
  - Il n'y a pas d'endpoint pour récupérer le contenu brut d'un fichier (`GET /files/{file_id}/content` ou similaire) pour l'afficher dans les `file-viewers`.
  - Il n'y a pas d'endpoint pour télécharger le binaire d'un fichier.
  - Il n'y a pas d'endpoint pour renommer ou déplacer un fichier.
- **Question** :
  - Pour la création / édition : le frontend peut générer un `Blob`/`File` et l'envoyer via `POST /files/upload?dir=...`. Est-ce l'approche attendue ?
  - Pour la lecture du contenu : est-il prévu d'ajouter un endpoint de lecture du contenu (ex: `GET /files/{file_id}/content`), ou devons-nous pour l'instant afficher les métadonnées et simuler la prévisualisation / lecture locale lors de l'upload ?
