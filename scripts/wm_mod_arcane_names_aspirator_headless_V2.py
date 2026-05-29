import requests
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Set
import sys
import io

# Force UTF-8 encoding pour les emojis (Important pour PowerShell)
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

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

def fetch_item_details(slug: str) -> Any:
    """
    Récupère les détails d'un item.
    L'API Warframe Market V2 retourne le détail dans la clé 'data'.
    """
    global FIRST_API_CALL_LOGGED
    try:
        response = requests.get(f"{BASE_URL}/item/{slug}", headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            full_data = response.json()
            
            # --- BLOC DE DEBUG (S'affiche une seule fois dans vos logs) ---
            if not FIRST_API_CALL_LOGGED:
                print(f"\n🔍 DEBUG - Structure API pour '{slug}':")
                print(json.dumps(full_data, indent=2, ensure_ascii=False)[:500] + "...")
                FIRST_API_CALL_LOGGED = True
            
            # On extrait les données de l'item
            return full_data.get("data")
        elif response.status_code == 404:
            # Item n'existe pas
            return None
        else:
            print(f"⚠️ HTTP {response.status_code} sur {slug}")
            return None
    except requests.exceptions.Timeout:
        print(f"⚠️ Timeout sur {slug} (10s)")
    except requests.exceptions.ConnectionError:
        print(f"⚠️ Erreur de connexion sur {slug}")
    except Exception as e:
        print(f"⚠️ Erreur réseau sur {slug}: {e}")
    return None

def normalize_item_data(api_item: Dict) -> Dict:
    """
    Transforme les données de l'API au format attendu.
    API → Format normalisé
    """
    if not api_item:
        return {}
    
    # Extraction des TOUS les noms multilingues depuis i18n
    names = {}
    description = None
    wiki_link = None
    
    i18n = api_item.get("i18n", {})
    
    # Récupérer TOUS les noms dans toutes les langues disponibles
    for lang, lang_data in i18n.items():
        if isinstance(lang_data, dict):
            names[lang] = lang_data.get("name", "")
    
    # Prioriser l'anglais pour description et wiki_link (MUST BE EN ONLY)
    if "en" in i18n and isinstance(i18n["en"], dict):
        description = i18n["en"].get("description")
        wiki_link = i18n["en"].get("wikiLink")
    
    # Construction de l'item normalisé
    normalized = {
        "url_name": api_item.get("slug", ""),
        "names": names,
        "tags": api_item.get("tags", []),
    }
    
    # Ajouter les champs optionnels s'ils existent
    if description:
        normalized["description"] = description
    if wiki_link:
        normalized["wiki_link"] = wiki_link
    
    # Ajouter d'autres champs utiles
    if "rarity" in api_item:
        normalized["rarity"] = api_item["rarity"]
    if "tradable" in api_item:
        normalized["tradable"] = api_item["tradable"]
    if "tradingTax" in api_item:
        normalized["tradingTax"] = api_item["tradingTax"]
    if "maxRank" in api_item:
        normalized["maxRank"] = api_item["maxRank"]
    
    return normalized

# ==============================================================================
# LOGIQUE DE CONSTRUCTION
# ==============================================================================

def build_database():
    """Boucle principale pour remplir le dictionnaire de données."""
    
    # 1. Chargement de l'existant avec gestion d'erreur
    database = {}
    if DATABASE_PATH.exists():
        try:
            with open(DATABASE_PATH, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:  # Vérifier que le fichier n'est pas vide
                    old_data = json.loads(content)
                    database = old_data.get("items", {})
                    print(f"✅ Base de données existante chargée : {len(database)} items")
                else:
                    print("⚠️ Fichier mods_database.json vide, création d'une nouvelle base")
        except json.JSONDecodeError as e:
            print(f"⚠️ Erreur JSON dans mods_database.json : {e}")
            print("🔄 Création d'une nouvelle base de données")
            database = {}
        except Exception as e:
            print(f"⚠️ Erreur lors de la lecture : {e}")
            database = {}

    blacklist = set()
    if BLACKLIST_PATH.exists():
        try:
            with open(BLACKLIST_PATH, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    blacklist = set(json.loads(content))
        except (json.JSONDecodeError, Exception):
            pass  # Recommencer avec une liste vide si erreur

    # 2. Récupération du manifeste (liste de tous les items) [5]
    print("📡 Récupération du manifeste global...")
    response = requests.get(f"{BASE_URL}/items", headers=HEADERS)
    all_items = response.json().get("data", [])
    total = len(all_items)
    print(f"✅ {total} items trouvés. Début de l'analyse...")

    new_count = 0
    
    # 3. Parcours de tous les items
    for index, item_short in enumerate(all_items):
        slug = item_short.get("slug") or item_short.get("url_name")

        # Skip si déjà en base ou si c'est un item qu'on sait inutile
        if not slug or slug in database or slug in blacklist:
            continue

        # Requête de détail
        item_details = fetch_item_details(slug)
        time.sleep(DELAY) # Pause pour le Rate Limit [2, 6]

        if item_details:
            main_item = item_details if isinstance(item_details, dict) else (item_details[0] if item_details else None)
            tags = set(main_item.get("tags", [])) if main_item else set()

            if tags.intersection(ALLOWED_TAGS):
                # Normaliser les données avant de les stocker
                normalized_item = normalize_item_data(main_item)
                database[slug] = normalized_item
                new_count += 1
            else:
                # Si ce n'est ni un mod ni une arcane, on blacklist
                blacklist.add(slug)

        # Logs de progression tous les 500 items pour GitHub Actions
        if (index + 1) % 500 == 0 or (index + 1) == total:
            print(f"🕒 Progression : {index + 1}/{total} | Nouveaux ajoutés : {new_count}")

    # 4. Sauvegarde de la blacklist pour le prochain run (toujours créé)
    try:
        with open(BLACKLIST_PATH, 'w', encoding='utf-8') as f:
            json.dump(sorted(list(blacklist)), f, indent=2, ensure_ascii=False)
        print(f"💾 Blacklist sauvegardée : {len(blacklist)} items ignorés")
    except Exception as e:
        print(f"⚠️ Erreur lors de la sauvegarde de la blacklist : {e}")

    return database

def add_umbra_mods(database: Dict) -> Dict:
    """Injection manuelle des mods Umbra (car non listés dans l'API publique) [7]."""
    print("🛠️ Injection des mods Umbra...")
    # Vos données Umbra (extraites de votre source 12) - format normalisé
    umbra_mods = [
        {
            "url_name": "umbral_intensify",
            "names": {"en": "Umbral Intensify", "fr": "Intensité Umbrale"},
            "tags": ["mod", "umbra", "legendary"],
            "description": "+440% Power Strength\n+11% Sentient Damage Resistance"
        },
        {
            "url_name": "umbral_vitality",
            "names": {"en": "Umbral Vitality", "fr": "Vitalité Umbrale"},
            "tags": ["mod", "umbra", "legendary"],
            "description": "+440% Health\n+11% Sentient Damage Resistance"
        },
        {
            "url_name": "umbral_fiber",
            "names": {"en": "Umbral Fiber", "fr": "Fibre Umbrale"},
            "tags": ["mod", "umbra", "legendary"],
            "description": "+440% Armor\n+11% Sentient Damage Resistance"
        },
        {
            "url_name": "sacrificial_steel",
            "names": {"en": "Sacrificial Steel", "fr": "Acier Sacrificiel"},
            "tags": ["mod", "sacrificial", "legendary"],
            "description": "+440% Melee Damage\n+11% Sentient Damage Resistance"
        },
        {
            "url_name": "sacrificial_pressure",
            "names": {"en": "Sacrificial Pressure", "fr": "Pression Sacrificielle"},
            "tags": ["mod", "sacrificial", "legendary"],
            "description": "+330% Status Chance\n+11% Sentient Damage Resistance"
        }
    ]
    
    for mod in umbra_mods:
        slug = mod["url_name"]
        if slug not in database:
            database[slug] = mod
    
    return database

if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)
    
    try:
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
    except KeyboardInterrupt:
        print("\n⚠️ Script interrompu par l'utilisateur")
    except Exception as e:
        print(f"❌ Erreur critique : {e}")
        import traceback
        traceback.print_exc()
