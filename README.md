# Calculateur d'empreinte carbone d'equipements IT

Application web qui estime l'empreinte carbone (CO2e) d'un equipement informatique a partir d'une base de donnees issue de Boavizta.

## Objectif du projet

- Permettre a un utilisateur de rechercher une machine (ex: "Latitude 7410").
- Recuperer la fiche correspondante depuis l'API backend.
- Afficher une valeur `co2_kg` exploitable rapidement, avec des details techniques.

## Architecture (vue simple)

- `frontend/` : application Angular (interface utilisateur).
- `backend/` : API Flask (recherche en base, normalisation JSON).
- `database/` : script SQL d'initialisation + fichiers CSV de reference.
- `docker-compose.yml` : compose historique (voir section jury : preferer `docker-compose.dev.yml` pour une demo locale fiable).
- `docker-compose.dev.yml` : **demo locale** (Angular en dev + backend + Postgres).
- `docker-compose.prod.yml` : deploiement avec images Nginx + registry.
- `Hackathon-Scripts/` et `Presentation_Groupe4.pdf` : **livrables demandes par le jury** (conserver dans le depot).

Flux principal :
1. L'utilisateur saisit un modele dans le frontend.
2. Le frontend appelle `POST /calculate` sur le backend.
3. Le backend interroge PostgreSQL et renvoie la meilleure correspondance.
4. Le frontend affiche la fiche et la valeur CO2.

## Prerequis

- Docker Desktop (ou Docker Engine + Compose)
- Port `4200` libre (frontend)
- Port `5000` libre (backend)
- Port `5432` libre (PostgreSQL)

## Demarrage pour le jury (a suivre en priorite)

Pour evaluer l'application **sans ambiguite**, utiliser le compose **dev** dedie :

```bash
docker compose -f docker-compose.dev.yml up --build
```

Puis ouvrir [http://localhost:4200](http://localhost:4200) (frontend) et verifier l'API sur [http://localhost:5000/calculate](http://localhost:5000/calculate) (POST JSON).

**Pourquoi pas `docker compose up` seul ?**  
Le fichier `docker-compose.yml` lance `ng serve` sur une image construite a partir du `frontend/Dockerfile` dont l'image finale est **Nginx** (sans Node). Ce chemin peut echouer au demarrage du conteneur frontend. Le fichier `docker-compose.dev.yml` evite ce probleme.

**Deploiement type prod (VM, images sur Docker Hub)** :

Sur la machine virtuelle, une seule commande suffit en general : Compose telecharge automatiquement les images `backend` et `frontend` si elles ne sont pas encore presentes localement.

```bash
docker compose -f docker-compose.prod.yml up -d
```

Pour forcer le re-telechargement des dernieres versions (meme si une ancienne image est en cache) :

```bash
docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d
```

## Lancer le projet (autres chemins)

- Demo locale fiable : voir section **Demarrage pour le jury** ci-dessus.
- Le fichier `docker-compose.yml` seul est conserve pour compatibilite ; en cas de souci sur le service `frontend`, preferer `docker-compose.dev.yml`.

Exemple d'appel API :

```bash
curl -X POST http://localhost:5000/calculate \
  -H "Content-Type: application/json" \
  -d "{\"machine\":\"Latitude 7410\"}"
```

## Structure utile pour la relecture

- `backend/app.py`
  - Gestion pool PostgreSQL
  - Endpoint `POST /calculate`
  - Conversion des types SQL vers JSON
- `frontend/src/app/app.ts`
  - Types de reponse API
  - Normalisation des anciennes/nouvelles reponses
  - Gestion erreurs et affichage resultats
- `database/init.sql`
  - Creation schema/table + import des donnees

## Choix techniques (resume)

- **Flask + psycopg2** : API simple, lisible, rapide a prendre en main.
- **Angular standalone component** : frontend compact pour un POC/demo.
- **Docker Compose** : execution identique sur toutes les machines.
- **Pool de connexions DB** : meilleure robustesse qu'une connexion unique.

## Comment un evaluateur peut tester rapidement

1. Lancer `docker compose -f docker-compose.dev.yml up --build`.
2. Ouvrir `http://localhost:4200`.
3. Tester une recherche, par exemple :
   - `Latitude 7410`
   - `Monitor`
4. Verifier qu'une fiche est retournee avec `co2_kg` et des attributs detailes.
5. Tester un cas negatif (`zzzzzz`) pour verifier le message "machine not found".

## Limites connues

- Recherche par `ILIKE %motcle%` : pertinente pour une demo, mais pas un moteur de recherche avance.
- Donnees dependantes du jeu Boavizta importe (qualite/couverture variables).
- Pas encore de suite de tests automatisee complete (unitaire + integration).

## Pistes d'amelioration

- Ajouter tests backend (pytest) et frontend (Angular tests cibles).
- Ajouter pagination/fuzzy matching pour la recherche machine.
- Ajouter observabilite minimale (logs structures, endpoint health).
- Gerer l'authentification si exposition hors environnement local.

## Documentation du code

Les points critiques du code sont documentes directement dans :
- `backend/app.py` (fonctions de pool, serialisation, endpoint)
- `frontend/src/app/app.ts` (normalisation des reponses, logique UI/API)

L'objectif est qu'une personne qui n'a pas code le projet puisse :
- comprendre le flux en quelques minutes,
- localiser rapidement la logique metier,
- et faire evoluer l'application sans ambiguites.

## Git : push depuis Windows

Si Git affiche *dubious ownership* sur `C:/project`, ajouter une exception (une fois par machine) :

```bash
git config --global --add safe.directory C:/project
```

Ou corriger le proprietaire du dossier `.git` pour qu'il corresponde a ton utilisateur Windows.

## Ne pas versionner l'environnement Python local

Le dossier `.venv/` (racine) est ignore par `.gitignore` : ne pas le committer (trop lourd, specifique a chaque machine).  
Si `.venv` etait deja suivi par Git : `git rm -r --cached .venv` puis commit.
