# Pipeline Apple Santé pour agent IA

Ce dépôt propose une petite architecture auto-hébergée qui transforme des exports Apple Santé en une base SQLite normalisée, puis les rend consultables par un agent IA au moyen d'outils strictement contrôlés et en lecture seule.

Le dépôt est volontairement généraliste : aucun chemin personnel, aucune adresse IP, aucun jeton, aucune donnée de santé et aucune configuration propre à un assistant n'y figurent.

> Projet expérimental de données personnelles. Ce n'est ni un dispositif médical, ni un système de diagnostic ou d'alerte d'urgence.

## Principe

```text
Apple Santé
    ↓
application d'export sur l'iPhone
    ↓
transport privé et authentifié
    ↓
récepteur
    ↓
JSON brut + déduplication
    ↓
normalisateur
    ↓
base SQLite santé
    ↓
API en lecture seule ou adaptateur MCP
    ↓
agent spécialisé santé
    ↓
assistant personnel principal
```

La séparation importante est la suivante :

- le code réalise les calculs reproductibles ;
- un agent spécialisé interprète les résultats ;
- l'assistant principal les replace dans le contexte général de l'utilisateur.

Le modèle de langage ne reçoit jamais un accès SQL libre et ne calcule pas les statistiques à partir d'échantillons bruts dans son contexte.

## Contenu du dépôt

- récepteur HTTP authentifié ;
- déduplication des payloads par SHA-256 ;
- normalisation asynchrone dans un service séparé ;
- stockage SQLite des données brutes, mesures, agrégats, épisodes de sommeil et entraînements ;
- règles adaptées aux métriques cumulatives, physiologiques et corporelles ;
- petite API en lecture seule, facile à envelopper dans un MCP ;
- configuration Docker Compose ;
- exemples, tests, scripts d'inspection et de sauvegarde.

## Démarrage rapide

```bash
cp .env.example .env
python3 scripts/generate_token.py
```

Reporter les jetons générés dans `.env`, puis lancer :

```bash
docker compose up -d --build
```

Tester le récepteur :

```bash
curl http://127.0.0.1:8765/healthz
```

Tester l'API en lecture seule :

```bash
curl -H "Authorization: Bearer VOTRE_JETON_LECTURE" \
  "http://127.0.0.1:8770/daily?date=2026-01-01"
```

## Configuration de l'exporteur

Configurer l'application iPhone pour envoyer ses JSON en POST vers :

```text
http://ADRESSE_PRIVEE_DU_SERVEUR:8765/health
```

Ajouter l'en-tête :

```text
X-Health-Token: <HEALTH_INGEST_TOKEN>
```

Il est conseillé de séparer logiquement : le sommeil, les métriques générales et les entraînements. Utiliser le mode incrémental lorsque l'application le permet. Un historique complet doit être importé dans une base de staging, dédupliqué, puis fusionné proprement.

## Accès de l'agent

L'API fournie n'accepte pas de SQL arbitraire. Elle expose seulement des requêtes bornées : bilan quotidien, tendance d'une métrique, historique du sommeil, entraînements récents et complétude des données.

Un adaptateur MCP pourra ensuite proposer des outils tels que `get_daily_summary`, `get_metric_trend`, `get_sleep_history`, `get_workouts` et `check_data_completeness`.

## Vie privée

Les données de santé sont particulièrement sensibles : ne jamais versionner `.env` ni les bases SQLite, utiliser un réseau privé ou un proxy HTTPS authentifié, chiffrer les sauvegardes, limiter les permissions du système de fichiers et donner aux agents uniquement des outils en lecture seule.

La documentation principale et les commentaires techniques sont en anglais afin de faciliter le partage public.
