# Guide de déploiement - HelloAsso Scraper

Ce guide vous explique comment déployer l'application HelloAsso Scraper avec le frontend sur Netlify et le backend sur Render.

## Architecture

- **Frontend**: Next.js sur Netlify
- **Backend**: FastAPI sur Render
- **Stockage**: Fichiers locaux sur le disque Render

## Prérequis

- Un compte [Netlify](https://www.netlify.com/) (gratuit)
- Un compte [Render](https://render.com/) (gratuit)
- Un repository Git (GitHub, GitLab, ou Bitbucket)

---

## 1. Préparation du code

### Pousser le code sur Git

```bash
# Si pas encore initialisé
cd /path/to/HelloScraperWebApp
git init
git add .
git commit -m "Initial commit: HelloAsso Scraper webapp"

# Créer un repo sur GitHub et pousser
git remote add origin https://github.com/votre-username/helloasso-scraper.git
git branch -M main
git push -u origin main
```

---

## 2. Déploiement du Backend sur Render

### Étape 1: Créer un nouveau Web Service

1. Connectez-vous à [Render](https://dashboard.render.com/)
2. Cliquez sur **"New +"** → **"Web Service"**
3. Connectez votre repository Git
4. Sélectionnez le repository contenant votre code

### Étape 2: Configuration du service

**Build & Deploy:**
- **Name**: `helloasso-scraper-api` (ou autre nom de votre choix)
- **Region**: Choisissez la région la plus proche (ex: Frankfurt pour l'Europe)
- **Branch**: `main`
- **Root Directory**: `backend`
- **Runtime**: `Python 3`
- **Build Command**:
  ```
  pip install -r requirements.txt
  ```
- **Start Command**:
  ```
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```

**Instance Type:**
- Sélectionnez **Free** (suffisant pour commencer)

### Étape 3: Configuration du disque persistant (Important!)

Pour conserver les fichiers de résultats entre les redémarrages:

1. Dans les paramètres du service, allez dans **"Disks"**
2. Cliquez sur **"Add Disk"**
3. Configurez:
   - **Name**: `scraper-results`
   - **Mount Path**: `/opt/render/project/src/results`
   - **Size**: `1 GB` (gratuit)
4. Cliquez sur **"Save"**

### Étape 4: Variables d'environnement (optionnel)

Vous pouvez ajouter des variables d'environnement si nécessaire:
- Allez dans **"Environment"**
- Ajoutez vos variables (aucune n'est requise pour l'instant)

### Étape 5: Déployer

1. Cliquez sur **"Create Web Service"**
2. Render va automatiquement:
   - Cloner votre repository
   - Installer les dépendances
   - Démarrer votre API
3. Attendez que le déploiement soit terminé (statut "Live")
4. **Notez l'URL de votre API** (ex: `https://helloasso-scraper-api.onrender.com`)

### Vérification

Testez votre API en visitant:
```
https://votre-app.onrender.com/
```

Vous devriez voir:
```json
{
  "message": "HelloAsso Scraper API",
  "version": "1.0.0",
  ...
}
```

---

## 3. Déploiement du Frontend sur Netlify

### Étape 1: Configurer la variable d'environnement

Avant de déployer, vous devez créer un fichier de configuration pour l'URL de l'API:

1. Dans le dossier `frontend`, éditez le fichier `.env.local`
2. **Important**: Ce fichier ne doit PAS être commité dans Git

### Étape 2: Créer un nouveau site sur Netlify

1. Connectez-vous à [Netlify](https://app.netlify.com/)
2. Cliquez sur **"Add new site"** → **"Import an existing project"**
3. Choisissez votre provider Git (GitHub, GitLab, etc.)
4. Sélectionnez votre repository

### Étape 3: Configuration du build

**Site settings:**
- **Base directory**: `frontend`
- **Build command**: `npm run build`
- **Publish directory**: `frontend/.next`

**Build settings:**
- Framework: `Next.js`

### Étape 4: Variables d'environnement

⚠️ **TRÈS IMPORTANT** - Configurez la variable d'environnement:

1. Avant de déployer, allez dans **"Site configuration"** → **"Environment variables"**
2. Cliquez sur **"Add a variable"**
3. Ajoutez:
   - **Key**: `NEXT_PUBLIC_API_URL`
   - **Value**: `https://votre-app.onrender.com` (l'URL de votre API Render)
   - **Scopes**: Cochez "All scopes"
4. Cliquez sur **"Create variable"**

### Étape 5: Déployer

1. Cliquez sur **"Deploy site"**
2. Netlify va automatiquement:
   - Installer les dépendances npm
   - Builder l'application Next.js
   - Déployer le site
3. Attendez la fin du déploiement
4. **Notez l'URL de votre site** (ex: `https://random-name-123.netlify.app`)

### Étape 6: Configurer un domaine personnalisé (optionnel)

1. Dans Netlify, allez dans **"Domain management"**
2. Cliquez sur **"Add custom domain"**
3. Suivez les instructions pour configurer votre DNS

---

## 4. Configuration finale

### Mettre à jour le CORS sur le backend

Si vous avez des problèmes de CORS, vous devrez peut-être mettre à jour le backend:

1. Ouvrez `backend/main.py`
2. Modifiez la configuration CORS:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://votre-site.netlify.app",  # Votre URL Netlify
        "http://localhost:3000"            # Pour le développement local
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

3. Committez et poussez:
```bash
git add backend/main.py
git commit -m "Update CORS configuration"
git push
```

4. Render redéploiera automatiquement

---

## 5. Tester l'application

1. Visitez votre site Netlify
2. Entrez une URL HelloAsso dans le formulaire (ex: `https://www.helloasso.com/associations/...`)
3. Cliquez sur "Lancer le scraping"
4. Vérifiez que le statut se met à jour
5. Téléchargez les fichiers générés

---

## 6. Développement local

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

L'API sera disponible sur `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Le site sera disponible sur `http://localhost:3000`

---

## 7. Surveillance et logs

### Render (Backend)
- Allez dans votre service sur Render
- Cliquez sur **"Logs"** pour voir les logs en temps réel
- Utilisez **"Events"** pour voir l'historique des déploiements

### Netlify (Frontend)
- Allez dans votre site sur Netlify
- Cliquez sur **"Deploys"** pour voir l'historique
- Utilisez **"Functions"** pour voir les logs des fonctions (si applicable)

---

## 8. Limitations du plan gratuit

### Render (Free Tier)
- ⚠️ Le service s'endort après 15 minutes d'inactivité
- Premier appel après inactivité: ~30-60 secondes de délai (cold start)
- 750 heures/mois d'utilisation
- Disque persistant: 1 GB gratuit

### Netlify (Free Tier)
- 100 GB de bande passante/mois
- 300 minutes de build/mois
- Pas de limite de sites

---

## 9. Résolution de problèmes

### Le backend ne répond pas
- Vérifiez les logs sur Render
- Le service est peut-être en veille (attendez 30-60 secondes)
- Vérifiez que le port est bien configuré (`$PORT` dans Render)

### Erreur CORS
- Vérifiez que `NEXT_PUBLIC_API_URL` est bien configuré dans Netlify
- Vérifiez la configuration CORS dans `backend/main.py`

### Les fichiers disparaissent
- Vérifiez que le disque persistant est bien monté sur Render
- Path: `/opt/render/project/src/results`

### Le frontend ne se connecte pas au backend
- Vérifiez que la variable `NEXT_PUBLIC_API_URL` est bien définie dans Netlify
- Ouvrez la console du navigateur pour voir les erreurs
- Vérifiez que l'URL de l'API est correcte (sans `/` à la fin)

---

## 10. Mises à jour

### Déployer une nouvelle version

```bash
# Faire vos modifications
git add .
git commit -m "Description des changements"
git push
```

- **Render**: Redéploie automatiquement le backend
- **Netlify**: Redéploie automatiquement le frontend

### Forcer un redéploiement

**Render:**
- Allez dans le service
- Cliquez sur **"Manual Deploy"** → **"Deploy latest commit"**

**Netlify:**
- Allez dans **"Deploys"**
- Cliquez sur **"Trigger deploy"** → **"Deploy site"**

---

## Support

Pour toute question:
- Documentation Render: https://render.com/docs
- Documentation Netlify: https://docs.netlify.com
- Documentation Next.js: https://nextjs.org/docs
- Documentation FastAPI: https://fastapi.tiangolo.com