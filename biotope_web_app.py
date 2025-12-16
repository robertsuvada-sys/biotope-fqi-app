import streamlit as st
import re
import pandas as pd
from collections import defaultdict
from datetime import date 
import io 

# NÁZOV PÔVODNÉHO KATALÓGOVÉHO SÚBORU
CATALOG_FILENAME = "ES Katalog biotopov Suvada ed 2023 v1.05.txt"

# ODKAZY NA VLAJKY (FlagCDN - verejný zdroj)
FLAG_URL_SK = "https://flagcdn.com/w40/sk.png"
FLAG_URL_GB = "https://flagcdn.com/w40/gb.png"

# --- TRANSLATION DICTIONARY ---

TRANSLATIONS = {
    # UI General
    "app_title": {
        "SK": "🌿 Identifikátor Biotopov (FQI) na základe Expertného Systému",
        "EN": "🌿 Habitat Identifier (FQI) based on Expert System"
    },
    "data_loaded_from": {
        "SK": "Dáta načítané zo súboru: **{}**",
        "EN": "Data loaded from file: **{}**"
    },
    "citation_header": {
        "SK": "**Podľa publikácie:**",
        "EN": "**Based on publication:**"
    },
    "citation_text": {
        "SK": "Šuvada R. (ed.), 2023: Katalóg biotopov Slovenska. Druhé, rozšírené vydanie. – Štátna ochrana prírody SR, Banská Bystrica, 511 p. ISBN 978-80-8184-106-4",
        "EN": "Šuvada R. (ed.), 2023: Habitat Catalogue of Slovakia. Second, extended edition. – State Nature Conservancy of SR, Banská Bystrica, 511 p. ISBN 978-80-8184-106-4"
    },
    "stats_header": {
        "SK": "Štatistiky Dát",
        "EN": "Data Statistics"
    },
    "stats_biotopes": {
        "SK": "Biotopov (skupín): **{}**",
        "EN": "Habitats (groups): **{}**"
    },
    "stats_matrix": {
        "SK": "Spracovaných druhov v matici: **{}**",
        "EN": "Species processed in matrix: **{}**"
    },
    "stats_total": {
        "SK": "Celkový počet názvov/synoným na výber: **{}**",
        "EN": "Total names/synonyms for selection: **{}**"
    },
    # Section 1: Input
    "sec1_title": {
        "SK": "1. Zadanie Druhov",
        "EN": "1. Species Input"
    },
    "sec1_1_subtitle": {
        "SK": "1.1. Hromadné zadanie (TXT súbor)",
        "EN": "1.1. Bulk Input (TXT file)"
    },
    "upload_info": {
        "SK": "Nahrajte textový súbor, ktorý bude mať na každom riadku len meno jedného druhu bez informácie o pokryvnosti. Aplikácia automaticky spracuje známe druhy a identifikuje neznáme.",
        "EN": "Upload a text file with one species name per line (without cover information). The app will automatically process known species and identify unknown ones."
    },
    "upload_label": {
        "SK": "Vyberte TXT súbor so zoznamom druhov",
        "EN": "Select TXT file with species list"
    },
    "upload_success": {
        "SK": "Načítaných známych druhov zo súboru: **{}**",
        "EN": "Known species loaded from file: **{}**"
    },
    "upload_warning": {
        "SK": "Neznáme druhy v súbore (na manuálnu korekciu): **{}**",
        "EN": "Unknown species in file (for manual correction): **{}**"
    },
    "upload_caption": {
        "SK": "Tieto druhy nebudú zahrnuté do analýzy, kým ich nepriradíte k známemu druhu pomocou ručného výberu (možnosť 1.2).",
        "EN": "These species will not be included in the analysis until you assign them to a known species using manual selection (option 1.2)."
    },
    "expander_unknown": {
        "SK": "Zobraziť neznáme druhy",
        "EN": "Show unknown species"
    },
    "sec1_2_subtitle": {
        "SK": "1.2. Manuálny výber (doplnenie / úprava / korekcia)",
        "EN": "1.2. Manual Selection (Addition / Edit / Correction)"
    },
    "multiselect_label": {
        "SK": "Vyberte druh zo zoznamu (začnite písať pre filtrovanie), alebo ním **korigujte neznáme druhy** zo súboru:",
        "EN": "Select a species from the list (start typing to filter), or use it to **correct unknown species** from the file:"
    },
    "total_analysis_info": {
        "SK": "Celkový počet druhov pre FQI analýzu (známe zo súboru + ručne vybrané): **{}**",
        "EN": "Total species for FQI analysis (known from file + manually selected): **{}**"
    },
    "btn_calculate": {
        "SK": "🟢 Všetky druhy zadané, vypočítaj FQI",
        "EN": "🟢 All species entered, Calculate FQI"
    },
    "btn_calculate_disabled": {
        "SK": "Všetky druhy zadané, vypočítaj FQI",
        "EN": "All species entered, Calculate FQI"
    },
    "toast_loaded": {
        "SK": "Načítaných druhov: {}. Známych: {}, Neznámych: {}.",
        "EN": "Species loaded: {}. Known: {}, Unknown: {}."
    },
    "toast_removed": {
        "SK": "Nahratý súbor bol odstránený. Zoznam druhov z neho bol vyčistený.",
        "EN": "Uploaded file removed. Species list cleared."
    },
    # Section 2: Results
    "err_no_species": {
        "SK": "Chyba: Neboli nájdené žiadne druhy na analýzu. Prepnite späť na výber.",
        "EN": "Error: No species found for analysis. Switch back to selection."
    },
    "btn_back": {
        "SK": "⬅️ Zmeň druhovú skupinu",
        "EN": "⬅️ Change Species Group"
    },
    "sec2_title": {
        "SK": "2. Výsledky Analýzy FQI",
        "EN": "2. FQI Analysis Results"
    },
    "analysis_running": {
        "SK": "Analýza beží pre **{}** vybraných druhov.",
        "EN": "Analysis running for **{}** selected species."
    },
    "err_no_matrix_match": {
        "SK": "Nenašiel sa žiaden zadaný druh v matici podobnosti. Výpočet FQI nie je možný.",
        "EN": "No entered species found in the similarity matrix. FQI calculation not possible."
    },
    "top3_title": {
        "SK": "Biotopy s najvyššou podobnosťou (FQI)",
        "EN": "Habitats with highest similarity (FQI)"
    },
    "fqi_caption": {
        "SK": "FQI (Frekvenčný Index) je **%**, ktoré vyjadruje podiel súčtu frekvencií vybraných druhov na celkovej možnej frekvencii všetkých kanonických druhov v danej skupine. Vyššie percento = Vyššia zhoda.",
        "EN": "FQI (Frequency Index) is a **%** representing the share of the cumulative frequency of selected species to the total possible frequency of all canonical species in the group. Higher percentage = Higher match."
    },
    # Columns for Results Table
    "col_rank": {
        "SK": "Poradie",
        "EN": "Rank"
    },
    "col_code": {
        "SK": "KÓD Biotopu",
        "EN": "Habitat CODE"
    },
    "col_name": {
        "SK": "Názov Biotopu",
        "EN": "Habitat Name"
    },
    "col_fqi": {
        "SK": "FQI (% Zhody)",
        "EN": "FQI (% Match)"
    },
    # Section 3: Details
    "sec3_title": {
        "SK": "3. Detaily Spracovania",
        "EN": "3. Processing Details"
    },
    "expander_check": {
        "SK": "Kontrola spracovania druhov zo súboru a manuálnych korekcií",
        "EN": "Review of file processing and manual corrections"
    },
    "warn_not_included": {
        "SK": "**{}** druhov nebolo v analýze zahrnutých. Mená druhov z importovaného súboru, ktoré nebolo možné automaticky priradiť ku kanonickým druhom.",
        "EN": "**{}** species were not included in the analysis. Species names from the imported file that could not be automatically assigned to canonical species."
    },
    "success_unknown_fixed": {
        "SK": "Všetky pôvodne neznáme druhy boli manuálne opravené/priradené.",
        "EN": "All originally unknown species were manually corrected/assigned."
    },
    "success_no_unknown": {
        "SK": "V nahratom súbore neboli žiadne neznáme druhy.",
        "EN": "There were no unknown species in the uploaded file."
    },
    "success_manual_added": {
        "SK": "**{}** druhov bolo **manuálne pridaných alebo korigovaných** v kroku 1.2 a boli zahrnuté do analýzy:",
        "EN": "**{}** species were **manually added or corrected** in step 1.2 and included in the analysis:"
    },
    "info_no_manual": {
        "SK": "Do analýzy neboli pridané žiadne druhy ručným výberom.",
        "EN": "No species were added manually to the analysis."
    },
    "processed_canon": {
        "SK": "##### Spracované druhy (kanonické)",
        "EN": "##### Processed Species (Canonical)"
    },
    "processed_count": {
        "SK": "**Počet spracovaných kanonických druhov:** {}",
        "EN": "**Number of processed canonical species:** {}"
    },
    "expander_canon": {
        "SK": "Zobraziť použité kanonické mená",
        "EN": "Show used canonical names"
    },
    "synonym_conversions": {
        "SK": "##### Konverzie Synonym (zadaný → kanonický)",
        "EN": "##### Synonym Conversions (Input → Canonical)"
    },
    "no_synonyms": {
        "SK": "Neboli zadané žiadne synonymá, alebo bol zadaný už kanonický názov.",
        "EN": "No synonyms entered, or the canonical name was already provided."
    },
    "ignored_dups": {
        "SK": "##### Ignorované duplikáty vstupu",
        "EN": "##### Ignored Input Duplicates"
    },
    "ignored_count": {
        "SK": "**Ignorovaných vstupov: {}**",
        "EN": "**Ignored inputs: {}**"
    },
    "ignored_caption": {
        "SK": "Tieto druhy majú kanonické meno, ktoré už bolo v rámci výpočtu zahrnuté. Boli preskočené, aby sa predišlo duplicitnému započítaniu.",
        "EN": "These species have a canonical name that was already included in the calculation. They were skipped to avoid double counting."
    },
    "success_no_dups": {
        "SK": "Neboli zadané žiadne duplikáty.",
        "EN": "No duplicates were entered."
    },
    # Section 4: Export
    "sec4_title": {
        "SK": "4. Údaje z terénu a Export",
        "EN": "4. Field Data and Export"
    },
    "form_field_info": {
        "SK": "##### Informácie o terénnom zázname",
        "EN": "##### Field Record Information"
    },
    "lbl_locality": {
        "SK": "Lokalita",
        "EN": "Locality"
    },
    "lbl_coords": {
        "SK": "Súradnice",
        "EN": "Coordinates"
    },
    "lbl_mapper": {
        "SK": "Meno mapovateľa",
        "EN": "Mapper Name"
    },
    "lbl_date": {
        "SK": "Dátum zápisu",
        "EN": "Date of Record"
    },
    "form_covers": {
        "SK": "##### Pokryvnosť etáží (E\u2083-E\u2080)",
        "EN": "##### Layer Coverage (E\u2083-E\u2080)"
    },
    "help_cover": {
        "SK": "Pokryvnosť v %",
        "EN": "Coverage in %"
    },
    "lbl_e3": {
        "SK": "E\u2083 (Stromové poschodie)",
        "EN": "E\u2083 (Tree Layer)"
    },
    "lbl_e2": {
        "SK": "E\u2082 (Krovité poschodie)",
        "EN": "E\u2082 (Shrub Layer)"
    },
    "lbl_e1": {
        "SK": "E\u2081 (Bylinné poschodie)",
        "EN": "E\u2081 (Herb Layer)"
    },
    "lbl_e0": {
        "SK": "E\u2080 (Machové/Liš. poschodie)",
        "EN": "E\u2080 (Moss/Lichen Layer)"
    },
    "btn_save_data": {
        "SK": "Uložiť údaje (pred exportom)",
        "EN": "Save Data (Before Export)"
    },
    "btn_download_xlsx": {
        "SK": "⬇️ Export výsledkov (Excel XLSX)",
        "EN": "⬇️ Export Results (Excel XLSX)"
    },
    "btn_download_txt": {
        "SK": "⬇️ Export výsledkov (TXT formát)",
        "EN": "⬇️ Export Results (TXT format)"
    },
    # Export Content (TXT/Excel)
    "export_title": {
        "SK": "--- EXPORT VÝSLEDKOV ANALÝZY BIOTOPU ---",
        "EN": "--- HABITAT ANALYSIS RESULTS EXPORT ---"
    },
    "export_based_on": {
        "SK": "podľa publikácie Šuvada R. (ed.), 2023: Katalóg biotopov Slovenska...",
        "EN": "based on publication Šuvada R. (ed.), 2023: Habitat Catalogue of Slovakia..."
    },
    "export_sec1": {
        "SK": "SEKCIA 1: ÚDAJE Z TERÉNU",
        "EN": "SECTION 1: FIELD DATA"
    },
    "export_covers_title": {
        "SK": "Pokryvnosť etáží",
        "EN": "Layer Coverage"
    },
    "export_sec2": {
        "SK": "SEKCIA 2: VÝSLEDKY FQI ANALÝZY (TOP 3)",
        "EN": "SECTION 2: FQI ANALYSIS RESULTS (TOP 3)"
    },
    "export_sec3": {
        "SK": "SEKCIA 3: POUŽITÉ KANONICKÉ DRUHY",
        "EN": "SECTION 3: USED CANONICAL SPECIES"
    },
    "export_count_canon": {
        "SK": "Počet kanonických druhov: ",
        "EN": "Number of canonical species: "
    },
    "export_sec4": {
        "SK": "SEKCIA 4: MANUÁLNE PRIDANÉ DRUHY (Korekcia/Doplnenie)",
        "EN": "SECTION 4: MANUALLY ADDED SPECIES (Correction/Addition)"
    },
    "export_desc_manual": {
        "SK": "Druhy, ktoré boli manuálne pridané/korigované v kroku 1.2:",
        "EN": "Species manually added/corrected in step 1.2:"
    },
    "export_sec5": {
        "SK": "SEKCIA 5: NEZARADENÉ DRUHY",
        "EN": "SECTION 5: UNCLASSIFIED SPECIES"
    },
    "export_desc_unknown": {
        "SK": "Mená druhov z importovaného súboru, ktoré nebolo možné automaticky priradiť ku kanonickým druhom:",
        "EN": "Species names from the imported file that could not be automatically assigned to canonical species:"
    },
    "export_end": {
        "SK": "--- KONIEC EXPORTU ---",
        "EN": "--- END OF EXPORT ---"
    },
    # Excel Sheets
    "sheet_field_data": {
        "SK": "Data z terénu",
        "EN": "Field Data"
    },
    "sheet_fqi": {
        "SK": "FQI Výsledky",
        "EN": "FQI Results"
    },
    "sheet_canon": {
        "SK": "Kanonické druhy",
        "EN": "Canonical Species"
    },
    "sheet_unknown": {
        "SK": "Stav Neznámych Druhov",
        "EN": "Unknown Species Status"
    },
    "col_desc": { "SK": "Popis", "EN": "Description" },
    "col_val": { "SK": "Hodnota", "EN": "Value" },
    "col_canon_header": { "SK": "Kanonické druhy (použité v analýze)", "EN": "Canonical Species (Used in Analysis)" },
    "col_status": { "SK": "Stav", "EN": "Status" },
    "col_species": { "SK": "Druh", "EN": "Species" },
    "status_manual": { "SK": "Manuálne pridané (zaradené do analýzy)", "EN": "Manually added (included in analysis)" },
    "status_unclassified": { "SK": "Nezaradené (pôvodný neznámy/preklep)", "EN": "Unclassified (original unknown/typo)" }
}

# --- HELPER FUNCTIONS ---

def inner_dict_factory():
    return defaultdict(int)

def t(key):
    """Vráti text na základe aktuálneho jazyka v session_state."""
    lang = st.session_state.get('lang', 'SK')
    return TRANSLATIONS.get(key, {}).get(lang, key)

@st.cache_data
def load_file_content(filename):
    try:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(filename, 'r', encoding='Windows-1250') as f:
                return f.read()
    except FileNotFoundError:
        st.error(f"⚠️ {t('err_file_not_found')} '{filename}'")
        return None
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None

@st.cache_data
def parse_catalog_data(catalog_text):
    lines = catalog_text.split('\n')
    section_1_active = False
    section_4_active = False
    
    synonym_map = {}
    similarity_matrix = defaultdict(inner_dict_factory)
    group_names = {}
    current_canonical_name = None
    
    re_section_1_start = re.compile(r"SECTION 1:\s*Species aggregation", re.IGNORECASE)
    re_section_4_start = re.compile(r"SECTION 4:\s*Similarity", re.IGNORECASE) 
    re_section_end = re.compile(r"SECTION [23]:", re.IGNORECASE)
    re_canonical_name_1 = re.compile(r"^([A-Za-z].*?)\s+-\s*(\d+)\s*$")
    re_species_entry_1 = re.compile(r"^\s+([A-Za-z].*?)\s+(\d+)\s*$")
    re_group_name_4 = re.compile(r"^(Group\d+)\s*name:\s*(.+)\s*$") 
    re_species_name_only = re.compile(r"^\s*([A-Za-z].+?)\s*$", re.IGNORECASE) 
    re_total_line = re.compile(r"^\s*Total:\s*(\d+)\s*$", re.IGNORECASE)
    re_matrix_entry_4 = re.compile(r"^\s*(Group\d+):\s*(\d+)\s*$", re.IGNORECASE)
    
    current_species_in_matrix = None
    group_names_found = 0
    matrix_entries_found = 0

    for line in lines:
        line_clean = line.strip()

        if re_section_1_start.search(line):
            section_1_active = True; section_4_active = False; continue
        elif re_section_4_start.search(line):
            section_1_active = False; section_4_active = True; current_canonical_name = None; continue
        elif re_section_end.search(line):
            section_1_active = False; section_4_active = False; continue
        
        if section_1_active:
            match_canonical = re_canonical_name_1.match(line_clean)
            if match_canonical:
                current_canonical_name = match_canonical.group(1).strip()
                continue
            match_synonym = re_species_entry_1.match(line) 
            if match_synonym and current_canonical_name:
                synonym = match_synonym.group(1).strip()
                if synonym not in synonym_map: synonym_map[synonym] = current_canonical_name
            
        elif section_4_active:
            match_group_name = re_group_name_4.match(line_clean)
            if match_group_name:
                group_id = match_group_name.group(1).strip()
                group_name_full = match_group_name.group(2).split(" Count:")[0].strip()
                group_names[group_id] = group_name_full
                group_names_found += 1
                continue
            
            if line_clean.startswith("Count:") or line_clean.startswith("No.") or line_clean.startswith("Frequency table"):
                continue

            match_species_line = re_species_name_only.match(line)
            if match_species_line and 'Total:' not in line and 'Group' not in line:
                current_species_in_matrix = match_species_line.group(1).strip()
                continue
            
            if re_total_line.match(line): continue
            
            match_matrix_entry = re_matrix_entry_4.match(line)
            if match_matrix_entry and current_species_in_matrix:
                group_id = match_matrix_entry.group(1).strip()
                try:
                    count = int(match_matrix_entry.group(2))
                    similarity_matrix[current_species_in_matrix][group_id] = count
                    matrix_entries_found += 1
                except ValueError: pass
                
    if not group_names_found or not matrix_entries_found:
        return None, None, None
         
    return synonym_map, group_names, similarity_matrix

@st.cache_data
def calculate_total_frequency_per_group(similarity_matrix, group_names):
    total_frequency = defaultdict(int)
    all_groups = set(group_names.keys())

    for canonical_name in similarity_matrix:
        species_data = similarity_matrix[canonical_name]
        for group_id, count in species_data.items():
            if group_id in all_groups:
                total_frequency[group_id] += count
    
    return dict(total_frequency)


def get_canonical_name(species_name, synonym_map):
    species_name = species_name.strip()
    return synonym_map.get(species_name, species_name)

@st.cache_data
def get_all_known_species(synonym_map, similarity_matrix):
    canonical_species = set(similarity_matrix.keys())
    all_known = canonical_species.union(set(synonym_map.keys())).union(set(synonym_map.values()))
    return sorted(list(all_known))

def process_uploaded_species_list(uploaded_file, all_known_species):
    known_species = []
    unknown_species = []
    
    try:
        string_data = uploaded_file.getvalue().decode("utf-8")
    except UnicodeDecodeError:
        try:
            string_data = uploaded_file.getvalue().decode("windows-1250")
        except:
            return None, None
            
    for line in string_data.split('\n'):
        species = re.sub(r'\s+', ' ', line).strip()
        
        if species:
            if species in all_known_species:
                known_species.append(species)
            else:
                unknown_species.append(species)
                
    known_species = sorted(list(set(known_species)))
    unknown_species = sorted(list(set(unknown_species)))
    
    return known_species, unknown_species


@st.cache_data(show_spinner=False)
def analyze_similarity(species_list, synonym_map, group_names, similarity_matrix, total_frequency_per_group):
    cumulative_scores = defaultdict(int)
    valid_groups = set(group_names.keys())
    processed_canonical_species = set() 
    name_conversion_map = {} 
    ignored_inputs = [] 
    
    for user_species in species_list:
        user_species = user_species.strip()
        canonical_name = get_canonical_name(user_species, synonym_map)
        
        if canonical_name in similarity_matrix:
            
            name_conversion_map[user_species] = canonical_name

            if canonical_name not in processed_canonical_species:
                processed_canonical_species.add(canonical_name)
                
                species_data = similarity_matrix[canonical_name]
                for group_id, count in species_data.items():
                    if group_id in valid_groups:
                        cumulative_scores[group_id] += count
            else:
                ignored_inputs.append(user_species)
                

    if not cumulative_scores:
        return None, processed_canonical_species, name_conversion_map, ignored_inputs 

    fqi_scores = {}
    
    for group_id, cumulative_score in cumulative_scores.items():
        max_score = total_frequency_per_group.get(group_id, 0)
        
        if max_score > 0:
            fqi = (cumulative_score / max_score) * 100
            fqi_scores[group_id] = fqi
        else:
            fqi_scores[group_id] = 0.0

    sorted_scores = sorted(fqi_scores.items(), key=lambda item: item[1], reverse=True)
    top_matches_data = []
    
    re_biotope_code_extractor = re.compile(r'^(\S+)\s+(.*)', re.IGNORECASE)

    for rank, (group_id, score) in enumerate(sorted_scores[:3]):
        biotope_full_name = group_names.get(group_id, f"Unknown ({group_id})")
        
        biotope_code = group_id 
        biotope_name = biotope_full_name

        match_code = re_biotope_code_extractor.match(biotope_full_name)
        
        if match_code:
            biotope_code = match_code.group(1).strip() 
            biotope_name = match_code.group(2).strip()
            
            if biotope_name.startswith('-'):
                 biotope_name = biotope_name[1:].strip()

        
        top_matches_data.append({
            'rank': rank + 1, # Internal key, replaced for display
            'code': biotope_code,
            'name': biotope_name,
            'fqi': f"{score:.2f} %", 
        })

    return top_matches_data, processed_canonical_species, name_conversion_map, ignored_inputs

# --- EXPORT FUNCTIONS (LOCALIZED) ---

def generate_export_data(fqi_results_df, canonical_species_list, manual_data, lang='SK'):
    """Generates text export based on current language."""
    
    E3, E2, E1, E0 = "\u2083", "\u2082", "\u2081", "\u2080"
    
    # Helper to get text for this specific function scope
    def lt(key): 
        return TRANSLATIONS.get(key, {}).get(lang, key)

    # Convert DF to string
    fqi_table = fqi_results_df.reset_index(drop=True).to_csv(sep='\t', index=False)
    
    output = f"{lt('export_title')}\n"
    output += f"{lt('export_based_on')}\n\n"

    # 1. Header
    output += f"{lt('export_sec1')}\n"
    output += "--------------------------------------------------\n"
    output += f"{lt('lbl_locality')}:              {manual_data['lokalita']}\n"
    output += f"{lt('lbl_coords')}:             {manual_data['suradnica']}\n"
    output += f"{lt('lbl_mapper')}:       {manual_data['mapovatel']}\n"
    output += f"{lt('lbl_date')}:                 {manual_data['datum'].strftime('%Y-%m-%d') if isinstance(manual_data['datum'], date) else manual_data['datum']}\n"
    output += f"{lt('export_covers_title')} (E{E3}, E{E2}, E{E1}, E{E0}):\n"
    output += f"  E{E3}:                  {manual_data['pokryvnost_E3']}\n"
    output += f"  E{E2}:                  {manual_data['pokryvnost_E2']}\n"
    output += f"  E{E1}:                  {manual_data['pokryvnost_E1']}\n"
    output += f"  E{E0}:                  {manual_data['pokryvnost_E0']}\n\n"
    
    # 2. Results
    output += f"{lt('export_sec2')}\n"
    output += "--------------------------------------------------\n"
    output += fqi_table
    output += "\n"

    # 3. Canonical Species
    output += f"{lt('export_sec3')}\n"
    output += "--------------------------------------------------\n"
    output += f"{lt('export_count_canon')}" + str(len(canonical_species_list)) + "\n"
    output += "\n".join(sorted(canonical_species_list))
    
    remaining_unknown_species = manual_data.get('remaining_unknown_species')
    manual_selections_for_analysis = manual_data.get('manual_selections_for_analysis', []) 
    
    if manual_selections_for_analysis:
        output += f"\n\n{lt('export_sec4')}\n"
        output += "--------------------------------------------------\n"
        output += f"{lt('export_desc_manual')}\n"
        output += "\n".join(manual_selections_for_analysis)

    if remaining_unknown_species:
        output += f"\n\n{lt('export_sec5')}\n"
        output += "--------------------------------------------------\n"
        output += f"{lt('export_desc_unknown')}\n"
        output += "\n".join(remaining_unknown_species)
    
    output += f"\n\n{lt('export_end')}\n"
    
    return output

def generate_excel_data(fqi_results_df, canonical_species_list, manual_data, lang='SK'):
    """Generates Excel export based on current language."""
    
    def lt(key): 
        return TRANSLATIONS.get(key, {}).get(lang, key)
    
    header_data = [
        ("--- ZÁKLADNÉ ÚDAJE ---", ""),
        (lt('lbl_locality'), manual_data['lokalita']),
        (lt('lbl_coords'), manual_data['suradnica']),
        (lt('lbl_mapper'), manual_data['mapovatel']),
        (lt('lbl_date'), manual_data['datum'].strftime('%Y-%m-%d') if isinstance(manual_data['datum'], date) else manual_data['datum']),
        ("--- POKRYVNOSŤ ETÁŽÍ ---", ""),
        (lt('lbl_e3'), manual_data['pokryvnost_E3']),
        (lt('lbl_e2'), manual_data['pokryvnost_E2']),
        (lt('lbl_e1'), manual_data['pokryvnost_E1']),
        (lt('lbl_e0'), manual_data['pokryvnost_E0']),
    ]
    df_header = pd.DataFrame(header_data, columns=[lt('col_desc'), lt('col_val')])
    
    df_species = pd.DataFrame(sorted(canonical_species_list), columns=[lt('col_canon_header')])
    
    remaining = manual_data.get('remaining_unknown_species', [])
    manual_added = manual_data.get('manual_selections_for_analysis', [])
    
    df_status = pd.DataFrame({
        lt('col_status'): 
            [lt('status_manual')] * len(manual_added) + 
            [lt('status_unclassified')] * len(remaining),
        lt('col_species'): manual_added + remaining
    })
    
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_header.to_excel(writer, sheet_name=lt('sheet_field_data')[:30], index=False, startrow=0, startcol=0)
        
        # FQI Results (already localized DF passed in)
        df_fqi_excel = fqi_results_df.copy()
        df_fqi_excel.to_excel(writer, sheet_name=lt('sheet_fqi')[:30], index=False, startrow=0, startcol=0)

        df_species.to_excel(writer, sheet_name=lt('sheet_canon')[:30], index=False, startrow=0, startcol=0)

        if not df_status.empty:
            df_status.to_excel(writer, sheet_name=lt('sheet_unknown')[:30], index=False, startrow=0, startcol=0)

        for sheetname in writer.sheets:
            worksheet = writer.sheets[sheetname]
            worksheet.set_column('A:D', 30)
            
    output.seek(0)
    return output.read()

# --- CALLBACKS ---

def calculate_fqi_action():
    uploaded_known = st.session_state.get('uploaded_known_species', [])
    manual_selected = st.session_state.selected_species_multiselect
    
    combined_species = list(set(uploaded_known + manual_selected))
    
    st.session_state['calculated_species'] = combined_species
    st.session_state['manual_selections_for_display'] = manual_selected 
    st.session_state['app_mode'] = 'results'
    
def handle_upload():
    uploaded_file = st.session_state.uploaded_file_key
    all_known_species = st.session_state.all_known_species_data
    
    if uploaded_file is not None:
        known_species, unknown_species = process_uploaded_species_list(uploaded_file, all_known_species)
        
        if known_species is None:
             st.error("Error decoding file.")
             return
             
        st.session_state['uploaded_known_species'] = known_species
        st.session_state['uploaded_unknown_species'] = unknown_species
        msg = t('toast_loaded').format(
            len(known_species) + len(unknown_species),
            len(known_species),
            len(unknown_species)
        )
        st.toast(msg, icon='📄')
    else:
        st.session_state['uploaded_known_species'] = []
        st.session_state['uploaded_unknown_species'] = []
        st.toast(t('toast_removed'), icon='🗑️')

def reset_selection_action():
    st.session_state['app_mode'] = 'selection'
    st.session_state['uploaded_known_species'] = []
    st.session_state['uploaded_unknown_species'] = []
    
    if 'manual_selections_for_display' in st.session_state:
        st.session_state['selected_species_multiselect'] = st.session_state['manual_selections_for_display']

def set_lang(lang_code):
    st.session_state['lang'] = lang_code
    # No explicit rerun needed if used in callback or button leading to refresh, 
    # but strictly speaking st.rerun() ensures immediate update.
    # In Streamlit versions > 1.27 st.rerun() is preferred.
    # We will let the button click handle the refresh naturally.

# --- MAIN APP ---

def biotope_web_app():
    
    st.set_page_config(page_title="Habitat Identifier / Identifikátor Biotopov", layout="wide")
    
    # Initialize Language
    if 'lang' not in st.session_state:
        st.session_state['lang'] = 'SK'

    # --- LANGUAGE SWITCHER (TOP LEFT) ---
    # Upravené: Používa HTML tag <img> v st.markdown namiesto st.image,
    # čo zabraňuje fullscreen módu a umožňuje lepšie zarovnanie.
    col_lang_1, col_lang_2, col_spacer = st.columns([0.08, 0.08, 0.84])
    
    with col_lang_1:
        st.markdown(f'<div style="text-align: center;"><img src="{FLAG_URL_SK}" width="32" style="margin-bottom: 5px;"></div>', unsafe_allow_html=True)
        if st.button("SK", key="lang_sk", help="Slovensky", use_container_width=True):
            st.session_state['lang'] = 'SK'
            st.rerun()
            
    with col_lang_2:
        st.markdown(f'<div style="text-align: center;"><img src="{FLAG_URL_GB}" width="32" style="margin-bottom: 5px;"></div>', unsafe_allow_html=True)
        if st.button("EN", key="lang_en", help="English", use_container_width=True):
            st.session_state['lang'] = 'EN'
            st.rerun()

    # --- HEADER ---
    st.title(t("app_title"))
    st.caption(t("data_loaded_from").format(CATALOG_FILENAME))

    # Citácia
    st.markdown(f"""
        {t("citation_header")}
        {t("citation_text")}
    """)
    st.markdown("---")


    # Inicializácia stavu
    if 'app_mode' not in st.session_state:
        st.session_state['app_mode'] = 'selection'
        st.session_state['calculated_species'] = [] 
        st.session_state['uploaded_known_species'] = []
        st.session_state['uploaded_unknown_species'] = []
        st.session_state['selected_species_multiselect'] = [] 
        st.session_state['manual_selections_for_display'] = []

    # Krok 0: Načítanie a parsovanie dát
    catalog_text = load_file_content(CATALOG_FILENAME)
    if catalog_text is None:
        return

    synonym_map, group_names, similarity_matrix = parse_catalog_data(catalog_text)
    if synonym_map is None: 
        st.error("Nepodarilo sa spracovať dáta z katalógu.")
        return
        
    all_species = get_all_known_species(synonym_map, similarity_matrix)
    total_frequency_per_group = calculate_total_frequency_per_group(similarity_matrix, group_names)

    st.session_state.all_known_species_data = all_species 

    # Sidebar štatistiky
    st.sidebar.header(t("stats_header"))
    st.sidebar.write(t("stats_biotopes").format(len(group_names)))
    st.sidebar.write(t("stats_matrix").format(len(similarity_matrix)))
    st.sidebar.write(t("stats_total").format(len(all_species)))


    # --- RIADENIE REŽIMU APLIKÁCIE ---

    if st.session_state['app_mode'] == 'selection':
        # Režim 1: VÝBER DRUHOV

        st.header(t("sec1_title"))
        
        st.subheader(t("sec1_1_subtitle"))
        st.info(t("upload_info"))
        
        uploaded_file = st.file_uploader(
            t("upload_label"), 
            type=['txt'], 
            on_change=handle_upload,
            key='uploaded_file_key'
        )

        uploaded_known_species = st.session_state.get('uploaded_known_species', [])
        uploaded_unknown_species = st.session_state.get('uploaded_unknown_species', [])

        if uploaded_file and (uploaded_known_species or uploaded_unknown_species):
            st.success(t("upload_success").format(len(uploaded_known_species)))
            
            if uploaded_unknown_species:
                st.warning(t("upload_warning").format(len(uploaded_unknown_species)))
                st.caption(t("upload_caption"))
                with st.expander(t("expander_unknown"), expanded=True): 
                    st.code("\n".join(uploaded_unknown_species))
            
            st.markdown("---")


        st.subheader(t("sec1_2_subtitle"))

        current_species_list = st.multiselect(
            t("multiselect_label"),
            options=all_species,
            default=st.session_state.get('selected_species_multiselect', []), 
            key="selected_species_multiselect" 
        )
        
        total_species_for_analysis = list(set(uploaded_known_species + current_species_list))

        st.info(t("total_analysis_info").format(len(total_species_for_analysis)))
        
        if total_species_for_analysis:
            st.button(
                t("btn_calculate"), 
                on_click=calculate_fqi_action, 
                use_container_width=True
            )
        else:
            st.button(t("btn_calculate_disabled"), disabled=True, use_container_width=True)


    elif st.session_state['app_mode'] == 'results':
        # Režim 2: ZOBRAZENIE VÝSLEDKOV

        user_species_list = st.session_state['calculated_species']
        uploaded_unknown_species = st.session_state.get('uploaded_unknown_species', [])
        manual_selected_for_display = st.session_state.get('manual_selections_for_display', []) 
        uploaded_known_species = st.session_state.get('uploaded_known_species', []) 
        
        remaining_unknown_species = uploaded_unknown_species 
        manual_selections_for_analysis = manual_selected_for_display

        show_processing_details = (
            len(uploaded_known_species) > 0 or
            len(uploaded_unknown_species) > 0
        )
        
        if not user_species_list:
            st.error(t("err_no_species"))
            st.button(t("btn_back"), on_click=reset_selection_action)
            return

        st.header(t("sec2_title"))
        
        st.button(t("btn_back"), on_click=reset_selection_action)
        
        st.markdown("---")
        
        st.info(t("analysis_running").format(len(user_species_list)))

        top_matches_data, processed_species, name_conversion_map, ignored_inputs = analyze_similarity(
            user_species_list, synonym_map, group_names, similarity_matrix, total_frequency_per_group
        )
        
        if top_matches_data is None:
            st.error(t("err_no_matrix_match"))
            processed_species = set()
            name_conversion_map = {}
            ignored_inputs = [] 
            return

        # 3.1. TOP 3 ZHODY
        st.subheader(t("top3_title"))
        
        # Prepare localized dataframe for display
        localized_results = []
        for item in top_matches_data:
            localized_results.append({
                t("col_rank"): item['rank'],
                t("col_code"): item['code'],
                t("col_name"): item['name'],
                t("col_fqi"): item['fqi']
            })

        df_results = pd.DataFrame(localized_results)
        if not df_results.empty:
            df_results_display = df_results.set_index(t("col_rank"))
            st.dataframe(df_results_display, use_container_width=True)

        st.caption(t("fqi_caption"))

        st.markdown("---")
        
        # --- SEKCIA 3: DETAIY SPRACOVANIA ---
        st.subheader(t("sec3_title"))

        col1, col2, col3 = st.columns(3) 
        
        if show_processing_details:
            with st.expander(t("expander_check"), expanded=False):
                
                if remaining_unknown_species:
                    st.warning(t("warn_not_included").format(len(remaining_unknown_species)))
                    st.code("\n".join(remaining_unknown_species))
                    
                elif len(uploaded_unknown_species) > 0 and not remaining_unknown_species:
                    st.success(t("success_unknown_fixed"))
                elif len(uploaded_unknown_species) == 0 and len(uploaded_known_species) > 0:
                    st.success(t("success_no_unknown"))
                    
                if manual_selections_for_analysis:
                    if remaining_unknown_species or len(uploaded_unknown_species) > 0:
                        st.markdown("") 
                    st.success(t("success_manual_added").format(len(manual_selections_for_analysis)))
                    st.code("\n".join(manual_selections_for_analysis))
                else:
                    if not remaining_unknown_species and not uploaded_known_species:
                        st.info(t("info_no_manual"))
                
        with col1:
            st.markdown(t("processed_canon"))
            st.write(t("processed_count").format(len(processed_species)))
            
            with st.expander(t("expander_canon")):
                st.code("\n".join(sorted(list(processed_species))))

        with col2:
            conversions = {original: canonical for original, canonical in name_conversion_map.items() if original != canonical}
            st.markdown(t("synonym_conversions"))
            
            if conversions:
                df_conversions = pd.DataFrame(list(conversions.items()), columns=['Original', 'Canonical'])
                st.dataframe(df_conversions, use_container_width=True, hide_index=True)
            else:
                st.success(t("no_synonyms"))

        with col3:
            st.markdown(t("ignored_dups"))
            
            if ignored_inputs:
                st.warning(t("ignored_count").format(len(ignored_inputs)))
                st.caption(t("ignored_caption"))
                with st.expander("List"):
                    st.code("\n".join(ignored_inputs))
            else:
                st.success(t("success_no_dups"))

        st.markdown("---") 

        # --- SEKCIA 4: ÚDAJE Z TERÉNU A EXPORT ---
        st.subheader(t("sec4_title"))
        
        # Etáže
        
        lokalita_default = st.session_state.get('export_lokalita', '')
        suradnica_default = st.session_state.get('export_suradnica', '')
        mapovatel_default = st.session_state.get('export_mapovatel', '')
        datum_default = st.session_state.get('export_datum', date.today())
        pokryvnost_E3_default = st.session_state.get('export_E3', '0')
        pokryvnost_E2_default = st.session_state.get('export_E2', '0')
        pokryvnost_E1_default = st.session_state.get('export_E1', '0')
        pokryvnost_E0_default = st.session_state.get('export_E0', '0')

        with st.form("field_data_form"):
            col_a, col_b = st.columns([3, 1]) 
            with col_a:
                st.markdown(t("form_field_info"))
                lokalita = st.text_input(t("lbl_locality"), value=lokalita_default, key='export_lokalita')
                suradnica = st.text_input(t("lbl_coords"), value=suradnica_default, key='export_suradnica')
                mapovatel = st.text_input(t("lbl_mapper"), value=mapovatel_default, key='export_mapovatel')
                datum = st.date_input(t("lbl_date"), value=datum_default, key='export_datum')

            with col_b:
                st.markdown(t("form_covers"))
                help_text_etaze = t("help_cover")
                # Opravené použitie popiskov bez duplicity
                pokryvnost_E3 = st.text_input(t("lbl_e3"), value=pokryvnost_E3_default, key='export_E3', help=help_text_etaze)
                pokryvnost_E2 = st.text_input(t("lbl_e2"), value=pokryvnost_E2_default, key='export_E2', help=help_text_etaze)
                pokryvnost_E1 = st.text_input(t("lbl_e1"), value=pokryvnost_E1_default, key='export_E1', help=help_text_etaze)
                pokryvnost_E0 = st.text_input(t("lbl_e0"), value=pokryvnost_E0_default, key='export_E0', help=help_text_etaze)
                
            st.form_submit_button(t("btn_save_data"), type="primary")

        manual_data = {
            'lokalita': lokalita,
            'suradnica': suradnica,
            'mapovatel': mapovatel,
            'datum': datum,
            'pokryvnost_E3': pokryvnost_E3,
            'pokryvnost_E2': pokryvnost_E2,
            'pokryvnost_E1': pokryvnost_E1,
            'pokryvnost_E0': pokryvnost_E0,
            'manual_selections_for_analysis': manual_selections_for_analysis,
            'remaining_unknown_species': remaining_unknown_species,
        }

        # Need to regenerate df_results for export to ensure raw data structure if needed, 
        # or just pass the display DF. Passing df_results (localized) is fine for export.
        
        export_data_str = generate_export_data(
            df_results, 
            list(processed_species), 
            manual_data,
            lang=st.session_state['lang']
        )
        
        excel_data_bytes = generate_excel_data(
            df_results, 
            list(processed_species), 
            manual_data,
            lang=st.session_state['lang']
        )
        
        file_name_prefix = lokalita[:10].replace(' ', '_').strip() if lokalita else "new_record"
        
        # Určenie prefixu názvu súboru (biotope / habitat) podľa jazyka
        if st.session_state['lang'] == 'EN':
            file_base = "habitat_analysis"
        else:
            file_base = "biotop_analyza"

        col_xlsx, col_txt = st.columns(2)
        
        with col_xlsx: 
            st.download_button(
                label=t("btn_download_xlsx"),
                data=excel_data_bytes,
                file_name=f"{file_base}_{date.today().strftime('%Y%m%d')}_{file_name_prefix}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with col_txt: 
            st.download_button(
                label=t("btn_download_txt"),
                data=export_data_str,
                file_name=f"{file_base}_{date.today().strftime('%Y%m%d')}_{file_name_prefix}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        st.markdown("---") 
            

    st.markdown("<footer><p style='text-align: right; color: gray; font-size: small;'>© Róbert Šuvada 2025</p></footer>", unsafe_allow_html=True)


if __name__ == "__main__":
    biotope_web_app()