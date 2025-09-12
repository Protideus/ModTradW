Warframe Mod Translator

This project is a web-based application designed for Warframe players to easily translate mod and arcane names into multiple languages. The application provides a simple, interactive user interface that allows players to search for items and apply various filters.

Key Features:
Real-time Search: Instantly find items by name in multiple languages as you type.
Multi-language Support: View item names and descriptions in a variety of languages, including English, French, German, Russian, and more. You can select which languages you want to display.
Tag Filtering: Refine your search results by using dynamic tag filters (e.g., "mod", "rifle", "rare", "melee"). The tags are automatically generated based on your search results.
Embedded Data: The application uses a pre-existing JSON file to provide all the data, making it a fast and server-free static website.
Responsive Design: The interface is optimized for all devices, from mobile phones to desktop computers.
Easy to update: The data is gathered with a scrapper that reads the warframe.market api

Technologies Used
HTML: The core structure of the web page.
CSS (Tailwind CSS): A utility-first CSS framework for a modern and responsive design.
JavaScript: Powers all the interactive features, including search, filtering, and data display.
JSON: A lightweight data-interchange format used to store the item information locally within the application.
Python: the scrapper is a local program that tou run on your computer that takes around 1 hour to read the api. It makes a JSON file that you had into the html file.
