import requests
from bs4 import BeautifulSoup
import time
import random
import csv
import json
import os
import logging
import re
import signal
import sys
import datetime
import glob
from urllib.parse import urljoin
from dotenv import load_dotenv

# Variables globales pour gérer l'interruption
results = []  # Stocker les résultats pendant l'exécution
interrupted = False  # Drapeau pour signaler une interruption
search_term = ""  # Terme de recherche spécifié par l'utilisateur
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # Horodatage pour les fichiers
skip_urls = set()  # URLs à ignorer car déjà traitées dans un fichier existant

# Liste de User-Agents pour rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1"
]

# Compteur pour suivre les erreurs 403 consécutives
consecutive_403_errors = 0
MAX_CONSECUTIVE_403 = 5  # Seuil pour déclencher une pause longue

# Fonction pour gérer l'interruption (Ctrl+C ou kill)
def signal_handler(sig, frame):
    global interrupted, results
    print("\n\nInterruption détectée! Souhaitez-vous sauvegarder les données et arrêter? (O/n): ", end="")
    choice = input().strip().lower()
    if choice == "" or choice == "o":
        print("Sauvegarde des données et arrêt propre...")
        interrupted = True
        # Copier les résultats avant de les sauvegarder, car save_results() vide la liste
        results_to_analyze = results.copy()
        save_results()
        # Analyser les résultats copiés
        if results_to_analyze:
            analyze_results(results_to_analyze)
        else:
            print("Aucune nouvelle donnée à analyser depuis le dernier enregistrement.")
        sys.exit(0)
    else:
        print("Reprise du scraping...")

# Enregistrement des gestionnaires de signaux
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler) # kill

# Fonction utilitaire pour lister et choisir un fichier
def choose_file(directory, pattern="*", message="Choisissez un fichier"):
    """Permet à l'utilisateur de choisir un fichier parmi ceux correspondant au motif dans le répertoire."""
    # Vérifier si le répertoire existe
    if not os.path.exists(directory):
        print(f"Le répertoire {directory} n'existe pas.")
        return None
    
    # Chercher les fichiers
    files = glob.glob(os.path.join(directory, pattern))
    if not files:
        print(f"Aucun fichier correspondant au motif {pattern} trouvé dans {directory}.")
        return None
    
    # Trier par date de modification (le plus récent en premier)
    files.sort(key=os.path.getmtime, reverse=True)
    
    # Afficher les options
    print(f"\n{message}:")
    for i, file in enumerate(files):
        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file)).strftime("%d/%m/%Y %H:%M")
        print(f"{i+1}. {os.path.basename(file)} (modifié le {mod_time})")
    
    # Option pour ne pas choisir de fichier
    print("0. Aucun fichier / Nouveau fichier")
    
    # Demander à l'utilisateur de choisir
    choice = -1
    while choice < 0 or choice > len(files):
        try:
            choice = int(input(f"\nChoisissez un fichier (0-{len(files)}): "))
        except ValueError:
            print("Veuillez entrer un nombre valide.")
    
    # Retourner le fichier choisi ou None
    if choice == 0:
        return None
    else:
        return files[choice-1]

# Fonction pour charger les URLs déjà scrappées d'un fichier CSV existant
def load_skip_urls_from_csv(csv_file):
    """Charge les URLs des associations déjà scrappées depuis un fichier CSV existant."""
    skip_urls = set()
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if 'url' in row and row['url']:
                    skip_urls.add(row['url'])
        print(f"{len(skip_urls)} URLs chargées depuis {csv_file} (associations déjà scrappées).")
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier CSV {csv_file}: {e}")
    
    return skip_urls

# Fonction pour sauvegarder les résultats
def save_results():
    global results, search_term, timestamp, skip_urls
    if not results:
        print("Aucun résultat à sauvegarder.")
        return
    
    # Création du dossier de résultats si nécessaire
    os.makedirs('results', exist_ok=True)
    
    # Vérifier si nous continuons un fichier existant
    csv_file = None
    if hasattr(save_results, 'output_file') and save_results.output_file:
        csv_file = save_results.output_file
    else:
        # Créer un nom de fichier avec le terme de recherche et l'horodatage
        csv_file = f'results/associations_{search_term}_{timestamp}.csv'
        save_results.output_file = csv_file
    
    fieldnames = [
        'name', 'url', 'street_address', 'postal_code', 'city', 
        'email', 'phone', 'event_count', 'avg_event_price', 'association_type'
    ]
    
    # Si le fichier existe déjà et que nous ne l'avons pas encore ouvert, nous ajoutons des données
    file_exists = os.path.exists(csv_file)
    mode = 'a' if file_exists else 'w'
    
    with open(csv_file, mode, newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(results)
    
    # Ajouter les URLs traitées à skip_urls pour éviter les doublons
    for result in results:
        if 'url' in result and result['url']:
            skip_urls.add(result['url'])
            
    print(f"Données sauvegardées dans {csv_file} ({len(results)} nouvelles associations)")
    
    # Vider results après la sauvegarde pour éviter les doublons
    results.clear()

# Fonction pour charger les liens existants depuis un fichier spécifié
def load_existing_links(links_file=None):
    """Charge les liens depuis un fichier spécifié ou recherche un fichier correspondant au terme de recherche."""
    global search_term
    
    if not links_file:
        # Si aucun fichier n'est spécifié, permettre à l'utilisateur d'en choisir un
        links_file = choose_file('results', f"association_links_*.txt", 
                                "Choisissez un fichier de liens existant")
    
    if not links_file:
        logger.info("Aucun fichier de liens sélectionné.")
        return []
    
    with open(links_file, 'r', encoding='utf-8') as f:
        links = [line.strip() for line in f if line.strip()]
    
    if links:
        logger.info(f"Fichier {links_file} chargé avec {len(links)} liens")
        return links
    
    logger.info(f"Pas de liens trouvés dans le fichier {links_file}")
    return []

# Demander à l'utilisateur le terme de recherche
def get_search_term():
    while True:
        term = input("Entrez le terme de recherche (ex: bde, asso, club, etc.): ").strip()
        if term:
            return term
        print("Le terme de recherche ne peut pas être vide. Veuillez réessayer.")

# Fonction pour analyser une adresse et la séparer en composants
def parse_address(address_text):
    """
    Divise une adresse en ses composants: code postal, ville et reste de l'adresse
    Retourne un dictionnaire avec les clés: street_address, postal_code, city
    """
    if not address_text:
        return {
            "street_address": None,
            "postal_code": None,
            "city": None
        }
    
    # Nettoyage de l'adresse
    address_text = address_text.strip()
    
    # Expression régulière pour le code postal français (5 chiffres)
    postal_code_match = re.search(r'\b(\d{5})\b', address_text)
    postal_code = postal_code_match.group(1) if postal_code_match else None
    
    # Si nous avons trouvé un code postal, essayons de trouver la ville
    city = None
    street_address = address_text
    
    if postal_code:
        # La ville est généralement après le code postal
        # Format typique: "12 rue Example, 75001 Paris" ou "75001 Paris"
        parts_after_postal = address_text.split(postal_code, 1)
        
        if len(parts_after_postal) > 1:
            city_part = parts_after_postal[1].strip()
            
            # Si la partie après le code postal commence par une virgule, la supprimer
            if city_part.startswith(','):
                city_part = city_part[1:].strip()
            
            # Si la partie après le code postal contient une virgule, la ville est avant
            if ',' in city_part:
                city = city_part.split(',', 1)[0].strip()
            else:
                # Sinon prendre les premiers mots (en supposant que c'est la ville)
                # Limiter à 2 mots pour éviter de prendre trop de texte
                words = city_part.split()
                city_words = []
                for word in words[:3]:  # Prendre jusqu'à 3 mots
                    if word.lower() in ['cedex', 'france']:
                        continue  # Ignorer des mots spécifiques
                    city_words.append(word)
                
                city = ' '.join(city_words).strip()
            
            # Extraire l'adresse de la rue (tout ce qui est avant le code postal)
            if parts_after_postal[0]:
                street_part = parts_after_postal[0].strip()
                if street_part.endswith(','):
                    street_part = street_part[:-1].strip()
                street_address = street_part
            else:
                street_address = None
    
    # Si nous n'avons pas trouvé de code postal ou de ville, garder l'adresse complète
    # comme adresse de rue
    if not postal_code and not city:
        street_address = address_text
    
    return {
        "street_address": street_address,
        "postal_code": postal_code,
        "city": city
    }

# Chargement des variables d'environnement
load_dotenv()

# Configuration de la journalisation
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://www.helloasso.com"
SEARCH_URL = "https://www.helloasso.com/e/recherche/associations"
# Option pour forcer la récupération des liens même si des liens existants sont trouvés
FORCE_LINK_RETRIEVAL = os.getenv("FORCE_LINK_RETRIEVAL", "False").lower() in ('true', '1', 't')
# Délais configurables
MIN_DELAY = float(os.getenv("MIN_DELAY", "2"))
MAX_DELAY = float(os.getenv("MAX_DELAY", "5"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
# Délai spécial après erreur 403
DELAY_AFTER_403 = 60

# Générer des cookies aléatoires pour chaque session
def generate_random_cookies():
    """Génère des cookies aléatoires pour simuler un navigateur réel"""
    return {
        'session_id': f"{random.randint(1000000000, 9999999999)}",
        'visitor_id': f"{random.randint(100000000000, 999999999999)}",
        '_ga': f"GA1.2.{random.randint(1000000000, 9999999999)}.{int(time.time())}",
        '_gid': f"GA1.2.{random.randint(1000000000, 9999999999)}.{int(time.time())}",
        'OptanonConsent': f"isIABGlobal=false&datestamp={datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}&version=6.8.0",
        'HA_CONSENT': 'true',
        'HA_ACCEPTED': 'true'
    }

# Générer des headers aléatoires mais réalistes pour chaque requête
def generate_headers():
    """Génère des headers HTTP réalistes avec rotation de User-Agent"""
    # Choisir un User-Agent aléatoire
    user_agent = random.choice(USER_AGENTS)
    
    # Générer des valeurs réalistes pour les autres headers
    accept_language = random.choice([
        "fr,fr-FR;q=0.9,en-US;q=0.8,en;q=0.7",
        "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "en-US,en;q=0.9,fr;q=0.8",
        "fr;q=0.9,en-US;q=0.8,en;q=0.7"
    ])
    
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": accept_language,
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": random.choice(["none", "same-origin"]),
        "Sec-Fetch-User": "?1",
        "Cache-Control": random.choice(["max-age=0", "no-cache"]),
        "Referer": "https://www.helloasso.com/",
        "sec-ch-ua": "\" Not A;Brand\";v=\"99\", \"Chromium\";v=\"123\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": random.choice(["\"Windows\"", "\"macOS\"", "\"Linux\""]),
        "DNT": "1"
    }
    
    return headers

def random_delay(min_factor=1.0, max_factor=1.0, is_error=False):
    """Ajoute un délai aléatoire pour éviter la détection de scraping"""
    global consecutive_403_errors
    
    # Si on a détecté des erreurs 403 consécutives, on augmente le délai
    if is_error and consecutive_403_errors >= MAX_CONSECUTIVE_403:
        delay = DELAY_AFTER_403 + random.uniform(0, 30)  # 60-90 secondes
        logger.warning(f"Trop d'erreurs 403 consécutives. Pause longue de {delay:.1f} secondes pour éviter le blocage...")
        time.sleep(delay)
        consecutive_403_errors = 0  # Réinitialiser le compteur
        return
    
    # Délai normal ou légèrement augmenté en cas d'erreur
    base_min = MIN_DELAY * min_factor
    base_max = MAX_DELAY * max_factor
    
    # Ajouter une variation aléatoire pour éviter les motifs détectables
    jitter = random.uniform(0, 2)
    
    delay = random.uniform(base_min, base_max) + jitter
    logger.debug(f"Pause de {delay:.2f} secondes")
    
    # Diviser le délai en petites pauses pour simuler un comportement humain
    chunks = random.randint(1, 3)
    for i in range(chunks):
        time.sleep(delay / chunks)
        # Simuler de petites actions intermédiaires (comme le mouvement de la souris)
        if random.random() < 0.2 and i < chunks - 1:
            time.sleep(random.uniform(0.1, 0.5))

def make_request(url, params=None, retry_count=0):
    """Effectue une requête HTTP avec gestion des erreurs et des tentatives"""
    global consecutive_403_errors
    
    try:
        # Générer des headers et cookies aléatoires pour chaque requête
        headers = generate_headers()
        cookies = generate_random_cookies()
        
        # Ajouter une session pour maintenir les cookies
        session = requests.Session()
        
        # Faire une requête préliminaire à la page d'accueil pour obtenir des cookies légitimes
        if retry_count == 0 and random.random() < 0.3:  # 30% de chance
            try:
                session.get(
                    BASE_URL,
                    headers=headers,
                    timeout=10
                )
                # Petit délai pour simuler la lecture de la page
                time.sleep(random.uniform(1, 3))
            except:
                pass  # Ignorer les erreurs de la requête préliminaire
        
        # Modifier légèrement les headers pour chaque requête
        if random.random() < 0.5:
            headers["Cache-Control"] = random.choice(["max-age=0", "no-cache", "no-store"])
        
        response = session.get(
            url, 
            params=params, 
            headers=headers, 
            cookies=cookies,
            timeout=30,
            allow_redirects=True
        )
        
        # Gérer spécifiquement l'erreur 403
        if response.status_code == 403:
            consecutive_403_errors += 1
            logger.warning(f"Erreur 403 (Forbidden) pour {url} - Tentative {retry_count+1}/{MAX_RETRIES}")
            
            if retry_count < MAX_RETRIES:
                retry_count += 1
                # Délai progressif en cas d'erreur 403
                backoff_delay = min(60, 5 * (2 ** retry_count))
                logger.info(f"Attente de {backoff_delay} secondes avant nouvelle tentative...")
                time.sleep(backoff_delay)
                return make_request(url, params, retry_count)
        else:
            # Réinitialiser le compteur si on obtient une réponse non-403
            consecutive_403_errors = 0
        
        response.raise_for_status()
        return response
    
    except requests.RequestException as e:
        logger.warning(f"Erreur lors de la requête vers {url}: {e}")
        
        # Gérer les erreurs spécifiques
        if "403" in str(e):
            consecutive_403_errors += 1
        
        if retry_count < MAX_RETRIES:
            retry_count += 1
            
            # Déterminer le délai de retry en fonction du type d'erreur
            if "403" in str(e):
                # Délai progressif pour les 403
                backoff_delay = min(60, 5 * (2 ** retry_count))
                logger.info(f"Attente de {backoff_delay} secondes avant nouvelle tentative ({retry_count}/{MAX_RETRIES})...")
                time.sleep(backoff_delay)
            else:
                # Délai standard pour les autres erreurs
                logger.info(f"Nouvelle tentative ({retry_count}/{MAX_RETRIES})...")
                random_delay(1.5, 2.5, is_error=True)
            
            return make_request(url, params, retry_count)
        else:
            logger.error(f"Échec après {MAX_RETRIES} tentatives pour {url}")
            return None

def extract_email_from_html(html_content):
    """Extrait les emails du contenu HTML en utilisant des expressions régulières"""
    # Chercher les attributs data-email
    data_email_pattern = r'data-email=["\']([^"\']+)["\']'
    data_email_matches = re.findall(data_email_pattern, html_content)
    if data_email_matches:
        return data_email_matches[0]
    
    # Chercher les liens mailto
    mailto_pattern = r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    mailto_matches = re.findall(mailto_pattern, html_content)
    if mailto_matches:
        return mailto_matches[0]
    
    # Chercher des emails dans le texte
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    email_matches = re.findall(email_pattern, html_content)
    if email_matches:
        return email_matches[0]
    
    return None

def extract_phone_from_html(html_content):
    """Extrait les numéros de téléphone du contenu HTML en utilisant des expressions régulières"""
    # Chercher les attributs data-phone
    data_phone_pattern = r'data-phone=["\']([^"\']+)["\']'
    data_phone_matches = re.findall(data_phone_pattern, html_content)
    if data_phone_matches:
        return data_phone_matches[0]
    
    # Chercher les liens tel
    tel_pattern = r'tel:([0-9+\(\)\s.-]{8,})'
    tel_matches = re.findall(tel_pattern, html_content)
    if tel_matches:
        return tel_matches[0]
    
    # Chercher des numéros de téléphone français dans le texte
    phone_patterns = [
        r'(?:0|\+33|0033)[1-9](?:[\s.-]?[0-9]{2}){4}',  # Format standard français
        r'[0-9]{2}[\s.-]?[0-9]{2}[\s.-]?[0-9]{2}[\s.-]?[0-9]{2}[\s.-]?[0-9]{2}'  # Format sans indicatif
    ]
    
    for pattern in phone_patterns:
        matches = re.findall(pattern, html_content)
        if matches:
            return matches[0]
    
    return None

def get_all_association_links():
    """Récupère tous les liens d'associations à partir des pages de recherche"""
    global search_term
    all_links = []
    page = 1
    more_pages = True
    consecutive_empty_pages = 0
    max_empty_pages = 3  # Arrêter après 3 pages vides consécutives
    
    logger.info(f"Récupération des liens d'associations avec le terme '{search_term}'...")
    
    while more_pages and consecutive_empty_pages < max_empty_pages:
        logger.info(f"Traitement de la page {page}...")
        params = {
            "query": search_term,
            "page": page
        }
        
        # Ajouter un paramètre aléatoire pour éviter la mise en cache
        if random.random() < 0.7:  # 70% de chance
            params['_'] = int(time.time() * 1000)
        
        response = make_request(SEARCH_URL, params)
        if not response:
            # En cas d'échec, tenter une autre approche
            logger.info(f"Échec sur la page {page}, tentative avec une approche alternative...")
            
            # Changer l'URL légèrement pour contourner les limitations
            alt_url = f"{SEARCH_URL}?q={search_term}&page={page}"
            response = make_request(alt_url)
            
            if not response:
                # Si l'approche alternative échoue aussi, faire une pause plus longue
                logger.warning(f"Échec des tentatives pour la page {page}, pause longue et passage à la page suivante...")
                random_delay(3.0, 5.0, is_error=True)
                page += 1
                consecutive_empty_pages += 1
                continue
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Chercher les liens des associations - différentes méthodes
        association_links = []
        
        # Méthode 1: Chercher les liens directs vers les associations
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            if href.startswith('/associations/') and not href.endswith('/paiement'):
                full_url = urljoin(BASE_URL, href)
                if full_url not in all_links and full_url not in association_links:
                    association_links.append(full_url)
        
        # Méthode 2: Chercher les cartes d'associations
        for card in soup.select('.association-card, .card, .result-item, [data-type="association"]'):
            link_elem = card.find('a', href=True)
            if link_elem:
                href = link_elem.get('href', '')
                if href.startswith('/associations/'):
                    full_url = urljoin(BASE_URL, href)
                    if full_url not in all_links and full_url not in association_links:
                        association_links.append(full_url)
        
        if not association_links:
            # Méthode 3: Parser le script JSON pour extraire les liens
            scripts = soup.find_all('script', type='application/json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and 'results' in data:
                        for result in data['results']:
                            if 'url' in result and '/associations/' in result['url']:
                                full_url = urljoin(BASE_URL, result['url'])
                                if full_url not in all_links and full_url not in association_links:
                                    association_links.append(full_url)
                except:
                    continue
        
        if not association_links:
            logger.info(f"Aucun lien trouvé sur la page {page}")
            consecutive_empty_pages += 1
            
            # Vérifier si nous sommes arrivés à la dernière page
            pagination = soup.select('.pagination, .paging, nav[aria-label="pagination"]')
            if pagination:
                next_button = soup.select('.pagination__next, .next-page, [aria-label="Next"]')
                if not next_button or 'disabled' in str(next_button):
                    logger.info("Fin de la pagination détectée")
                    more_pages = False
            
            # Si aucun lien n'est trouvé mais qu'il y a du contenu sur la page,
            # cela pourrait être un changement de format. Essayer avec regexp
            if len(response.text) > 5000:  # Page non vide
                url_pattern = r'href=["\']\/associations\/([^"\'\/]+)["\']'
                matches = re.findall(url_pattern, response.text)
                
                for match in matches:
                    if match and not match.endswith('paiement'):
                        full_url = f"{BASE_URL}/associations/{match}"
                        if full_url not in all_links and full_url not in association_links:
                            association_links.append(full_url)
                
                if association_links:
                    consecutive_empty_pages = 0
                    logger.info(f"{len(association_links)} liens trouvés avec méthode alternative sur la page {page}")
        else:
            consecutive_empty_pages = 0
            logger.info(f"{len(association_links)} liens trouvés sur la page {page}")
        
        if association_links:
            all_links.extend(association_links)
            page += 1
        else:
            # Si 3 pages vides consécutives, arrêter
            if consecutive_empty_pages >= max_empty_pages:
                logger.info(f"{max_empty_pages} pages vides consécutives, fin de la pagination")
                more_pages = False
            else:
                # Sinon, essayer la page suivante
                page += 1
        
        # Délai variable entre les pages pour simuler un comportement humain
        wait_factor = random.uniform(1.5, 3.0)
        random_delay(wait_factor, wait_factor * 1.5)
        
        # Petite chance (20%) de faire une pause plus longue pour simuler un comportement humain
        if random.random() < 0.2:
            logger.debug("Pause plus longue pour simuler une navigation humaine...")
            time.sleep(random.uniform(5, 15))
    
    # Supprimer les doublons
    all_links = list(set(all_links))
    logger.info(f"Total des liens uniques trouvés: {len(all_links)}")
    return all_links

def extract_address_from_text(text):
    """Extrait une adresse française potentielle du texte"""
    # Motifs d'adresse française (code postal + ville)
    address_patterns = [
        r'\b\d{5}\s+[A-Za-zÀ-ÿ\s\-\']+\b',  # Code postal suivi d'une ville
        r'(?:[0-9]+,?\s)?(?:rue|avenue|boulevard|impasse|place|chemin|allée|cours)\s[A-Za-zÀ-ÿ\s\-\'0-9]+'  # Rue, avenue, etc.
    ]
    
    for pattern in address_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return matches[0].strip()
    
    return None

# Fonction pour extraire les événements et leurs prix
def extract_events_info(soup, html_content):
    """Extrait les informations sur les événements d'une association et calcule le prix moyen"""
    prices = []
    event_count = 0
    
    # Rechercher les événements sur la page
    # Différentes structures possibles sur HelloAsso
    event_containers = soup.select('.event-card, .campaign-card, .organization-actions, .organization-campaigns')
    
    # Si pas d'événements trouvés avec les sélecteurs, chercher avec des mots-clés
    if not event_containers:
        # Chercher les sections qui contiennent "événement", "billetterie", "adhésion", etc.
        keyword_sections = soup.find_all(['div', 'section'], class_=lambda x: x and any(
            keyword in x.lower() for keyword in ['event', 'campaign', 'ticket', 'billet', 'adhésion', 'action']
        ))
        if keyword_sections:
            event_containers.extend(keyword_sections)
    
    # Extraire les événements en recherchant des éléments avec des prix
    price_elements = soup.select('[class*="price"], [class*="tarif"], [class*="cost"], [class*="amount"]')
    price_pattern = r'(\d+(?:[\.,]\d+)?)\s*(?:€|EUR)'
    
    # Analyser les prix dans ces éléments
    for element in price_elements:
        price_text = element.text.strip()
        price_matches = re.findall(price_pattern, price_text)
        if price_matches:
            for price in price_matches:
                try:
                    price_value = float(price.replace(',', '.'))
                    prices.append(price_value)
                    event_count += 1
                except ValueError:
                    continue
    
    # Si nous n'avons pas trouvé d'événements par cette méthode, chercher dans le HTML brut
    if not prices:
        # Rechercher des motifs de prix dans le HTML
        price_matches = re.findall(price_pattern, html_content)
        if price_matches:
            # Filtrer les doublons et convertir les virgules en points
            unique_prices = set()
            for price in price_matches:
                try:
                    price_value = float(price.replace(',', '.'))
                    unique_prices.add(price_value)
                except ValueError:
                    continue
            
            prices = list(unique_prices)
            event_count = len(prices)
    
    # Si nous avons trouvé plus de 20 prix, c'est probablement du bruit
    # Limiter à un nombre raisonnable
    if len(prices) > 20:
        prices = prices[:20]
        event_count = len(prices)
    
    # Calculer la moyenne des prix s'il y en a
    avg_price = None
    if prices:
        avg_price = sum(prices) / len(prices)
        # Formater avec 2 décimales
        avg_price = round(avg_price, 2)
    
    return {
        "event_count": event_count,
        "avg_event_price": avg_price
    }

# Fonction pour identifier le type d'association
def identify_association_type(name, description="", url=""):
    """
    Identifie le type d'association en fonction de son nom, sa description et son URL.
    Retourne un type d'association (BDE, BDS, BDA, etc.) ou "Autre" si indéterminé.
    """
    # Convertir en minuscules pour la comparaison
    name_lower = name.lower() if name else ""
    description_lower = description.lower() if description else ""
    url_lower = url.lower() if url else ""
    
    # Texte combiné pour la recherche
    combined_text = f"{name_lower} {description_lower} {url_lower}"
    
    # Dictionnaire des types d'associations avec leurs mots-clés associés
    association_types = {
        "BDE": ["bureau des étudiants", "bde", "étudiant", "student", "vie étudiante"],
        "BDS": ["bureau des sports", "bds", "sport", "sportif", "sportive", "athléti"],
        "BDA": ["bureau des arts", "bda", "art", "artistique", "culture", "culturel"],
        "Association Humanitaire": ["humanitaire", "humanitarian", "solidari", "aide", "help", "charity", "ong"],
        "Association Scientifique": ["scientifique", "science", "recherche", "research", "tech", "technolog", "innovation"],
        "Association Professionnelle": ["professionnel", "professional", "métier", "carrière", "career", "business", "entrepreneur"],
        "Club": ["club", "cercle", "interest group"],
        "Junior Entreprise": ["junior entreprise", "junior-entreprise", "je ", "entrepreneuriat étudiant"],
        "Amicale": ["amicale", "alumni", "ancien", "former student"],
        "Association Religieuse": ["religieu", "religio", "faith", "culte", "spirit"],
        "Association Écologique": ["écolo", "ecolo", "environment", "développement durable", "sustainable", "climat", "climate", "green"],
        "Association Musicale": ["musique", "music", "orchestre", "orchestra", "chorale", "choir", "band"],
        "Association Théâtrale": ["théâtre", "theater", "drama", "comédie", "comedy", "impro", "improv"],
        "Association de Jeux": ["jeu", "game", "ludique", "gaming", "joueur", "player", "board game"],
        "Association Politique": ["politique", "politic", "débat", "debate", "citoyen", "citizen"]
    }
    
    # Éléments spécifiques qui peuvent indiquer des types précis
    if any(x in name_lower for x in ["bde", "bureau des étudiant"]):
        return "BDE"
    elif any(x in name_lower for x in ["bds", "bureau des sport"]):
        return "BDS"
    elif any(x in name_lower for x in ["bda", "bureau des art"]):
        return "BDA"
    
    # Recherche par mots-clés
    matched_types = []
    match_counts = {}
    
    for type_name, keywords in association_types.items():
        matches = sum(1 for keyword in keywords if keyword in combined_text)
        if matches > 0:
            matched_types.append(type_name)
            match_counts[type_name] = matches
    
    # Si plusieurs types correspondent, prendre celui avec le plus de correspondances
    if matched_types:
        best_match = max(matched_types, key=lambda x: match_counts[x])
        return best_match
    
    # Identifier les associations étudiantes génériques
    student_keywords = ["étudiant", "student", "campus", "université", "university", "faculty", "iut", "école", "school"]
    if any(keyword in combined_text for keyword in student_keywords):
        return "Association Étudiante"
    
    # Par défaut
    return "Autre"

def get_association_details(url):
    """Récupère les détails d'une association à partir de son URL"""
    logger.info(f"Récupération des détails pour: {url}")
    
    # Tenter d'obtenir une réponse avec gestion des erreurs
    response = make_request(url)
    if not response:
        return None
        
    soup = BeautifulSoup(response.text, 'html.parser')
    html_content = response.text
    
    # Extraction du nom de l'association
    name = None
    h1_tag = soup.find('h1')
    if h1_tag:
        name = h1_tag.text.strip()
        logger.debug(f"Nom trouvé: {name}")
    else:
        # Essayer de trouver avec une classe spécifique
        header_elements = soup.select('.organization-header__title, .organization-name, .page-title')
        if header_elements:
            name = header_elements[0].text.strip()
            logger.debug(f"Nom trouvé via sélecteur alternatif: {name}")
    
    # Si le nom n'est toujours pas trouvé, essayer de l'extraire de l'URL
    if not name:
        try:
            # Extraire le dernier segment de l'URL pour avoir un nom approximatif
            url_parts = url.strip('/').split('/')
            if len(url_parts) > 0:
                name = url_parts[-1].replace('-', ' ').title()
                logger.debug(f"Nom extrait de l'URL: {name}")
        except Exception as e:
            logger.warning(f"Erreur lors de l'extraction du nom depuis l'URL: {e}")
    
    # Extraction de la description pour aider à identifier le type d'association
    description = ""
    # Chercher la description dans les méta-tags
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and 'content' in meta_desc.attrs:
        description = meta_desc['content']
    
    # Chercher aussi dans les sections "À propos", "Qui sommes-nous", etc.
    about_keywords = ['à propos', 'qui sommes-nous', 'about us', 'description', 'présentation', 'notre association']
    for heading in soup.find_all(['h1', 'h2', 'h3', 'h4']):
        heading_text = heading.text.lower()
        if any(keyword in heading_text for keyword in about_keywords):
            # Récupérer les paragraphes suivants
            sibling = heading.find_next(['p', 'div'])
            if sibling:
                description += " " + sibling.text.strip()
    
    # Identifier le type d'association
    association_type = identify_association_type(name, description, url)
    logger.debug(f"Type d'association identifié: {association_type}")
    
    # Extraction de l'email et du téléphone d'abord pour identifier la section de contact
    email = None
    phone = None
    contact_section = None
    
    # Première méthode: recherche par attribut data-email
    email_button = soup.find('button', string=lambda t: t and 'Afficher l\'email' in t)
    if email_button:
        if 'data-email' in email_button.attrs:
            email = email_button['data-email']
            logger.debug(f"Email trouvé via data-attribute: {email}")
        # Trouver le parent ou le conteneur de cette section de contact
        contact_section = find_contact_container(email_button, soup)
    
    # Chercher les liens mailto et tel pour localiser la section de contact
    mailto_links = soup.select('a[href^="mailto:"]')
    tel_links = soup.select('a[href^="tel:"]')
    
    if mailto_links and not contact_section:
        email_elem = mailto_links[0]
        email = email_elem['href'].replace('mailto:', '').strip()
        logger.debug(f"Email trouvé via lien mailto: {email}")
        contact_section = find_contact_container(email_elem, soup)
    
    if tel_links and not contact_section:
        phone_elem = tel_links[0]
        phone = phone_elem['href'].replace('tel:', '').strip()
        logger.debug(f"Téléphone trouvé via lien tel: {phone}")
        contact_section = find_contact_container(phone_elem, soup)
    
    # Recherche des sections de contact par mots-clés    
    if not contact_section:
        contact_keywords = ['coordonnées', 'contact', 'nous contacter', 'nous trouver', 'où nous trouver']
        for section in soup.find_all(['section', 'div']):
            # Vérifier si un titre ou une classe contient un mot-clé de contact
            has_contact_keyword = False
            
            # Vérifier les titres h1-h6 contenus dans la section
            for heading in section.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                if any(keyword in heading.text.lower() for keyword in contact_keywords):
                    has_contact_keyword = True
                    break
            
            # Vérifier les attributs de classe
            if not has_contact_keyword and section.has_attr('class'):
                section_classes = ' '.join(section['class']).lower()
                if any(keyword in section_classes for keyword in contact_keywords):
                    has_contact_keyword = True
            
            # Vérifier les attributs id
            if not has_contact_keyword and section.has_attr('id'):
                section_id = section['id'].lower()
                if any(keyword in section_id for keyword in contact_keywords):
                    has_contact_keyword = True
            
            if has_contact_keyword:
                contact_section = section
                logger.debug("Section de contact trouvée via mots-clés")
                break
    
    # Extraction de l'adresse
    address = None
    
    # Première méthode: chercher l'adresse dans la section de contact identifiée
    if contact_section:
        logger.debug("Recherche d'adresse dans la section de contact")
        
        # Rechercher les éléments d'adresse dans la section de contact
        address_elements = contact_section.select('[itemprop="address"], address, .address, .location, .contact-info__address')
        if address_elements:
            address = address_elements[0].text.strip()
            logger.debug(f"Adresse trouvée dans la section de contact: {address}")
        else:
            # Chercher des paragraphes ou des divs contenant un code postal dans la section de contact
            for element in contact_section.find_all(['p', 'div', 'span']):
                text = element.text.strip()
                # Vérifier si le texte semble être une adresse (contient un code postal français)
                if re.search(r'\b\d{5}\b', text) and len(text) < 100:
                    address = text
                    logger.debug(f"Adresse trouvée via code postal dans la section de contact: {address}")
                    break
    
    # Si l'adresse n'est toujours pas trouvée, essayer les méthodes habituelles
    if not address:
        # Recherche par attribut itemprop="address"
        address_div = soup.select_one('div[itemprop="address"]')
        if address_div:
            address = address_div.text.strip()
            logger.debug(f"Adresse trouvée via itemprop: {address}")
    
    # Deuxième méthode: recherche par balise d'adresse standard
    if not address:
        address_elements = soup.find_all('address')
        if address_elements:
            address = address_elements[0].text.strip()
            logger.debug(f"Adresse trouvée via tag address: {address}")
    
    # Troisième méthode: recherche par classes spécifiques
    if not address:
        address_elements = soup.select('.organization-address, .address, .location, .contact-info__address')
        if address_elements:
            address = address_elements[0].text.strip()
            logger.debug(f"Adresse trouvée via classes spécifiques: {address}")
    
    # Quatrième méthode: recherche par motif dans le texte
    if not address:
        for p in soup.find_all(['p', 'div', 'span']):
            text = p.text.strip()
            if text and len(text) > 10 and len(text) < 100:  # Une adresse a généralement cette longueur
                found_address = extract_address_from_text(text)
                if found_address:
                    address = found_address
                    logger.debug(f"Adresse trouvée via motif: {address}")
                    break
    
    # Cinquième méthode: recherche dans le HTML brut
    if not address:
        address_pattern = r'itemprop="address"[^>]*>(.*?)</div>'
        address_matches = re.findall(address_pattern, html_content)
        if address_matches:
            # Nettoyer l'adresse des balises HTML
            raw_address = address_matches[0]
            address = re.sub(r'<[^>]+>', ' ', raw_address).strip()
            address = re.sub(r'\s+', ' ', address)
            logger.debug(f"Adresse trouvée via code HTML brut: {address}")
    
    # Analyser l'adresse pour extraire ses composants
    address_components = parse_address(address)
    
    # Si email n'est toujours pas trouvé, chercher par d'autres moyens
    if not email:
        # Deuxième méthode: chercher d'autres attributs data-* contenant @
        for button in soup.find_all('button'):
            for attr_name, attr_value in button.attrs.items():
                if attr_name.startswith('data-') and isinstance(attr_value, str) and '@' in attr_value:
                    email = attr_value
                    logger.debug(f"Email trouvé via autre attribut data-*: {email}")
                    break
            if email:
                break
    
    # Quatrième méthode: recherche dans le HTML brut
    if not email:
        email = extract_email_from_html(html_content)
        if email:
            logger.debug(f"Email trouvé via HTML brut: {email}")
    
    # Si phone n'est toujours pas trouvé, chercher par d'autres moyens
    if not phone:
        # Première méthode: recherche par attribut data-phone
        phone_button = soup.find('button', string=lambda t: t and 'Afficher le numéro' in t)
        if phone_button and 'data-phone' in phone_button.attrs:
            phone = phone_button['data-phone']
            logger.debug(f"Téléphone trouvé via data-attribute: {phone}")
    
        # Deuxième méthode: chercher d'autres attributs data-* contenant des chiffres
        if not phone:
            for button in soup.find_all('button'):
                for attr_name, attr_value in button.attrs.items():
                    if attr_name.startswith('data-') and isinstance(attr_value, str) and any(c.isdigit() for c in attr_value):
                        # Vérifier que c'est probablement un numéro de téléphone (contient beaucoup de chiffres)
                        digits = sum(c.isdigit() for c in attr_value)
                        if digits >= 8:  # Un numéro de téléphone a généralement au moins 8 chiffres
                            phone = attr_value
                            logger.debug(f"Téléphone trouvé via autre attribut data-*: {phone}")
                            break
                if phone:
                    break
    
        # Quatrième méthode: recherche dans le HTML brut
        if not phone:
            phone = extract_phone_from_html(html_content)
            if phone:
                logger.debug(f"Téléphone trouvé via HTML brut: {phone}")
    
    # Extraction des informations sur les événements
    events_info = extract_events_info(soup, html_content)
    
    # Extraire les données d'un script JSON LD potentiel
    json_ld = None
    script_tags = soup.find_all('script', type='application/ld+json')
    for script in script_tags:
        try:
            data = json.loads(script.string)
            
            # Si nous avons un objet unique
            if isinstance(data, dict):
                if '@type' in data and data['@type'] in ['Organization', 'NGO', 'LocalBusiness', 'EducationalOrganization']:
                    json_ld = data
                    logger.debug("Données JSON-LD trouvées")
                    
                    # Si on a trouvé les données JSON LD, extraire les informations manquantes
                    if not name and 'name' in json_ld:
                        name = json_ld['name']
                        logger.debug(f"Nom trouvé via JSON-LD: {name}")
                    
                    if not address and 'address' in json_ld:
                        addr = json_ld['address']
                        if isinstance(addr, dict):
                            address_parts = []
                            
                            # Extraire directement les composants d'adresse
                            if 'streetAddress' in addr:
                                address_components['street_address'] = addr['streetAddress']
                            
                            if 'postalCode' in addr:
                                address_components['postal_code'] = addr['postalCode']
                            
                            if 'addressLocality' in addr:
                                address_components['city'] = addr['addressLocality']
                            
                            # Construire aussi l'adresse complète pour référence
                            for field in ['streetAddress', 'postalCode', 'addressLocality']:
                                if field in addr and addr[field]:
                                    address_parts.append(str(addr[field]))
                            address = " ".join(address_parts)
                            logger.debug(f"Adresse trouvée via JSON-LD: {address}")
                        elif isinstance(addr, str):
                            address = addr
                            logger.debug(f"Adresse trouvée via JSON-LD (string): {address}")
                            # Analyser cette adresse string
                            address_components = parse_address(address)
                    
                    if not email and 'email' in json_ld:
                        email = json_ld['email']
                        logger.debug(f"Email trouvé via JSON-LD: {email}")
                    
                    if not phone and 'telephone' in json_ld:
                        phone = json_ld['telephone']
                        logger.debug(f"Téléphone trouvé via JSON-LD: {phone}")
            
            # Si nous avons une liste d'objets
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and '@type' in item and item['@type'] in ['Organization', 'NGO', 'LocalBusiness', 'EducationalOrganization']:
                        logger.debug("Données JSON-LD trouvées dans liste")
                        
                        if not name and 'name' in item:
                            name = item['name']
                            logger.debug(f"Nom trouvé via JSON-LD (liste): {name}")
                        
                        if not address and 'address' in item:
                            addr = item['address']
                            if isinstance(addr, dict):
                                # Extraire directement les composants d'adresse
                                if 'streetAddress' in addr:
                                    address_components['street_address'] = addr['streetAddress']
                                
                                if 'postalCode' in addr:
                                    address_components['postal_code'] = addr['postalCode']
                                
                                if 'addressLocality' in addr:
                                    address_components['city'] = addr['addressLocality']
                                
                                # Construire aussi l'adresse complète pour référence
                                address_parts = []
                                for field in ['streetAddress', 'postalCode', 'addressLocality']:
                                    if field in addr and addr[field]:
                                        address_parts.append(str(addr[field]))
                                address = " ".join(address_parts)
                                logger.debug(f"Adresse trouvée via JSON-LD (liste): {address}")
                            elif isinstance(addr, str):
                                address = addr
                                logger.debug(f"Adresse trouvée via JSON-LD (liste, string): {address}")
                                # Analyser cette adresse string
                                address_components = parse_address(address)
                        
                        if not email and 'email' in item:
                            email = item['email']
                            logger.debug(f"Email trouvé via JSON-LD (liste): {email}")
                        
                        if not phone and 'telephone' in item:
                            phone = item['telephone']
                            logger.debug(f"Téléphone trouvé via JSON-LD (liste): {phone}")
        except Exception as e:
            logger.debug(f"Erreur lors du parsing JSON-LD: {e}")
            continue
    
    result = {
        'name': name,
        'url': url,
        'street_address': address_components['street_address'],
        'postal_code': address_components['postal_code'],
        'city': address_components['city'],
        'email': email if email else "Non dispo",
        'phone': phone if phone else "Non dispo",
        'event_count': events_info['event_count'],
        'avg_event_price': events_info['avg_event_price'],
        'association_type': association_type
    }
    
    # Vérification de la qualité des données
    missing_fields = [field for field, value in result.items() 
                     if field not in ['street_address', 'postal_code', 'city', 'event_count', 'avg_event_price', 'email', 'phone', 'association_type'] 
                     and not value]
    if missing_fields:
        logger.warning(f"Données manquantes pour {url}: {', '.join(missing_fields)}")
    
    return result

# Nouvelle fonction pour trouver le conteneur parent d'un élément qui contient les coordonnées
def find_contact_container(element, soup):
    """
    Trouve le conteneur parent d'un élément qui est susceptible de contenir les coordonnées complètes.
    Retourne le conteneur ou None si aucun n'est trouvé.
    """
    if not element:
        return None
    
    # Remonter jusqu'à 5 niveaux de parents pour trouver un conteneur de contact
    current = element
    for _ in range(5):
        if not current or current == soup:
            break
            
        parent = current.parent
        if not parent:
            break
            
        # Vérifier si le parent semble être un conteneur de contact
        if parent.name in ['div', 'section', 'aside', 'article', 'footer']:
            # Vérifier les classes et IDs
            has_contact_indicator = False
            
            if parent.has_attr('class'):
                classes = ' '.join(parent['class']).lower()
                if any(keyword in classes for keyword in ['contact', 'coord', 'info', 'address', 'adresse', 'nous', 'find']):
                    has_contact_indicator = True
            
            if not has_contact_indicator and parent.has_attr('id'):
                parent_id = parent['id'].lower()
                if any(keyword in parent_id for keyword in ['contact', 'coord', 'info', 'address', 'adresse', 'nous', 'find']):
                    has_contact_indicator = True
            
            # Vérifier le contenu
            if not has_contact_indicator:
                headings = parent.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                for heading in headings:
                    heading_text = heading.text.lower()
                    if any(keyword in heading_text for keyword in ['contact', 'coordonnées', 'adresse', 'nous trouver', 'où nous trouver']):
                        has_contact_indicator = True
                        break
            
            # Si le parent a des indications d'être un conteneur de contact
            if has_contact_indicator:
                return parent
            
            # Vérifier aussi si le parent contient des éléments d'adresse
            address_elements = parent.find_all(['address']) + parent.select('[itemprop="address"]')
            if address_elements:
                return parent
        
        current = parent
    
    return None

# Fonction pour analyser les résultats
def analyze_results(results_data):
    """Analyse les données récupérées et affiche des statistiques"""
    if not results_data:
        print("Aucune donnée à analyser.")
        return
    
    print("\n" + "="*50)
    print(f"ANALYSE DES DONNÉES ({len(results_data)} associations)")
    print("="*50)
    
    # 1. Répartition par type d'association
    print("\n--- RÉPARTITION PAR TYPE D'ASSOCIATION ---")
    type_counts = {}
    for result in results_data:
        assoc_type = result.get('association_type', 'Non défini')
        type_counts[assoc_type] = type_counts.get(assoc_type, 0) + 1
    
    # Trier par fréquence décroissante
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
    for assoc_type, count in sorted_types:
        percentage = (count / len(results_data)) * 100
        print(f"{assoc_type}: {count} ({percentage:.1f}%)")
    
    # 2. Répartition géographique
    print("\n--- RÉPARTITION GÉOGRAPHIQUE ---")
    city_counts = {}
    postal_code_counts = {}
    for result in results_data:
        city = result.get('city')
        if city and city != "None":
            city_counts[city] = city_counts.get(city, 0) + 1
        
        postal_code = result.get('postal_code')
        if postal_code and postal_code != "None":
            postal_code_counts[postal_code] = postal_code_counts.get(postal_code, 0) + 1
    
    # Top 10 des villes
    print("\nTop 10 des villes:")
    top_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for city, count in top_cities:
        percentage = (count / len(results_data)) * 100
        print(f"{city}: {count} ({percentage:.1f}%)")
    
    # 3. Statistiques sur les événements
    print("\n--- STATISTIQUES SUR LES ÉVÉNEMENTS ---")
    event_counts = [r.get('event_count', 0) for r in results_data if r.get('event_count') is not None]
    avg_prices = [r.get('avg_event_price') for r in results_data if r.get('avg_event_price') is not None]
    
    if event_counts:
        avg_event_count = sum(event_counts) / len(event_counts)
        max_event_count = max(event_counts)
        event_assocs = sum(1 for count in event_counts if count > 0)
        event_percent = (event_assocs / len(results_data)) * 100
        print(f"Associations avec événements: {event_assocs} ({event_percent:.1f}%)")
        print(f"Nombre moyen d'événements par association: {avg_event_count:.1f}")
        print(f"Nombre maximum d'événements: {max_event_count}")
    
    if avg_prices:
        valid_prices = [p for p in avg_prices if p is not None]
        if valid_prices:
            avg_price = sum(valid_prices) / len(valid_prices)
            min_price = min(valid_prices)
            max_price = max(valid_prices)
            print(f"Prix moyen des événements: {avg_price:.2f}€")
            print(f"Prix minimum: {min_price:.2f}€")
            print(f"Prix maximum: {max_price:.2f}€")
    
    # 4. Taux de complétude des données
    print("\n--- COMPLÉTUDE DES DONNÉES ---")
    fields = {
        'name': 'Nom',
        'email': 'Email',
        'phone': 'Téléphone',
        'street_address': 'Adresse',
        'postal_code': 'Code postal',
        'city': 'Ville'
    }
    
    for field, label in fields.items():
        field_count = sum(1 for r in results_data if r.get(field) and r.get(field) not in ["None", "Non dispo"])
        field_percent = (field_count / len(results_data)) * 100
        print(f"{label}: {field_count} ({field_percent:.1f}%)")
    
    print("\n" + "="*50)
    
    # Sauvegarder les statistiques dans un fichier séparé avec une belle mise en forme
    save_statistics_to_file(results_data, type_counts, city_counts, postal_code_counts, event_counts, avg_prices, fields)

# Nouvelle fonction pour sauvegarder les statistiques dans un fichier HTML
def save_statistics_to_file(results_data, type_counts, city_counts, postal_codes, event_counts, avg_prices, fields):
    """Sauvegarde les statistiques dans un fichier HTML bien formaté"""
    global search_term, timestamp
    
    if not results_data:
        return
    
    # Créer le dossier de statistiques si nécessaire
    os.makedirs('results/stats', exist_ok=True)
    
    # Nom du fichier de statistiques
    stats_file = f'results/stats/statistiques_{search_term}_{timestamp}.html'
    
    # Préparer les données pour la carte
    map_data = []
    for result in results_data:
        city = result.get('city')
        postal_code = result.get('postal_code')
        if city and postal_code and city != "None" and postal_code != "None":
            map_data.append({
                'city': city, 
                'postal_code': postal_code,
                'name': result.get('name', 'Association'),
                'type': result.get('association_type', 'Autre')
            })
    
    # Convertir les données en JSON pour l'utilisation en JavaScript
    map_data_json = json.dumps(map_data)
    
    # Convertir type_counts en JSON pour l'insérer dans le JavaScript
    type_data = {k: v for k, v in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)}
    type_counts_json = json.dumps(type_data)
    
    # Préparer les données pour l'histogramme des prix
    price_bins = {}
    if avg_prices:
        valid_prices = [p for p in avg_prices if p is not None]
        if valid_prices:
            # Créer des tranches de prix
            bins = [0, 10, 20, 30, 50, 100, float('inf')]
            bin_labels = ['0-10€', '10-20€', '20-30€', '30-50€', '50-100€', '100€+']
            
            for i in range(len(bins)-1):
                price_bins[bin_labels[i]] = len([p for p in valid_prices if bins[i] <= p < bins[i+1]])
    
    price_bins_json = json.dumps(price_bins)
    
    # Calculer le nombre d'associations avec et sans événements pour le graphique
    event_data = [0, 0]
    if event_counts:
        event_assocs = sum(1 for count in event_counts if count > 0)
        no_event_assocs = len(results_data) - event_assocs
        event_data = [event_assocs, no_event_assocs]
    
    # En-tête HTML avec styles CSS et scripts modernes
    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Statistiques des Associations - {search_term}</title>
    
    <!-- Leaflet CSS pour la carte -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" 
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
    
    <!-- Chart.js pour les graphiques -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    
    <style>
        :root {{
            --primary-color: #4361ee;
            --secondary-color: #3a0ca3;
            --accent-color: #f72585;
            --background-color: #f8f9fa;
            --text-color: #333;
            --card-bg: #ffffff;
            --border-radius: 12px;
            --shadow: 0 4px 6px rgba(0, 0, 0, 0.05), 0 1px 3px rgba(0, 0, 0, 0.1);
            --transition: all 0.3s ease;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', sans-serif;
            line-height: 1.6;
            background-color: var(--background-color);
            color: var(--text-color);
            padding: 0;
            margin: 0;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        header {{
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 40px 0;
            text-align: center;
            margin-bottom: 30px;
            box-shadow: var(--shadow);
        }}
        
        header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 700;
        }}
        
        header p {{
            font-size: 1.2rem;
            opacity: 0.9;
        }}
        
        section {{
            margin-bottom: 40px;
        }}
        
        h2 {{
            color: var(--primary-color);
            font-size: 1.8rem;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--primary-color);
        }}
        
        h3 {{
            color: var(--secondary-color);
            font-size: 1.4rem;
            margin-bottom: 15px;
        }}
        
        .card {{
            background-color: var(--card-bg);
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
            padding: 25px;
            margin-bottom: 20px;
            transition: var(--transition);
        }}
        
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            padding: 20px;
        }}
        
        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary-color);
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            color: #666;
            font-size: 1rem;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            overflow: hidden;
            border-radius: var(--border-radius);
            box-shadow: var(--shadow);
        }}
        
        th, td {{
            padding: 15px;
            text-align: left;
        }}
        
        th {{
            background-color: var(--primary-color);
            color: white;
            font-weight: 600;
        }}
        
        tr:nth-child(even) {{
            background-color: rgba(0, 0, 0, 0.03);
        }}
        
        tr:hover {{
            background-color: rgba(67, 97, 238, 0.1);
        }}
        
        .progress-container {{
            background-color: #e9ecef;
            border-radius: 10px;
            height: 15px;
            width: 100%;
            margin: 10px 0;
            overflow: hidden;
        }}
        
        .progress-bar {{
            height: 100%;
            border-radius: 10px;
            background: linear-gradient(90deg, var(--primary-color), var(--accent-color));
            transition: width 1s ease-in-out;
        }}
        
        .highlight {{
            font-weight: 600;
            color: var(--primary-color);
        }}
        
        .map-container {{
            height: 500px;
            border-radius: var(--border-radius);
            overflow: hidden;
            box-shadow: var(--shadow);
            margin-bottom: 30px;
        }}
        
        #map {{
            height: 100%;
            width: 100%;
        }}
        
        .chart-container {{
            position: relative;
            height: 300px;
            margin: 20px 0;
        }}
        
        .two-columns {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }}
        
        .footer {{
            background-color: var(--secondary-color);
            color: white;
            text-align: center;
            padding: 20px 0;
            margin-top: 50px;
        }}
        
        .footer p {{
            margin: 5px 0;
            font-size: 0.9rem;
            opacity: 0.9;
        }}
        
        /* Animation pour les cartes */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .card {{
            animation: fadeIn 0.5s ease-out forwards;
        }}
        
        .card:nth-child(2) {{ animation-delay: 0.1s; }}
        .card:nth-child(3) {{ animation-delay: 0.2s; }}
        .card:nth-child(4) {{ animation-delay: 0.3s; }}
        
        /* Styles responsifs */
        @media (max-width: 768px) {{
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .two-columns {{
                grid-template-columns: 1fr;
            }}
            
            .map-container {{
                height: 400px;
            }}
            
            header {{
                padding: 30px 0;
            }}
            
            header h1 {{
                font-size: 2rem;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>Statistiques des Associations</h1>
            <p>Analyse des données pour le terme: "{search_term}"</p>
        </div>
    </header>
    
    <div class="container">
        <section>
            <div class="stats-grid">
                <div class="card stat-item">
                    <div class="stat-value">{len(results_data)}</div>
                    <div class="stat-label">Associations analysées</div>
                </div>
                
                <div class="card stat-item">
                    <div class="stat-value">{len(city_counts)}</div>
                    <div class="stat-label">Villes représentées</div>
                </div>
                
                <div class="card stat-item">
                    <div class="stat-value">{len(type_counts)}</div>
                    <div class="stat-label">Types d'associations</div>
                </div>
                
                <div class="card stat-item">
                    <div class="stat-value">{datetime.datetime.now().strftime("%d/%m/%Y")}</div>
                    <div class="stat-label">Date d'analyse</div>
                </div>
            </div>
        </section>
        
        <section>
            <h2>Répartition Géographique</h2>
            <div class="card map-container">
                <div id="map"></div>
            </div>
            
            <div class="two-columns">
                <div class="card">
                    <h3>Top 10 des Villes</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Ville</th>
                                <th>Nombre</th>
                                <th>%</th>
                            </tr>
                        </thead>
                        <tbody>
"""
    
    # Ajouter les données des villes
    top_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for city, count in top_cities:
        percentage = (count / len(results_data)) * 100
        html_content += f"""
                            <tr>
                                <td>{city}</td>
                                <td>{count}</td>
                                <td>{percentage:.1f}%</td>
                            </tr>
"""
    
    html_content += """
                        </tbody>
                    </table>
                </div>
                
                <div class="card">
                    <h3>Répartition par Type</h3>
                    <div class="chart-container">
                        <canvas id="typeChart"></canvas>
                    </div>
                </div>
            </div>
        </section>
        
        <section>
            <h2>Types d'Associations</h2>
            <div class="card">
                <table>
                    <thead>
                        <tr>
                            <th>Type d'Association</th>
                            <th>Nombre</th>
                            <th>Pourcentage</th>
                        </tr>
                    </thead>
                    <tbody>
"""
    
    # Ajouter les données de types d'associations
    sorted_types = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)
    for assoc_type, count in sorted_types:
        percentage = (count / len(results_data)) * 100
        html_content += f"""
                        <tr>
                            <td>{assoc_type}</td>
                            <td>{count}</td>
                            <td>{percentage:.1f}%</td>
                        </tr>
"""
    
    html_content += """
                    </tbody>
                </table>
            </div>
        </section>
        
        <section>
            <h2>Statistiques sur les Événements</h2>
            <div class="two-columns">
                <div class="card">
                    <h3>Activité des Associations</h3>
"""
    
    if event_counts:
        avg_event_count = sum(event_counts) / len(event_counts)
        max_event_count = max(event_counts)
        event_assocs = sum(1 for count in event_counts if count > 0)
        event_percent = (event_assocs / len(results_data)) * 100
        html_content += f"""
                    <p>Associations avec événements: <span class="highlight">{event_assocs}</span> ({event_percent:.1f}%)</p>
                    <p>Nombre moyen d'événements par association: <span class="highlight">{avg_event_count:.1f}</span></p>
                    <p>Nombre maximum d'événements: <span class="highlight">{max_event_count}</span></p>
                    <div class="chart-container">
                        <canvas id="eventsChart"></canvas>
                    </div>
"""
    else:
        html_content += """
                    <p>Aucune donnée sur les événements n'est disponible.</p>
"""
    
    html_content += """
                </div>
                <div class="card">
                    <h3>Prix des Événements</h3>
"""
    
    if avg_prices:
        valid_prices = [p for p in avg_prices if p is not None]
        if valid_prices:
            avg_price = sum(valid_prices) / len(valid_prices)
            min_price = min(valid_prices)
            max_price = max(valid_prices)
            html_content += f"""
                    <p>Prix moyen des événements: <span class="highlight">{avg_price:.2f}€</span></p>
                    <p>Prix minimum: <span class="highlight">{min_price:.2f}€</span></p>
                    <p>Prix maximum: <span class="highlight">{max_price:.2f}€</span></p>
                    <div class="chart-container">
                        <canvas id="priceChart"></canvas>
                    </div>
"""
        else:
            html_content += """
                    <p>Aucune information sur les prix n'est disponible.</p>
"""
    else:
        html_content += """
                    <p>Aucune information sur les prix n'est disponible.</p>
"""
    
    html_content += """
                </div>
            </div>
        </section>
        
        <section>
            <h2>Complétude des Données</h2>
            <div class="card">
"""
    
    # Ajouter les barres de progression pour la complétude des données
    for field, label in fields.items():
        field_count = sum(1 for r in results_data if r.get(field) and r.get(field) not in ["None", "Non dispo"])
        field_percent = (field_count / len(results_data)) * 100
        html_content += f"""
                <p>{label}: {field_count} ({field_percent:.1f}%)</p>
                <div class="progress-container">
                    <div class="progress-bar" style="width: {field_percent}%;"></div>
                </div>
"""
    
    html_content += """
            </div>
        </section>
    </div>
    
    <footer class="footer">
        <div class="container">
            <p>Rapport généré automatiquement par le script de scraping HelloAsso</p>
            <p>Date de génération: {0}</p>
        </div>
    </footer>

    <!-- Leaflet JS pour la carte -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" 
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    
    <!-- Script pour initialiser la carte et les graphiques -->
    <script>
        // Attendre que tout le DOM soit chargé
        document.addEventListener('DOMContentLoaded', function() {{
            // Initialisation de la carte
            initMap();
            
            // Initialisation des graphiques
            initCharts();
        }});
        
        function initMap() {{
            try {{
                // Données pour la carte
                const mapData = {map_data_json};
                
                // Vérification si l'élément map existe
                const mapElement = document.getElementById('map');
                if (!mapElement) {{
                    console.error("Élément DOM 'map' non trouvé");
                    return;
                }}
                
                // Initialisation de la carte au centre de la France
                const map = L.map('map').setView([46.603354, 1.888334], 5);
                
                // Ajout du fond de carte OpenStreetMap
                L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }}).addTo(map);
                
                // Regrouper les données par ville
                const cityData = {{}};
                mapData.forEach(item => {{
                    if (!cityData[item.city]) {{
                        cityData[item.city] = {{
                            count: 0,
                            postalCode: item.postal_code,
                            types: {{}},
                            associations: []
                        }};
                    }}
                    
                    cityData[item.city].count++;
                    cityData[item.city].associations.push(item.name);
                    
                    if (!cityData[item.city].types[item.type]) {{
                        cityData[item.city].types[item.type] = 0;
                    }}
                    cityData[item.city].types[item.type]++;
                }});
                
                // Ajouter des marqueurs pour chaque ville
                Object.keys(cityData).forEach(city => {{
                    const data = cityData[city];
                    const coordinates = getCoordinatesFromPostalCode(data.postalCode);
                    
                    // Créer le contenu du popup
                    let popupContent = `<strong>${{city}}</strong><br>`;
                    popupContent += `${{data.count}} association(s)<br><br>`;
                    
                    // Ajouter les types d'associations
                    popupContent += '<strong>Types:</strong><br>';
                    Object.keys(data.types).forEach(type => {{
                        popupContent += `${{type}}: ${{data.types[type]}}<br>`;
                    }});
                    
                    // Limiter le nombre d'associations affichées
                    const MAX_ASSOC = 5;
                    if (data.associations.length > 0) {{
                        popupContent += '<br><strong>Associations:</strong><br>';
                        data.associations.slice(0, MAX_ASSOC).forEach(assoc => {{
                            popupContent += `${{assoc}}<br>`;
                        }});
                        
                        if (data.associations.length > MAX_ASSOC) {{
                            popupContent += `... et ${{data.associations.length - MAX_ASSOC}} autres`;
                        }}
                    }}
                    
                    // Créer le marqueur avec un rayon proportionnel au nombre d'associations
                    const radius = Math.max(5, Math.min(20, 5 + data.count / 2));
                    L.circleMarker(coordinates, {{
                        radius: radius,
                        fillColor: "#4361ee",
                        color: "#3a0ca3",
                        weight: 1,
                        opacity: 1,
                        fillOpacity: 0.8
                    }})
                    .bindPopup(popupContent)
                    .addTo(map);
                }});
            }} catch (error) {{
                console.error("Erreur lors de l'initialisation de la carte:", error);
            }}
        }}
        
        function initCharts() {{
            try {{
                // Création du graphique des types
                const typeChartElement = document.getElementById('typeChart');
                if (typeChartElement) {{
                    createTypeChart(typeChartElement);
                }}
                
                // Création du graphique des événements
                const eventsChartElement = document.getElementById('eventsChart');
                if (eventsChartElement) {{
                    createEventsChart(eventsChartElement);
                }}
                
                // Création du graphique des prix
                const priceChartElement = document.getElementById('priceChart');
                if (priceChartElement) {{
                    createPriceChart(priceChartElement);
                }}
            }} catch (error) {{
                console.error("Erreur lors de l'initialisation des graphiques:", error);
            }}
        }}
        
        function createTypeChart(element) {{
            const typeData = {type_counts_json};
            const typeLabels = [];
            const typeCounts = [];
            const typeColors = [
                '#4361ee', '#3a0ca3', '#f72585', '#7209b7', '#560bad',
                '#4cc9f0', '#4895ef', '#4361ee', '#3f37c9', '#b5179e'
            ];
            
            // Préparer les données pour le graphique
            let others = 0;
            let counter = 0;
            
            // Trier les types par nombre d'occurrences
            const sortedEntries = Object.entries(typeData).sort((a, b) => b[1] - a[1]);
            
            sortedEntries.forEach(([type, count]) => {{
                if (counter < 5) {{
                    // Afficher les 5 premiers types directement
                    typeLabels.push(type);
                    typeCounts.push(count);
                    counter++;
                }} else {{
                    // Regrouper le reste sous "Autres"
                    others += count;
                }}
            }});
            
            // Ajouter la catégorie "Autres" si nécessaire
            if (others > 0) {{
                typeLabels.push('Autres');
                typeCounts.push(others);
            }}
            
            // Créer le graphique
            new Chart(element, {{
                type: 'doughnut',
                data: {{
                    labels: typeLabels,
                    datasets: [{{
                        data: typeCounts,
                        backgroundColor: typeColors.slice(0, typeLabels.length),
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'right',
                        }}
                    }}
                }}
            }});
        }}
        
        function createEventsChart(element) {{
            const eventData = {event_data};
            
            new Chart(element, {{
                type: 'bar',
                data: {{
                    labels: ['Avec événements', 'Sans événements'],
                    datasets: [{{
                        data: eventData,
                        backgroundColor: ['#4361ee', '#e9ecef'],
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            beginAtZero: true
                        }}
                    }},
                    plugins: {{
                        legend: {{
                            display: false
                        }}
                    }}
                }}
            }});
        }}
        
        function createPriceChart(element) {{
            const priceData = {price_bins_json};
            const priceLabels = Object.keys(priceData);
            const priceCounts = Object.values(priceData);
            
            new Chart(element, {{
                type: 'bar',
                data: {{
                    labels: priceLabels,
                    datasets: [{{
                        label: 'Nombre d\'associations',
                        data: priceCounts,
                        backgroundColor: '#4361ee',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            beginAtZero: true
                        }}
                    }},
                    plugins: {{
                        legend: {{
                            display: false
                        }}
                    }}
                }}
            }});
        }}
        
        // Fonction pour obtenir des coordonnées approximatives basées sur le code postal
        function getCoordinatesFromPostalCode(postalCode) {{
            try {{
                // Converti le code postal en nombre pour générer des coordonnées pseudo-aléatoires mais cohérentes
                const seed = parseInt(postalCode);
                
                // Départements français (2 premiers chiffres du code postal)
                const dept = Math.floor(seed / 1000);
                
                // Coordonnées approximatives de la France métropolitaine par département
                let lat = 44 + (dept % 10) * 0.5;
                let lng = 0 + (dept % 10) * 0.5;
                
                // Ajustements pour les régions françaises approximatives
                if (dept >= 1 && dept <= 19) {{ // Nord-Est
                    lat = 48 + (seed % 100) * 0.01;
                    lng = 2 + (seed % 100) * 0.01;
                }} else if (dept >= 20 && dept <= 39) {{ // Sud-Est
                    lat = 43 + (seed % 100) * 0.01;
                    lng = 5 + (seed % 100) * 0.01;
                }} else if (dept >= 40 && dept <= 69) {{ // Centre
                    lat = 45 + (seed % 100) * 0.01;
                    lng = 2 + (seed % 100) * 0.01;
                }} else if (dept >= 70 && dept <= 89) {{ // Ouest
                    lat = 47 + (seed % 100) * 0.01;
                    lng = -1 + (seed % 100) * 0.01;
                }} else if (dept >= 90) {{ // Sud-Ouest
                    lat = 44 + (seed % 100) * 0.01;
                    lng = 0 + (seed % 100) * 0.01;
                }}
                
                return [lat, lng];
            }} catch (error) {{
                console.error("Erreur lors du calcul des coordonnées:", error);
                // Coordonnées par défaut (Paris)
                return [48.856614, 2.3522219];
            }}
        }}
    </script>
</body>
</html>
""".format(datetime.datetime.now().strftime("%d/%m/%Y %H:%M"))
    
    # Écrire le contenu HTML dans le fichier
    with open(stats_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\nLes statistiques détaillées ont été sauvegardées dans: {stats_file}")

# Ajouter cette fonction utilitaire
def format_time(seconds):
    """Formate les secondes en HH:MM:SS"""
    if seconds < 0:
        return "N/A"
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# Après la fonction load_skip_urls_from_csv, ajouter la fonction suivante
def choose_reference_file():
    """Permet à l'utilisateur de choisir un fichier CSV de référence pour éviter les doublons."""
    print("\nSouhaitez-vous utiliser un fichier de référence pour éviter les doublons? (O/n): ", end="")
    choice = input().strip().lower()
    
    if choice == "" or choice == "o":
        # Permettre à l'utilisateur de choisir un fichier CSV existant
        csv_file = choose_file('results', f"*.csv", 
                               "Choisissez un fichier CSV de référence")
        
        if csv_file:
            # Charger les URLs déjà traitées
            skip_urls = load_skip_urls_from_csv(csv_file)
            print(f"Le script ignorera {len(skip_urls)} associations déjà présentes dans le fichier de référence.")
            return skip_urls
    
    print("Aucun fichier de référence sélectionné. Toutes les associations seront traitées.")
    return set()

# Maintenant, modifions la fonction main() pour utiliser cette nouvelle fonctionnalité
def main():
    """Fonction principale du scraper"""
    global results, interrupted, search_term, timestamp, skip_urls, consecutive_403_errors
    
    print("\n=======================================")
    print("   Scraper HelloAsso pour associations")
    print("=======================================\n")
    
    # Demander le terme de recherche à l'utilisateur
    search_term = get_search_term()
    
    logger.info(f"Démarrage du scraper HelloAsso pour les associations avec le terme: {search_term}")
    print(f"Recherche lancée pour le terme: {search_term}")
    
    # Demander à l'utilisateur s'il souhaite reprendre un scraping précédent
    print("\nSouhaitez-vous reprendre un scraping précédent? (O/n): ", end="")
    choice = input().strip().lower()
    
    save_results.output_file = None  # Réinitialiser le fichier de sortie
    
    if choice == "" or choice == "o":
        # Permettre à l'utilisateur de choisir un fichier CSV existant
        csv_file = choose_file('results', f"*.csv", 
                              "Choisissez un fichier CSV existant pour continuer le scraping")
        
        if csv_file:
            # Charger les URLs déjà traitées
            skip_urls = load_skip_urls_from_csv(csv_file)
            # Définir le fichier de sortie pour save_results
            save_results.output_file = csv_file
            print(f"Les résultats seront ajoutés à: {csv_file}")
        else:
            print(f"Nouveau fichier sera créé: results/associations_{search_term}_{timestamp}.csv")
    else:
        # Option pour utiliser un fichier de référence sans y ajouter les résultats
        reference_urls = choose_reference_file()
        skip_urls.update(reference_urls)
        
        print(f"Les résultats seront sauvegardés dans: results/associations_{search_term}_{timestamp}.csv")
    
    try:
        # Création du dossier de résultats si nécessaire
        os.makedirs('results', exist_ok=True)
        
        # Vérifier d'abord s'il y a des liens existants
        association_links = load_existing_links()
        
        # Si pas de liens existants ou si on force la récupération, récupérer les liens
        if not association_links or FORCE_LINK_RETRIEVAL:
            logger.info("Récupération des liens d'associations...")
            association_links = get_all_association_links()
            
            # Sauvegarde des liens
            links_file = f'results/association_links_{search_term}_{timestamp}.txt'
            with open(links_file, 'w', encoding='utf-8') as f:
                for link in association_links:
                    f.write(f"{link}\n")
            logger.info(f"Liens sauvegardés dans {links_file}")
        else:
            logger.info(f"Utilisation des {len(association_links)} liens existants depuis le fichier")
        
        # Étape 3: Récupérer les détails pour chaque association
        total_links = len(association_links)
        links_to_process = [link for link in association_links if link not in skip_urls]
        total_links_to_process = len(links_to_process)
        
        if total_links_to_process < total_links:
            logger.info(f"{total_links - total_links_to_process} liens seront ignorés car déjà traités.")
        
        if total_links_to_process == 0:
            logger.info("Tous les liens ont déjà été traités. Rien à faire.")
            return
        
        logger.info(f"{total_links_to_process} liens à traiter...")
        
        start_time = time.time() # Heure de début du traitement des détails
        processed_in_session = 0  # Nombre d'associations traitées dans cette session
        
        # Pour éviter les blocages, réorganiser l'ordre de traitement pour ne pas suivre un motif
        # évident (comme toutes les associations contenant "bde" d'affilée)
        random.shuffle(links_to_process)
        
        # Traitement par lots pour éviter une surcharge
        BATCH_SIZE = 100  # Nombre de liens à traiter avant une pause plus longue
        
        for batch_index in range(0, len(links_to_process), BATCH_SIZE):
            batch = links_to_process[batch_index:batch_index + BATCH_SIZE]
            
            # Traiter un lot
            for i, link in enumerate(batch):
                # Vérifier si le programme a été interrompu
                if interrupted:
                    break
                
                # Position globale dans la liste
                global_index = batch_index + i
                processed_in_session += 1
                
                # Calcul et affichage de l'ETA basé sur la vitesse de traitement de cette session
                links_processed = global_index + 1
                if processed_in_session > 1:  # Commencer l'estimation après le premier lien
                    elapsed_time = time.time() - start_time
                    avg_time_per_link = elapsed_time / processed_in_session
                    links_remaining = total_links_to_process - links_processed
                    eta_seconds = avg_time_per_link * links_remaining
                    eta_formatted = format_time(eta_seconds)
                    logger.info(f"Traitement association {links_processed}/{total_links_to_process} - ETA: {eta_formatted}")
                else:
                    logger.info(f"Traitement association {links_processed}/{total_links_to_process}...")
                
                # Vérifier les erreurs 403 consécutives
                if consecutive_403_errors >= MAX_CONSECUTIVE_403:
                    logger.warning(f"Détection de blocage potentiel ({consecutive_403_errors} erreurs 403 consécutives)")
                    logger.info("Pause longue pour éviter le blocage permanent...")
                    time.sleep(DELAY_AFTER_403 * 2)
                    consecutive_403_errors = 0
                
                # Traitement du lien
                details = get_association_details(link)
                if details:
                    results.append(details)
                    
                    # Sauvegarde intermédiaire 
                    if links_processed % 5 == 0 or consecutive_403_errors > 0:
                        save_results()
                
                # Délai variable entre les liens
                delay_factor = random.uniform(1.0, 2.0)
                random_delay(delay_factor, delay_factor * 1.5)
            
            # Après chaque lot, faire une pause plus longue pour éviter de se faire bloquer
            if batch_index + BATCH_SIZE < len(links_to_process) and not interrupted:
                pause_duration = random.uniform(30, 60)  # 30-60 secondes
                logger.info(f"Pause de {pause_duration:.1f} secondes après le traitement d'un lot de {len(batch)} associations...")
                time.sleep(pause_duration)
        
        # Étape 4: Créer un fichier CSV avec les résultats et analyser
        final_results = []
        
        # Sauvegarder les résultats restants s'il y en a
        if results:
            # Copier les résultats avant de les sauvegarder pour l'analyse
            final_results = results.copy()
            save_results() # Sauvegarde finale
            
        # Charger et analyser toutes les données si on a repris un fichier existant
        if save_results.output_file and os.path.exists(save_results.output_file):
            try:
                all_data = []
                with open(save_results.output_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    all_data = list(reader)
                
                logger.info(f"Scraping terminé avec succès. {len(all_data)} associations au total dans le fichier.")
                
                # Analyser toutes les données
                if all_data:
                    print("\nAnalyse de toutes les données du fichier...")
                    analyze_results(all_data)
            except Exception as e:
                logger.error(f"Erreur lors de l'analyse des données finales: {e}")
                # Analyser au moins les derniers résultats si possible
                if final_results:
                    analyze_results(final_results)
        elif final_results:
            # Si pas de fichier existant, analyser les résultats obtenus
            logger.info(f"Scraping terminé avec {len(final_results)} associations récupérées")
            analyze_results(final_results)
        else:
            logger.warning("Aucun résultat trouvé.")
            
    except Exception as e:
        logger.error(f"Erreur lors du scraping: {e}")
        # Sauvegarder les résultats même en cas d'erreur
        results_to_analyze = results.copy() if results else []
        save_results()
        # Analyser les données obtenues
        if results_to_analyze:
            analyze_results(results_to_analyze)
    finally:
        logger.info("Scraping terminé")

if __name__ == "__main__":
    main()