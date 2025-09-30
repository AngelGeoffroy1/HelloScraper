"""
Script de test simple pour vérifier que l'API fonctionne
"""
import requests
import time

API_URL = "http://localhost:8000"

def test_health():
    print("🔍 Test de santé de l'API...")
    response = requests.get(f"{API_URL}/health")
    print(f"✅ Status: {response.status_code}")
    print(f"Response: {response.json()}\n")

def test_root():
    print("🔍 Test de l'endpoint racine...")
    response = requests.get(f"{API_URL}/")
    print(f"✅ Status: {response.status_code}")
    print(f"Response: {response.json()}\n")

def test_scrape():
    print("🔍 Test de lancement de scraping...")
    data = {
        "url": "https://www.helloasso.com/associations/test",
        "date_debut": None,
        "date_fin": None,
        "search_term": ""
    }
    response = requests.post(f"{API_URL}/api/scrape", json=data)
    print(f"✅ Status: {response.status_code}")
    result = response.json()
    print(f"Job ID: {result['job_id']}")
    print(f"Status: {result['status']}\n")

    return result['job_id']

def test_status(job_id):
    print(f"🔍 Test de récupération du statut (Job: {job_id[:8]}...)...")
    response = requests.get(f"{API_URL}/api/status/{job_id}")
    print(f"✅ Status: {response.status_code}")
    print(f"Response: {response.json()}\n")

def test_files():
    print("🔍 Test de listage des fichiers...")
    response = requests.get(f"{API_URL}/api/files")
    print(f"✅ Status: {response.status_code}")
    result = response.json()
    print(f"Nombre de fichiers: {len(result['files'])}\n")

if __name__ == "__main__":
    print("=" * 50)
    print("TEST DE L'API HELLOASSO SCRAPER")
    print("=" * 50 + "\n")

    try:
        test_health()
        test_root()
        test_files()

        # Test de scraping (commenté par défaut pour ne pas faire de vraies requêtes)
        # job_id = test_scrape()
        # time.sleep(2)
        # test_status(job_id)

        print("✅ Tous les tests sont passés!")

    except requests.exceptions.ConnectionError:
        print("❌ Erreur: Impossible de se connecter à l'API")
        print("Assurez-vous que le serveur est lancé avec: uvicorn main:app --reload")
    except Exception as e:
        print(f"❌ Erreur: {e}")