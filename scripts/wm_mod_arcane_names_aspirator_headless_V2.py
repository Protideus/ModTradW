import requests
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Set

# ==============================================================================
# CONFIGURATION
# ==============================================================================

BASE_URL = "https://api.warframe.market/v2"
# Délai de 0.4s pour respecter la limite de 3 requêtes/seconde (1 / 0.33) [2]
DELAY = 0.4 

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "WFM-Aspirator-V2-Bot",
    "Language": "fr" # Pour récupérer les noms en français quand disponibles [3]
}

# Filtres pour ne garder que ce qui nous intéresse
ALLOWED_TAGS = {"mod", "arcane_enhancement"}

DATA_DIR = Path("data")
DATABASE_PATH = DATA_DIR / "mods_database.json"
BLACKLIST_PATH = DATA_DIR / "ignored_slugs.json"

# Variable globale pour ne logger le contenu de l'API qu'une seule fois
FIRST_API_CALL_LOGGED = False

# ==============================================================================
# FONCTIONS DE RÉCUPÉRATION
# ==============================================================================

def get_server_version():
    """Vérifie la version actuelle sur le serveur pour éviter de tout rescanner [4]."""
    try:
        response = requests.get(f"{BASE_URL}/versions", headers=HEADERS)
        return response.json().get("data", {}).get("version")
    except:
        return None

def fetch_item_details(slug: str) -> list:
    """
    Récupère les détails d'un item. 
    CORRECTIF : L'API V2 renvoie une liste dans la clé 'items' [1].
    """
    global FIRST_API_CALL_LOGGED
    try:
        response = requests.get(f"{BASE_URL}/item/{slug}", headers=HEADERS)
        if response.status_code == 200:
            full_data = response.json()
            
            # --- BLOC DE DEBUG (S'affiche une seule fois dans vos logs) ---
            if not FIRST_API_CALL_LOGGED:
                print(f"\n🔍 DEBUG - Structure API pour '{slug}':")
                print(json.dumps(full_data, indent=2, ensure_ascii=False)[:500] + "...")
                FIRST_API_CALL_LOGGED = True
            
            # On extrait la liste 'items' (pluriel)
            return full_data.get("data", {}).get("items", [])
    except Exception as e:
        print(f"⚠️ Erreur réseau sur {slug}: {e}")
    return []

# ==============================================================================
# LOGIQUE DE CONSTRUCTION
# ==============================================================================

def build_database():
    """Boucle principale pour remplir le dictionnaire de données."""
    
    # 1. Chargement de l'existant
    database = {}
    if DATABASE_PATH.exists():
        with open(DATABASE_PATH, 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            database = old_data.get("items", {})

    blacklist = set()
    if BLACKLIST_PATH.exists():
        with open(BLACKLIST_PATH, 'r', encoding='utf-8') as f:
            blacklist = set(json.load(f))

    # 2. Récupération du manifeste (liste de tous les items) [5]
    print("📡 Récupération du manifeste global...")
    response = requests.get(f"{BASE_URL}/items", headers=HEADERS)
    all_items = response.json().get("data", [])
    total = len(all_items)
    print(f"✅ {total} items trouvés. Début de l'analyse...")

    new_count = 0
    
    # 3. Parcours de tous les items
    for index, item_short in enumerate(all_items):
        slug = item_short.get("url_name")

        # Skip si déjà en base ou si c'est un item qu'on sait inutile
        if slug in database or slug in blacklist:
            continue

        # Requête de détail
        details_list = fetch_item_details(slug)
        time.sleep(DELAY) # Pause pour le Rate Limit [2, 6]

        if details_list:
            # On analyse le premier item de la liste renvoyée
            main_item = details_list
            tags = set(main_item.get("tags", []))

            if tags.intersection(ALLOWED_TAGS):
                # AJOUT CRUCIAL : On stocke l'item dans notre base
                database[slug] = main_item
                new_count += 1
            else:
                # Si ce n'est ni un mod ni une arcane, on blacklist
                blacklist.add(slug)

        # Logs de progression tous les 500 items pour GitHub Actions
        if (index + 1) % 500 == 0 or (index + 1) == total:
            print(f"🕒 Progression : {index + 1}/{total} | Nouveaux ajoutés : {new_count}")

    # 4. Sauvegarde de la blacklist pour le prochain run
    with open(BLACKLIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(sorted(list(blacklist)), f, indent=2)

    return database

def add_umbra_mods(database: Dict) -> Dict:
    """Injection manuelle des mods Umbra (car non listés dans l'API publique) [7]."""
    print("🛠️ Injection des mods Umbra...")
    # Vos données Umbra (extraites de votre source 12)
    umbra_slugs = ["umbral_intensify", "umbral_vitality", "umbral_fiber", "sacrificial_steel", "sacrificial_pressure"]
    for slug in umbra_slugs:
        if slug not in database:
            database[slug] = {"url_name": slug, "tags": ["mod", "umbra", "legendary"]}
    return database

if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    
    # Lancement du processus
    final_items = build_database()
    final_items = add_umbra_mods(final_items)
    
    # Sauvegarde finale avec métadonnées
    output = {
        "metadata": {
            "last_update": datetime.now().isoformat(),
            "count": len(final_items)
        },
        "items": final_items
    }
    
    with open(DATABASE_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"🎉 Terminé ! Base de données : {len(final_items)} items au total.")
