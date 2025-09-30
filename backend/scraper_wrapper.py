"""
Wrapper pour le scraper HelloAsso
Adapte le scraper existant pour fonctionner de manière asynchrone avec FastAPI
"""
import asyncio
import os
import sys
import datetime
from typing import Optional, List
import requests
from bs4 import BeautifulSoup
import time
import random
import csv
import re
from urllib.parse import urljoin

# Liste de User-Agents pour rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
]

class ScraperWrapper:
    def __init__(self, url: str, date_debut: Optional[str], date_fin: Optional[str], search_term: str, job_id: str, results_dir: str):
        self.url = url
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.search_term = search_term
        self.job_id = job_id
        self.results_dir = results_dir
        self.results = []
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.consecutive_403_errors = 0
        self.MAX_CONSECUTIVE_403 = 5

    def generate_headers(self):
        """Génère des headers HTTP aléatoires"""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

    def random_delay(self, min_factor=1.0, max_factor=1.0, is_error=False):
        """Ajoute un délai aléatoire entre les requêtes"""
        if is_error:
            base_delay = random.uniform(10, 20)
        else:
            base_delay = random.uniform(2, 5)

        delay = base_delay * random.uniform(min_factor, max_factor)
        time.sleep(delay)

    def make_request(self, url: str, params=None, retry_count=0):
        """Effectue une requête HTTP avec gestion des erreurs"""
        max_retries = 3

        try:
            headers = self.generate_headers()
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 403:
                self.consecutive_403_errors += 1
                if self.consecutive_403_errors >= self.MAX_CONSECUTIVE_403:
                    print(f"⚠️  Trop d'erreurs 403 consécutives. Pause longue de 60 secondes...")
                    time.sleep(60)
                    self.consecutive_403_errors = 0

                if retry_count < max_retries:
                    wait_time = (retry_count + 1) * 15
                    print(f"⚠️  Erreur 403. Nouvelle tentative dans {wait_time}s...")
                    time.sleep(wait_time)
                    return self.make_request(url, params, retry_count + 1)
                else:
                    return None

            elif response.status_code == 429:
                if retry_count < max_retries:
                    wait_time = (retry_count + 1) * 30
                    print(f"⚠️  Rate limit atteint. Attente de {wait_time}s...")
                    time.sleep(wait_time)
                    return self.make_request(url, params, retry_count + 1)
                else:
                    return None

            elif response.status_code == 200:
                self.consecutive_403_errors = 0
                return response

            else:
                print(f"⚠️  Erreur HTTP {response.status_code} pour {url}")
                return None

        except Exception as e:
            print(f"❌ Erreur lors de la requête: {e}")
            if retry_count < max_retries:
                self.random_delay(is_error=True)
                return self.make_request(url, params, retry_count + 1)
            return None

    def extract_email_from_html(self, html_content: str) -> Optional[str]:
        """Extrait l'email du contenu HTML"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, html_content)

        unwanted_patterns = [
            r'\.png$', r'\.jpg$', r'\.jpeg$', r'\.gif$', r'\.webp$',
            r'example\.com$', r'test\.com$', r'localhost'
        ]

        for email in emails:
            if not any(re.search(pattern, email, re.IGNORECASE) for pattern in unwanted_patterns):
                return email

        return None

    def extract_phone_from_html(self, html_content: str) -> Optional[str]:
        """Extrait le numéro de téléphone du contenu HTML"""
        phone_patterns = [
            r'\b0[1-9](?:[\s.-]?\d{2}){4}\b',
            r'\+33[\s.-]?[1-9](?:[\s.-]?\d{2}){4}\b',
            r'\b(?:01|02|03|04|05|06|07|08|09)(?:[\s.-]?\d{2}){4}\b'
        ]

        for pattern in phone_patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(0)

        return None

    def get_association_details(self, url: str) -> dict:
        """Récupère les détails d'une association"""
        print(f"🔍 Scraping: {url}")

        response = self.make_request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extraction basique des informations
        name = soup.find('h1')
        name = name.text.strip() if name else "N/A"

        description = soup.find('meta', {'name': 'description'})
        description = description.get('content', '').strip() if description else "N/A"

        email = self.extract_email_from_html(response.text)
        phone = self.extract_phone_from_html(response.text)

        return {
            'nom': name,
            'description': description,
            'email': email or "Non trouvé",
            'telephone': phone or "Non trouvé",
            'url': url,
            'date_scraping': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def save_results_to_csv(self, results: List[dict]) -> str:
        """Sauvegarde les résultats dans un fichier CSV"""
        if not results:
            return None

        filename = f"helloasso_results_{self.job_id}_{self.timestamp}.csv"
        filepath = os.path.join(self.results_dir, filename)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            if results:
                writer = csv.DictWriter(f, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)

        print(f"✅ Résultats sauvegardés: {filepath}")
        return filename

    def save_results_to_html(self, results: List[dict]) -> str:
        """Sauvegarde les résultats dans un fichier HTML"""
        if not results:
            return None

        filename = f"helloasso_results_{self.job_id}_{self.timestamp}.html"
        filepath = os.path.join(self.results_dir, filename)

        html_content = """
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Résultats HelloAsso Scraper</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
                th { background-color: #4CAF50; color: white; }
                tr:nth-child(even) { background-color: #f2f2f2; }
                h1 { color: #333; }
            </style>
        </head>
        <body>
            <h1>Résultats du Scraping HelloAsso</h1>
            <p>Nombre total de résultats: """ + str(len(results)) + """</p>
            <table>
                <thead>
                    <tr>
        """

        # Headers
        if results:
            for key in results[0].keys():
                html_content += f"<th>{key}</th>"

        html_content += """
                    </tr>
                </thead>
                <tbody>
        """

        # Data rows
        for result in results:
            html_content += "<tr>"
            for value in result.values():
                html_content += f"<td>{value}</td>"
            html_content += "</tr>"

        html_content += """
                </tbody>
            </table>
        </body>
        </html>
        """

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"✅ Résultats HTML sauvegardés: {filepath}")
        return filename

    async def run(self) -> List[str]:
        """Exécute le scraping de manière asynchrone"""
        print(f"🚀 Démarrage du scraping pour: {self.url}")
        print(f"📅 Période: {self.date_debut or 'non spécifiée'} - {self.date_fin or 'non spécifiée'}")
        print(f"🔍 Terme de recherche: {self.search_term or 'aucun'}")

        # Pour l'instant, on scrappe juste l'URL fournie
        # Dans une version plus complète, on pourrait implémenter la logique complète du scraper

        result = await asyncio.to_thread(self.get_association_details, self.url)

        if result:
            self.results.append(result)

        # Sauvegarder les résultats
        result_files = []

        csv_file = self.save_results_to_csv(self.results)
        if csv_file:
            result_files.append(csv_file)

        html_file = self.save_results_to_html(self.results)
        if html_file:
            result_files.append(html_file)

        print(f"✅ Scraping terminé. {len(self.results)} résultat(s) trouvé(s)")

        return result_files