import requests
import json
import time
from pathlib import Path
from typing import Dict, Any

# ==============================================================================
# CONFIGURATION & CONSTANTES
# ==============================================================================
BASE_URL = "https://api.warframe.market/v2"

# Le User-Agent simule un navigateur Chrome pour éviter les blocages de sécurité
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Délai de sécurité en secondes (0.5s = ~2 requêtes par seconde, sous la limite de 3/s)
DELAY = 0.5  
ALLOWED_TAGS = {"mod", "arcane"}

# ==============================================================================
# FONCTIONS DE RÉCUPÉRATION (API)
# ==============================================================================

def fetch_item_details(slug: str) -> Dict:
    """Récupère la fiche détaillée d'un item spécifique sur la V2."""
    for attempt in range(3):
        try:
            response = requests.get(f"{BASE_URL}/items/{slug}", headers=HEADERS)
            response.raise_for_status()
            # En V2, l'objet détaillé de l'item est imbriqué dans data -> item
            return response.json().get("data", {}).get("item", {})
        except Exception as e:
            if attempt == 2:
                print(f"❌ Échec définitif sur {slug} après 3 tentatives. Erreur: {e}")
                return {}
            # Attente exponentielle en cas d'erreur de connexion temporaire
            wait_time = DELAY * (2 ** attempt)
            time.sleep(wait_time)
    return {}

# ==============================================================================
# LOGIQUE DE CONSTITUTION DE LA BASE DE DONNÉES
# ==============================================================================

def build_database() -> Dict[str, Any]:
    """Boucle principale : Récupère le manifeste puis interroge chaque fiche détaillée."""
    print("📡 Récupération du manifeste global (API V2)...")
    try:
        response = requests.get(f"{BASE_URL}/items", headers=HEADERS)
        response.raise_for_status()
        res_json = response.json()
        
        # En V2, la liste globale des objets est stockée dans la clé 'data'
        items_list = res_json.get("data", [])
        print(f"✅ Manifeste récupéré : {len(items_list)} items trouvés au total.")
        
    except Exception as e:
        print(f"❌ Impossible de récupérer le manifeste global : {e}")
        return {}

    database = {}
    processed = 0
    ignored_count = 0

    # On parcourt chaque item du manifeste pour interroger sa fiche détaillée
    for item in items_list:
        slug = item.get("slug")
        if not slug:
            continue

        processed += 1
        print(f"➡️ [{processed}/{len(items_list)}] Extraction de la fiche détaillée : {slug}")
        
        # Requête individuelle obligatoire pour obtenir le modèle Item complet (V2)
        details = fetch_item_details(slug)
        
        if not details:
            time.sleep(DELAY)
            continue

        # Dans la fiche détaillée V2, les tags sont à la racine de l'objet
        tags = details.get("tags", [])

        # --- FILTRAGE STRICT ---
        # On ne garde l'objet que si c'est un mod ou une arcane
        if not tags or not any(tag in ALLOWED_TAGS for tag in tags):
            ignored_count += 1
            time.sleep(DELAY)
            continue

        # Extraction de la structure linguistique i18n depuis les détails
        i18n_data = details.get("i18n", {})
        
        # Reconstruction du dictionnaire des noms par langue
        names = {}
        for lang, lang_data in i18n_data.items():
            if isinstance(lang_data, dict) and "name" in lang_data:
                names[lang] = lang_data["name"]

        # Récupération des infos anglaises pour la description, l'image et le wiki
        en_data = i18n_data.get("en", {}) if isinstance(i18n_data, dict) else {}

        # Construction du dictionnaire final optimisé pour ton site web
        database[slug] = {
            "url_name": slug,
            "names": names,
            "description": en_data.get("description", ""),
            "wiki_link": en_data.get("wikiLink"),  # Structure V2 : 'wikiLink' avec un L majuscule
            "image_link": en_data.get("thumb"),
            "tags": tags
        }

        # Pause de sécurité pour respecter la limite de débit de l'API
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
        "note": "Extraction sélective (Uniquement les mods et les arcanes)"
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
    # Définition du chemin de sortie relatif vers le dossier data/
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    db = build_database()
    
    # Si le manifeste et les fiches ont été récupérés, on injecte Umbra et on enregistre
    if db:
        db = add_umbra_mods(db)
        save_json(db, output_dir / "mods_database.json")
    else:
        print("❌ Script interrompu car la base de données extraite est vide.")
