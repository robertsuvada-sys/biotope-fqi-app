import streamlit as st
import re
import pandas as pd
from collections import defaultdict
from datetime import date 
import io 
from urllib.parse import quote 

# NÁZOV PÔVODNÉHO KARTALÓGVOÉHO SÚBORU
CATALOG_FILENAME = "ES Katalog biotopov Suvada ed 2023 v1.05.txt"

# --- CORE FACTORY AND DATA FUNCTIONS (Pre-cached) ---

def inner_dict_factory():
    """Používa sa ako factory pre vnorený defaultdict namiesto nespôsobnej lambda funkcie."""
    return defaultdict(int)

@st.cache_data
def load_file_content(filename):
    """Načíta obsah katalógu zo súboru, skúša bežné kódovania."""
    try:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(filename, 'r', encoding='Windows-1250') as f:
                return f.read()
    except FileNotFoundError:
        st.error(f"⚠️ CHYBA: Súbor s dátami '{filename}' sa nenašiel v priečinku aplikácie.")
        st.caption("Uistite sa, že súbor má presne tento názov a je v rovnakom priečinku ako python skript.")
        return None
    except Exception as e:
        st.error(f"Chyba pri načítaní súboru: {e}")
        return None

@st.cache_data
def parse_catalog_data(catalog_text):
    """Spracuje text katalógu a extrahuje mapu synoným (Sekcia 1) a maticu podobnosti (Sekcia 4)."""
    
    lines = catalog_text.split('\n')
    section_1_active = False
    section_4_active = False
    
    synonym_map = {}
    similarity_matrix = defaultdict(inner_dict_factory)
    group_names = {}
    current_canonical_name = None
    
    # Regulárne výrazy 
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
                # Ukladáme plný názov, ktorý obsahuje aj kód biotypu
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
    """Vypočíta súčet frekvencií pre VŠETKY kanonické druhy pre každý biotyp (Max Score)."""
    total_frequency = defaultdict(int)
    all_groups = set(group_names.keys())

    for canonical_name in similarity_matrix:
        species_data = similarity_matrix[canonical_name]
        for group_id, count in species_data.items():
            if group_id in all_groups:
                total_frequency[group_id] += count
    
    return dict(total_frequency)


def get_canonical_name(species_name, synonym_map):
    """Získa kanonické meno druhu, ak existuje, inak vráti pôvodné meno."""
    species_name = species_name.strip()
    return synonym_map.get(species_name, species_name)

@st.cache_data
def get_all_known_species(synonym_map, similarity_matrix):
    """Získa zjednotený zoznam všetkých známych druhov a synoným."""
    canonical_species = set(similarity_matrix.keys())
    all_known = canonical_species.union(set(synonym_map.keys())).union(set(synonym_map.values()))
    return sorted(list(all_known))

# NOVÁ FUNKCIA: Spracovanie nahraného súboru
def process_uploaded_species_list(uploaded_file, all_known_species):
    """
    Načíta druhy z TXT súboru a rozdelí ich na známe a neznáme druhy.
    Predpokladá, že každý riadok je jeden druh.
    """
    
    known_species = []
    unknown_species = []
    
    # Skúšame rôzne kódovania (utf-8, Windows-1250)
    try:
        string_data = uploaded_file.getvalue().decode("utf-8")
    except UnicodeDecodeError:
        try:
            string_data = uploaded_file.getvalue().decode("windows-1250")
        except:
            return None, None # Chyba kódovania
            
    # Spracovanie riadkov
    for line in string_data.split('\n'):
        # Očistíme riadok (trim, odstránenie tabulátorov/viacnásobných medzier)
        species = re.sub(r'\s+', ' ', line).strip()
        
        if species:
            if species in all_known_species:
                known_species.append(species)
            else:
                unknown_species.append(species)
                
    # Odstránenie duplikátov
    known_species = sorted(list(set(known_species)))
    unknown_species = sorted(list(set(unknown_species)))
    
    return known_species, unknown_species


# --- ANALYTICKÁ FUNKCIA S FQI VÝPOČTOM ---

@st.cache_data(show_spinner="Prebieha výpočet Frekvenčného Indexu (FQI)...")
def analyze_similarity(species_list, synonym_map, group_names, similarity_matrix, total_frequency_per_group):
    """
    Vyhodnotí podobnosť k biotopom (skupinám).
    FQI = (Kumulatívne skóre zadaných druhov / Celkové možné skóre skupiny) * 100
    Tiež sleduje, ktoré vstupy boli preskočené (kanonický duplikát).
    """
    
    cumulative_scores = defaultdict(int)
    valid_groups = set(group_names.keys())
    # OPRAVA: Premenná iniciovaná ako 'processed_species'
    processed_species = set() 
    name_conversion_map = {} 
    ignored_inputs = [] 
    
    # 1. KUMULATÍVNE SČÍTANIE A KONVERZIA
    for user_species in species_list:
        user_species = user_species.strip()
        canonical_name = get_canonical_name(user_species, synonym_map)
        
        if canonical_name in similarity_matrix:
            
            name_conversion_map[user_species] = canonical_name

            if canonical_name not in processed_species:
                processed_species.add(canonical_name)
                
                species_data = similarity_matrix[canonical_name]
                for group_id, count in species_data.items():
                    if group_id in valid_groups:
                        cumulative_scores[group_id] += count
            else:
                # Kanonický druh bol už spracovaný, tento vstup ignorujeme
                ignored_inputs.append(user_species)
                

    if not cumulative_scores:
        # Používame processed_species
        return None, processed_species, name_conversion_map, ignored_inputs 

    # 2. VÝPOČET FQI (Percentuálna normalizácia)
    fqi_scores = {}
    
    for group_id, cumulative_score in cumulative_scores.items():
        max_score = total_frequency_per_group.get(group_id, 0)
        
        if max_score > 0:
            fqi = (cumulative_score / max_score) * 100
            fqi_scores[group_id] = fqi
        else:
            fqi_scores[group_id] = 0.0

    # 3. ZORADENIE A VÝBER TOP 3
    sorted_scores = sorted(fqi_scores.items(), key=lambda item: item[1], reverse=True)
    top_matches_data = []
    
    # Regex pre robustnú extrakciu kódu (prvý non-whitespace token) a zvyšku názvu
    re_biotope_code_extractor = re.compile(r'^(\S+)\s+(.*)', re.IGNORECASE)

    for rank, (group_id, score) in enumerate(sorted_scores[:3]):
        biotope_full_name = group_names.get(group_id, f"Neznámy Biotop ({group_id})")
        
        # Pôvodný group_id (napr. Group42) ako fallback
        biotope_code = group_id 
        biotope_name = biotope_full_name

        match_code = re_biotope_code_extractor.match(biotope_full_name)
        
        if match_code:
            # Ak regex nájde zhodu
            biotope_code = match_code.group(1).strip() 
            biotope_name = match_code.group(2).strip()
            
            # Odstránenie voliteľnej pomlčky/medzier na začiatku názvu, ak tam zostala
            if biotope_name.startswith('-'):
                 biotope_name = biotope_name[1:].strip()

        
        top_matches_data.append({
            'Poradie': rank + 1,
            'KÓD Biotopu': biotope_code, # Zobraziť skratku LES05.1a, TRB01a atď.
            'Názov Biotopu': biotope_name, # Zobraziť plný názov
            'FQI (% Zhody)': f"{score:.2f} %", 
        })

    return top_matches_data, processed_species, name_conversion_map, ignored_inputs

# --- EXPORTNÁ FUNKCIA PRE TXT ---

def generate_export_data(fqi_results_df, canonical_species_list, manual_data):
    """
    Generuje ucelený textový reťazec pre export obsahujúci hlavičku, FQI výsledky a zoznam druhov.
    """
    
    # Dolné indexy pre etáže
    E3, E2, E1, E0 = "\u2083", "\u2082", "\u2081", "\u2080"
    
    # Prevod DataFrame na textovú tabuľku (CSV s tabulátorom pre čitateľnosť)
    fqi_table = fqi_results_df.reset_index(drop=True).to_csv(sep='\t', index=False)
    
    output = "--- EXPORT VÝSLEDKOV ANALÝZY BIOTOPU ---\n"
    output += "podľa publikácie Šuvada R. (ed.), 2023: Katalóg biotopov Slovenska. Druhé, rozšírené vydanie.\n\n"

    # 1. HLAVIČKA PRE MANUÁLNY ZÁPIS
    output += "SEKCIA 1: ÚDAJE Z TERÉNU (VYPLNENÉ V APLIKÁCII)\n"
    output += "--------------------------------------------------\n"
    output += f"Lokalita:              {manual_data['lokalita']}\n"
    output += f"Súradnice:             {manual_data['suradnica']}\n"
    output += f"Meno mapovateľa:       {manual_data['mapovatel']}\n"
    output += f"Dátum:                 {manual_data['datum'].strftime('%Y-%m-%d') if isinstance(manual_data['datum'], date) else manual_data['datum']}\n"
    output += f"Pokryvnosť etáží (E{E3}: stromové, E{E2}: krovité, E{E1}: bylinné, E{E0}: machové/lišajníkové):\n"
    output += f"  E{E3}:                  {manual_data['pokryvnost_E3']}\n"
    output += f"  E{E2}:                  {manual_data['pokryvnost_E2']}\n"
    output += f"  E{E1}:                  {manual_data['pokryvnost_E1']}\n"
    output += f"  E{E0}:                  {manual_data['pokryvnost_E0']}\n\n"
    
    # 2. VÝSLEDKY FQI ANALÝZY
    output += "SEKCIA 2: VÝSLEDKY FQI ANALÝZY (TOP 3)\n"
    output += "--------------------------------------------------\n"
    output += fqi_table
    output += "\n"

    # 3. KANONICKÉ DRUHY
    output += "SEKCIA 3: POUŽITÉ KANONICKÉ DRUHY\n"
    output += "--------------------------------------------------\n"
    output += "Počet kanonických druhov: " + str(len(canonical_species_list)) + "\n"
    output += "\n".join(sorted(canonical_species_list))
    
    # NOVÉ ZMENY PRE EXPORT NEZNÁMYCH DRUHOV
    remaining_unknown_species = manual_data.get('remaining_unknown_species')
    # Zabezpečíme, že zoznam je k dispozícii
    manual_selections_for_analysis = manual_data.get('manual_selections_for_analysis', []) 
    
    if manual_selections_for_analysis:
        # Sekcia 4: MANUÁLNE PRIDANÉ DRUHY
        output += "\n\nSEKCIA 4: MANUÁLNE PRIDANÉ DRUHY (Korekcia/Doplnenie)\n"
        output += "--------------------------------------------------\n"
        output += "Druhy, ktoré boli manuálne pridané/korigované v kroku 1.2:\n"
        output += "\n".join(manual_selections_for_analysis)

    if remaining_unknown_species:
        # Sekcia 5: NEZARADENÉ DRUHY (s upraveným textom)
        output += "\n\nSEKCIA 5: NEZARADENÉ DRUHY\n"
        output += "--------------------------------------------------\n"
        output += "Mená druhov z importovaného súboru, ktoré nebolo možné automaticky priradiť ku kanonickým druhom:\n" 
        output += "\n".join(remaining_unknown_species)
    # KONIEC NOVÝCH ZMIEN
    
    output += "\n\n--- KONIEC EXPORTU ---\n"
    
    return output

# --- EXPORTNÁ FUNKCIA PRE XLSX ---

def generate_excel_data(fqi_results_df, canonical_species_list, manual_data):
    """Generuje Excel súbor (.xlsx) s tromi listami dát."""
    
    # Dolné indexy pre etáže
    E3, E2, E1, E0 = "\u2083", "\u2082", "\u2081", "\u2080"
    
    # 1. PRIPRAVA DAT PRE HLAVICKU (ako DataFrame)
    header_data = [
        ("--- ZÁKLADNÉ ÚDAJE ---", ""),
        ("Lokalita", manual_data['lokalita']),
        ("Súradnice", manual_data['suradnica']),
        ("Meno mapovateľa", manual_data['mapovatel']),
        ("Dátum", manual_data['datum'].strftime('%Y-%m-%d') if isinstance(manual_data['datum'], date) else manual_data['datum']),
        ("--- POKRYVNOSŤ ETÁŽÍ ---", ""),
        (f"E{E3} (Stromové poschodie)", manual_data['pokryvnost_E3']),
        (f"E{E2} (Krovité poschodie)", manual_data['pokryvnost_E2']),
        (f"E{E1} (Bylinné poschodie)", manual_data['pokryvnost_E1']),
        (f"E{E0} (Machové/Liš. poschodie)", manual_data['pokryvnost_E0']),
    ]
    df_header = pd.DataFrame(header_data, columns=['Popis', 'Hodnota'])
    
    # 2. PRIPRAVA DAT PRE DRUHY
    df_species = pd.DataFrame(sorted(canonical_species_list), columns=['Kanonické druhy (použité v analýze)'])
    
    # NOVÉ ZMENY: Dáta o stave neznámych druhov
    remaining = manual_data.get('remaining_unknown_species', [])
    manual_added = manual_data.get('manual_selections_for_analysis', [])
    
    df_status = pd.DataFrame({
        'Stav': 
            ['Manuálne pridané (zaradené do analýzy)'] * len(manual_added) + 
            ['Nezaradené (pôvodný neznámy/preklep)'] * len(remaining),
        'Druh': manual_added + remaining
    })
    
    # 3. ZAPIS DO BYTESIO BUFFERU
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # A. Manuálne údaje (Hlavička)
        df_header.to_excel(writer, sheet_name='Data z terénu', index=False, startrow=0, startcol=0)

        # B. FQI Výsledky (už je DataFrame)
        df_fqi_excel = fqi_results_df.copy()
        df_fqi_excel.to_excel(writer, sheet_name='FQI Výsledky', index=False, startrow=0, startcol=0)

        # C. Kanonické druhy
        df_species.to_excel(writer, sheet_name='Kanonické druhy', index=False, startrow=0, startcol=0)

        # D. NOVÉ: Stav neznámych druhov
        if not df_status.empty:
            df_status.to_excel(writer, sheet_name='Stav Neznámych Druhov', index=False, startrow=0, startcol=0)

        # Optimalizácia šírky stĺpcov pre lepšiu čitateľnosť
        for sheetname in writer.sheets:
            worksheet = writer.sheets[sheetname]
            # Nastaví šírku pre prvé 4 stĺpce
            worksheet.set_column('A:D', 30)
            
    # Resetovanie pozície bufferu a vrátenie obsahu
    output.seek(0)
    return output.read()

# --- AKCIE PRE TLAČIDLÁ (Callbacks) ---

def calculate_fqi_action():
    """Uloží aktuálny výber a prepne režim na zobrazenie výsledkov."""
    
    # Spojenie ručne vybraných a známych nahraných druhov
    uploaded_known = st.session_state.get('uploaded_known_species', [])
    manual_selected = st.session_state.selected_species_multiselect
    
    # Odstránenie duplikátov medzi nahratými a ručne vybranými
    combined_species = list(set(uploaded_known + manual_selected))
    
    st.session_state['calculated_species'] = combined_species
    # NOVINKA: Explicitné uloženie manuálne vybraných druhov pre perzistentné zobrazenie v režime "results"
    st.session_state['manual_selections_for_display'] = manual_selected 
    st.session_state['app_mode'] = 'results'
    
# Callback pre spracovanie nahraného súboru
def handle_upload():
    """Spracuje nahraný súbor a aktualizuje session state."""
    
    uploaded_file = st.session_state.uploaded_file_key
    all_known_species = st.session_state.all_known_species_data
    
    if uploaded_file is not None:
        known_species, unknown_species = process_uploaded_species_list(uploaded_file, all_known_species)
        
        if known_species is None:
             st.error("Chyba: Nepodarilo sa prečítať súbor. Skúste iné kódovanie (napr. UTF-8 alebo Windows-1250).")
             return
             
        st.session_state['uploaded_known_species'] = known_species
        st.session_state['uploaded_unknown_species'] = unknown_species
        # Nechávame existujúci výber v multiselecte tak, ako je, ale upozorníme na novú situáciu
        st.toast(f"Načítaných druhov: {len(known_species) + len(unknown_species)}. Známych: {len(known_species)}, Neznámych: {len(unknown_species)}.", icon='📄')
    else:
        # Ak sa súbor odstráni
        st.session_state['uploaded_known_species'] = []
        st.session_state['uploaded_unknown_species'] = []
        st.toast("Nahratý súbor bol odstránený. Zoznam druhov z neho bol vyčistený.", icon='🗑️')


def reset_selection_action():
    """Prepne režim späť na výber a vyčistí stav nahraného súboru."""
    st.session_state['app_mode'] = 'selection'
    # Vyčistenie stavu pre hromadný upload a ručný výber
    st.session_state['uploaded_known_species'] = []
    st.session_state['uploaded_unknown_species'] = []
    st.session_state['selected_species_multiselect'] = []
    # Vyčistíme aj perzistentný kľúč
    st.session_state['manual_selections_for_display'] = []


# --- HLAVNÁ WEB APLIKÁCIA ---

def biotope_web_app():
    
    st.set_page_config(page_title="Identifikátor Biotopov (FQI)", layout="wide")
    
    st.title("🌿 Identifikátor Biotopov (FQI) na základe Expertného Systému")
    st.caption(f"Dáta načítané zo súboru: **{CATALOG_FILENAME}**")

    # Citácia
    st.markdown("""
        **Podľa publikácie:**
        Šuvada R. (ed.), 2023: Katalóg biotopov Slovenska. Druhé, rozšírené vydanie. –
        Štátna ochrana prírody SR, Banská Bystrica, 511 p. ISBN 978-80-8184-106-4
    """)
    st.markdown("---")


    # Inicializácia stavu
    if 'app_mode' not in st.session_state:
        st.session_state['app_mode'] = 'selection'
        st.session_state['calculated_species'] = [] 
        # PREMENNÉ PRE HROMADNÝ UPLOAD
        st.session_state['uploaded_known_species'] = []
        st.session_state['uploaded_unknown_species'] = []
        st.session_state['selected_species_multiselect'] = [] # Stav pre multiselect - inicializované
        st.session_state['manual_selections_for_display'] = [] # NOVINKA: Perzistentný stav manuálneho výberu

    # Krok 0: Načítanie a parsovanie dát (Cache dáta)
    catalog_text = load_file_content(CATALOG_FILENAME)
    if catalog_text is None:
        return

    synonym_map, group_names, similarity_matrix = parse_catalog_data(catalog_text)
    if synonym_map is None: 
        st.error("Nepodarilo sa spracovať dáta z katalógu. Skontrolujte jeho formátovanie.")
        return
        
    all_species = get_all_known_species(synonym_map, similarity_matrix)
    total_frequency_per_group = calculate_total_frequency_per_group(similarity_matrix, group_names)

    # Uloženie ALL_SPECIES do session (potrebné pre handle_upload)
    st.session_state.all_known_species_data = all_species 

    # Sidebar štatistiky
    st.sidebar.header("Štatistiky Dát")
    st.sidebar.write(f"Biotopov (skupín): **{len(group_names)}**")
    st.sidebar.write(f"Spracovaných druhov v matici: **{len(similarity_matrix)}**")
    st.sidebar.write(f"Celkový počet názvov/synoným na výber: **{len(all_species)}**")


    # --- RIADENIE REŽIMU APLIKÁCIE ---

    if st.session_state['app_mode'] == 'selection':
        # Režim 1: VÝBER DRUHOV

        st.header("1. Zadanie Druhov")
        
        # NOVÁ FUNKCIONALITA: HROMADNÝ UPLOAD
        st.subheader("1.1. Hromadné zadanie (TXT súbor)")
        # *** ZMENENÝ TEXT PODĽA POŽIADAVKY ***
        st.info("Nahrajte textový súbor, ktorý bude mať na riadku len meno jedného druhu bez informácie o pokryvnosti. Aplikácia automaticky spracuje známe druhy a identifikuje neznáme.")
        # ***********************************
        
        uploaded_file = st.file_uploader(
            "Vyberte TXT súbor so zoznamom druhov", 
            type=['txt'], 
            on_change=handle_upload,
            key='uploaded_file_key'
        )

        uploaded_known_species = st.session_state.get('uploaded_known_species', [])
        uploaded_unknown_species = st.session_state.get('uploaded_unknown_species', [])

        if uploaded_file and (uploaded_known_species or uploaded_unknown_species):
            st.success(f"Načítaných známych druhov zo súboru: **{len(uploaded_known_species)}**")
            
            # Zobrazenie neznámych druhov
            if uploaded_unknown_species:
                st.warning(f"Neznáme druhy v súbore (na manuálnu korekciu): **{len(uploaded_unknown_species)}**")
                st.caption("Tieto druhy nebudú zahrnuté do analýzy, kým ich nepriradíte k známemu druhu pomocou ručného výberu (možnosť 1.2).")
                # Zmena: Automatické rozbalenie zoznamu
                with st.expander("Zobraziť neznáme druhy", expanded=True): 
                    st.code("\n".join(uploaded_unknown_species))
            
            st.markdown("---")


        # NOVÁ/UPRAVENÁ FUNKCIONALITA: Ručný výber alebo úprava
        st.subheader("1.2. Manuálny výber (doplnenie / úprava / korekcia)")

        # OPRAVA: Odstránenie explicitného "default" na elimináciu Streamlit varovania
        current_species_list = st.multiselect(
            "Vyberte druh zo zoznamu (začnite písať pre filtrovanie), alebo ním **korigujte neznáme druhy** zo súboru:",
            options=all_species,
            key="selected_species_multiselect" 
        )
        
        # SÚHRN PRE ANALÝZU
        total_species_for_analysis = list(set(uploaded_known_species + current_species_list))

        st.info(f"Celkový počet druhov pre FQI analýzu (známe zo súboru + ručne vybrané): **{len(total_species_for_analysis)}**")
        
        if total_species_for_analysis:
            st.button(
                "🟢 Všetky druhy zadané, vypočítaj FQI", 
                on_click=calculate_fqi_action, 
                use_container_width=True
            )
        else:
            st.button("Všetky druhy zadané, vypočítaj FQI", disabled=True, use_container_width=True)


    elif st.session_state['app_mode'] == 'results':
        # Režim 2: ZOBRAZENIE VÝSLEDKOV

        user_species_list = st.session_state['calculated_species']
        uploaded_unknown_species = st.session_state.get('uploaded_unknown_species', [])
        # POUŽÍVAME NOVÚ, PERZISTENTNÚ HODNOTU (manuálne vybrané druhy v kroku 1.2)
        manual_selected_for_display = st.session_state.get('manual_selections_for_display', []) 
        uploaded_known_species = st.session_state.get('uploaded_known_species', []) 
        
        # ----------------------------------------------------
        # Zjednodušená LOGIKA PRE KONTROLU DRUHOV
        # ----------------------------------------------------
        
        # Druhy, ktoré boli PÔVODNE neznáme zo súboru (tieto sú nezaradené)
        remaining_unknown_species = uploaded_unknown_species 
        
        # Druhy, ktoré boli MANUÁLNE pridané/korigované v kroku 1.2. Tieto boli ZARADENÉ.
        manual_selections_for_analysis = manual_selected_for_display

        # KONTROLA PRE PODMIENENÉ ZOBRAZENIE
        # Zobrazíme detaily, len ak bol vykonaný HROMADNÝ IMPORT
        show_processing_details = (
            len(uploaded_known_species) > 0 or
            len(uploaded_unknown_species) > 0 or
            len(manual_selections_for_analysis) > 0 # Zobraziť aj ak bol iba manuálny výber
        )
        
        # ----------------------------------------------------

        if not user_species_list:
            st.error("Chyba: Neboli nájdené žiadne druhy na analýzu. Prepnite späť na výber.")
            st.button("⬅️ Zmeň druhovú skupinu", on_click=reset_selection_action)
            return

        st.header("2. Výsledky Analýzy FQI")
        
        st.button("⬅️ Zmeň druhovú skupinu", on_click=reset_selection_action)
        
        st.markdown("---")
        
        st.info(f"Analýza beží pre **{len(user_species_list)}** vybraných druhov.")

        # Spustenie FQI analýzy (cache)
        top_matches_data, processed_species, name_conversion_map, ignored_inputs = analyze_similarity(
            user_species_list, synonym_map, group_names, similarity_matrix, total_frequency_per_group
        )
        
        if top_matches_data is None:
            st.error("Nenašiel sa žiaden zadaný druh v matici podobnosti. Výpočet FQI nie je možný.")
            processed_species = set()
            name_conversion_map = {}
            ignored_inputs = [] 
            return

        # Krok 3: Zobrazenie výsledkov
        
        # 3.1. TOP 3 ZHODY
        st.subheader("Biotopy s najvyššou podobnosťou (FQI)")
        
        df_results = pd.DataFrame(top_matches_data)
        df_results_display = df_results.set_index('Poradie')
        st.dataframe(df_results_display, use_container_width=True)

        st.caption("FQI (Frekvenčný Index) je **%**, ktoré vyjadruje podiel súčtu frekvencií vybraných druhov na celkovej možnej frekvencii všetkých kanonických druhov v danej skupine. Vyššie percento = Vyššia zhoda.")

        st.markdown("---")
        
        # --- SEKCIA 3: DETAIY SPRACOVANIA ---
        st.subheader("3. Detaily Spracovania")

        col1, col2, col3 = st.columns(3) 
        
        # PODMIENENÉ ZOBRAZENIE
        if show_processing_details:
            with st.expander("Kontrola spracovania druhov zo súboru a manuálnych korekcií", expanded=True):
                
                # 1. Čo zostalo nezaradené (Pôvodné neznáme) - TERAZ AKO PRVÉ
                if remaining_unknown_species:
                    # Použitie upraveného textu
                    st.warning(
                        f"**{len(remaining_unknown_species)}** druhov nebolo v analýze zahrnutých. Mená druhov z importovaného súboru, ktoré nebolo možné automaticky priradiť ku kanonickým druhom."
                    )
                    st.code("\n".join(remaining_unknown_species))
                    
                
                elif len(uploaded_unknown_species) > 0 and not remaining_unknown_species:
                    st.success("Všetky pôvodne neznáme druhy boli manuálne opravené/priradené.")
                elif len(uploaded_unknown_species) == 0 and len(uploaded_known_species) > 0:
                    st.success("V nahratom súbore neboli žiadne neznáme druhy.")
                    
                
                # 2. Čo bolo manuálne pridané (Potenciálne opravené) - TERAZ AKO DRUHÉ
                if manual_selections_for_analysis:
                    # Drobné oddelenie, len ak predchádzajúci blok nebol st.success/st.info
                    if remaining_unknown_species or len(uploaded_unknown_species) > 0:
                        st.markdown("") # Malý vertikálny priestor
                        
                    st.success(f"**{len(manual_selections_for_analysis)}** druhov bolo **manuálne pridaných/korigovaných** v kroku 1.2 a boli zahrnuté do analýzy:")
                    st.code("\n".join(manual_selections_for_analysis))
                else:
                    # Zmenené z info na text, aby to vizuálne nezaťažovalo
                    if not remaining_unknown_species and not uploaded_known_species:
                        st.info("Do analýzy neboli pridané žiadne druhy ručným výberom.")
                

        # Pôvodné detaily spracovania
        with col1:
            st.markdown("##### Spracované druhy (kanonické)")
            st.write(f"**Počet spracovaných kanonických druhov:** {len(processed_species)}")
            
            with st.expander("Zobraziť použité kanonické mená"):
                st.code("\n".join(sorted(list(processed_species))))

        with col2:
            conversions = {original: canonical for original, canonical in name_conversion_map.items() if original != canonical}
            
            st.markdown(f"##### Konverzie Synonym (zadaný → kanonický)")
            
            if conversions:
                df_conversions = pd.DataFrame(list(conversions.items()), columns=['Zadané meno', 'Kanonické meno'])
                st.dataframe(df_conversions, use_container_width=True, hide_index=True)
            else:
                st.success("Neboli zadané žiadne synonymá, alebo bol zadaný už kanonický názov.")

        with col3:
            st.markdown(f"##### Ignorované duplikáty vstupu")
            
            if ignored_inputs:
                st.warning(f"**Ignorovaných vstupov: {len(ignored_inputs)}**")
                st.caption("Tieto druhy majú kanonické meno, ktoré už bolo v rámci výpočtu zahrnuté. Boli preskočené, aby sa predišlo duplicitnému započítaniu.")
                with st.expander("Zobraziť ignorované vstupy"):
                    st.code("\n".join(ignored_inputs))
            else:
                st.success("Neboli zadané žiadne duplikáty.")

        st.markdown("---") 

        # --- SEKCIA 4: ÚDAJE Z TERÉNU A EXPORT ---
        st.subheader("4. Údaje z terénu a Export")
        
        # Použitie dolných indexov
        E3, E2, E1, E0 = "\u2083", "\u2082", "\u2081", "\u2080"
        
        # Uchovanie dát zadaných do formuláru pre export
        lokalita_default = st.session_state.get('export_lokalita', '')
        suradnica_default = st.session_state.get('export_suradnica', '')
        mapovatel_default = st.session_state.get('export_mapovatel', '')
        datum_default = st.session_state.get('export_datum', date.today())
        pokryvnost_E3_default = st.session_state.get('export_E3', '0')
        pokryvnost_E2_default = st.session_state.get('export_E2', '0')
        pokryvnost_E1_default = st.session_state.get('export_E1', '0')
        pokryvnost_E0_default = st.session_state.get('export_E0', '0')

        lokalita, suradnica, mapovatel, datum = lokalita_default, suradnica_default, mapovatel_default, datum_default
        pokryvnost_E3, pokryvnost_E2, pokryvnost_E1, pokryvnost_E0 = pokryvnost_E3_default, pokryvnost_E2_default, pokryvnost_E1_default, pokryvnost_E0_default

        with st.form("field_data_form"):
            
            col_a, col_b = st.columns([3, 1]) 
            
            with col_a:
                st.markdown("##### Informácie o terénnom zázname")
                
                lokalita = st.text_input("Lokalita", value=lokalita_default, key='export_lokalita')
                suradnica = st.text_input("Súradnice", value=suradnica_default, key='export_suradnica')
                mapovatel = st.text_input("Meno mapovateľa", value=mapovatel_default, key='export_mapovatel')
                datum = st.date_input("Dátum zápisu", value=datum_default, key='export_datum')

            with col_b:
                st.markdown(f"##### Pokryvnosť etáží (E{E3}-E{E0})")
                
                help_text_etaze = "Pokryvnosť v %"
                pokryvnost_E3 = st.text_input(f"E{E3} (Stromové poschodie)", value=pokryvnost_E3_default, key='export_E3', help=help_text_etaze)
                pokryvnost_E2 = st.text_input(f"E{E2} (Krovité poschodie)", value=pokryvnost_E2_default, key='export_E2', help=help_text_etaze)
                pokryvnost_E1 = st.text_input(f"E{E1} (Bylinné poschodie)", value=pokryvnost_E1_default, key='export_E1', help=help_text_etaze)
                pokryvnost_E0 = st.text_input(f"E{E0} (Machové/Liš. poschodie)", value=pokryvnost_E0_default, key='export_E0', help=help_text_etaze)
                
            st.form_submit_button("Uložiť údaje (pred exportom)", type="primary")

        # Zostavenie manuálnych dát pre export
        manual_data = {
            'lokalita': lokalita,
            'suradnica': suradnica,
            'mapovatel': mapovatel,
            'datum': datum,
            'pokryvnost_E3': pokryvnost_E3,
            'pokryvnost_E2': pokryvnost_E2,
            'pokryvnost_E1': pokryvnost_E1,
            'pokryvnost_E0': pokryvnost_E0,
            # PRIDANÉ PRE EXPORT - používa perzistentnú hodnotu pre konzistentnosť
            'manual_selections_for_analysis': manual_selections_for_analysis,
            'remaining_unknown_species': remaining_unknown_species,
        }

        # Generovanie obsahu pre TXT export
        export_data_str = generate_export_data(
            df_results, 
            list(processed_species), 
            manual_data
        )
        
        # Generovanie obsahu pre XLSX export
        excel_data_bytes = generate_excel_data(
            df_results, 
            list(processed_species), 
            manual_data
        )
        
        # Tlačidlá pre stiahnutie v stĺpcoch (vyrovnané na jednom riadku)
        file_name_prefix = lokalita[:10].replace(' ', '_').strip() if lokalita else "novy_zapis"
        
        col_xlsx, col_txt = st.columns(2)
        
        with col_xlsx: 
            st.download_button(
                label="⬇️ Export výsledkov (Excel XLSX)",
                data=excel_data_bytes,
                file_name=f"biotop_analyza_{date.today().strftime('%Y%m%d')}_{file_name_prefix}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with col_txt: 
            st.download_button(
                label="⬇️ Export výsledkov (TXT formát)",
                data=export_data_str,
                file_name=f"biotop_analyza_{date.today().strftime('%Y%m%d')}_{file_name_prefix}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
        st.markdown("---") 
            

    # Copyright Footer
    st.markdown("<footer><p style='text-align: right; color: gray; font-size: small;'>© Róbert Šuvada 2025</p></footer>", unsafe_allow_html=True)


if __name__ == "__main__":
    biotope_web_app()