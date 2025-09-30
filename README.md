# HelloAsso Scraper WebApp

Application web pour scraper les données des associations sur HelloAsso.

## 🚀 Fonctionnalités

- ✅ Interface web moderne avec Next.js et shadcn/ui
- ✅ API REST avec FastAPI
- ✅ Scraping asynchrone des pages HelloAsso
- ✅ Export des résultats en CSV et HTML
- ✅ Suivi en temps réel du statut de scraping
- ✅ Gestion des fichiers de résultats
- ✅ Interface responsive

## 📋 Structure du projet

```
HelloScraperWebApp/
├── frontend/              # Application Next.js
│   ├── app/              # Pages Next.js (App Router)
│   ├── components/       # Composants React
│   ├── lib/              # Utilitaires
│   └── public/           # Assets statiques
├── backend/              # API FastAPI
│   ├── main.py          # Point d'entrée de l'API
│   ├── scraper_wrapper.py  # Wrapper du scraper
│   ├── scraper_core.py  # Scraper original
│   └── requirements.txt # Dépendances Python
└── DEPLOYMENT.md        # Guide de déploiement
```

## 🛠️ Technologies utilisées

### Frontend
- **Next.js 14** - Framework React avec App Router
- **TypeScript** - Typage statique
- **Tailwind CSS** - Styling
- **shadcn/ui** - Composants UI
- **lucide-react** - Icônes

### Backend
- **FastAPI** - Framework API Python
- **BeautifulSoup4** - Parsing HTML
- **Requests** - Requêtes HTTP
- **Uvicorn** - Serveur ASGI

## 📦 Installation locale

### Prérequis
- Node.js 18+ et npm
- Python 3.10+
- Git

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

L'API sera disponible sur http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Le site sera disponible sur http://localhost:3000

## 🌐 Déploiement

Consultez le fichier [DEPLOYMENT.md](./DEPLOYMENT.md) pour un guide complet de déploiement sur:
- **Frontend**: Netlify
- **Backend**: Render

## 🎯 Utilisation

1. Ouvrez l'application web
2. Entrez l'URL HelloAsso d'une association
3. (Optionnel) Spécifiez une période avec les dates de début et fin
4. (Optionnel) Ajoutez un terme de recherche
5. Cliquez sur "Lancer le scraping"
6. Suivez la progression en temps réel
7. Téléchargez les fichiers CSV ou HTML générés

## 📝 API Endpoints

### `POST /api/scrape`
Lance un nouveau job de scraping
```json
{
  "url": "https://www.helloasso.com/associations/...",
  "date_debut": "2024-01-01",
  "date_fin": "2024-12-31",
  "search_term": "sport"
}
```

### `GET /api/status/{job_id}`
Récupère le statut d'un job

### `GET /api/files`
Liste tous les fichiers de résultats

### `GET /api/download/{filename}`
Télécharge un fichier de résultat

### `DELETE /api/files/{filename}`
Supprime un fichier de résultat

## ⚠️ Limitations

- Le scraping respecte les délais entre les requêtes pour éviter le rate limiting
- Les fichiers sont stockés localement sur le serveur
- Le plan gratuit de Render met le service en veille après 15 min d'inactivité

## 🔒 Sécurité

- Validation des entrées utilisateur
- Protection contre les path traversal
- Headers HTTP randomisés
- Délais aléatoires entre les requêtes
- Pas d'authentification (à ajouter pour une utilisation en production)

## 📄 Licence

Ce projet est à usage personnel et éducatif.

## 🤝 Contribution

Les contributions sont les bienvenues! N'hésitez pas à ouvrir une issue ou une pull request.

## 📧 Contact

Pour toute question, contactez [votre email]