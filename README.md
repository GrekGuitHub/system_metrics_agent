# Rapport DevOps : conteneurisation et CI/CD

**Auteur :** GREKOVOUNGBO Thibaut Mermoz, INGC2, IAI Libreville

| Livrable | Lien |
|---|---|
| Image API | https://hub.docker.com/r/grekovdocker/system-metrics-api |
| Image agent | https://hub.docker.com/r/grekovdocker/system-metrics-agent |
| Pipeline vert | `<lien vers l'exécution verte dans Actions>` |
| Pipeline rouge (échec volontaire) | `<lien vers l'exécution rouge dans Actions>` |

## Choix techniques

- **Tests** : les tests sont dans `app/tests/`, pas dans `tests/` comme l'indiquait le README, et `test_api.py` n'existait pas. Les tests du collecteur échouaient sous Windows, car ils ne simulaient pas l'OS. Ils ont été corrigés, puis complétés (API, configuration, agent) : 20 tests, environ 83 % de couverture du code applicatif.
- **Dépendances** : `requirements.txt` (exécution, versions fixées) est séparé de `requirements-dev.txt` (pytest, black, flake8), qui n'entre jamais dans les images.
- **Images** : base `python:3.12.15-slim-trixie` (version exacte, jamais `latest`). Build **multi-stage** : les dépendances sont installées dans un venv, et seul ce venv est copié dans l'image finale. `requirements.txt` est copié avant le code pour profiter du cache. L'image tourne avec l'utilisateur **non-root** `app`, le code appartient à root (lecture seule), et `.dockerignore` exclut `.env`, `.git` et les tests. L'API a un `HEALTHCHECK` en Python (pas de curl dans l'image slim) et lance uvicorn sans `--reload`, sur `0.0.0.0`. La configuration est injectée par variables d'environnement.
- **`uptime`** : absente de l'image slim. Elle est fournie par le paquet Debian `procps`, installé dans l'image de l'agent uniquement (`--no-install-recommends`, cache apt supprimé).
- **Agent conteneurisé** : il lit les compteurs du noyau qui l'héberge (la VM WSL2 sous Docker Desktop : 3,96 Go mesurés contre 8,3 Go sur Windows) et ignore les limites du conteneur. Son nom d'hôte est l'ID du conteneur. Pour superviser un vrai serveur, il faut lui donner accès à l'hôte (`pid: host`, `/proc` de l'hôte monté) ou l'installer directement sur la machine, comme node_exporter.
- **Compose** : l'agent joint `http://api:8000` par le nom du service et ne démarre qu'avec `depends_on: condition: service_healthy`. `METRICS_ENDPOINT` est forcé dans le Compose, les autres réglages viennent du `.env` (non versionné), avec `restart: unless-stopped`.
- **Pipeline** : un job `test` (pytest + couverture XML, SonarQube Cloud avec `sonar.qualitygate.wait=true`), puis un job `build-scan-push` lancé via une matrice api/agent : build `load: true`, Trivy (`exit-code: 1`, HIGH/CRITICAL, `ignore-unfixed`), puis push des tags `<sha>` et `latest` **sur `main` uniquement**. C'est l'image scannée qui est poussée, sans rebuild. Le cache des couches est stocké dans GitHub Actions (bonus).
- **Sécurité** : quatre secrets GitHub, aucun secret dans le dépôt. Jetons Docker Hub et Sonar dédiés, avec expiration. L'application SonarQube Cloud est limitée à ce seul dépôt (moindre privilège). Trivy est épinglé sur un **SHA de commit**, suite à la compromission des tags `trivy-action` en mars 2026.

## Tailles des images

| Image | Sur disque | Compressée |
|---|---|---|
| `python:3.12-slim-trixie` (base) | 179 Mo | 45 Mo |
| `system-metrics-api` | 224 Mo | 54 Mo |
| `system-metrics-agent` | 226 Mo | 54 Mo |

Le code et les dépendances n'ajoutent qu'environ 45 Mo à l'image de base.

## Démonstration de l'échec volontaire

Sur `main`, l'image de base de l'API a été remplacée par `python:3.12.0-slim-bookworm` (2023). Trivy a détecté `<N>` vulnérabilités HIGH/CRITICAL corrigeables : le job API a échoué et **l'étape de push a été sautée**. L'image de l'agent, non modifiée, est restée verte. Le changement a ensuite été annulé avec `git revert`, et le pipeline est repassé au vert.

## Difficultés rencontrées

- Téléchargements pip interrompus (connexion lente) : `--timeout` et `--retries`.
- Docker Desktop ne résolvait pas `registry-1.docker.io` (DNS IPv6 local) : réglé avec `wsl --shutdown`.
- Windows retirait le point de `.dockerignore` et `.gitattributes` au téléchargement, si bien que l'ancien `.dockerignore` était utilisé.
- SonarQube Cloud : il faut désactiver l'*Automatic Analysis* pour analyser depuis la CI.
- Pull request depuis un fork : il faut cibler `main` du fork et non le dépôt d'origine.
- L'agent met 10 s à s'arrêter (il ignore SIGTERM) ; amélioration possible : `STOPSIGNAL SIGINT`.

---

# System Metrics Agent

Un agent Python modulaire capable de collecter les métriques système,
de les formater et de les transmettre en temps réel vers une API ou un
Webhook externe.

## Fonctionnalités

- Collecte du pourcentage CPU.
- Collecte de la mémoire RAM totale, utilisée et disponible.
- Utilisation de `psutil`.
- Utilisation de **`subprocess`** pour exécuter la commande système
  `uptime` et récupérer la charge système.
- Architecture modulaire :
  - `collector.py` : collecte ;
  - `formatter.py` : normalisation du payload ;
  - `sender.py` : envoi HTTP ;
  - `agent.py` : orchestration ;
  - `api.py` : API de réception avec **FastAPI**.
- Configuration externe avec `.env`.
- Gestion des erreurs réseau et des erreurs de collecte.
- Tests automatisés avec `pytest`.

## Architecture

```text
system_metrics_agent/
├── app/
│   ├── __init__.py
│   ├── agent.py
│   ├── api.py
│   ├── collector.py
│   ├── config.py
│   ├── formatter.py
│   └── sender.py
├── tests/
│   ├── test_api.py
│   ├── test_collector.py
│   ├── test_formatter.py
│   └── test_sender.py
├── .env.example
├── requirements.txt
└── README.md
```

## Installation

Créer un environnement virtuel :

```bash
python -m venv .venv
```

Linux/macOS :

```bash
source .venv/bin/activate
```

Windows :

```powershell
.venv\Scripts\Activate.ps1
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

Créer le fichier de configuration :

```bash
cp .env.example .env
```

Sous Windows, copier manuellement `.env.example` en `.env`.

## Démarrer l'API FastAPI

```bash
uvicorn app.api:app --reload
```

L'API est alors disponible sur :

```text
http://127.0.0.1:8000
```

Documentation interactive FastAPI :

```text
http://127.0.0.1:8000/docs
```

## Démarrer l'agent

Dans un deuxième terminal :

```bash
python -m app.agent
```

L'agent collecte les métriques selon l'intervalle défini dans `.env`
puis les envoie automatiquement vers `METRICS_ENDPOINT`.

## Exemple de configuration

```env
METRICS_ENDPOINT=http://127.0.0.1:8000/metrics
COLLECTION_INTERVAL=5
REQUEST_TIMEOUT=5
```

Pour envoyer vers un webhook externe, remplacer simplement :

```env
METRICS_ENDPOINT=https://example.com/webhook
```

## Exemple de métrique envoyée

```json
{
  "agent": "system-metrics-agent",
  "event_type": "system_metrics",
  "data": {
    "timestamp": "2026-08-27T12:00:00.000000+00:00",
    "hostname": "server-01",
    "cpu": {
      "percent": 23.4,
      "logical_cores": 8
    },
    "memory": {
      "total_bytes": 16777216000,
      "available_bytes": 8000000000,
      "used_bytes": 7777216000,
      "percent": 48.2
    },
    "system": {
      "load_1m": 0.12,
      "load_5m": 0.18,
      "load_15m": 0.20
    }
  }
}
```

## Endpoints

### Vérifier l'état de l'API

```http
GET /health
```

Réponse :

```json
{
  "status": "ok"
}
```

### Envoyer des métriques

```http
POST /metrics
```

### Récupérer la dernière métrique

```http
GET /metrics/latest
```

## Tests

Exécuter toute la suite :

```bash
pytest -q
```

Exécuter avec une couverture de code nécessite l'installation de
`pytest-cov` :

```bash
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

## Robustesse

Le projet gère notamment :

- les erreurs d'exécution de `subprocess` ;
- les timeouts ;
- les erreurs de connexion HTTP ;
- les réponses HTTP en erreur ;
- les configurations invalides ;
- les payloads incomplets ;
- l'absence de métriques dans l'API.

## Démonstration du flux

```text
┌──────────────────┐
│ Système          │
│ CPU / RAM        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ collector.py     │
│ psutil           │
│ subprocess       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ formatter.py     │
│ Payload JSON     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ sender.py        │
│ HTTP POST        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ FastAPI          │
│ /metrics         │
└──────────────────┘
```
