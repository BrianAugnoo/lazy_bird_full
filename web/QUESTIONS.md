# Backend Integration Status & Notes

Conformément à la section 7 de `AGENTS.md` :

## 1. Commande de démarrage du backend
- **Rappel** : Pour démarrer le backend FastAPI avec rechargement à chaud, utiliser :
  ```bash
  uv run uvicorn lazy_bird.main:app --reload
  ```
  (accessible par défaut sur `http://localhost:8000`).

## 2. Statut des endpoints ajoutés dans `endpoint.md`
Les points précédemment soulevés sont désormais **intégrés et consommés par le frontend** :
- `id`, `embedded_by` et `vector_db` sont inclus dans le schéma `FileItem`.
- Lecture de contenu textuel : `GET /files/{file_id}/content` (consommé par les éditeurs de code et markdown).
- Mise à jour de contenu : `PUT /files/{file_id}/content`.
- Téléchargement binaire : `GET /files/{file_id}/download`.
- Déplacement / renommage : `PATCH /files/{file_id}`.
- Création / déplacement / suppression de répertoires : `POST`, `PATCH`, `DELETE /files/directory`.
- Préférences applicatives : `GET` et `PUT /preferences/` (avec prise en charge de `auto-embedding`).
