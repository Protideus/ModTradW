import requests
import json
import time
from pathlib import Path
from typing import Dict, Any

# ==============================================================================
# CONFIGURATION & CONSTANTES
# ==============================================================================
BASE_URL = "https://api.warframe.market/v2"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 0.3s d'attente entre les requêtes pour respecter la limite de l'API (~3 requêtes/s)
DELAY = 0.3  

# Les vrais tags officiels de la V2
ALLOWED_TAGS = {"mod", "arcane_enhancement"}

# ==============================================================================
# FONCTIONS DE RÉCUPÉRATION (API)
# ==============================================================================

def fetch_item_details(slug: str) -> Dict:
    """Récupère la fiche détaillée d'un item sur l'endpoint au singulier (/v2/item/{slug})."""
    for attempt in range(3):
        try:
            # CORRECTION CRITIQUE : l'endpoint de détail est bien '/item/{slug}' au singulier
            response = requests.get(f"{BASE_URL}/item/{slug}", headers=HEADERS)
            response.raise_for_status()
            
            # En V2, l'objet complet de l'item est imbriqué dans data -> item
            return response.json().get("data", {}).get("item", {})
        except Exception as e:
            if attempt == 2:
                print(f"❌ Échec définitif sur {slug} après 3 tentatives. Erreur: {e}")
                return {}
            wait_time = DELAY * (2 ** attempt)
            time.sleep(wait_time)
    return {}

# ==============================================================================
# LOGIQUE DE CONSTITUTION DE LA BASE DE DONNÉES
# ==============================================================================

def build_database() -> Dict[str, Any]:
    """Boucle principale : Récupère le manifeste global puis extrait chaque mod/arcane."""
    print("📡 Récupération du manifeste global (API V2 /items)...")
    try:
        # L'endpoint de la liste globale reste bien '/items' au pluriel
        response = requests.get(f"{BASE_URL}/items", headers=HEADERS)
        response.raise_for_status()
        res_json = response.json()
        
        items_list = res_json.get("data", [])
        print(f"✅ Manifeste récupéré : {len(items_list)} items trouvés au total.")
        
    except Exception as e:
        print(f"❌ Impossible de récupérer le manifeste global : {e}")
        return {}

    database = {}
    processed = 0
    ignored_count = 0

    for item in items_list:
        slug = item.get("slug")
        if not slug:
            continue

        processed += 1
        
        # Log de suivi condensé pour GitHub Actions
        if processed % 100 == 0 or processed == len(items_list):
            print(f"➡️ Avancement : [{processed}/{len(items_list)}] fiches analysées...")
        
        details = fetch_item_details(slug)
        if not details:
            time.sleep(DELAY)
            continue

        # Récupération et normalisation des tags de la fiche détaillée
        raw_tags = details.get("tags", [])
        tags = [str(t).strip().lower() for t in raw_tags] if raw_tags else []

        # --- FILTRAGE PAR TAG STRICT ---
        if not tags or not any(tag in ALLOWED_TAGS for tag in tags):
            ignored_count += 1
            time.sleep(DELAY)
            continue

        # Extraction de la structure linguistique i18n
        i18n_data = details.get("i18n", {})
        
        # Reconstruction de la table des noms multilingues
        names = {}
        for lang, lang_data in i18n_data.items():
            if isinstance(lang_data, dict) and "name" in lang_data:
                names[lang] = lang_data["name"]

        # Extraction des données en anglais pour les détails génériques
        en_data = i18n_data.get("en", {}) if isinstance(i18n_data, dict) else {}

        # Structuration de la ligne pour ta base de données finale
        database[slug] = {
            "url_name": slug,
            "names": names,
            "description": en_data.get("description", ""),
            "wiki_link": en_data.get("wikiLink"),  # Structure V2 : wikiLink avec 'L' majuscule
            "image_link": en_data.get("thumb"),
            "tags": raw_tags
        }

        time.sleep(DELAY)

    print(f"\n⚡ Filtrage terminé : {ignored_count} items non pertinents ont été ignorés.")
    print(f"📦 Nombre de mods/arcanes valides conservés : {len(database)}")
    return database


def add_umbra_mods(database: Dict) -> Dict:
    """Injection manuelle des 5 mods Umbra exclusifs (non échangeables)."""
    print("🛠️ Injection des mods Umbra manuels...")
    umbra_data = {
  "umbral_intensify": {
    "url_name": "umbral_intensify",
    "names": {
      "en": "Umbral Intensify",
      "ru": "Умбральное Усиление",
      "ko": "엄브랄 인텐시파이",
      "fr": "Intensification Umbrale",
      "sv": "Umbral Intensify",
      "de": "Umbral Intensify",
      "zh-hant": "影幕強化",
      "zh-hans": "影幕强化",
      "pt": "Umbral Intensify",
      "es": "Intensificación Umbral",
      "pl": "Umbral Intensify",
      "cs": "Umbral Intensify",
      "uk": "Умбральне Посилення",
      "it": "Intensificazione Umbrale"
    },
    "description": "+44% Ability Strength\n+11% Sentient Damage Resistance",
    "wiki_link": "https://wiki.warframe.com/w/Umbral_Intensify",
    "tags": [
      "mod",
      "legendary",
      "warframe",
      "umbra"
    ]
  },
  "umbral_vitality": {
    "url_name": "umbral_vitality",
    "names": {
      "en": "Umbral Vitality",
      "ru": "Умбральная Жизнеспособность",
      "ko": "엄브랄 바이탈리티",
      "fr": "Vitalité Umbrale",
      "sv": "Umbral Vitality",
      "de": "Umbral Vitality",
      "zh-hant": "影幕生命",
      "zh-hans": "影幕生命",
      "pt": "Umbral Vitality",
      "es": "Vitalidad Umbral",
      "pl": "Umbral Vitality",
      "cs": "Umbral Vitality",
      "uk": "Умбральна Життєздатність",
      "it": "Vitalità Umbrale"
    },
    "description": "+440% Health\n+11% Sentient Damage Resistance",
    "wiki_link": "https://wiki.warframe.com/w/Umbral_Vitality",
    "tags": [
      "mod",
      "legendary",
      "warframe",
      "umbra"
    ]
  },
  "umbral_fiber": {
    "url_name": "umbral_fiber",
    "names": {
      "en": "Umbral Fiber",
      "ru": "Умбральное Волокно",
      "ko": "엄브랄 파이버",
      "fr": "Fibres Umbrales",
      "sv": "Umbral Fiber",
      "de": "Umbral Fiber",
      "zh-hant": "影幕纖維",
      "zh-hans": "影幕纤维",
      "pt": "Umbral Fiber",
      "es": "Fibra Umbral",
      "pl": "Umbral Fiber",
      "cs": "Umbral Fiber",
      "uk": "Умбральне Волокно",
      "it": "Fibra Umbrale"
    },
    "description": "+660% Armor\n+11% Sentient Damage Resistance",
    "wiki_link": "https://wiki.warframe.com/w/Umbral_Fiber",
    "tags": [
      "mod",
      "legendary",
      "warframe",
      "umbra"
    ]
  },
  "sacrificial_steel": {
    "url_name": "sacrificial_steel",
    "names": {
      "en": "Sacrificial Steel",
      "ru": "Жертвенная Сталь",
      "ko": "삭리피셜 스틸",
      "fr": "Acier Sacrificiel",
      "sv": "Sacrificial Steel",
      "de": "Opferstahl",
      "zh-hant": "犧牲鋼",
      "zh-hans": "牺牲钢",
      "pt": "Sacrificial Steel",
      "es": "Acero Sacrificial",
      "pl": "Sacrificial Steel",
      "cs": "Sacrificial Steel",
      "uk": "Жертвена Сталь",
      "it": "Acciaio Sacrificale"
    },
    "description": "+220% Critical Chance (x2 for Heavy Attacks)\n+30% Damage to Sentients",
    "wiki_link": "https://wiki.warframe.com/w/Sacrificial_Steel",
    "tags": [
      "mod",
      "legendary",
      "melee",
      "umbra"
    ]
  },
  "sacrificial_pressure": {
    "url_name": "sacrificial_pressure",
    "names": {
      "en": "Sacrificial Pressure",
      "ru": "Жертвенное Давление",
      "ko": "삭리피셜 프레셔",
      "fr": "Pression Sacrificielle",
      "sv": "Sacrificial Pressure",
      "de": "Opferdruck",
      "zh-hant": "犧牲壓力",
      "zh-hans": "牺牲压力",
      "pt": "Sacrificial Pressure",
      "es": "Presión Sacrificial",
      "pl": "Sacrificial Pressure",
      "cs": "Sacrificial Pressure",
      "uk": "Жертвений Тиск",
      "it": "Pressione Sacrificale"
    },
    "description": "+110% Melee Damage\n+30% Damage to Sentients",
    "wiki_link": "https://wiki.warframe.com/w/Sacrificial_Pressure",
    "tags": [
      "mod",
      "legendary",
      "melee",
      "umbra"
    ]
  }
    }
    database.update(umbra_data)
    return database


def save_json(database: Dict, output_path: Path):
    """Sauvegarde la base de données au format JSON structuré propre (UTF-8)."""
    metadata = {
        "total_items": len(database),
        "source": "Warframe.Market API V2",
        "note": "Extraction par tag strict (mod & arcane_enhancement)"
    }

    final_db = {
        "metadata": metadata,
        "items": database
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_db, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Base de données JSON sauvegardée : {len(database)} items.")
    print(f"   → {output_path}")


# ==============================================================================
# POINT D'ENTRÉE
# ==============================================================================
if __name__ == "__main__":
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    db = build_database()
    
    if db:
        db = add_umbra_mods(db)
        save_json(db, output_dir / "mods_database.json")
    else:
        print("❌ Script interrompu car la base de données extraite est vide.")
