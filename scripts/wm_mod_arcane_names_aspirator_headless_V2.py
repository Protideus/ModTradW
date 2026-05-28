import requests
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Set

# ==============================================================================
# CONFIGURATION & RÉGLAGES
# ==============================================================================

# L'adresse de base de l'API Warframe Market (V2) [4, 5]
BASE_URL = "https://api.warframe.market/v2"

# Délai entre les requêtes pour ne pas être banni (Limite: 3 req/s) [5]
# On utilise 0.4s pour être en sécurité (environ 2.5 req/s)
DELAY = 0.4 

# "L'identité" du script pour l'API. Indispensable pour passer les protections [4]
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "WFM-Aspirator-Bot/2.0 (GitHub Action)"
}

# Les catégories d'objets que l'on veut garder [6]
ALLOWED_TAGS = {"mod", "arcane_enhancement"}

# Chemins des fichiers (Path permet de gérer les dossiers proprement) [6]
DATA_DIR = Path("data")
DATABASE_PATH = DATA_DIR / "mods_database.json"
BLACKLIST_PATH = DATA_DIR / "ignored_slugs.json"

# ==============================================================================
# FONCTIONS DE GESTION DES FICHIERS (PERSISTANCE)
# ==============================================================================

def load_local_data():
    """Charge les données existantes (Base de données et Blacklist)."""
    db_content = {"version": "0.0.0", "items": {}}
    blacklist = set()

    # On essaie de charger la DB actuelle [6]
    if DATABASE_PATH.exists():
        with open(DATABASE_PATH, 'r', encoding='utf-8') as f:
            db_content = json.load(f)
    
    # On charge la liste des objets inutiles (pour ne pas les scanner à nouveau) [7]
    if BLACKLIST_PATH.exists():
        with open(BLACKLIST_PATH, 'r', encoding='utf-8') as f:
            blacklist = set(json.load(f))
            
    return db_content, blacklist

# ==============================================================================
# COMMUNICATIONS AVEC L'API
# ==============================================================================

def get_server_version():
    """Vérifie la version actuelle des données sur le serveur WFM [3]."""
    try:
        response = requests.get(f"{BASE_URL}/versions", headers=HEADERS)
        return response.json().get("data", {}).get("version", "unknown")
    except:
        return None

def fetch_item_details(slug: str):
    """Récupère la fiche détaillée d'un seul objet [8]."""
    try:
        response = requests.get(f"{BASE_URL}/item/{slug}", headers=HEADERS)
        if response.status_code == 200:
            return response.json().get("data", {}).get("item", {})
    except Exception as e:
        print(f"⚠️ Erreur sur {slug}: {e}")
    return None

# ==============================================================================
# LOGIQUE PRINCIPALE
# ==============================================================================

def build_database():
    """Fonction coeur : compare, télécharge et assemble la base de données."""
    
    # 1. Préparation des données locales
    local_db, blacklist = load_local_data()
    database = local_db.get("items", {})
    local_version = local_db.get("version", "0.0.0")

    # 2. Vérification de la version du serveur [3]
    # C'est crucial : si le serveur n'a pas changé, on s'arrête là (économie de ressources)
    server_version = get_server_version()
    print(f"📡 Version Serveur: {server_version} | Version Locale: {local_version}")
    
    if server_version == local_version and server_version is not None:
        print("✅ La base de données est déjà à jour. Fin du processus.")
        return local_db 

    # 3. Récupération de la liste de tous les items existants [8]
    print("📥 Récupération de la liste globale des items...")
    response = requests.get(f"{BASE_URL}/items", headers=HEADERS)
    all_items = response.json().get("data", [])
    total_to_check = len(all_items)
    
    # 4. Boucle de mise à jour (Le cerveau du script)
    new_items_count = 0
    skipped_count = 0
    
    print(f"🔍 Analyse de {total_to_check} items potentiels...")
    
    for index, item in enumerate(all_items):
        slug = item.get("url_name")

        # On ignore si c'est déjà connu ou inutile
        if slug in database or slug in blacklist:
            skipped_count += 1
            continue

        # Si l'objet est inconnu, on demande ses détails à l'API
        details = fetch_item_details(slug)
        time.sleep(DELAY) # On attend pour respecter la limite [5]

        if details:
            # On vérifie si c'est un Mod ou une Arcane [6]
            item_tags = set(details.get("tags", []))
            if item_tags.intersection(ALLOWED_TAGS):
                # ICI : On enregistre bien l'objet dans notre dictionnaire (le correctif !)
                database[slug] = details
                new_items_count += 1
            else:
                # Sinon on le blacklist pour ne plus perdre de temps avec lui
                blacklist.add(slug)

        # LOGGING INTELLIGENT : On n'écrit pas tout, seulement tous les 500 items
        if (index + 1) % 500 == 0 or (index + 1) == total_to_check:
            percent = int(((index + 1) / total_to_check) * 100)
            print(f"🕒 Progression : {percent}% ({index + 1}/{total_to_check}) | Nouveaux: {new_items_count}")

    # 5. Sauvegarde de la blacklist mise à jour
    with open(BLACKLIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(sorted(list(blacklist)), f, ensure_ascii=False, indent=2)

    # On retourne la structure finale prête à être sauvegardée
    return {
        "version": server_version,
        "last_update": datetime.now().isoformat(),
        "items": database
    }

def add_umbra_mods(db_wrapper: Dict) -> Dict:
    """Injection des mods Umbra (car ils ne sont pas dans l'API publique) [9]."""
    print("🛠️ Injection des mods Umbra manuels...")
    # (Données Umbra abrégées pour la clarté)
    umbra_list = ["umbral_intensify", "umbral_vitality", "umbral_fiber", "sacrificial_steel", "sacrificial_pressure"]
    for u in umbra_list:
        if u not in db_wrapper["items"]:
            db_wrapper["items"][u] = {"url_name": u, "tags": ["mod", "umbra"]}
    return db_wrapper

if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    
    # Exécution du processus
    final_db = build_database()
    final_db = add_umbra_mods(final_db)
    
    # Sauvegarde finale [10, 11]
    with open(DATABASE_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_db, f, ensure_ascii=False, indent=2)
    
    print(f"🎉 Terminé ! Total en base : {len(final_db['items'])} items.")
