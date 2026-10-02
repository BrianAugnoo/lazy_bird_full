# Tâche : moteur de recherche + arbre d'appels sur `logs.txt`

## Contexte
Projet `lazy_bird`. Le logging (`lazy_bird.logging_config`) écrit dans `logs.txt` (format loguru) :

    <date heure.ms> | <NIVEAU> | <process>:<pid> | <thread>:<tid> | <module>:<fonction>:<ligne> | <message>

Quand le message est un événement de tracing, c'est un JSON :
- `{"event":"function_call","call_id","parent_id","module","function","args":{...}}`
- `{"event":"function_return","call_id","parent_id","module","function","status","duration_ms","result"}`

`call_id` / `parent_id` permettent de reconstruire l'arbre d'appels. **Avant de coder, lis `logs.txt` et `logging_config.py`** pour vérifier le format réel, notamment comment sont loggées les exceptions et les tracebacks (événement d'erreur, `status: "error"`, lignes multi-lignes, etc.). Ne suppose rien que tu n'as pas vu.

## Livrable 1 : parsing (`log_parser`)
- Lecture en streaming (le fichier peut être gros), jamais de `read()` complet inutile.
- Une **entrée de log** = une ligne d'en-tête (commençant par un timestamp) + ses lignes de continuation (traceback, messages multi-lignes).
- Dataclass `LogEntry` : `start_line`, `end_line` (numéros de ligne 1-indexés dans le fichier), `timestamp`, `level`, `process`, `thread`, `location`, `message`, `payload` (dict si JSON valide, sinon `None`), `raw_text`, `score` (BM25, sinon `None`).
- Tolérant : ligne finale tronquée, JSON invalide ou encodage douteux ne doivent jamais faire planter le parsing (l'entrée est gardée avec `payload=None`).

## Livrable 2 : `search_logs`

    search_logs(
        query: str | None = None,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        last_n: int | None = None,
        mode: Literal["bm25", "regex"] = "bm25",
        ignore_case: bool = True,
        log_file: Path = Path("logs.txt"),
    ) -> list[LogEntry]

Règles :
1. `query` renseignée → recherche selon `mode` :
   - `bm25` : classement BM25 sur `raw_text`. Choisis la lib la plus adaptée (ex. `rank_bm25` ou `bm25s`), avec un tokenizer adapté aux logs (découpe sur `.`, `_`, `:`, espaces, ponctuation, `camelCase`), et justifie ton choix en 2-3 lignes.
   - `regex` : module `re` de la stdlib, pattern compilé une seule fois, `re.error` converti en erreur claire.
2. `query` vide/`None` → toutes les entrées à partir de `since`.
3. `query` vide **et** `since` à `None` → lève `LogSearchError` (message explicite).
4. `since` / `until` filtrent par timestamp (bornes incluses). Applique le filtre de dates **avant** d'indexer en BM25 pour réduire le corpus.
5. `last_n` → ne garde que les N entrées les plus **récentes** parmi les correspondances. Le résultat est toujours renvoyé en **ordre chronologique**.
6. BM25 : une entrée est « trouvée » si son score > 0.
7. Chaque `LogEntry` retournée inclut ses numéros de ligne (`start_line`–`end_line`).

## Livrable 3 : `trace_function_calls` (destinée au tracing des appels)

    trace_function_calls(
        function_name: str,
        module_name: str | None = None,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        last_n: int | None = None,
        raw: bool = False,
        log_file: Path = Path("logs.txt"),
    ) -> str

- Trouve les appels dont `function` == `function_name` (et `module` == `module_name` si fourni), dans la plage de dates, puis garde les `last_n` plus récents. Si `module_name` est omis et que plusieurs modules correspondent, retourne tous les résultats en préfixant chacun par son module.
- Pour chaque appel trouvé, reconstruis **tout son sous-arbre** (descendants via `parent_id`) en associant chaque `function_call` à son `function_return` / erreur par `call_id`.
- `raw=True` → affiche les lignes brutes du fichier (comme dans `logs.txt`), triées chronologiquement, avec leur numéro de ligne. exemple:

2026-10-01 21:52:04.849 | INFO     | SpawnProcess-1:25992 | AnyIO worker thread:22044 | lazy_bird.logging_config:_log_event:43 | {"event":"function_call","call_id":"18a381d6c6da435d99137408f1e0e0c5","parent_id":"1a63383d0c844ff384f7945baa349dbd","module":"lazy_bird.api.endpoints.api_key","function":"create_api_key","args":{"api_key_in":"APIKeyIn(name='test', key='test')"}}
2026-10-01 21:52:04.849 | INFO     | SpawnProcess-1:25992 | AnyIO worker thread:22044 | lazy_bird.logging_config:_log_event:43 | {"event":"function_call","call_id":"eca55fb08f15416c8a41135ade95c534","parent_id":"18a381d6c6da435d99137408f1e0e0c5","module":"lazy_bird.crud.api_key","function":"create","args":{"api_key_in":"APIKeyIn(name='test', key='test')"}}
2026-10-01 21:52:04.849 | INFO     | SpawnProcess-1:25992 | AnyIO worker thread:22044 | lazy_bird.logging_config:_log_event:43 | {"event":"function_call","call_id":"44ea626caf5b410eb9a19535fc131b11","parent_id":"eca55fb08f15416c8a41135ade95c534","module":"lazy_bird.database","function":"db","args":{}}
2026-10-01 21:52:04.849 | INFO     | SpawnProcess-1:25992 | AnyIO worker thread:22044 | lazy_bird.logging_config:_log_event:43 | {"event":"function_return","call_id":"44ea626caf5b410eb9a19535fc131b11","parent_id":"eca55fb08f15416c8a41135ade95c534","module":"lazy_bird.database","function":"db","status":"success","duration_ms":0.22,"result":"<sqlmodel.orm.session.Session object at 0x000001F1593EE000>"}
2026-10-01 21:52:04.863 | INFO     | SpawnProcess-1:25992 | AnyIO worker thread:22044 | lazy_bird.logging_config:_log_event:43 | {"event":"function_call","call_id":"679413881f30462eb8ec0a27d3fc701a","parent_id":"eca55fb08f15416c8a41135ade95c534","module":"lazy_bird.database","function":"db","args":{}}
2026-10-01 21:52:04.864 | INFO     | SpawnProcess-1:25992 | AnyIO worker thread:22044 | lazy_bird.logging_config:_log_event:43 | {"event":"function_return","call_id":"679413881f30462eb8ec0a27d3fc701a","parent_id":"eca55fb08f15416c8a41135ade95c534","module":"lazy_bird.database","function":"db","status":"success","duration_ms":0.55,"result":"None"}
2026-10-01 21:52:04.864 | INFO     | SpawnProcess-1:25992 | AnyIO worker thread:22044 | lazy_bird.logging_config:_log_event:43 | {"event":"function_return","call_id":"eca55fb08f15416c8a41135ade95c534","parent_id":"18a381d6c6da435d99137408f1e0e0c5","module":"lazy_bird.crud.api_key","function":"create","status":"success","duration_ms":14.79,"result":"APIKeyOut(name='test')"}
2026-10-01 21:52:04.865 | INFO     | SpawnProcess-1:25992 | AnyIO worker thread:22044 | lazy_bird.logging_config:_log_event:43 | {"event":"function_return","call_id":"18a381d6c6da435d99137408f1e0e0c5","parent_id":"1a63383d0c844ff384f7945baa349dbd","module":"lazy_bird.api.endpoints.api_key","function":"create_api_key","status":"success","duration_ms":15.41,"result":"APIKeyOut(name='test')"}

- `raw=False` → arbre indenté (4 espaces par niveau) :

      lazy_bird.api.endpoints.api_key.create_api_key(api_key_in: APIKeyIn(name='test', key='test')): -> APIKeyOut(name='test')
          lazy_bird.crud.api_key.create(api_key_in: APIKeyIn(name='test', key='test')): -> APIKeyOut(name='test')
              lazy_bird.database.db(): -> None

- **Cas à gérer explicitement dans l'arbre :**
  - Appel terminé par une exception → `-> ✗ NomErreur: message`, suivi du traceback complet indenté sous l'appel.
  - Appel **sans retour ni erreur** (programme tué/fermé, crash, fichier tronqué) → `-> ⚠ INTERROMPU (aucun retour ni erreur loggé)`. Ne jamais afficher un faux `None`.
  - `function_return` orphelin (appel parent absent du fichier) → rattaché à la racine avec un marqueur `(parent introuvable)`.
  - Aucune correspondance → message clair et code de sortie dédié (voir CLI).

## Livrable 4 : CLI (utilisable par des agents IA)
Point d'entrée unique, par ex. `python -m lazy_bird.log_tools` (argparse ou typer), avec deux sous-commandes :

    search  [QUERY] [--mode bm25|regex] [--since D] [--until D] [--last-n N] [--ignore-case/--case-sensitive]
    trace   FUNCTION_NAME [--module M] [--since D] [--until D] [--last-n N] [--raw]

Options communes : `--log-file PATH` (défaut `logs.txt`), `--json` (sortie JSON structurée, stable, pensée pour les agents IA, y compris pour les erreurs), `--color auto|always|never`.

- Dates acceptées : ISO 8601 (`2026-10-01`, `2026-10-01T21:52:04`) **et** durées relatives (`15m`, `2h`, `1d` = « il y a … »).
- Codes de sortie : `0` résultats trouvés, `1` aucun résultat, `2` erreur d'usage/arguments (ex. query et since vides), `3` fichier introuvable/illisible.
- Erreurs sur **stderr**, résultats sur **stdout**. Un agent doit pouvoir distinguer « aucun résultat » d'une vraie erreur grâce au code de sortie.
- `--help` clair avec exemples sur chaque sous-commande.

## Couleurs
- Respecter `NO_COLOR`, désactiver automatiquement si stdout n'est pas un TTY (`--color auto`), forcer avec `--color always`. Aucune couleur en mode `--json`.
- Niveaux : ERROR/CRITICAL rouge, WARNING jaune, INFO vert, DEBUG gris.
- Arbre : nom du module en dim, nom de fonction en gras/cyan, `✗` erreur et traceback en rouge, `⚠ INTERROMPU` en jaune/orange, durée en dim.
- Recherche : surligner les termes/matches trouvés (regex : le match ; BM25 : les tokens de la requête), numéros de ligne en dim.

## Contraintes
- Python typé (annotations complètes), docstrings courtes, pas de dépendance superflue (ajoute celles requises dans `pyproject.toml`/`requirements`).
- Séparer en modules clairs : parsing, recherche, arbre d'appels, rendu (couleurs), CLI.
- Aucune modification du comportement existant du logging.

## Tests (pytest)
Avec un petit `logs.txt` de fixture contenant : appels imbriqués réussis, un appel en erreur avec traceback, un appel interrompu (sans retour), une ligne finale tronquée, une entrée multi-lignes. Couvrir : les deux modes de recherche, `last_n`, les bornes de dates, l'erreur « query et since vides », `raw` True/False, les codes de sortie CLI.

## À la fin
1. Résume en quelques lignes les choix techniques (lib BM25, tokenizer).
2. **Explique-moi précisément comment appeler chaque commande** : une section par sous-commande avec tous les paramètres, 3-4 exemples réels par commande (dont un exemple `--json` pour un agent IA, un cas d'erreur et un cas d'appel interrompu), les codes de sortie, et comment lire la sortie.