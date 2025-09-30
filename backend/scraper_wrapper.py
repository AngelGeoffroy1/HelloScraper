"""
Wrapper pour le scraper HelloAsso
Utilise la logique complète du scraper original de manière asynchrone
"""
import asyncio
import os
import sys
import datetime
from typing import Optional, List
import logging

# Importer le scraper original en adaptant son code
# On va copier et adapter les fonctions principales
import importlib.util
spec = importlib.util.spec_from_file_location("scraper_core", "scraper_core.py")
scraper_module = importlib.util.module_from_spec(spec)

class ScraperWrapper:
    """Wrapper qui utilise le scraper original de manière asynchrone"""

    def __init__(self, url: str, date_debut: Optional[str], date_fin: Optional[str], search_term: str, job_id: str, results_dir: str, max_results: int = 50):
        self.url = url
        self.date_debut = date_debut
        self.date_fin = date_fin
        self.search_term = search_term or self._extract_search_from_url(url)
        self.job_id = job_id
        self.results_dir = results_dir
        self.max_results = max_results  # Nombre max d'associations à scraper
        self.timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # Setup logging
        self.logger = logging.getLogger(f"scraper_{job_id}")
        self.logger.setLevel(logging.INFO)

    def _extract_search_from_url(self, url: str) -> str:
        """Extrait le terme de recherche depuis l'URL"""
        if "query=" in url:
            import urllib.parse
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            return params.get('query', [''])[0] or params.get('q', [''])[0]
        return ""

    async def run(self) -> List[str]:
        """Exécute le scraping de manière asynchrone"""
        print(f"🚀 Démarrage du scraping pour: {self.url}")
        print(f"📅 Période: {self.date_debut or 'non spécifiée'} - {self.date_fin or 'non spécifiée'}")
        print(f"🔍 Terme de recherche: {self.search_term}")

        # Exécuter le scraping dans un thread séparé pour ne pas bloquer FastAPI
        result_files = await asyncio.to_thread(self._run_scraping_sync)

        return result_files

    def _run_scraping_sync(self) -> List[str]:
        """Exécute le scraping de manière synchrone (appelé dans un thread)"""
        # Charger le scraper original
        spec = importlib.util.spec_from_file_location("scraper_core", "scraper_core.py")
        scraper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scraper)

        # Configurer le scraper
        results = []
        all_links = []

        try:
            # Si c'est une URL de recherche, récupérer tous les liens
            if "recherche" in self.url or "search" in self.url:
                print("🔍 Récupération des liens d'associations...")

                # Utiliser la fonction get_all_association_links du scraper original
                # mais en la modifiant pour utiliser notre search_term
                scraper.search_term = self.search_term
                all_links = scraper.get_all_association_links()

                print(f"✅ {len(all_links)} associations trouvées")

                # Limiter au nombre max configuré
                if len(all_links) > self.max_results:
                    print(f"⚠️  Limitation à {self.max_results} associations (sur {len(all_links)} trouvées)")
                    all_links = all_links[:self.max_results]

            else:
                # Si c'est une URL directe d'association
                all_links = [self.url]

            # Scraper chaque association
            total = len(all_links)
            for idx, link in enumerate(all_links, 1):
                print(f"📊 Progression: {idx}/{total}")

                try:
                    details = scraper.get_association_details(link)
                    if details:
                        results.append(details)
                        print(f"✅ {details.get('name', 'Association')} - {link}")

                    # Petit délai entre chaque scraping
                    import time
                    import random
                    time.sleep(random.uniform(2, 4))

                except Exception as e:
                    print(f"❌ Erreur pour {link}: {e}")
                    continue

                # Sauvegarder tous les 10 résultats
                if len(results) % 10 == 0 and len(results) > 0:
                    print(f"💾 Sauvegarde intermédiaire ({len(results)} résultats)...")
                    self._save_intermediate_results(results.copy())

        except Exception as e:
            print(f"❌ Erreur générale: {e}")
            import traceback
            traceback.print_exc()

        # Sauvegarder les résultats finaux
        result_files = []

        if results:
            print(f"💾 Sauvegarde finale de {len(results)} résultats...")

            csv_file = self._save_to_csv(results)
            if csv_file:
                result_files.append(csv_file)

            html_file = self._save_to_html(results)
            if html_file:
                result_files.append(html_file)

            print(f"✅ Scraping terminé avec succès!")
        else:
            print(f"⚠️  Aucun résultat trouvé")

        return result_files

    def _save_intermediate_results(self, results: List[dict]):
        """Sauvegarde intermédiaire des résultats"""
        try:
            filename = f"temp_results_{self.job_id}.csv"
            filepath = os.path.join(self.results_dir, filename)

            import csv
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                if results:
                    writer = csv.DictWriter(f, fieldnames=results[0].keys())
                    writer.writeheader()
                    writer.writerows(results)
        except Exception as e:
            print(f"⚠️  Erreur sauvegarde intermédiaire: {e}")

    def _save_to_csv(self, results: List[dict]) -> Optional[str]:
        """Sauvegarde les résultats en CSV"""
        if not results:
            return None

        filename = f"associations_{self.search_term}_{self.job_id}_{self.timestamp}.csv"
        filepath = os.path.join(self.results_dir, filename)

        import csv
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

        print(f"✅ CSV: {filename}")
        return filename

    def _save_to_html(self, results: List[dict]) -> Optional[str]:
        """Sauvegarde les résultats en HTML"""
        if not results:
            return None

        filename = f"associations_{self.search_term}_{self.job_id}_{self.timestamp}.html"
        filepath = os.path.join(self.results_dir, filename)

        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Résultats Scraping HelloAsso - {self.search_term}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
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
        header p {{ font-size: 1.2em; opacity: 0.9; }}
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
        .table-container {{
            padding: 40px;
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
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
        .email, .phone {{
            color: #667eea;
            text-decoration: none;
        }}
        .email:hover, .phone:hover {{ text-decoration: underline; }}
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
            <h1>🎯 Résultats Scraping HelloAsso</h1>
            <p>Terme de recherche: <strong>{self.search_term}</strong></p>
            <p>Date: {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
        </header>

        <div class="stats">
            <div class="stat-card">
                <div class="number">{len(results)}</div>
                <div class="label">Associations</div>
            </div>
            <div class="stat-card">
                <div class="number">{len([r for r in results if r.get('email') and r.get('email') != 'Non dispo'])}</div>
                <div class="label">Avec Email</div>
            </div>
            <div class="stat-card">
                <div class="number">{len([r for r in results if r.get('phone') and r.get('phone') != 'Non dispo'])}</div>
                <div class="label">Avec Téléphone</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(set(r.get('city') for r in results if r.get('city')))}</div>
                <div class="label">Villes</div>
            </div>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
"""

        # Headers
        if results:
            for key in results[0].keys():
                html_content += f"<th>{key.replace('_', ' ').title()}</th>"

        html_content += """
                    </tr>
                </thead>
                <tbody>
"""

        # Rows
        for result in results:
            html_content += "<tr>"
            for key, value in result.items():
                if key == 'email' and value and value != 'Non dispo':
                    html_content += f'<td><a href="mailto:{value}" class="email">{value}</a></td>'
                elif key == 'phone' and value and value != 'Non dispo':
                    html_content += f'<td><a href="tel:{value}" class="phone">{value}</a></td>'
                elif key == 'url':
                    html_content += f'<td><a href="{value}" target="_blank" class="email">{value}</a></td>'
                else:
                    html_content += f"<td>{value if value else '-'}</td>"
            html_content += "</tr>"

        html_content += """
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
            f.write(html_content)

        print(f"✅ HTML: {filename}")
        return filename