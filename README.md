# 🌌 Warframe Mod & Arcane Translator

An interactive, ultra-fast, multi-language translation tool tailored for **Warframe** players to instantly find mod and arcane names across different languages. 

Built as a lightweight, serverless static web application, it provides global players with a seamless way to bridge language barriers while exploring crucial item metrics (descriptions, images, and official Wiki links).

---

## 🚀 Key Features

* **Real-Time Translation:** Instant search with partial or exact matching, translating simultaneously across all supported languages as you type.
* **Full Multilingual Support:** Comprehensive coverage of 14 official game languages (EN, FR, DE, ES, IT, PT, RU, UK, PL, CS, SV, ZH-Hans, ZH-Hant, KO).
* **Dynamic Tag Filtering:** Refine results instantly using an automated tagging system that adapts dynamically to your search queries (e.g., *mod*, *rare*, *melee*, *arcane_enhancement*).
* **Serverless & Lightweight Architecture:** The front-end directly consumes an embedded, heavily optimized local JSON database. The website is 100% static, lightning-fast, and fully mobile-responsive.
* **Incremental Automated Updates:** No manual scraping required. An automated backend pipeline synchronizes daily with official data sources.

---

## 🛠️ Technology Stack & Architecture

### Front-End (Web Application)
* **HTML5 & Vanilla JavaScript (ES6+):** Powers the high-performance local search engine, handling intersection-set filtering and fluid UI responsiveness.
* **Tailwind CSS:** A modern utility-first CSS framework providing a sleek, responsive dark-mode layout optimized for mobile and desktop screens.
* **Embedded JSON:** Acts as a single local source of truth, completely eliminating live external API requests on the client side for unmatched speed.

### Back-End & Automation (Data Aspirator V2)
The localized database file (`mods_database.json`) is maintained by a highly optimized **Python 3** script that interfaces with the *Warframe.Market* V2 API.
* **API Version Lock:** The script checks the server's `/versions` endpoint prior to processing. If no remote version change is found, it terminates early to conserve resources.
* **Optimized Multilingual Fetching:** Collects all 14 language translations simultaneously via global manifest calls, dramatically reducing the overall HTTP request footprint.
* **Cache & Blacklist Framework:** Non-target items (weapons, resources, components) along with unchanged assets are memorized locally. This intelligent differential scanning shortens execution times from a 44-minute brute force cycle down to **less than 5 seconds** daily.
* **CI/CD Integration (GitHub Actions):** Runs automatically every night through a GitHub Workflow, tracking new releases, updating the database, and committing changes autonomously to the repository.

---

## 📂 Project Structure

```text
├── .github/workflows/
│   └── cron_update.yml      # GitHub Actions daily update scheduler
├── data/
│   ├── mods_database.json   # Generated, normalized final database
│   └── ignored_slugs.json   # Exclusion blacklist file (ignores unrelated items)
├── scripts/
│   └── wm_mod_arcane_names_aspirator_headless_V2.py  # Python extraction script
├── index.html               # Web application entry point
└── README.md
```
📝 Data Attribution
Translation schemas, rarities, and descriptions are gathered dynamically from the public Warframe.Market (V2) API. Exclusive, non-tradable assets (such as Umbra mods) are manually injected into the compilation script to guarantee an exhaustive global database.
