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
    "User-Agent": "WFM-Aspirator-V2-Bot"
}

HEADERS_EN = {
    "Accept": "application/json",
    "User-Agent": "WFM-Aspirator-V2-Bot",
    "Language": "en"
}

# Base path pour écrire data/ et blacklist de manière déterministe.
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "mods_database.json"
BLACKLIST_PATH = DATA_DIR / "ignored_slugs.json"

LANGUAGE_CODES = [
    "en", "fr", "de", "es", "it", "pt", "ru", "uk", "pl", "cs", "sv", "zh-hans", "zh-hant", "ko"
]

# Filtres pour ne garder que ce qui nous intéresse
ALLOWED_TAGS = {"mod", "arcane_enhancement"}

# Variable globale pour ne logger le contenu de l'API qu'une seule fois
FIRST_API_CALL_LOGGED = False

# ==============================================================================
# FONCTIONS DE RÉCUPÉRATION
# ==============================================================================

def get_server_version():
    """Vérifie la version actuelle sur le serveur pour éviter de tout rescanner [4]."""
    try:
        response = requests.get(f"{BASE_URL}/versions", headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("apiVersion") or data.get("data", {}).get("version")
    except Exception:
        return None


def load_existing_metadata() -> Dict[str, Any]:
    """Lit les métadonnées existantes dans mods_database.json, si elles sont disponibles."""
    if not DATABASE_PATH.exists():
        return {}

    try:
        with open(DATABASE_PATH, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                return {}
            data = json.loads(content)
            return data.get("metadata", {}) or {}
    except Exception:
        return {}


def fetch_manifest_names() -> tuple[list, Dict[str, Dict[str, str]]]:
    """Récupère les noms multilingues du manifeste pour toutes les langues voulues."""
    names_by_slug: Dict[str, Dict[str, str]] = {}
    all_items = []

    for index, lang in enumerate(LANGUAGE_CODES):
        headers = {**HEADERS, "Language": lang}
        print(f"📡 Récupération des noms ({lang})...")
        try:
            response = requests.get(f"{BASE_URL}/items", headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json().get("data", [])
        except Exception as e:
            print(f"⚠️ Échec de la récupération des noms pour {lang} : {e}")
            continue

        if index == 0:
            all_items = data

        for item in data:
            slug = item.get("slug") or item.get("url_name")
            if not slug:
                continue

            i18n = item.get("i18n", {})
            if not isinstance(i18n, dict):
                continue

            for code, lang_data in i18n.items():
                if isinstance(lang_data, dict) and lang_data.get("name"):
                    names_by_slug.setdefault(slug, {})[code] = lang_data["name"]

    return all_items, names_by_slug


def fetch_item_details(slug: str) -> Any:
    """
    Récupère les détails d'un item.
    L'API Warframe Market V2 retourne le détail dans la clé 'data'.
    """
    global FIRST_API_CALL_LOGGED
    try:
        response = requests.get(f"{BASE_URL}/item/{slug}", headers=HEADERS_EN, timeout=10)
        
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

def normalize_item_data(api_item: Dict, names: Dict[str, str] | None = None) -> Dict:
    """
    Transforme les données de l'API au format attendu.
    API → Format normalisé
    """
    if not api_item:
        return {}
    
    if names is None:
        names = {}
        i18n = api_item.get("i18n", {})
        for lang, lang_data in i18n.items():
            if isinstance(lang_data, dict) and lang_data.get("name"):
                names[lang] = lang_data.get("name", "")
    
    description = None
    wiki_link = None
    
    i18n = api_item.get("i18n", {})
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
    all_items, names_by_slug = fetch_manifest_names()
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
                normalized_item = normalize_item_data(main_item, names_by_slug.get(slug))
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
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BLACKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"📁 Blacklist path: {BLACKLIST_PATH}")
    print(f"📁 Database path: {DATABASE_PATH}")
    
    try:
        api_version = get_server_version()
        existing_metadata = load_existing_metadata()

        if api_version:
            print(f"ℹ️ Version API détectée : {api_version}")
            if existing_metadata.get("api_version") == api_version:
                print(f"✅ Version identique ({api_version}) trouvée dans mods_database.json, mise à jour ignorée.")
                sys.exit(0)
        else:
            print("⚠️ Impossible de récupérer la version API")

        # Lancement du processus
        final_items = build_database()
        final_items = add_umbra_mods(final_items)
        
        # Sauvegarde finale avec métadonnées
        metadata = {
            "last_update": datetime.now().isoformat(),
            "count": len(final_items)
        }
        if api_version:
            metadata["api_version"] = api_version

        output = {
            "metadata": metadata,
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
