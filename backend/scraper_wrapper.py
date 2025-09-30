"""
Wrapper pour le scraper HelloAsso
Version simplifiée qui réutilise les fonctions du scraper original
"""
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
import json
from urllib.parse import urljoin
import asyncio

# Liste de User-Agents pour rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

BASE_URL = "https://www.helloasso.com"
SEARCH_URL = "https://www.helloasso.com/e/recherche/associations"

class ScraperWrapper:
    """Wrapper qui réutilise la logique du scraper original"""

    def __init__(self, url: str, date_debut: Optional[str], date_fin: Optional[str], search_term: str, job_id: str, results_dir: str, max_results: int = 50, log_callback=None):
        self.url = url
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.search_term = search_term or self._extract_search_from_url(url)
        self.job_id = job_id
        self.results_dir = results_dir
        self.max_results = max_results
        self.log_callback = log_callback  # Callback pour envoyer les logs
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.consecutive_403_errors = 0
        self.MAX_CONSECUTIVE_403 = 5

        # Session avec cookies persistants
        self.session = requests.Session()
        self.session.cookies.set("consent", "true", domain=".helloasso.com")
        self.session.cookies.set("_ga", f"GA1.2.{random.randint(100000000, 999999999)}.{int(time.time())}", domain=".helloasso.com")
        self.session.cookies.set("_gid", f"GA1.2.{random.randint(100000000, 999999999)}.{int(time.time())}", domain=".helloasso.com")

    def log(self, message: str, level: str = "info"):
        """Log un message (console + callback)"""
        print(message)
        if self.log_callback:
            self.log_callback(message, level)

    def _extract_search_from_url(self, url: str) -> str:
        """Extrait le terme de recherche depuis l'URL"""
        if "query=" in url:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            return params.get('query', [''])[0] or params.get('q', [''])[0]
        return ""

    def generate_headers(self):
        """Génère des headers HTTP réalistes avec tous les détails d'un vrai navigateur"""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.helloasso.com/",
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": '"Chromium";v="123", "Not(A:Brand";v="8"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Cache-Control": "max-age=0",
        }

    def random_delay(self, min_seconds=3, max_seconds=7):
        """Délai aléatoire entre requêtes (plus longs pour éviter la détection)"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def make_request(self, url: str, params=None, retry_count=0):
        """Effectue une requête HTTP avec gestion des erreurs"""
        max_retries = 3

        try:
            headers = self.generate_headers()
            response = self.session.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 403:
                self.consecutive_403_errors += 1
                if self.consecutive_403_errors >= self.MAX_CONSECUTIVE_403:
                    self.log(f"⚠️  Trop d'erreurs 403. Pause de 60 secondes...", "warning")
                    time.sleep(60)
                    self.consecutive_403_errors = 0

                if retry_count < max_retries:
                    wait_time = (retry_count + 1) * 15
                    self.log(f"⚠️  Erreur 403. Nouvelle tentative dans {wait_time}s...", "warning")
                    time.sleep(wait_time)
                    return self.make_request(url, params, retry_count + 1)
                return None

            elif response.status_code == 429:
                if retry_count < max_retries:
                    wait_time = (retry_count + 1) * 30
                    self.log(f"⚠️  Rate limit. Attente de {wait_time}s...", "warning")
                    time.sleep(wait_time)
                    return self.make_request(url, params, retry_count + 1)
                return None

            elif response.status_code == 200:
                self.consecutive_403_errors = 0
                return response
            else:
                self.log(f"⚠️  Erreur HTTP {response.status_code}", "warning")
                return None

        except Exception as e:
            self.log(f"❌ Erreur requête: {e}", "error")
            if retry_count < max_retries:
                time.sleep(random.uniform(5, 10))
                return self.make_request(url, params, retry_count + 1)
            return None

    def get_all_association_links(self):
        """Récupère les liens d'associations depuis la recherche"""
        all_links = []
        page = 1
        consecutive_empty = 0
        max_empty = 3

        self.log(f"🔍 Recherche d'associations pour '{self.search_term}'...")

        while consecutive_empty < max_empty:
            self.log(f"📄 Page {page}...")

            params = {
                "query": self.search_term,
                "page": page
            }

            response = self.make_request(SEARCH_URL, params)
            if not response:
                consecutive_empty += 1
                page += 1
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            association_links = []

            # Méthode 1: Liens directs /associations/
            for a_tag in soup.find_all('a', href=True):
                href = a_tag.get('href', '')
                if href.startswith('/associations/') and not href.endswith('/paiement'):
                    full_url = urljoin(BASE_URL, href)
                    if full_url not in all_links and full_url not in association_links:
                        association_links.append(full_url)

            # Méthode 2: Cartes d'associations
            for card in soup.select('.association-card, .card, .result-item'):
                link_elem = card.find('a', href=True)
                if link_elem:
                    href = link_elem.get('href', '')
                    if '/associations/' in href:
                        full_url = urljoin(BASE_URL, href)
                        if full_url not in all_links and full_url not in association_links:
                            association_links.append(full_url)

            # Méthode 3: Extraction par regex
            if not association_links:
                url_pattern = r'href=["\']\/associations\/([^"\'\/]+)["\']'
                matches = re.findall(url_pattern, response.text)
                for match in matches:
                    if match and not match.endswith('paiement'):
                        full_url = f"{BASE_URL}/associations/{match}"
                        if full_url not in all_links and full_url not in association_links:
                            association_links.append(full_url)

            if association_links:
                all_links.extend(association_links)
                consecutive_empty = 0
                self.log(f"✅ {len(association_links)} associations trouvées")
            else:
                consecutive_empty += 1
                self.log(f"⚠️  Aucune association sur cette page", "warning")

            page += 1
            self.random_delay(2, 4)

        all_links = list(set(all_links))
        self.log(f"✅ Total: {len(all_links)} associations uniques")
        return all_links

    def extract_email(self, html_content: str):
        """Extrait l'email du HTML"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, html_content)

        unwanted = [r'\.png$', r'\.jpg$', r'example\.com$', r'test\.com$']
        for email in emails:
            if not any(re.search(p, email, re.IGNORECASE) for p in unwanted):
                return email
        return None

    def extract_phone(self, html_content: str):
        """Extrait le téléphone du HTML"""
        patterns = [
            r'\b0[1-9](?:[\s.-]?\d{2}){4}\b',
            r'\+33[\s.-]?[1-9](?:[\s.-]?\d{2}){4}\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_content)
            if match:
                return match.group(0)
        return None

    def parse_address(self, address_text: str):
        """Parse une adresse en composants"""
        if not address_text:
            return {"street_address": None, "postal_code": None, "city": None}

        postal_match = re.search(r'\b(\d{5})\b', address_text)
        postal_code = postal_match.group(1) if postal_match else None

        city = None
        street = address_text

        if postal_code:
            parts = address_text.split(postal_code, 1)
            if len(parts) > 1:
                city_part = parts[1].strip()
                if city_part.startswith(','):
                    city_part = city_part[1:].strip()

                words = city_part.split()
                city = ' '.join([w for w in words[:3] if w.lower() not in ['cedex', 'france']])

                if parts[0]:
                    street = parts[0].strip().rstrip(',')

        return {
            "street_address": street,
            "postal_code": postal_code,
            "city": city
        }

    def get_association_details(self, url: str):
        """Récupère les détails d'une association"""
        response = self.make_request(url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        html = response.text

        # Nom
        name = None
        h1 = soup.find('h1')
        if h1:
            name = h1.text.strip()
        if not name:
            name = url.split('/')[-1].replace('-', ' ').title()

        # Email et téléphone
        email = self.extract_email(html)
        phone = self.extract_phone(html)

        # Adresse
        address_text = None
        address_div = soup.select_one('div[itemprop="address"]')
        if address_div:
            address_text = address_div.text.strip()

        if not address_text:
            for elem in soup.find_all(['address', 'p', 'div']):
                text = elem.text.strip()
                if re.search(r'\b\d{5}\b', text) and len(text) < 100:
                    address_text = text
                    break

        address = self.parse_address(address_text)

        return {
            'name': name,
            'url': url,
            'street_address': address['street_address'],
            'postal_code': address['postal_code'],
            'city': address['city'],
            'email': email or "Non dispo",
            'phone': phone or "Non dispo",
        }

    async def run(self) -> List[str]:
        """Exécute le scraping"""
        self.log(f"🚀 Démarrage du scraping pour: {self.url}")
        self.log(f"🔍 Terme de recherche: {self.search_term}")
        self.log(f"📊 Maximum: {self.max_results} associations")

        results = await asyncio.to_thread(self._run_sync)
        return results

    def _run_sync(self) -> List[str]:
        """Scraping synchrone"""
        results = []

        try:
            # Récupérer les liens
            if "recherche" in self.url or "search" in self.url:
                all_links = self.get_all_association_links()

                if len(all_links) > self.max_results:
                    self.log(f"⚠️  Limitation à {self.max_results} associations (sur {len(all_links)})", "warning")
                    all_links = all_links[:self.max_results]
            else:
                all_links = [self.url]

            # Scraper chaque association
            total = len(all_links)
            for idx, link in enumerate(all_links, 1):
                self.log(f"📊 {idx}/{total}: {link}")

                try:
                    details = self.get_association_details(link)
                    if details:
                        results.append(details)
                        self.log(f"✅ {details['name']}")

                    self.random_delay(2, 4)

                except Exception as e:
                    self.log(f"❌ Erreur: {e}", "error")
                    continue

        except Exception as e:
            self.log(f"❌ Erreur générale: {e}", "error")
            import traceback
            traceback.print_exc()

        # Sauvegarder
        result_files = []
        if results:
            self.log(f"💾 Sauvegarde de {len(results)} résultats...")

            csv_file = self._save_csv(results)
            if csv_file:
                result_files.append(csv_file)

            html_file = self._save_html(results)
            if html_file:
                result_files.append(html_file)

            self.log(f"✅ Scraping terminé!")
        else:
            self.log(f"⚠️  Aucun résultat", "warning")

        return result_files

    def _save_csv(self, results: List[dict]) -> Optional[str]:
        """Sauvegarde en CSV"""
        if not results:
            return None

        filename = f"associations_{self.search_term}_{self.job_id}_{self.timestamp}.csv"
        filepath = os.path.join(self.results_dir, filename)

        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

        self.log(f"✅ CSV: {filename}")
        return filename

    def _save_html(self, results: List[dict]) -> Optional[str]:
        """Sauvegarde en HTML"""
        if not results:
            return None

        filename = f"associations_{self.search_term}_{self.job_id}_{self.timestamp}.html"
        filepath = os.path.join(self.results_dir, filename)

        # Statistiques
        with_email = len([r for r in results if r.get('email') and r['email'] != 'Non dispo'])
        with_phone = len([r for r in results if r.get('phone') and r['phone'] != 'Non dispo'])
        cities = len(set(r.get('city') for r in results if r.get('city')))

        html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Résultats - {self.search_term}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px 40px;
            background: #f8f9fa;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .stat-card .number {{ font-size: 2.5em; color: #667eea; font-weight: bold; }}
        .stat-card .label {{ color: #666; margin-top: 10px; }}
        .table-container {{ padding: 40px; overflow-x: auto; }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
            position: sticky;
            top: 0;
        }}
        tr:hover {{ background: #f8f9fa; }}
        a {{ color: #667eea; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        footer {{
            background: #2c3e50;
            color: white;
            text-align: center;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 Résultats HelloAsso</h1>
            <p>Recherche: <strong>{self.search_term}</strong></p>
            <p>Date: {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
        </header>

        <div class="stats">
            <div class="stat-card">
                <div class="number">{len(results)}</div>
                <div class="label">Associations</div>
            </div>
            <div class="stat-card">
                <div class="number">{with_email}</div>
                <div class="label">Avec Email</div>
            </div>
            <div class="stat-card">
                <div class="number">{with_phone}</div>
                <div class="label">Avec Téléphone</div>
            </div>
            <div class="stat-card">
                <div class="number">{cities}</div>
                <div class="label">Villes</div>
            </div>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
"""

        # Headers
        for key in results[0].keys():
            html += f"<th>{key.replace('_', ' ').title()}</th>"

        html += """
                    </tr>
                </thead>
                <tbody>
"""

        # Rows
        for result in results:
            html += "<tr>"
            for key, value in result.items():
                if key == 'email' and value and value != 'Non dispo':
                    html += f'<td><a href="mailto:{value}">{value}</a></td>'
                elif key == 'phone' and value and value != 'Non dispo':
                    html += f'<td><a href="tel:{value}">{value}</a></td>'
                elif key == 'url':
                    html += f'<td><a href="{value}" target="_blank">{value}</a></td>'
                else:
                    html += f"<td>{value if value else '-'}</td>"
            html += "</tr>"

        html += f"""
                </tbody>
            </table>
        </div>

        <footer>
            <p>Généré par HelloAsso Scraper WebApp</p>
            <p>⚠️ Fichier temporaire - Téléchargez maintenant!</p>
        </footer>
    </div>
</body>
</html>
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        self.log(f"✅ HTML: {filename}")
        return filename