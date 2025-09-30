from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, List
import os
import json
import asyncio
import uuid
from datetime import datetime
import glob
from scraper_wrapper import ScraperWrapper

app = FastAPI(title="HelloAsso Scraper API")

# Configuration CORS pour permettre les requêtes depuis le frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, spécifier le domaine Netlify
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stockage en mémoire des jobs (en production, utiliser Redis ou une DB)
jobs: Dict[str, dict] = {}

# Dossier pour stocker les résultats
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

class ScrapeRequest(BaseModel):
    url: HttpUrl
    date_debut: Optional[str] = None
    date_fin: Optional[str] = None
    search_term: Optional[str] = ""
    max_results: Optional[int] = 50  # Nombre max d'associations à scraper

class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: Optional[str] = None
    result_files: Optional[List[str]] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None

@app.get("/")
async def root():
    return {
        "message": "HelloAsso Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/scrape": "Launch a new scraping job",
            "GET /api/status/{job_id}": "Get job status",
            "GET /api/files": "List all result files",
            "GET /api/download/{filename}": "Download a result file",
            "DELETE /api/files/{filename}": "Delete a result file"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

async def run_scraper(job_id: str, url: str, date_debut: Optional[str], date_fin: Optional[str], search_term: str, max_results: int):
    """Fonction qui exécute le scraper en arrière-plan"""
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["progress"] = "Initialisation du scraper..."

        # Créer une instance du wrapper de scraper
        scraper = ScraperWrapper(
            url=url,
            date_debut=date_debut,
            date_fin=date_fin,
            search_term=search_term,
            job_id=job_id,
            results_dir=RESULTS_DIR,
            max_results=max_results
        )

        # Exécuter le scraping
        result_files = await scraper.run()

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = "Scraping terminé avec succès"
        jobs[job_id]["result_files"] = result_files
        jobs[job_id]["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        print(f"Error in job {job_id}: {str(e)}")

@app.post("/api/scrape", response_model=JobResponse)
async def start_scraping(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Lance un nouveau job de scraping"""

    # Générer un ID unique pour le job
    job_id = str(uuid.uuid4())

    # Initialiser le job
    jobs[job_id] = {
        "status": "pending",
        "progress": "En attente de démarrage...",
        "created_at": datetime.now().isoformat(),
        "url": str(request.url),
        "date_debut": request.date_debut,
        "date_fin": request.date_fin,
        "search_term": request.search_term,
        "max_results": request.max_results
    }

    # Lancer le scraping en arrière-plan
    background_tasks.add_task(
        run_scraper,
        job_id,
        str(request.url),
        request.date_debut,
        request.date_fin,
        request.search_term or "",
        request.max_results or 50
    )

    return JobResponse(
        job_id=job_id,
        status="pending",
        message="Job de scraping créé avec succès"
    )

@app.get("/api/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Récupère le statut d'un job"""

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job non trouvé")

    job = jobs[job_id]

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        result_files=job.get("result_files"),
        error=job.get("error"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at")
    )

@app.get("/api/files")
async def list_files():
    """Liste tous les fichiers de résultats disponibles"""

    if not os.path.exists(RESULTS_DIR):
        return {"files": []}

    files = []
    for file_path in glob.glob(os.path.join(RESULTS_DIR, "*")):
        if os.path.isfile(file_path):
            stat = os.stat(file_path)
            files.append({
                "filename": os.path.basename(file_path),
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

    # Trier par date de modification (plus récent en premier)
    files.sort(key=lambda x: x["modified_at"], reverse=True)

    return {"files": files}

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """Télécharge un fichier de résultat"""

    # Sécurité: éviter les path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")

    file_path = os.path.join(RESULTS_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.delete("/api/files/{filename}")
async def delete_file(filename: str):
    """Supprime un fichier de résultat"""

    # Sécurité: éviter les path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")

    file_path = os.path.join(RESULTS_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier non trouvé")

    try:
        os.remove(file_path)
        return {"message": f"Fichier {filename} supprimé avec succès"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la suppression: {str(e)}")

@app.get("/api/jobs")
async def list_jobs():
    """Liste tous les jobs"""
    return {"jobs": jobs}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)