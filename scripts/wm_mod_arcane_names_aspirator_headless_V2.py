import requests
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Set

# ==============================================================================
# CONFIGURATION & CONSTANTES
# ==============================================================================
BASE_URL = "https://api.warframe.market/v2"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

DELAY = 0.3  
ALLOWED_TAGS = {"mod", "arcane_enhancement"}

# Chemins des fichiers de persistance
DATA_DIR = Path("data")
DATABASE_PATH = DATA_DIR / "mods_database.json"
BLACKLIST_PATH = DATA_DIR / "ignored_slugs.json"

# ==============================================================================
# GESTION DU CACHE ET DE LA BLACKLIST
# ==============================================================================

def load_existing_database() -> Dict[str, Any]:
    """Charge la base de données actuelle si elle existe."""
    if DATABASE_PATH.exists():
        try:
            with open(DATABASE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("items", {})
        except Exception:
            print("⚠️ Impossible de lire la base de données existante.")
    return {}

def load_blacklist() -> Set[str]:
    """Charge la liste des slugs ignorés (ni mods ni arcanes)."""
    if BLACKLIST_PATH.exists():
        try:
            with open(BLACKLIST_PATH, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except Exception:
            print("⚠️ Impossible de lire la blacklist existante.")
    return set()

def save_blacklist(blacklist: Set[str]):
    """Sauvegarde la liste d'exclusion pour les prochains runs."""
    with open(BLACKLIST_PATH, 'w', encoding='utf-8') as f:
        json.dump(sorted(list(blacklist)), f, ensure_ascii=False, indent=2)
    print(f"💾 Blacklist mise à jour : {len(blacklist)} items exclus pour les prochains runs.")

# ==============================================================================
# FONCTIONS DE RÉCUPÉRATION (API)
# ==============================================================================

def fetch_item_details(slug: str) -> Dict:
    """Récupère la fiche détaillée d'un item sur l'endpoint au singulier (/v2/item/{slug})."""
    for attempt in range(3):
        try:
            response = requests.get(f"{BASE_URL}/item/{slug}", headers=HEADERS)
            response.raise_for_status()
            return response.json().get("data", {}).get("item", {})
        except Exception as e:
            if attempt == 2:
                print(f"❌ Échec définitif sur {slug} après 3 tentatives. Erreur: {e}")
                return {}
            wait_time = DELAY * (2 ** attempt)
            time.sleep(wait_time)
    return {}

# ==============================================================================
# LOGIQUE PRINCIPALE
# ==============================================================================

def build_database() -> Dict[str, Any]:
    """Boucle principale : gère les nouveautés quotidiennes ou force un check-up trimestriel."""
    print("📡 Récupération du manifeste global (API V2 /items)...")
    try:
        response = requests.get(f"{BASE_URL}/items", headers=HEADERS)
        response.raise_for_status()
        items_list = response.json().get("data", [])
        print(f"✅ Manifeste récupéré : {len(items_list)} items trouvés au total.")
    except Exception as e:
        print(f"❌ Impossible de récupérer le manifeste global : {e}")
        return {}

    # --- AUTOMATISATION DU CHECK-UP TRIMESTRIEL ---
    now = datetime.now()
    # Trimestres : 1er Janvier (1/1), 1er Avril (1/4), 1er Juillet (1/7), 1er Octobre (1/10)
    is_first_of_quarter = now.day == 1 and now.month in [1, 4, 7, 10]

    if is_first_of_quarter:
        print(f"📅 Date actuelle : {now.strftime('%d/%m/%Y')}")
        print("🔄 [CHECK-UP TRIMESTRIEL] Détection du premier jour du trimestre !")
        print("🗑️ Force-refresh : Réinitialisation temporaire de la mémoire pour tout re-vérifier...")
        database = {}
        blacklist = set()
    else:
        # Chargement normal depuis la mémoire locale (Incrémental quotidien)
        database = load_existing_database()
        blacklist = load_blacklist()
        print(f"🧠 Mode quotidien : {len(database)} mods en cache | {len(blacklist)} items connus à ignorer.")

    processed = 0
    analyzed_count = 0
    skipped_count = 0

    for item in items_list:
        slug = item.get("slug")
        if not slug:
            continue

        processed += 1

        # Sauter si l'item est connu (uniquement hors mode check-up trimestriel)
        if slug in blacklist or slug in database:
            skipped_count += 1
            continue

        # Extraction de la fiche (Nouveautés ou run complet trimestriel)
        analyzed_count += 1
        
        # Log périodique pour suivre l'avancement sans inonder la console GitHub
        if analyzed_count % 100 == 0 or processed == len(items_list):
            print(f"➡️ Analyse en cours... Fiches requêtées lors de ce run : {analyzed_count}")

        details = fetch_item_details(slug)
        if not details:
            time.sleep(DELAY)
            continue

        raw_tags = details.get("tags", [])
        tags = [str(t).strip().lower() for t in raw_tags] if raw_tags else []

        # --- FILTRAGE PAR TAG STRICT ---
        if not tags or not any(tag in ALLOWED_TAGS for tag in tags):
            blacklist.add(slug)
            time.sleep(DELAY)
            continue

        # Extraction i18n
        i18n_data = details.get("i18n", {})
        names = {}
        for lang, lang_data in i18n_data.items():
            if isinstance(lang_data, dict) and "name" in lang_data:
                names[lang] = lang_data["name"]

        en_data = i18n_data.get("en", {}) if isinstance(i18n_data, dict) else {}

        # Stockage propre
        database[slug] = {
            "url_name": slug,
            "names": names,
            "description": en_data.get("description", ""),
            "wiki_link": en_data.get("wikiLink"),
            "image_link": en_data.get("thumb"),
            "tags": raw_tags
        }

        time.sleep(DELAY)

    print(f"\n⚡ Traitement terminé : {skipped_count} items ignorés (déjà en mémoire).")
    print(f"📥 {analyzed_count} requêtes réelles ont été exécutées au total durant ce run.")
    
    # Sauvegarde des fichiers mis à jour
    save_blacklist(blacklist)
    
    return database


def add_umbra_mods(database: Dict) -> Dict:
    """Injection manuelle des 5 mods Umbra exclusifs (non échangeables)."""
    print("🛠️ Injection des mods Umbra manuels...")
    umbra_data = {
        "umbral_intensify": {
            "url_name": "umbral_intensify",
            "names": {
                "en": "Umbral Intensify", "ru": "Умбральное Усиление", "ko": "엄브랄 인텐시파и",
                "fr": "Intensification Umbrale", "sv": "Umbral Intensify", "de": "Umbral Intensify",
                "zh-hant": "影幕強化", "zh-hans": "影幕强化", "pt": "Umbral Intensify",
                "es": "Intensification Umbral", "pl": "Umbral Intensify", "cs": "Umbral Intensify",
                "uk": "Умбральне Посилення", "it": "Intensificazione Umbrale"
            },
            "description": "+44% Ability Strength\n+11% Sentient Damage Resistance",
            "wiki_link": "https://warframe.fandom.com/wiki/Umbral_Intensify",
            "tags": ["mod", "legendary", "warframe", "umbra"]
        },
        "umbral_vitality": {
            "url_name": "umbral_vitality",
            "names": {
                "en": "Umbral Vitality", "ru": "Умбральная Жизнеспособность", "ko": "엄브랄 바이탈리티",
                "fr": "Vitalité Umbrale", "sv": "Umbral Vitality", "de": "Umbral Vitality",
                "zh-hant": "影幕生命", "zh-hans": "影幕生命", "pt": "Umbral Vitality",
                "es": "Vitalidad Umbral", "pl": "Umbral Vitality", "cs": "Umbral Vitality",
                "uk": "Умбральна Життєздатність", "it": "Vitalità Umbrale"
            },
            "description": "+440% Health\n+11% Sentient Damage Resistance",
            "wiki_link": "https://warframe.fandom.com/wiki/Umbral_Vitality",
            "tags": ["mod", "legendary", "warframe", "umbra"]
        },
        "umbral_fiber": {
            "url_name": "umbral_fiber",
            "names": {
                "en": "Umbral Fiber", "ru": "Умбральное Волокно", "ko": "엄б랄 파이버",
                "fr": "Fibres Umbrales", "sv": "Umbral Fiber", "de": "Umbral Fiber",
                "zh-hant": "影幕纖維", "zh-hans": "影幕纤维", "pt": "Umbral Fiber",
                "es": "Fibra Umbral", "pl": "Umbral Fiber", "cs": "Umbral Fiber",
                "uk": "Умбральное Волокно", "it": "Fibra Umbrale"
            },
            "description": "+660% Armor\n+11% Sentient Damage Resistance",
            "wiki_link": "https://warframe.fandom.com/wiki/Umbral_Fiber",
            "tags": ["mod", "legendary", "warframe", "umbra"]
        },
        "sacrificial_steel": {
            "url_name": "sacrificial_steel",
            "names": {
                "en": "Sacrificial Steel", "ru": "Жертвенная Сталь", "ko": "삭리피셜 스틸",
                "fr": "Acier Sacrificiel", "sv": "Sacrificial Steel", "de": "Opferstahl",
                "zh-hant": "犧牲鋼", "zh-hans": "牺牲钢", "pt": "Sacrificial Steel",
                "es": "Acero Sacrificial", "pl": "Sacrificial Steel", "cs": "Sacrificial Steel",
                "uk": "Жертвена Сталь", "it": "Acciaio Sacrificale"
            },
            "description": "+220% Critical Chance (x2 for Heavy Attacks)\n+30% Damage to Sentients",
            "wiki_link": "https://warframe.fandom.com/wiki/Sacrificial_Steel",
            "tags": ["mod", "legendary", "melee", "umbra"]
        },
        "sacrificial_pressure": {
            "url_name": "sacrificial_pressure",
            "names": {
                "en": "Sacrificial Pressure", "ru": "Жертвенное Давление", "ko": "삭리피셜 프решер",
                "fr": "Pression Sacrificielle", "sv": "Sacrificial Pressure", "de": "Opferdruck",
                "zh-hant": "犧牲壓力", "zh-hans": "牺牲压力", "pt": "Sacrificial Pressure",
                "es": "Presión Sacrificial", "pl": "Sacrificial Pressure", "cs": "Sacrificial Pressure",
                "uk": "Жертвений Тиск", "it": "Pressione Sacrificale"
            },
            "description": "+110% Melee Damage\n+30% Damage to Sentients",
            "wiki_link": "https://warframe.fandom.com/wiki/Sacrificial_Pressure",
            "tags": ["mod", "legendary", "melee", "umbra"]
        }
    }
    database.update(umbra_data)
    return database


def save_json(database: Dict):
    """Sauvegarde la base de données au format JSON propre."""
    metadata = {
        "total_items": len(database),
        "source": "Warframe.Market API V2",
        "note": "Mise à jour quotidienne rapide / Check-up trimestriel automatique"
    }

    final_db = {
        "metadata": metadata,
        "items": database
    }

    with open(DATABASE_PATH, 'w', encoding='utf-8') as f:
        json.dump(final_db, f, ensure_ascii=False, indent=2)

    print(f"🎉 Base de données JSON sauvegardée : {len(database)} items au total.")
    print(f"   → {DATABASE_PATH}")


# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================
if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)

    db = build_database()
    
    if db:
        db = add_umbra_mods(db)
        save_json(db)
    else:
        print("❌ Script interrompu car la base de données est indisponible.")
