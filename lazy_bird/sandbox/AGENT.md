# Sandbox Document Atlas

Ce dossier contient un serveur FastAPI autonome pour construire progressivement
un dataset de documents et de relations. Il ne depend pas de la base de donnees
de l'application principale.

## Demarrage

Depuis la racine du depot:

```bash
./.venv/bin/uvicorn sandbox.main:app --reload --port 8100
```

Ouvrir <http://127.0.0.1:8100/> pour l'interface. La documentation interactive
est disponible sur <http://127.0.0.1:8100/docs>.

Le service utilise `sandbox/documents.db` et `sandbox/documents/` par defaut.
Pour isoler un test ou une branche de travail:

```bash
SANDBOX_DB_PATH=/tmp/atlas.db SANDBOX_DOCUMENTS_DIR=/tmp/atlas-docs \
  ./.venv/bin/uvicorn sandbox.main:app --port 8100
```

## API

Les routes canoniques sont sous `/api/documents`; `/documents` est un alias
pratique pour les scripts simples.

```text
GET    /api/documents?query=mail
POST   /api/documents
GET    /api/documents/{id}
PUT    /api/documents/{id}
PATCH  /api/documents/{id}
DELETE /api/documents/{id}
POST   /api/documents/{id}/relations/{other_id}
DELETE /api/documents/{id}/relations/{other_id}
```

Exemple de creation:

```bash
curl -X POST http://127.0.0.1:8100/api/documents \
  -H 'content-type: application/json' \
  -d '{"name":"reply.md","subfolder":"emails","content":"A reply","related_docs":[]}'
```

`name` est le nom du fichier. `subfolder` est optionnel et peut contenir des
sous-dossiers (`emails/2026`). Il est aussi possible de donner directement un
nom relatif comme `emails/reply.md`. Les chemins absolus, `..`, les chemins
Windows et toute sortie de `documents/` sont refuses.

Le champ `related_docs` contient une liste d'identifiants. Chaque relation est
stockee dans les deux sens; supprimer un lien depuis l'un des documents le
supprime donc pour les deux.

## CLI pour les agents

Toutes les commandes renvoient du JSON, sauf `delete` qui renvoie `ok`:

```bash
./.venv/bin/python -m sandbox.cli list
./.venv/bin/python -m sandbox.cli create emails/inbox.md --content 'Message'
./.venv/bin/python -m sandbox.cli create notes.md --file /tmp/notes.md
./.venv/bin/python -m sandbox.cli show 1
./.venv/bin/python -m sandbox.cli update 1 --content 'Version 2'
./.venv/bin/python -m sandbox.cli update 1 --related 2 3
./.venv/bin/python -m sandbox.cli link 1 2
./.venv/bin/python -m sandbox.cli unlink 1 2
./.venv/bin/python -m sandbox.cli delete 1
```

Pour alimenter le contenu depuis stdin:

```bash
printf '# Source\n\nTexte' | ./.venv/bin/python -m sandbox.cli create source.md
```

Les agents doivent utiliser la CLI ou l'API plutot que modifier directement la
base SQLite. Les fichiers peuvent etre lus pour analyse, mais leurs liens
doivent toujours passer par `link`, `unlink` ou `related_docs`.

