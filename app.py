import streamlit as st
import pandas as pd
import os
import datetime
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Gestion Bankroll Multi", page_icon="💰", layout="wide")

# --- FICHIERS DE SAUVEGARDE ---
FILE_MARKET = "mes_matchs.csv"
FILE_OVER25 = "over_25_special.csv"  # NOUVEAU FICHIER POUR LA STRATEGIE +2.5 BUTS
FILE_STATS = "stats_max.csv"
FILE_SECURE = "home_draw.csv"
FILE_CIA = "cia_80.csv"
FILE_GOLD = "prono_or.csv"
FILE_HOCKEY = "hockey.csv"
FILE_SCORERS = "buteurs.csv"

# ==============================================================================
# FONCTIONS PARTAGÉES & OPTIMISÉES
# ==============================================================================

@st.cache_data(show_spinner=False) 
def clean_and_read_csv(file_path):
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            
            # Nettoyage colonnes parasites
            cols_to_drop = ["ID_Tech", "Original_Idx", "Unnamed: 0"]
            for bad_col in cols_to_drop:
                if bad_col in df.columns: df = df.drop(columns=[bad_col])

            # Réparation pour les fichiers type "Market Move" (Market + Over2.5)
            # S'assure que les colonnes sont bien nommées
            if ("matchs" in file_path or "over_25" in file_path) and len(df.columns) >= 4:
                 if "Buts_Dernier_Match" not in df.columns:
                     # On tente de renommer la 4eme colonne si elle a un vieux nom
                     cols = list(df.columns)
                     if len(cols) > 3:
                        df = df.rename(columns={cols[3]: "Buts_Dernier_Match"})

        except:
            return pd.DataFrame()
        
        if "Date" in df.columns:
            df["Date"] = df["Date"].astype(str).str.split(" ").str[0]
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, format='mixed', errors='coerce')
            df["Date"] = df["Date"].fillna(pd.Timestamp.today())
            df["Date"] = df["Date"].dt.normalize()
            
        if "Cote" in df.columns:
            df["Cote"] = pd.to_numeric(df["Cote"], errors='coerce').fillna(0.0)
            
        return df
    return pd.DataFrame()

def calculate_gain_unit(df):
    if df.empty: return df
    def get_gain(row):
        statut = str(row.get("Resultat", "En attente"))
        try: cote = float(row.get("Cote", 0.0))
        except: cote = 0.0
        if statut == "Gagné": return cote - 1
        elif statut == "Perdu": return -1.0
        else: return 0.0
    df["Gain_Unit"] = df.apply(get_gain, axis=1)
    return df

def calculate_bankroll(df):
    if df.empty: return df
    df = calculate_gain_unit(df)
    df["Original_Idx"] = df.index
    df_calc = df.sort_values(by=["Date", "Original_Idx"], ascending=[True, False])
    df_calc["Total_Bankroll"] = df_calc["Gain_Unit"].cumsum()
    df_display = df_calc.sort_values(by=["Date", "Original_Idx"], ascending=[False, True])
    return df_display

def save_from_editor(edited_df, file_path, cols_to_save):
    if os.path.exists(file_path):
        try: df_full = pd.read_csv(file_path)
        except: return 
    else: return

    if "Date" in df_full.columns:
        df_full["Date"] = pd.to_datetime(df_full["Date"], dayfirst=True, format='mixed', errors='coerce')

    for index, row in edited_df.iterrows():
        original_idx = row["Original_Idx"]
        if original_idx in df_full.index:
            for col in cols_to_save:
                if col in row and col != "Date":
                    df_full.at[original_idx, col] = row[col]
            if "Date" in row:
                df_full.at[original_idx, "Date"] = pd.to_datetime(row["Date"])

    df_save = df_full.sort_values(by=["Date"], ascending=[False], kind='stable')
    df_save["Date"] = pd.to_datetime(df_save["Date"]).dt.strftime('%Y-%m-%d')
    df_save = df_save[cols_to_save]
    df_save.to_csv(file_path, index=False)
    st.cache_data.clear()

def add_new_bet(file_path, new_data):
    new_row = pd.DataFrame([new_data])
    if os.path.exists(file_path):
        try: df_old = pd.read_csv(file_path)
        except: df_old = pd.DataFrame()
    else: df_old = pd.DataFrame()
    df_final = pd.concat([new_row, df_old], ignore_index=True)
    df_final.to_csv(file_path, index=False)
    st.cache_data.clear()

# ==============================================================================
# LOGIQUE TYPE "MARKET MOVE" (Utilisée pour Market Moves ET +2.5 Buts)
# ==============================================================================
def page_market_style_logic(title, file_path):
    st.header(title)
    
    FILTER_OPTIONS = ["-1.5", "-2.5", "-3.5", "+1.5", "+2.5", "+3.5"]
    INPUT_OPTIONS = ["0", "1", "2", "3", "4", "5", "-1.5", "-2.5", "-3.5", "+1.5", "+2.5", "+3.5"]

    with st.expander(f"➕ Ajouter un pari {title}", expanded=False):
        with st.form(f"form_{file_path}", clear_on_submit=True):
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            date_in = c1.date_input("Date")
            team_in = c2.text_input("Équipe")
            drop_in = c3.number_input("% Baisse", step=0.1)
            buts_in = c4.selectbox("Buts D. Match", options=INPUT_OPTIONS, index=3) 
            cote_in = c5.number_input("Cote", 1.01, step=0.01)
            res_in = c6.selectbox("Résultat", ["En attente", "Gagné", "Perdu", "Remboursé"])
            
            if st.form_submit_button("Ajouter"):
                add_new_bet(file_path, {
                    "Date": date_in.strftime('%Y-%m-%d'),
                    "Equipe": team_in,
                    "Baisse_Moyenne": drop_in,
                    "Buts_Dernier_Match": buts_in,
                    "Cote": cote_in,
                    "Resultat": res_in
                })
                st.success("Ajouté !")
                st.rerun()

    st.divider()
    
    df = clean_and_read_csv(file_path)
    
    # Init colonnes
    required_cols = ["Date", "Equipe", "Baisse_Moyenne", "Buts_Dernier_Match", "Cote", "Resultat"]
    for c in required_cols: 
        if c not in df.columns: df[c] = ""

    df["Buts_Numeric"] = pd.to_numeric(df["Buts_Dernier_Match"], errors='coerce')
    df["Buts_Dernier_Match"] = df["Buts_Dernier_Match"].astype(str).replace("nan", "")

    # Filtres
    c_filter_drop, c_filter_buts, c_start, c_end = st.columns([1.5, 1.5, 1, 1])
    filter_min_drop = c_filter_drop.slider("📉 Baisse min (%) :", 0, 30, 0, step=5)
    filter_buts_choice = c_filter_buts.multiselect("⚽ Filtre Buts (Dernier match) :", FILTER_OPTIONS)
    
    d_start = c_start.date_input("Du", value=datetime.date(2025, 1, 1))
    d_end = c_end.date_input("Au", value=datetime.date.today() + datetime.timedelta(days=365))

    if not df.empty:
        mask = (df["Date"] >= pd.to_datetime(d_start)) & (df["Date"] <= pd.to_datetime(d_end))
        df["Baisse_Moyenne"] = pd.to_numeric(df["Baisse_Moyenne"], errors='coerce').fillna(0)
        mask = mask & (df["Baisse_Moyenne"] >= filter_min_drop)
        
        if filter_buts_choice:
            mask_buts = pd.Series(False, index=df.index)
            for choice in filter_buts_choice:
                if choice == "+1.5": mask_buts |= (df["Buts_Numeric"] > 1.5)
                elif choice == "+2.5": mask_buts |= (df["Buts_Numeric"] > 2.5)
                elif choice == "+3.5": mask_buts |= (df["Buts_Numeric"] > 3.5)
                elif choice == "-1.5": mask_buts |= (df["Buts_Numeric"] < 1.5)
                elif choice == "-2.5": mask_buts |= (df["Buts_Numeric"] < 2.5)
                elif choice == "-3.5": mask_buts |= (df["Buts_Numeric"] < 3.5)
            mask = mask & mask_buts
            
        df_filtered = df[mask].copy()
        df_display = calculate_bankroll(df_filtered)
        
        if not df_display.empty:
            roi = df_display["Total_Bankroll"].iloc[0]
            nb = len(df_display)
            avg_odds = df_display["Cote"].mean()
            win_rate = (len(df_display[df_display["Resultat"] == "Gagné"]) / nb * 100) if nb > 0 else 0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Bénéfice (Filtré)", f"{roi:+.2f} u")
            k2.metric("Nb Paris", nb)
            k3.metric("Cote Moy.", f"{avg_odds:.2f}")
            k4.metric("Réussite", f"{win_rate:.1f} %")
            
            df_show = df_display.copy()
            df_show["Date"] = df_show["Date"].dt.date
            
            h_calc = (len(df_show) + 1) * 38 + 10
            if h_calc > 1200: h_calc = 1200
            
            edited = st.data_editor(
                df_show, 
                height=h_calc, 
                width="stretch", 
                num_rows="fixed", 
                hide_index=True,
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                    "Equipe": st.column_config.TextColumn("Equipe"),
                    "Baisse_Moyenne": st.column_config.ProgressColumn("Drop %", format="%.1f%%", min_value=0, max_value=100),
                    "Buts_Dernier_Match": st.column_config.TextColumn("Buts DM", width="small"),
                    "Cote": st.column_config.NumberColumn("Cote", format="%.2f"),
                    "Resultat": st.column_config.SelectboxColumn("Résultat", options=["En attente", "Gagné", "Perdu", "Remboursé"], required=True),
                    "Gain_Unit": st.column_config.NumberColumn("Gain", format="%+.2f u", disabled=True),
                    "Total_Bankroll": st.column_config.NumberColumn("Cumul", format="%+.2f u", disabled=True),
                    "Original_Idx": None, "Buts_Numeric": None, "ID_Tech": None
                }
            )
            
            check_cols = ["Equipe", "Baisse_Moyenne", "Buts_Dernier_Match", "Cote", "Resultat"]
            if not edited[check_cols].equals(df_display[check_cols]):
                save_from_editor(edited, file_path, check_cols + ["Date"])
                st.rerun()
        else:
            st.warning("Aucun résultat avec ces filtres.")
    else:
        st.info(f"Ajoute ton premier pari {title} !")

# ==============================================================================
# PAGES BUTEURS ET GENERIQUES
# ==============================================================================

def page_buteurs():
    st.header("⚽ Buteurs")
    with st.expander("➕ Ajouter un pari Buteur", expanded=False):
        with st.form("form_buteurs", clear_on_submit=True):
            cols = st.columns(5)
            date_in = cols[0].date_input("Date")
            player_in = cols[1].text_input("Joueur")
            club_in = cols[2].text_input("Club")
            cote_in = cols[3].number_input("Cote", 1.01, step=0.01)
            res_in = cols[4].selectbox("Résultat", ["En attente", "Gagné", "Perdu", "Remboursé"])
            if st.form_submit_button("Ajouter"):
                add_new_bet(FILE_SCORERS, {"Date": date_in.strftime('%Y-%m-%d'), "Joueur": player_in, "Club": club_in, "Cote": cote_in, "Resultat": res_in})
                st.success("Ajouté !"); st.rerun()
    st.divider()
    c_start, c_end = st.columns(2)
    d_start = c_start.date_input("Du", value=datetime.date(2025, 1, 1))
    d_end = c_end.date_input("Au", value=datetime.date.today() + datetime.timedelta(days=365))

    df = clean_and_read_csv(FILE_SCORERS)
    required = ["Date", "Joueur", "Club", "Cote", "Resultat"]
    for c in required: 
        if c not in df.columns: df[c] = ""
    
    if not df.empty:
        mask = (df["Date"] >= pd.to_datetime(d_start)) & (df["Date"] <= pd.to_datetime(d_end))
        df_filtered = df[mask].copy()
        df_display = calculate_bankroll(df_filtered)
        if not df_display.empty:
            roi = df_display["Total_Bankroll"].iloc[0]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Bénéfice", f"{roi:+.2f} u")
            k2.metric("Nb", len(df_display))
            k3.metric("Cote Moy", f"{df_display['Cote'].mean():.2f}")
            k4.metric("Win %", f"{(len(df_display[df_display['Resultat']=='Gagné'])/len(df_display)*100):.1f}%")

            df_show = df_display.copy(); df_show["Date"] = df_show["Date"].dt.date
            edited = st.data_editor(df_show, height=(len(df_show)+1)*38+10, width="stretch", num_rows="fixed", hide_index=True, column_config={
                "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"), "Cote": st.column_config.NumberColumn("Cote", format="%.2f"),
                "Gain_Unit": st.column_config.NumberColumn("Gain", format="%+.2f u", disabled=True), "Total_Bankroll": st.column_config.NumberColumn("Cumul", format="%+.2f u", disabled=True), "Original_Idx": None
            })
            if not edited[required].equals(df_display[required]): save_from_editor(edited, FILE_SCORERS, required); st.rerun()
        else: st.warning("Aucune donnée.")
    else: st.info("Ajoute un pari Buteur !")

def generic_page(title, file_path, extra_col, placeholder):
    st.header(title)
    with st.expander(f"➕ Ajouter un pari {title}", expanded=False):
        with st.form(f"form_{file_path}", clear_on_submit=True):
            cols = st.columns(5)
            date_in = cols[0].date_input("Date")
            team_in = cols[1].text_input("Équipe")
            extra_val = cols[2].text_input(extra_col, placeholder=placeholder)
            cote_in = cols[3].number_input("Cote", 1.01, step=0.01)
            res_in = cols[4].selectbox("Résultat", ["En attente", "Gagné", "Perdu", "Remboursé"])
            if st.form_submit_button("Ajouter"):
                add_new_bet(file_path, {"Date": date_in.strftime('%Y-%m-%d'), "Equipe": team_in, extra_col: extra_val, "Cote": cote_in, "Resultat": res_in})
                st.success("Ajouté !"); st.rerun()
    st.divider()
    c_start, c_end = st.columns(2)
    d_start = c_start.date_input("Du", value=datetime.date(2025, 1, 1))
    d_end = c_end.date_input("Au", value=datetime.date.today() + datetime.timedelta(days=365))
    
    df = clean_and_read_csv(file_path)
    required = ["Date", "Equipe", extra_col, "Cote", "Resultat"]
    for c in required: 
        if c not in df.columns: df[c] = ""
        
    if not df.empty:
        mask = (df["Date"] >= pd.to_datetime(d_start)) & (df["Date"] <= pd.to_datetime(d_end))
        df_filtered = df[mask].copy()
        df_display = calculate_bankroll(df_filtered)
        if not df_display.empty:
            roi = df_display["Total_Bankroll"].iloc[0]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Bénéfice", f"{roi:+.2f} u")
            k2.metric("Nb", len(df_display))
            k3.metric("Cote Moy", f"{df_display['Cote'].mean():.2f}")
            k4.metric("Win %", f"{(len(df_display[df_display['Resultat']=='Gagné'])/len(df_display)*100):.1f}%")
            
            df_show = df_display.copy(); df_show["Date"] = df_show["Date"].dt.date
            col_conf = {"Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"), "Cote": st.column_config.NumberColumn("Cote", format="%.2f"), "Gain_Unit": st.column_config.NumberColumn("Gain", format="%+.2f u", disabled=True), "Total_Bankroll": st.column_config.NumberColumn("Cumul", format="%+.2f u", disabled=True), "Original_Idx": None}
            col_conf[extra_col] = st.column_config.TextColumn(extra_col, width="medium")
            
            edited = st.data_editor(df_show, height=(len(df_show)+1)*38+10, width="stretch", num_rows="fixed", hide_index=True, column_config=col_conf)
            if not edited[required].equals(df_display[required]): save_from_editor(edited, file_path, required); st.rerun()
        else: st.warning("Aucune donnée.")
    else: st.info(f"Ajoute ton premier pari {title} !")

# ==============================================================================
# RECAP
# ==============================================================================
def page_recap():
    st.header("🏆 Récapitulatif Mensuel Global")
    strategies = {
        "📉 Market Moves": FILE_MARKET, 
        "⚽ +2.5 Buts": FILE_OVER25,  # Ajouté au récap
        "📊 Stats Max": FILE_STATS, 
        "🛡️ 1N & Plus": FILE_SECURE, 
        "🧠 CIA 80%": FILE_CIA,
        "🏆 Prono en Or": FILE_GOLD,
        "🏒 Hockey": FILE_HOCKEY,
        "⚽ Buteurs": FILE_SCORERS
    }
    all_data = []
    for name, filepath in strategies.items():
        df = clean_and_read_csv(filepath)
        if not df.empty:
            df = calculate_gain_unit(df)
            df['Month_Sort'] = df['Date'].dt.to_period('M')
            months_fr = {1:'Janvier', 2:'Février', 3:'Mars', 4:'Avril', 5:'Mai', 6:'Juin', 7:'Juillet', 8:'Août', 9:'Septembre', 10:'Octobre', 11:'Novembre', 12:'Décembre'}
            df['Mois'] = df['Date'].apply(lambda x: f"{months_fr[x.month]} {x.year}")
            monthly_gains = df.groupby(['Month_Sort', 'Mois'])['Gain_Unit'].sum().reset_index()
            monthly_gains['Stratégie'] = name
            all_data.append(monthly_gains)
    
    if all_data:
        full_df = pd.concat(all_data)
        pivot = full_df.pivot_table(index=['Month_Sort', 'Mois'], columns='Stratégie', values='Gain_Unit', aggfunc='sum').fillna(0)
        pivot = pivot.sort_index(ascending=True)
        pivot.index = pivot.index.get_level_values('Mois')
        pivot["TOTAL MOIS"] = pivot.sum(axis=1)
        pivot = pd.concat([pivot, pd.DataFrame(pivot.sum(axis=0).rename("TOTAL GÉNÉRAL")).T])
        
        def color_coding(val): return f'color: {"red" if val < 0 else "green" if val > 0 else "black"}; font-weight: bold'
        st.dataframe(pivot.style.map(color_coding).format("{:+.2f} u"), width="stretch", height=(len(pivot)+1)*35+50)
        st.metric("Total", f"{pivot.loc['TOTAL GÉNÉRAL', 'TOTAL MOIS']:+.2f} u")
    else: st.warning("Pas de données.")

# ==============================================================================
# NAVIGATION
# ==============================================================================
with st.sidebar:
    st.title("Navigation")
    page = st.radio("Menu :", [
        "📉 Market Moves", 
        "⚽ +2.5 Buts",       # NOUVEAU MENU ICI
        "📊 Stats Max", 
        "🛡️ 1N & Plus", 
        "🧠 CIA 80%", 
        "🏆 Prono en Or", 
        "🏒 Hockey", 
        "⚽ Buteurs",
        "🏆 Récapitulatif Global"
    ])
    st.divider()

if page == "📉 Market Moves":
    page_market_style_logic("📉 Market Moves", FILE_MARKET)
elif page == "⚽ +2.5 Buts":
    page_market_style_logic("⚽ +2.5 Buts", FILE_OVER25) # Même logique que Market Moves
elif page == "📊 Stats Max":
    generic_page("📊 Stats Max", FILE_STATS, "Type_Pari", "Over 2.5...") # Remis comme avant
elif page == "🛡️ 1N & Plus":
    generic_page("🛡️ 1N & Plus", FILE_SECURE, "Infos", "+1.5 buts...")
elif page == "🧠 CIA 80%":
    generic_page("🧠 CIA 80%", FILE_CIA, "Infos", "Note...")
elif page == "🏆 Prono en Or":
    generic_page("🏆 Prono en Or", FILE_GOLD, "Infos", "Analyse...")
elif page == "🏒 Hockey":
    generic_page("🏒 Hockey", FILE_HOCKEY, "Type de Pari", "Ottawa ML / Over 5.5...")
elif page == "⚽ Buteurs":
    page_buteurs()
else:
    page_recap()