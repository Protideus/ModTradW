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
    items_list = fetch_all_items()
    database = {}
    ignored_count = 0
    kept_count = 0

    for item in items_list:
        url_name = item.get("slug") or item.get("url_name")  # V2 utilise souvent "slug"
        if not url_name:
            continue

        # Filtrage précoce avec les tags de la liste globale
        item_tags = set(item.get("tags", []))
        if item_tags and not item_tags.intersection(ALLOWED_TAGS):
            ignored_count += 1
            continue

        print(f"➡️ Extraction détails : {url_name}")
        details = fetch_item_details(url_name)

        if not details:
            time.sleep(DELAY)
            continue

        final_tags = details.get("tags", []) or item.get("tags", [])

        if not set(final_tags).intersection(ALLOWED_TAGS):
            ignored_count += 1
            time.sleep(DELAY)
            continue

        # Extraction i18n
        i18n_data = details.get("i18n", {})
        names = {}
        description_en = ""

        for lang, lang_data in i18n_data.items():
            if isinstance(lang_data, dict):
                if "name" in lang_data:
                    names[lang] = lang_data["name"]
                if lang == "en" and "description" in lang_data:
                    description_en = lang_data["description"]

        database[url_name] = {
            "url_name": url_name,
            "names": names,
            "description": description_en,
            "wiki_link": details.get("wiki_link"),
            "image_link": details.get("thumb") or item.get("i18n", {}).get("en", {}).get("thumb"),
            "tags": final_tags
        }

        kept_count += 1
        time.sleep(DELAY)

    print(f"\n⚡ Filtrage terminé : {ignored_count} items ignorés | {kept_count} mods/arcanes conservés.")
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
