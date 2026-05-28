import requests
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# ==============================================================================
# CONFIGURATION & CONSTANTES
# ==============================================================================
BASE_URL = "https://api.warframe.market/v2"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ModTradW Database Updater (github.com/Protideus/ModTradW)"
}

# 2.5 requêtes par seconde max (Limite de l'API : 3 req/s).
DELAY = 0.4  

# Tags autorisés pour garder la base de données ultra-légère
ALLOWED_TAGS = {"mod", "arcane"}

# ==============================================================================
# FONCTIONS DE RÉCUPÉRATION (API)
# ==============================================================================

def fetch_all_items() -> list:
    """Récupère la liste globale de tous les items référencés sur l'API V2."""
    print("📡 Récupération de la liste globale des items (API V2)...")
    try:
        response = requests.get(f"{BASE_URL_V2}/items", headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        
        payload = data.get("payload", {})
        
        # En V2, la liste globale est rangée sous une clé de langue par défaut (souvent 'en')
        # avant de donner la liste complète des objets.
        if "items" in payload:
            items_data = payload["items"]
            if isinstance(items_data, dict) and "en" in items_data:
                return items_data["en"]
            elif isinstance(items_data, list):
                return items_data
                
        # Si la structure n'est pas celle attendue, on cherche la première liste disponible
        for key, value in payload.items():
            if isinstance(value, list):
                return value
            elif isinstance(value, dict) and "en" in value:
                return value["en"]
                
        print(f"⚠️ Structure V2 inattendue. Clés : {list(payload.keys())}")
        return []
        
    except Exception as e:
        print(f"❌ Impossible de récupérer la liste des items : {e}")
        return []
        
    except Exception as e:
        print(f"❌ Impossible de récupérer la liste des items : {e}")
        return []


def fetch_item_details(url_name: str) -> Dict:
    """
    Récupère la fiche détaillée d'un item.
    Intègre un système de Retry + Exponential Backoff en cas de problème réseau.
    """
    for attempt in range(3):
        try:
            response = requests.get(f"{BASE_URL}/items/{url_name}", headers=HEADERS)
            response.raise_for_status()
            return response.json().get("payload", {}).get("item", {})
        except Exception as e:
            if attempt == 2:
                print(f"❌ Échec définitif sur {url_name} après 3 tentatives. Erreur: {e}")
                return {}
            wait_time = DELAY * (2 ** attempt)
            print(f"⚠️ Erreur sur {url_name}. Nouvelle tentative dans {wait_time}s...")
            time.sleep(wait_time)
    return {}

# ==============================================================================
# LOGIQUE DE CONSTITUTION DE LA BASE DE DONNÉES
# ==============================================================================

def build_database() -> Dict[str, Any]:
    """Boucle principale qui extrait les traductions des mods et arcanes uniquement."""
    items_list = fetch_all_items()
    print(f"✅ {len(items_list)} items trouvés dans la liste globale.")

    database = {}
    processed = 0
    ignored_count = 0

    for item in items_list:
        url_name = item.get("url_name")
        if not url_name:
            continue

        processed += 1
        
        # --- STRATÉGIE DE FILTRAGE PAR TAGS ---
        # L'API V2 fournit souvent des tags basiques dès la liste globale (relic, mod, weapon...).
        # Si l'item n'a pas de tags, ou s'il n'est ni un mod ni une arcane, on l'ignore 
        # AVANT de faire la requête détaillée pour économiser du temps et de la bande passante.
        item_tags = set(item.get("tags", []))
        if item_tags and not item_tags.intersection(ALLOWED_TAGS):
            ignored_count += 1
            continue

        print(f"➡️ [{processed}/{len(items_list)}] Extraction : {url_name}")
        
        details = fetch_item_details(url_name)
        
        if not details:
            time.sleep(DELAY)
            continue

        # Double vérification des tags avec les détails officiels de l'item
        final_tags = details.get("tags", [])
        if not set(final_tags).intersection(ALLOWED_TAGS):
            ignored_count += 1
            time.sleep(DELAY)
            continue

        # Extraction des langues (i18n) - API V2
        i18n_data = details.get("i18n", {})
        
        names = {}
        description_en = ""
        
        for lang, lang_data in i18n_data.items():
            if isinstance(lang_data, dict) and "name" in lang_data:
                names[lang] = lang_data["name"]
                # Stratégie minimaliste : On ne stocke que la description anglaise
                if lang == "en":
                    description_en = lang_data.get("description", "")

        # Structure ultra-légère pour ton site web
        database[url_name] = {
            "url_name": url_name,
            "names": names,
            "description": description_en,
            "wiki_link": details.get("wiki_link"),
            "image_link": details.get("thumb"),
            "tags": final_tags
        }

        # Respect du rythme de l'API
        time.sleep(DELAY)

    print(f"\n⚡ Filtrage terminé : {ignored_count} items non pertinents ont été ignorés.")
    return database


def add_umbra_mods(database: Dict) -> Dict:
    """Injection manuelle des 5 mods Umbra exclusifs (non échangeables)."""
    print("🛠️ Injection des mods Umbra manuels...")
    umbra_mods = {
        "umbral_intensify": {
            "url_name": "umbral_intensify",
            "names": {
                "en": "Umbral Intensify", "ru": "Умбральное Усиление", "ko": "엄브랄 인텐시파이",
                "fr": "Intensification Umbrale", "sv": "Umbral Intensify", "de": "Umbral Intensify",
                "zh-hant": "影幕強化", "zh-hans": "影幕强化", "pt": "Umbral Intensify",
                "es": "Intensification Umbral", "pl": "Umbral Intensify", "cs": "Umbral Intensify",
                "uk": "Умбральне Посилення", "it": "Intensificazione Umbrale"
            },
            "description": "+44% Ability Strength\n+11% Sentient Damage Resistance",
            "wiki_link": "https://wiki.warframe.com/w/Umbral_Intensify",
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
            "wiki_link": "https://wiki.warframe.com/w/Umbral_Vitality",
            "tags": ["mod", "legendary", "warframe", "umbra"]
        },
        "umbral_fiber": {
            "url_name": "umbral_fiber",
            "names": {
                "en": "Umbral Fiber", "ru": "Умбральное Волокно", "ko": "엄브랄 파이버",
                "fr": "Fibres Umbrales", "sv": "Umbral Fiber", "de": "Umbral Fiber",
                "zh-hant": "影幕纖維", "zh-hans": "影幕纤维", "pt": "Umbral Fiber",
                "es": "Fibra Umbral", "pl": "Umbral Fiber", "cs": "Umbral Fiber",
                "uk": "Умбральне Волокно", "it": "Fibra Umbrale"
            },
            "description": "+660% Armor\n+11% Sentient Damage Resistance",
            "wiki_link": "https://wiki.warframe.com/w/Umbral_Fiber",
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
            "wiki_link": "https://wiki.warframe.com/w/Sacrificial_Steel",
            "tags": ["mod", "legendary", "melee", "umbra"]
        },
        "sacrificial_pressure": {
            "url_name": "sacrificial_pressure",
            "names": {
                "en": "Sacrificial Pressure", "ru": "Жертвенное Давление", "ko": "삭리피셜 프레셔",
                "fr": "Pression Sacrificielle", "sv": "Sacrificial Pressure", "de": "Opferdruck",
                "zh-hant": "犧牲壓力", "zh-hans": "牺牲压力", "pt": "Sacrificial Pressure",
                "es": "Presión Sacrificial", "pl": "Sacrificial Pressure", "cs": "Sacrificial Pressure",
                "uk": "Жертвений Тиск", "it": "Pressione Sacrificale"
            },
            "description": "+110% Melee Damage\n+30% Damage to Sentients",
            "wiki_link": "https://wiki.warframe.com/w/Sacrificial_Pressure",
            "tags": ["mod", "legendary", "melee", "umbra"]
        }
    }
    database.update(umbra_mods)
    return database


def save_json(database: Dict, output_path: Path):
    """Sauvegarde la base de données au format JSON compact et lisible (UTF-8)."""
    metadata = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S CEST"),
        "total_items": len(database),
        "source": "Warframe.Market V2 + Umbra mods manuels",
        "note": "Filtre strict appliqué : Uniquement les mods et les arcanes"
    }

    final_db = {
        "metadata": metadata,
        "items": database
    }

    # ensure_ascii=False force l'écriture des vrais caractères (Russe, Chinois...) au lieu de \u041f
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_db, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Base de données JSON sauvegardée : {len(database)} items pertinents conservés.")
    print(f"   → {output_path}")


# ==============================================================================
# POINT D'ENTRÉE DU SCRIPT
# ==============================================================================
if __name__ == "__main__":
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    # Exécution de la pipeline
    db = build_database()
    db = add_umbra_mods(db)
    
    # Sauvegarde finale dans data/mods_database.json
save_json(db, output_dir / "mods_database.json")
