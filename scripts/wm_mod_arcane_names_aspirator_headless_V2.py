import requests
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# ==============================================================================
# CONFIGURATION
# ==============================================================================
BASE_URL = "https://api.warframe.market/v2"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ModTradW Database Updater (github.com/Protideus/ModTradW)"
}
DELAY = 0.4

ALLOWED_TAGS = {"mod", "arcane", "arcane_enhancement"}


def fetch_all_items() -> list:
    """Récupère la liste globale des items (API V2)"""
    print("📡 Récupération de la liste globale des items (API V2)...")
    try:
        response = requests.get(f"{BASE_URL}/items", headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        # Structure V2 : les items sont directement dans "data"
        items = data.get("data", [])
        print(f"✅ {len(items)} items trouvés dans la liste globale.")
        return items

    except Exception as e:
        print(f"❌ Impossible de récupérer la liste des items : {e}")
        return []


def fetch_item_details(url_name: str) -> Dict:
    """Récupère les détails d'un item avec retry"""
    for attempt in range(3):
        try:
            response = requests.get(f"{BASE_URL}/items/{url_name}", headers=HEADERS)
            response.raise_for_status()
            return response.json().get("payload", {}).get("item", {})
        except Exception as e:
            if attempt == 2:
                print(f"❌ Échec définitif sur {url_name} après 3 tentatives.")
                return {}
            wait_time = DELAY * (2 ** attempt)
            time.sleep(wait_time)
    return {}


def build_database() -> Dict[str, Any]:
    """Boucle principale ajustée sur la structure réelle de l'API V2."""
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
        print(f"➡️ [{processed}/{len(items_list)}] Extraction : {url_name}")
        
        details = fetch_item_details(url_name)
        
        if not details:
            time.sleep(DELAY)
            continue

        # L'API V2 imbrique les données spécifiques dans l'objet 'i18n'
        i18n_data = details.get("i18n", {})
        
        # On s'appuie sur la structure anglaise ('en') qui est la référence de l'API
        en_data = i18n_data.get("en", {}) if isinstance(i18n_data, dict) else {}
        
        if not en_data:
            ignored_count += 1
            time.sleep(DELAY)
            continue

        # Extraction des tags situés dans le bloc de langue 'en' (vu sur la console)
        final_tags = en_data.get("tags", [])

        # --- FILTRAGE STRICT PAR TAGS V2 ---
        # On vérifie si l'item contient le tag "mod" ou "arcane" à l'emplacement exact
        if not final_tags or not any(tag in ["mod", "arcane"] for tag in final_tags):
            ignored_count += 1
            time.sleep(DELAY)
            continue

        # Extraction multilingue des noms uniquement (pour garder le JSON léger)
        names = {}
        for lang, lang_data in i18n_data.items():
            if isinstance(lang_data, dict) and "name" in lang_data:
                names[lang] = lang_data["name"]

        # Structure finale ultra-optimisée pour ton site web
        database[url_name] = {
            "url_name": url_name,
            "names": names,
            "description": en_data.get("description", ""),
            "wiki_link": en_data.get("wiki_link"),
            "image_link": en_data.get("thumb"),
            "tags": final_tags
        }

        # Respect du rythme de l'API
        time.sleep(DELAY)

    print(f"\n⚡ Filtrage terminé : {ignored_count} items non pertinents ont été ignorés.")
    print(f"📦 Nombre de mods/arcanes valides conservés : {len(database)}")
    return database


def add_umbra_mods(database: Dict) -> Dict:
    print("🛠️ Injection des mods Umbra manuels...")
    # ... (ton code umbra actuel, je ne le recopie pas pour gagner de la place)
    # Colle ici ton dictionnaire umbra_mods
    database.update(umbra_mods)
    return database


def save_json(database: Dict, output_path: Path):
    metadata = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S CEST"),
        "total_items": len(database),
        "source": "Warframe.Market V2 + Umbra mods manuels",
        "note": "Uniquement mods et arcanes"
    }

    final_db = {"metadata": metadata, "items": database}

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_db, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Sauvegarde terminée → {output_path} ({len(database)} items)")


# ==============================================================================
if __name__ == "__main__":
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    db = build_database()
    db = add_umbra_mods(db)
    save_json(db, output_dir / "mods_database.json")
