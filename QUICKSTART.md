# 🚀 Guide de démarrage rapide

## Développement local en 5 minutes

### 1. Backend (Terminal 1)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

✅ API prête sur http://localhost:8000

### 2. Frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

✅ Application prête sur http://localhost:3000

### 3. Tester

- Ouvrez http://localhost:3000
- Entrez une URL HelloAsso
- Lancez le scraping!

---

## Déploiement en production

### Backend sur Render

1. Créez un compte sur [Render](https://render.com)
2. **New +** → **Web Service**
3. Connectez votre repo Git
4. Configuration:
   - Root Directory: `backend`
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Ajoutez un disque:
   - Mount Path: `/opt/render/project/src/results`
   - Size: 1 GB
6. **Create Web Service**
7. **Notez l'URL** (ex: `https://your-app.onrender.com`)

### Frontend sur Netlify

1. Créez un compte sur [Netlify](https://netlify.com)
2. **Add new site** → **Import project**
3. Connectez votre repo Git
4. Configuration:
   - Base directory: `frontend`
   - Build command: `npm run build`
   - Publish directory: `frontend/.next`
5. **Variables d'environnement** (IMPORTANT!):
   - Key: `NEXT_PUBLIC_API_URL`
   - Value: Votre URL Render (ex: `https://your-app.onrender.com`)
6. **Deploy site**

### ✅ C'est fait!

Votre application est en ligne!

⚠️ **Note**: Le service Render (plan gratuit) s'endort après 15 minutes d'inactivité. Le premier appel prendra 30-60 secondes.

---

## Problèmes courants

### ❌ "Failed to fetch" dans le frontend
→ Vérifiez que `NEXT_PUBLIC_API_URL` est bien configuré dans Netlify

### ❌ Erreur CORS
→ Mettez à jour `allow_origins` dans `backend/main.py` avec votre URL Netlify

### ❌ Les fichiers disparaissent
→ Vérifiez que le disque est bien monté dans Render (`/opt/render/project/src/results`)

---

Pour plus de détails, consultez [DEPLOYMENT.md](./DEPLOYMENT.md)