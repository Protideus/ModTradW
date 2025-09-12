import requests  # Imports the 'requests' library for making HTTP requests to the API.
import json  # Imports the 'json' library for working with JSON data.
import time  # Imports the 'time' library to add delays (essential for respecting the API's rate limits).
import tkinter as tk  # Imports the 'tkinter' library for creating the graphical user interface.
from tkinter import messagebox, filedialog, ttk
from threading import Thread, Event  # Allows API requests to be made in the background without blocking the UI.
from collections import defaultdict  # A specialized dictionary that provides a default value for missing keys.
from ttkthemes import ThemedTk  # Imports ThemedTk to use modern themes for better aesthetics.

# --- Constants and Configuration ---
# Base URL for the Warframe Market API
base_api_url = 'https://api.warframe.market/v1/items/'
all_items_api_url = 'https://api.warframe.market/v1/items'

# Headers to specify content type and language. English is used for better
# reliability of the data returned by the API.
headers = {
    'Accept': 'application/json',
    'Language': 'en'
}

# --- Global Application Variables ---
# An Event object to allow a thread to be stopped safely.
stop_event = Event()
# A list to store the raw data of all items.
all_items_data = []
# A dictionary to store the complete details (description, tags, etc.) of each item.
all_item_details = {}
# A dictionary to count the frequency of each tag.
tags_count = defaultdict(int)
# The total number of items that match the filter, used for the progress bar.
total_items_in_db = 0
# A list to store the Tkinter variables associated with the tag checkboxes.
tags_vars = []
# A flag to track the pause state.
is_paused = False
# A flag to control the blinking animation.
is_blinking = False
# A new global counter for connection errors.
total_connection_errors = 0


# --- Application Functions ---
def update_gui_thread_safe(widget, config_options):
    """
    Safely updates a widget from a non-GUI thread.

    Tkinter is not thread-safe, so all UI modifications must be made from the
    main (GUI) thread. This function uses `widget.after()` to schedule the
    update on the main thread.

    Args:
        widget (tk.Widget): The Tkinter widget to update.
        config_options (dict): A dictionary of configuration options (e.g., {'text': 'New text'}).
    """
    # Checks if the widget still exists before attempting to update it.
    if widget.winfo_exists():
        widget.after(0, lambda: widget.config(**config_options))


def update_text_widget_thread_safe(widget, text_content, state=tk.DISABLED):
    """
    Safely updates the content of a Text widget from a non-GUI thread.

    Args:
        widget (tk.Text): The Tkinter Text widget to update.
        text_content (str): The new content to set.
    """
    if widget.winfo_exists():
        def update():
            widget.config(state=tk.NORMAL)
            widget.delete('1.0', tk.END)
            widget.insert(tk.END, text_content)
            widget.config(state=state)

        widget.after(0, update)


def update_status_indicator_thread_safe(canvas, color):
    """
    Safely updates the color of the status indicator (circle) from a non-GUI thread.

    Args:
        canvas (tk.Canvas): The canvas widget for the indicator.
        color (str): The color to set the indicator to (e.g., "green", "grey", "red").
    """
    if canvas.winfo_exists():
        def update_color():
            canvas.delete("all")
            canvas.create_oval(5, 5, 25, 25, fill=color, outline=color)

        canvas.after(0, update_color)


def animate_indicator(canvas, colors, index=0):
    """
    Creates a blinking effect for a status indicator.

    This function is called recursively to cycle through a list of colors,
    creating a visual animation.

    Args:
        canvas (tk.Canvas): The canvas widget for the indicator.
        colors (list): A list of color strings to cycle through.
        index (int): The current index in the color list.
    """
    global is_blinking
    if not is_blinking:
        return

    next_color = colors[index]
    update_status_indicator_thread_safe(canvas, next_color)

    next_index = (index + 1) % len(colors)
    canvas.after(500, lambda: animate_indicator(canvas, colors, next_index))


def toggle_pause():
    """
    Toggles the pause state and updates the button text.
    """
    global is_paused, is_blinking
    is_paused = not is_paused
    if is_paused:
        is_blinking = False
        pause_button.config(text="Reprendre")
        update_gui_thread_safe(status2_label, {'text': "Processus en pause..."})
        update_status_indicator_thread_safe(status2_indicator, "yellow")
    else:
        is_blinking = True
        pause_button.config(text="Pause")
        # Resume the thread
        Thread(target=run_initial_fetch_step2).start()


def run_initial_fetch_step1():
    """
    Handles the first step: fetching the complete list of items.
    """
    global all_items_data, total_items_in_db

    update_status_indicator_thread_safe(status1_indicator, "grey")
    update_status_indicator_thread_safe(status2_indicator, "grey")

    status1_label.config(text="Récupération de la liste des items en cours...")
    status2_label.config(text="")

    try:
        response = requests.get(all_items_api_url, headers=headers)
        response.raise_for_status()

        data = response.json()
        all_items_data = data['payload']['items']

        total_items_in_db = len(all_items_data)

        update_gui_thread_safe(status1_label,
                               {'text': f"Récupération de la liste des items terminée. ({total_items_in_db} items)"})
        update_status_indicator_thread_safe(status1_indicator, "green")
        # The preview here should show the raw list of all items, as per the user's request
        update_text_widget_thread_safe(json_preview_text, json.dumps(all_items_data, indent=2))

        # Automatically proceed to Step 2
        Thread(target=run_initial_fetch_step2).start()

    except requests.exceptions.RequestException as e:
        update_gui_thread_safe(status1_label, {'text': f"Erreur de connexion : {e}"})
        messagebox.showerror("Erreur de connexion", f"Impossible de se connecter à l'API : {e}")


def run_initial_fetch_step2():
    """
    Handles the second step: detailed consultation of each item.
    This function is now designed to be resumable and exhaustive.
    """
    global all_item_details, tags_count, is_paused, is_blinking, total_connection_errors

    if is_paused:
        return  # Do nothing if already paused.

    start_time = time.time()

    is_blinking = True
    animate_indicator(status2_indicator, ["green", "grey"])

    status2_label.config(
        text=f"Étape 2: Consultation de chaque item pour extraire les détails (0/{total_items_in_db})...")
    progress_bar.config(maximum=total_items_in_db, value=0)

    # A delay is crucial to avoid API rate limiting.
    request_delay = 0.5

    # Use a list of items to process, starting from where we left off.
    items_to_process = all_items_data[len(all_item_details):]

    for item in items_to_process:
        if is_paused:
            break

        url_name = item['url_name']
        item_url = base_api_url + url_name

        # New, persistent retry logic.
        while True:
            try:
                response = requests.get(item_url, headers=headers)
                response.raise_for_status()

                item_data = response.json()['payload']['item']

                # Vérification de la validité de l'item_in_set avant de continuer
                if not item_data['items_in_set']:
                    print(f"Skipping item: {url_name} due to missing data.")
                    tags_count[''] += 1  # Compte les items sans tags
                    break  # Break the retry loop and move to the next item

                item_in_set = item_data['items_in_set'][0]

                tags = item_in_set.get('tags', [])
                if not tags:
                    tags_count[''] += 1  # Compte les items sans tags
                else:
                    for tag in tags:
                        tags_count[tag] += 1

                names = {key: value['item_name'] for key, value in item_in_set.items()
                         if isinstance(value, dict) and 'item_name' in value}

                all_item_details[url_name] = {
                    'url_name': url_name,
                    'names': names,
                    'description': item_in_set.get('en', {}).get('description'),
                    'wiki_link': item_in_set.get('en', {}).get('wiki_link'),
                    'image_link': item_in_set.get('thumb'),
                    'tags': tags
                }

                # Reset the delay on success and break the retry loop.
                request_delay = 0.5

                break

            except requests.exceptions.RequestException as e:
                # Exponential backoff: double the delay on failure.
                total_connection_errors += 1
                request_delay = min(request_delay * 2, 60)  # Cap the delay at 60 seconds
                update_gui_thread_safe(status2_label, {
                    'text': f"Erreur pour '{url_name}'. Nouvelle tentative dans {request_delay:.2f}s..."})
                time.sleep(request_delay)

        # Update the progress bar and time labels.
        current_item_index = len(all_item_details)
        progress_bar['value'] = current_item_index
        elapsed_time_seconds = time.time() - start_time

        elapsed_minutes = int(elapsed_time_seconds // 60)
        elapsed_seconds = int(elapsed_time_seconds % 60)

        if current_item_index > 0:
            avg_time_per_item = elapsed_time_seconds / current_item_index
            estimated_remaining_time_seconds = (total_items_in_db - current_item_index) * avg_time_per_item
            estimated_minutes = int(estimated_remaining_time_seconds // 60)
            estimated_seconds = int(estimated_remaining_time_seconds % 60)
            time_text = f"Temps écoulé: {elapsed_minutes}m {elapsed_seconds}s | Estimé restant: {estimated_minutes}m {estimated_seconds}s"
        else:
            time_text = f"Temps écoulé: {elapsed_minutes}m {elapsed_seconds}s"

        update_gui_thread_safe(status2_label, {
            'text': f"Étape 2: Consultation de l'item '{url_name}' ({current_item_index}/{total_items_in_db}) - Items traités: {len(all_item_details)}"})
        update_gui_thread_safe(time_label_fetch, {'text': time_text})
        update_gui_thread_safe(error_counter_label, {'text': f"Erreurs de connexion: {total_connection_errors}"})

        # Here, update the JSON preview with the full data collected so far.
        update_text_widget_thread_safe(json_preview_text, json.dumps(all_item_details, indent=2))

        # The sleep here is for the normal flow, after a successful fetch.
        time.sleep(request_delay)

    if not is_paused:
        is_blinking = False
        update_gui_thread_safe(status2_label, {
            'text': f"Consultation terminée. {len(all_item_details)}/{total_items_in_db} items consultés."})

        # Vérification finale du nombre d'items
        final_count = len(all_item_details)
        if final_count == total_items_in_db:
            final_message = f"Vérification finale: Tous les {final_count} items ont été collectés avec succès!"
            update_status_indicator_thread_safe(status2_indicator, "green")
        else:
            final_message = f"Vérification finale: Seulement {final_count} items sur {total_items_in_db} ont été collectés. Il y a eu une perte de données."
            update_status_indicator_thread_safe(status2_indicator, "red")

        messagebox.showinfo("Vérification terminée", final_message)
        update_gui_thread_safe(status2_label, {'text': final_message})

        # The preview now switches to the filtered view for Step 3.
        populate_tags_gui()
        update_gui_thread_safe(save_button, {'state': tk.NORMAL})


def update_filtered_count():
    """
    Calculates and updates the count of items based on selected tags.
    """
    selected_tags = [var.get() for var in tags_vars if var.get()]

    has_no_tags_filter = 'no_tags_filter' in selected_tags
    regular_tags = [tag for tag in selected_tags if tag != 'no_tags_filter']

    filtered_data = {}
    for url_name, item in all_item_details.items():
        matches_regular_tags = any(tag in regular_tags for tag in item.get('tags', []))

        matches_no_tags_filter = False
        if has_no_tags_filter:
            if 'tags' not in item or not item['tags']:
                matches_no_tags_filter = True

        if matches_regular_tags or matches_no_tags_filter:
            filtered_data[url_name] = item

    filtered_count = len(filtered_data)
    update_gui_thread_safe(filtered_count_label, {'text': f"Nombre d'entrées sélectionnées : {filtered_count}"})
    update_json_preview_names_only(filtered_data)


def update_json_preview_names_only(filtered_data):
    """
    Updates the JSON preview Text widget with the names of filtered items.
    """
    # Extract only the item names for a quick preview.
    preview_names = [item.get('names', {}).get('en', 'Nom inconnu') for item in filtered_data.values()]
    preview_text = json.dumps(preview_names, indent=2, ensure_ascii=False)
    # The preview text is now generated, let's update the widget.
    update_text_widget_thread_safe(json_preview_text, preview_text)
    # Change the preview title to reflect the filtered content.
    preview_frame.config(text="Aperçu du résultat filtré")


def save_json_file():
    """
    Opens a dialog box to save the JSON file of the filtered data.
    Displays error messages if the save fails.
    """
    if not all_item_details:
        messagebox.showinfo("Rien à sauvegarder", "Veuillez d'abord lancer l'initialisation pour générer des données.")
        return

    filepath = filedialog.asksaveasfilename(
        defaultextension=".json",
        filetypes=[("Fichiers JSON", "*.json")],
        initialfile="warframe_data.json"
    )

    if filepath:
        try:
            # Retrieve the selected tags for filtering.
            selected_tags = [var.get() for var in tags_vars if var.get()]

            # Check for the special 'no tags' filter.
            has_no_tags_filter = 'no_tags_filter' in selected_tags
            regular_tags = [tag for tag in selected_tags if tag != 'no_tags_filter']

            filtered_data = {}
            for url_name, item in all_item_details.items():
                matches_regular_tags = any(tag in regular_tags for tag in item.get('tags', []))

                matches_no_tags_filter = False
                if has_no_tags_filter:
                    if 'tags' not in item or not item['tags']:
                        matches_no_tags_filter = True

                if matches_regular_tags or matches_no_tags_filter:
                    filtered_data[url_name] = item

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(filtered_data, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Succès", f"Fichier sauvegardé avec succès à : {filepath}")
        except Exception as e:
            messagebox.showerror("Erreur de sauvegarde", f"Une erreur s'est produite lors de la sauvegarde : {e}")


def populate_tags_gui():
    """
    Dynamically displays the tag checkboxes.

    This function is called after data retrieval to populate the tag selection area
    with the found tags, sorted by frequency.
    """
    for widget in tags_scrollable_frame.winfo_children():
        widget.destroy()
    tags_vars.clear()

    # Change the preview title to reflect the new content.
    preview_frame.config(text="Aperçu du résultat filtré")

    # Get the count of items without tags.
    no_tags_count = tags_count.get('', 0)

    # Add the "Sans tags" option if there are any items without tags.
    if no_tags_count > 0:
        var = tk.StringVar(value="")
        cb = ttk.Checkbutton(tags_scrollable_frame, text=f"Sans tags ({no_tags_count})", variable=var,
                             onvalue='no_tags_filter', offvalue="", command=update_filtered_count)
        cb.pack(anchor="w", padx=5, pady=2)
        tags_vars.append(var)

    # Sort other tags by popularity (most frequent to least frequent).
    sorted_tags = sorted([item for item in tags_count.items() if item[0] != ''], key=lambda item: item[1], reverse=True)

    for tag, count in sorted_tags:
        var = tk.StringVar(value="")
        # Create a checkbox for each tag.
        cb = ttk.Checkbutton(tags_scrollable_frame, text=f"{tag} ({count})", variable=var, onvalue=tag, offvalue="",
                             command=update_filtered_count)
        cb.pack(anchor="w", padx=5, pady=2)
        tags_vars.append(var)

    update_filtered_count()


# --- Creating the GUI with Tkinter ---
root = ThemedTk(theme="arc")  # Uses a modern theme for better aesthetics.
root.title("Warframe Market Data Aspirator")
root.geometry("1000x800")

# Main frame with two columns.
main_frame = ttk.Frame(root, padding=10)
main_frame.pack(fill=tk.BOTH, expand=True)

# Left column for the stages.
stages_frame = ttk.Frame(main_frame, width=450)  # Fixed width to prevent resizing
stages_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)
stages_frame.pack_propagate(False)  # Prevents the frame from resizing to its children

# Right column for JSON preview.
preview_frame = ttk.LabelFrame(main_frame, text="Aperçu des données JSON", padding=10)
preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

json_preview_text = tk.Text(preview_frame, wrap="word", height=10)
json_preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

json_scrollbar = ttk.Scrollbar(preview_frame, command=json_preview_text.yview)
json_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
json_preview_text.config(yscrollcommand=json_scrollbar.set)

# Section 1: Initial item list retrieval.
stage1_frame = ttk.LabelFrame(stages_frame, text="Étape 1: Récupération de la liste des items", padding=10)
stage1_frame.pack(fill=tk.X, pady=10)

status1_indicator = tk.Canvas(stage1_frame, width=30, height=30)
status1_indicator.pack(side=tk.LEFT)
update_status_indicator_thread_safe(status1_indicator, "grey")

status1_label = ttk.Label(stage1_frame, text="Prêt à démarrer l'initialisation...", font=("Arial", 10), wraplength=350)
status1_label.pack(side=tk.LEFT, padx=10)

# Section 2: Detailed item consultation.
stage2_frame = ttk.LabelFrame(stages_frame, text="Étape 2: Consultation détaillée des items", padding=10)
stage2_frame.pack(fill=tk.X, pady=10)

warning_label = ttk.Label(stage2_frame,
                          text="Cette étape est très longue en raison des limites de l'API. Ne fermez pas l'application.",
                          font=("Arial", 9, "italic"), wraplength=400)
warning_label.pack(pady=5)

# Conteneur pour le statut et l'indicateur
status_line_frame = ttk.Frame(stage2_frame)
status_line_frame.pack(fill=tk.X, pady=(5, 0))

status2_indicator = tk.Canvas(status_line_frame, width=30, height=30)
status2_indicator.pack(side=tk.LEFT)
update_status_indicator_thread_safe(status2_indicator, "grey")

status2_label = ttk.Label(status_line_frame, text="", font=("Arial", 10), wraplength=350)
status2_label.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.X)

# Conteneur pour la barre de progression, le temps et le bouton Pause
progress_and_controls_frame = ttk.Frame(stage2_frame)
progress_and_controls_frame.pack(fill=tk.X, pady=5)

progress_bar = ttk.Progressbar(progress_and_controls_frame, orient="horizontal", mode="determinate")
progress_bar.pack(fill=tk.X, expand=True)

time_label_fetch = ttk.Label(progress_and_controls_frame, text="", font=("Arial", 10))
time_label_fetch.pack(anchor="w")

error_counter_label = ttk.Label(progress_and_controls_frame, text="Erreurs de connexion: 0", font=("Arial", 10),
                                foreground="red")
error_counter_label.pack(anchor="w")

pause_button = ttk.Button(progress_and_controls_frame, text="Pause", command=toggle_pause)
pause_button.pack(fill=tk.X, pady=(5, 0))

# Section 3: Tag selection and saving.
stage3_frame = ttk.LabelFrame(stages_frame, text="Étape 3: Choix des tags et sauvegarde", padding=10)
stage3_frame.pack(fill=tk.BOTH, expand=True, pady=10)

tags_info_label = ttk.Label(stage3_frame, text="Sélectionnez les tags pour le filtrage.", font=("Arial", 10))
tags_info_label.pack(anchor="w", pady=(0, 5))

# Label for the filtered item count
filtered_count_label = ttk.Label(stage3_frame, text="", font=("Arial", 10, "bold"), foreground="blue")
filtered_count_label.pack(anchor="w", pady=(5, 5))

# Le bouton de sauvegarde doit être placé avant le canevas défilable.
save_button = ttk.Button(stage3_frame, text="Sauvegarder le fichier JSON", state=tk.DISABLED, command=save_json_file)
save_button.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

# Tags scrollable area.
tags_canvas = tk.Canvas(stage3_frame, borderwidth=0, background="#ffffff")
tags_scrollbar = ttk.Scrollbar(stage3_frame, orient="vertical", command=tags_canvas.yview)
tags_scrollable_frame = ttk.Frame(tags_canvas, padding=5)

tags_scrollable_frame.bind(
    "<Configure>",
    lambda e: tags_canvas.configure(
        scrollregion=tags_canvas.bbox("all")
    )
)

tags_canvas.create_window((0, 0), window=tags_scrollable_frame, anchor="nw")
tags_canvas.configure(yscrollcommand=tags_scrollbar.set)

tags_canvas.pack(side="left", fill="both", expand=True)
tags_scrollbar.pack(side="right", fill="y")

# Start the fetch process automatically after the main window is created.
root.after(100, lambda: Thread(target=run_initial_fetch_step1).start())

root.mainloop()
