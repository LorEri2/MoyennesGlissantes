import streamlit as st
import pandas as pd
import os
import datetime
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Gestion Bankroll Multi", page_icon="💰", layout="wide")

# --- FICHIERS DE SAUVEGARDE ---
FILE_OVERS = "paris_overs.csv" 
FILE_STATS = "stats_max.csv"
FILE_SECURE = "home_draw.csv"
FILE_GOLD = "prono_or.csv"
FILE_CIA_2E = "cia_2echec.csv"

# ==============================================================================
# FONCTIONS PARTAGÉES & OPTIMISÉES
# ==============================================================================

@st.cache_data(show_spinner=False) 
def clean_and_read_csv(file_path):
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            
            # Nettoyage colonnes parasites
            cols_to_drop = ["ID_Tech", "Original_Idx", "Unnamed: 0", "Date.1"]
            for bad_col in cols_to_drop:
                if bad_col in df.columns: df = df.drop(columns=[bad_col])

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
# 1. PAGE OVERS (CORRIGÉE : Affichage des +1.5 / +2.5 et dates)
# ==============================================================================
def page_overs(title, file_path):
    st.header(title)
    
    with st.expander(f"➕ Ajouter un pari {title}", expanded=False):
        with st.form(f"form_{file_path}", clear_on_submit=True):
            cols = st.columns(5)
            date_in = cols[0].date_input("Date")
            team_in = cols[1].text_input("Équipe")
            type_in = cols[2].selectbox("Nb de Buts", ["+1.5", "+2.5"]) 
            cote_in = cols[3].number_input("Cote", 1.01, step=0.01)
            res_in = cols[4].selectbox("Résultat", ["En attente", "Gagné", "Perdu", "Remboursé"])
            
            if st.form_submit_button("Ajouter"):
                add_new_bet(file_path, {
                    "Date": date_in.strftime('%Y-%m-%d'),
                    "Equipe": team_in,
                    "Type_Over": type_in,
                    "Cote": cote_in,
                    "Resultat": res_in
                })
                st.success("Ajouté !")
                st.rerun()

    st.divider()
    
    df = clean_and_read_csv(file_path)
    required_cols = ["Date", "Equipe", "Type_Over", "Cote", "Resultat"]
    
    for c in required_cols: 
        if c not in df.columns: df[c] = ""

    # Correction automatique si le + a sauté dans le CSV
    if not df.empty:
        df["Type_Over"] = df["Type_Over"].astype(str).replace({"1.5": "+1.5", "2.5": "+2.5", "nan": ""})

    # Filtres
    c_filter, c_start, c_end = st.columns([2, 1, 1])
    filter_type = c_filter.multiselect("⚽ Filtrer par type :", ["+1.5", "+2.5"])
    
    d_start = c_start.date_input("Du", value=datetime.date(2023, 1, 1))
    d_end = c_end.date_input("Au", value=datetime.date.today() + datetime.timedelta(days=365))

    if not df.empty:
        mask = (df["Date"] >= pd.to_datetime(d_start)) & (df["Date"] <= pd.to_datetime(d_end))
        
        if filter_type:
            mask = mask & (df["Type_Over"].isin(filter_type))
            
        df_filtered = df[mask].copy()
        df_display = calculate_bankroll(df_filtered)
        
        if not df_display.empty:
            roi = df_display["Total_Bankroll"].iloc[0]
            nb = len(df_display)
            avg_odds = df_display["Cote"].mean()
            if nb > 0: win_rate = (len(df_display[df_display["Resultat"] == "Gagné"]) / nb * 100)
            else: win_rate = 0

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Bénéfice (Filtré)", f"{roi:+.2f} u")
            k2.metric("Nb Paris", nb)
            k3.metric("Cote Moy.", f"{avg_odds:.2f}")
            k4.metric("Réussite", f"{win_rate:.1f} %")
            
            df_show = df_display.copy()
            df_show["Date"] = df_show["Date"].dt.date
            
            h_calc = (len(df_show) + 1) * 38 + 10
            if h_calc > 1200: h_calc = 1200
            
            col_config = {
                "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                "Equipe": st.column_config.TextColumn("Equipe"),
                "Type_Over": st.column_config.SelectboxColumn("Nb Buts", options=["+1.5", "+2.5"], required=True),
                "Cote": st.column_config.NumberColumn("Cote", format="%.2f"),
                "Resultat": st.column_config.SelectboxColumn("Résultat", options=["En attente", "Gagné", "Perdu", "Remboursé"], required=True),
                "Gain_Unit": st.column_config.NumberColumn("Gain", format="%+.2f u", disabled=True),
                "Total_Bankroll": st.column_config.NumberColumn("Cumul", format="%+.2f u", disabled=True),
                "Original_Idx": None
            }

            edited = st.data_editor(
                df_show, 
                height=h_calc, 
                width="stretch", 
                num_rows="fixed", 
                hide_index=True,
                column_config=col_config
            )
            
            if not edited[required_cols].equals(df_display[required_cols]):
                save_from_editor(edited, file_path, required_cols)
                st.rerun()
        else:
            st.warning("Aucun résultat avec ces filtres.")
    else:
        st.info(f"Ajoute ton premier pari {title} !")


# ==============================================================================
# 2. PAGE GÉNÉRIQUE (Stats Max, 1N, Prono Or)
# ==============================================================================
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
    d_start = c_start.date_input("Du", value=datetime.date(2023, 1, 1))
    d_end = c_end.date_input("Au", value=datetime.date.today() + datetime.timedelta(days=365))
    
    df = clean_and_read_csv(file_path)
    required = ["Date", "Equipe", extra_col, "Cote", "Resultat"]
    for c in required: 
        if c not in df.columns: df[c] = ""
        
    if not df.empty:
        df[extra_col] = df[extra_col].astype(str).replace("nan", "") 

        mask = (df["Date"] >= pd.to_datetime(d_start)) & (df["Date"] <= pd.to_datetime(d_end))
        df_filtered = df[mask].copy()
        df_display = calculate_bankroll(df_filtered)
        if not df_display.empty:
            roi = df_display["Total_Bankroll"].iloc[0]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Bénéfice", f"{roi:+.2f} u")
            k2.metric("Nb", len(df_display))
            k3.metric("Cote Moy", f"{df_display['Cote'].mean():.2f}")
            if len(df_display) > 0: win_rate = (len(df_display[df_display['Resultat']=='Gagné'])/len(df_display)*100)
            else: win_rate = 0
            k4.metric("Win %", f"{win_rate:.1f}%")
            
            df_show = df_display.copy(); df_show["Date"] = df_show["Date"].dt.date
            col_conf = {"Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"), "Cote": st.column_config.NumberColumn("Cote", format="%.2f"), "Gain_Unit": st.column_config.NumberColumn("Gain", format="%+.2f u", disabled=True), "Total_Bankroll": st.column_config.NumberColumn("Cumul", format="%+.2f u", disabled=True), "Original_Idx": None}
            col_conf[extra_col] = st.column_config.TextColumn(extra_col, width="medium")
            
            edited = st.data_editor(df_show, height=(len(df_show)+1)*38+10, width="stretch", num_rows="fixed", hide_index=True, column_config=col_conf)
            if not edited[required].equals(df_display[required]): save_from_editor(edited, file_path, required); st.rerun()
        else: st.warning("Aucune donnée.")
    else: st.info(f"Ajoute ton premier pari {title} !")


# ==============================================================================
# 3. PAGE SIMPLE (CIA 2echec - CORRIGÉE POUR NE PLUS AVOIR DE DOUBLONS)
# ==============================================================================
def page_simple(title, file_path):
    st.header(title)
    with st.expander(f"➕ Ajouter un pari {title}", expanded=False):
        with st.form(f"form_{file_path}", clear_on_submit=True):
            cols = st.columns(4)
            date_in = cols[0].date_input("Date")
            team_in = cols[1].text_input("Équipe")
            cote_in = cols[2].number_input("Cote", 1.01, step=0.01)
            res_in = cols[3].selectbox("Résultat", ["En attente", "Gagné", "Perdu", "Remboursé"])
            
            if st.form_submit_button("Ajouter"):
                add_new_bet(file_path, {"Date": date_in.strftime('%Y-%m-%d'), "Equipe": team_in, "Cote": cote_in, "Resultat": res_in})
                st.success("Ajouté !"); st.rerun()
    st.divider()
    c_start, c_end = st.columns(2)
    d_start = c_start.date_input("Du", value=datetime.date(2023, 1, 1))
    d_end = c_end.date_input("Au", value=datetime.date.today() + datetime.timedelta(days=365))
    
    df = clean_and_read_csv(file_path)
    required = ["Date", "Equipe", "Cote", "Resultat"]
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
            if len(df_display) > 0: win_rate = (len(df_display[df_display['Resultat']=='Gagné'])/len(df_display)*100)
            else: win_rate = 0
            k4.metric("Win %", f"{win_rate:.1f}%")
            
            df_show = df_display.copy(); df_show["Date"] = df_show["Date"].dt.date
            col_conf = {"Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"), "Cote": st.column_config.NumberColumn("Cote", format="%.2f"), "Gain_Unit": st.column_config.NumberColumn("Gain", format="%+.2f u", disabled=True), "Total_Bankroll": st.column_config.NumberColumn("Cumul", format="%+.2f u", disabled=True), "Original_Idx": None}
            
            edited = st.data_editor(df_show, height=(len(df_show)+1)*38+10, width="stretch", num_rows="fixed", hide_index=True, column_config=col_conf)
            if not edited[required].equals(df_display[required]): save_from_editor(edited, file_path, required); st.rerun()
        else: st.warning("Aucune donnée.")
    else: st.info(f"Ajoute ton premier pari {title} !")


# ==============================================================================
# 4. PAGE PARIS PAR DATE
# ==============================================================================
def page_matchs_par_date():
    st.header("📅 Paris par Date")
    
    selected_date = st.date_input("Sélectionnez une date pour voir tous les paris associés :", value=datetime.date.today())
    
    st.markdown(f"#### Vos paris pour le : **{selected_date.strftime('%d/%m/%Y')}**")
    st.divider()

    strategies = {
        "⚽ Paris Overs": FILE_OVERS, 
        "📊 Stats Max": FILE_STATS, 
        "🛡️ 1N & Plus": FILE_SECURE, 
        "🧠 CIA 2echec": FILE_CIA_2E,
        "🏆 Prono en Or": FILE_GOLD
    }

    all_selected_bets = []

    for name, filepath in strategies.items():
        df = clean_and_read_csv(filepath)
        if not df.empty:
            df_selected = df[df["Date"].dt.date == selected_date].copy()
            if not df_selected.empty:
                df_selected.insert(0, "Stratégie", name)
                all_selected_bets.append(df_selected)

    if all_selected_bets:
        final_df = pd.concat(all_selected_bets, ignore_index=True)
        final_df["Date"] = final_df["Date"].dt.date
        
        cols_order = ["Stratégie", "Equipe", "Cote", "Resultat"]
        if "Type_Over" in final_df.columns: cols_order.append("Type_Over")
        if "Type_Pari" in final_df.columns: cols_order.append("Type_Pari")
        if "Infos" in final_df.columns: cols_order.append("Infos")
        
        cols_to_show = [c for c in cols_order if c in final_df.columns]
        
        st.dataframe(final_df[cols_to_show], use_container_width=True, hide_index=True)
        st.success(f"Vous avez **{len(final_df)} paris** enregistrés pour le {selected_date.strftime('%d/%m/%Y')}.")
    else:
        st.info(f"Aucun pari n'est enregistré pour le {selected_date.strftime('%d/%m/%Y')}.")

# ==============================================================================
# RECAPITULATIF GLOBAL
# ==============================================================================
def page_recap():
    st.header("🏆 Récapitulatif Mensuel Global")
    
    # --- FILTRES DE SIMULATION ---
    st.markdown("### 🎛️ Simulation des Gains (Filtres)")
    
    st.info("⚽ **Paris Overs**")
    recap_over_choice = st.multiselect("Filtrer par Type :", ["+1.5", "+2.5"], key="rec_overs")

    st.divider()

    strategies = {
        "⚽ Paris Overs": FILE_OVERS, 
        "📊 Stats Max": FILE_STATS, 
        "🧠 CIA 2echec": FILE_CIA_2E,
        "🏆 Prono en Or": FILE_GOLD
    }
    
    all_data = []
    
    for name, filepath in strategies.items():
        df = clean_and_read_csv(filepath)
        if not df.empty:
            
            # --- APPLICATION DES FILTRES DE SIMULATION ---
            if name == "⚽ Paris Overs":
                if recap_over_choice and "Type_Over" in df.columns:
                    # Sécurité pour bien comparer
                    df["Type_Over"] = df["Type_Over"].astype(str).replace({"1.5": "+1.5", "2.5": "+2.5"})
                    df = df[df["Type_Over"].isin(recap_over_choice)]

            if df.empty: continue

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
        
        total_global = pivot.loc['TOTAL GÉNÉRAL', 'TOTAL MOIS']
        st.metric("Bénéfice Total Cumulé (Après filtres)", f"{total_global:+.2f} u")
        
    else: st.warning("Pas de données correspondant aux critères.")

# ==============================================================================
# NAVIGATION
# ==============================================================================
with st.sidebar:
    st.title("Navigation")
    page = st.radio("Menu :", [
        "📅 Paris par Date",  
        "⚽ Paris Overs",       
        "📊 Stats Max", 
        "🛡️ 1N & Plus", 
        "🧠 CIA 2echec",
        "🏆 Prono en Or", 
        "🏆 Récapitulatif Global"
    ])
    st.divider()

if page == "📅 Paris par Date":
    page_matchs_par_date()
elif page == "⚽ Paris Overs":
    page_overs("⚽ Paris Overs", FILE_OVERS) 
elif page == "📊 Stats Max":
    generic_page("📊 Stats Max", FILE_STATS, "Type_Pari", "Over 2.5...") 
elif page == "🛡️ 1N & Plus":
    generic_page("🛡️ 1N & Plus", FILE_SECURE, "Infos", "+1.5 buts...")
elif page == "🧠 CIA 2echec":
    page_simple("🧠 CIA 2echec", FILE_CIA_2E)
elif page == "🏆 Prono en Or":
    generic_page("🏆 Prono en Or", FILE_GOLD, "Infos", "Analyse...")
else:
    page_recap()