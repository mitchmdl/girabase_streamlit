import streamlit as st
import pandas as pd
import numpy as np
from parameters import get_color
from engine import (
    calculer_flux_circulant, 
    calculer_capacite_girabase, 
    calculer_capacite_sortie, 
    calculer_files_et_retards
)
from visualizations import (
    generer_heatmap_od, 
    dessiner_schema_giratoire, 
    plot_saturation_curve, 
    plot_comparaison_barres, 
    plot_chord_diagram
)
from io_xml import exporter_xml, importer_xml

st.set_page_config(
    page_title="Girabase", 
    page_icon="🚗",
    layout="wide"
)

# --- ÉTAT INITIAL ---
if "nb_branches" not in st.session_state:
    st.session_state.nb_branches = 4
if "diametre" not in st.session_state:
    st.session_state.diametre = 40.0
if "mode_expert" not in st.session_state:
    st.session_state.mode_expert = False
if "t0" not in st.session_state:
    st.session_state.t0 = 4.0
if "ts" not in st.session_state:
    st.session_state.ts = 2.0
if "editor_version" not in st.session_state:
    st.session_state.editor_version = 0
if "last_imported_id" not in st.session_state:
    st.session_state.last_imported_id = None

# Initialisation des noms par défaut
for i in range(6):
    if f"nom_{i}" not in st.session_state:
        st.session_state[f"nom_{i}"] = f"Branche {i+1}"

if "df_od" not in st.session_state:
    n = st.session_state.nb_branches
    noms = [st.session_state[f"nom_{i}"] for i in range(n)]
    st.session_state.df_od = pd.DataFrame(
        np.zeros((n, n), dtype=int),
        columns=[f"Vers {nom}" for nom in noms],
        index=[f"Depuis {nom}" for nom in noms]
    )

st.title("🔄🛣️ Estimation de la capacité d'un carrefour giratoire")

st.markdown("""
Analyse capacitaire, files d'attente et retards selon les méthodes **Girabase / CEREMA**.
""")

# --- SIDEBAR : GESTION DE CONFIGURATION (XML) ---
st.sidebar.image("BlocMarque_RF-Cerema_horizontal.jpg", use_container_width=True)
st.sidebar.header("💾 Gestion de configuration")

with st.sidebar.expander("📂 Importer un fichier XML", expanded=True):
    uploaded_xml = st.file_uploader("Fichier XML", type=["xml"], label_visibility="collapsed")
    if uploaded_xml is not None:
        file_bytes = uploaded_xml.getvalue()
        file_hash = hash(file_bytes)
        if st.session_state.last_imported_id != file_hash:
            try:
                config_chargee = importer_xml(uploaded_xml)
                st.session_state.nb_branches = config_chargee["nb_branches"]
                st.session_state.diametre = config_chargee["diametre"]
                st.session_state.mode_expert = config_chargee["mode_expert"]
                st.session_state.t0 = config_chargee["t0"]
                st.session_state.ts = config_chargee["ts"]
                st.session_state.df_od = config_chargee["df_od"]
                
                for idx, b in enumerate(config_chargee["branches_config"]):
                    st.session_state[f"nom_{idx}"] = b["nom"]
                    st.session_state[f"v_{idx}"] = b["voies"]
                    st.session_state[f"l_{idx}"] = b["largeur"]
                
                st.session_state.last_imported_id = file_hash
                st.session_state.editor_version += 1
                st.success("✅ Configuration importée !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur d'import : {e}")

# --- SIDEBAR : GÉOMÉTRIE & BRANCHES ---
st.sidebar.header("📐 Géométrie du carrefour")

def on_branches_count_changed():
    n_new = st.session_state.slider_nb_branches
    n_old = len(st.session_state.df_od)
    if n_new != n_old:
        new_mat = np.zeros((n_new, n_new), dtype=int)
        min_n = min(n_new, n_old)
        new_mat[:min_n, :min_n] = st.session_state.df_od.values[:min_n, :min_n]
        
        noms = [st.session_state.get(f"nom_{i}", f"Branche {i+1}") for i in range(n_new)]
        st.session_state.df_od = pd.DataFrame(
            new_mat,
            columns=[f"Vers {nom}" for nom in noms],
            index=[f"Depuis {nom}" for nom in noms]
        )
        st.session_state.nb_branches = n_new
        st.session_state.editor_version += 1

nb_branches = st.sidebar.slider(
    "Nombre de branches", 3, 6, 
    value=st.session_state.nb_branches, 
    key="slider_nb_branches",
    on_change=on_branches_count_changed
)

diametre = st.sidebar.number_input(
    "Diamètre extérieur (m)", 20.0, 100.0, 
    value=float(st.session_state.diametre), step=1.0
)
st.session_state.diametre = diametre

# Configuration détaillée de chaque branche
branches_config = []
noms_actuels = []

for i in range(nb_branches):
    st.sidebar.subheader(f"Branche {i+1}")
    nom_branche = st.sidebar.text_input(
        f"Nom B{i+1}", 
        value=st.session_state.get(f"nom_{i}", f"Branche {i+1}"), 
        key=f"nom_{i}"
    )
    noms_actuels.append(nom_branche)
    
    voies_def = st.session_state.get(f"v_{i}", 1)
    voies = st.sidebar.selectbox(f"Voies {nom_branche}", [1, 2], index=0 if voies_def == 1 else 1, key=f"v_{i}")
    
    l_def = st.session_state.get(f"l_{i}", 3.5 if voies == 1 else 7.0)
    largeur = st.sidebar.slider(f"Largeur {nom_branche} (m)", 3.0, 8.0, float(l_def), key=f"l_{i}")
    
    branches_config.append({"nom": nom_branche, "voies": voies, "largeur": largeur})

# Synchronisation des libellés de la matrice avec les noms
current_cols = [f"Vers {nom}" for nom in noms_actuels]
current_idx = [f"Depuis {nom}" for nom in noms_actuels]
if list(st.session_state.df_od.columns) != current_cols or list(st.session_state.df_od.index) != current_idx:
    st.session_state.df_od.columns = current_cols
    st.session_state.df_od.index = current_idx

# --- PARAMÈTRES AVANCÉS ---
with st.sidebar.expander("⚙️ Paramètres avancés (Expert)"):
    mode_expert = st.checkbox("Utiliser modèle théorique (t0/ts)", value=st.session_state.mode_expert)
    st.session_state.mode_expert = mode_expert
    t0 = st.slider("Intervalle critique (t0) en s", 2.0, 6.0, float(st.session_state.t0))
    st.session_state.t0 = t0
    ts = st.slider("Temps de suivi (ts) en s", 1.0, 4.0, float(st.session_state.ts))
    st.session_state.ts = ts

# --- SECTION MATRICE O/D & OUTILS ---
st.header("📝 Matrice Origine-Destination (uvp/h)")

# Boîte à outils rapide
col_btn1, col_btn2, col_btn3, _ = st.columns([1.2, 1.2, 1, 2])
with col_btn1:
    if st.button("🔄 Inverser flux (Matin ↔ Soir)"):
        # Transposition mathématique de la matrice O/D
        mat_transp = st.session_state.df_od.values.T
        st.session_state.df_od = pd.DataFrame(mat_transp, columns=current_cols, index=current_idx)
        st.session_state.editor_version += 1
        st.rerun()

with col_btn2:
    if st.button("🚫 Diagonales à 0"):
        np.fill_diagonal(st.session_state.df_od.values, 0)
        st.session_state.editor_version += 1
        st.rerun()

with col_btn3:
    if st.button("🗑️ Effacer tout"):
        st.session_state.df_od.values[:] = 0
        st.session_state.editor_version += 1
        st.rerun()

# Éditeur de matrice
matrice_saisie = st.data_editor(
    st.session_state.df_od, 
    key=f"data_editor_od_{st.session_state.editor_version}",
    hide_index=False, 
    use_container_width=True
)
st.session_state.df_od = matrice_saisie

# Métriques rapides sous la matrice
tot_entrants = matrice_saisie.values.sum(axis=1)
tot_sortants = matrice_saisie.values.sum(axis=0)
vol_total = int(matrice_saisie.values.sum())

m1, m2, m3 = st.columns(3)
m1.metric("Trafic Total Carrefour", f"{vol_total:,} uvp/h".replace(",", " "))
m2.metric("Entrée la plus chargée", f"{noms_actuels[np.argmax(tot_entrants)]} ({int(max(tot_entrants))} uvp/h)")
m3.metric("Sortie la plus sollicitée", f"{noms_actuels[np.argmax(tot_sortants)]} ({int(max(tot_sortants))} uvp/h)")

# Bouton de téléchargement XML dans la barre latérale
xml_data = exporter_xml(diametre, branches_config, mode_expert, t0, ts, matrice_saisie.values)
st.sidebar.download_button(
    label="💾 Exporter la configuration (XML)",
    data=xml_data,
    file_name="giratoire_config.xml",
    mime="application/xml",
    use_container_width=True
)

if (matrice_saisie.values < 0).any():
    st.error("⚠️ Alerte : La matrice contient des valeurs négatives.")
    st.stop()

# --- ANALYSE DE PERFORMANCE ---
if st.button("Lancer l'analyse", type="primary"):
    
    od_values = matrice_saisie.values.tolist()
    list_q_genant, q_sortant = calculer_flux_circulant(od_values)
    list_q_entrant = [sum(row) for row in od_values]
    
    structure_resultats = []
    data_recap_table = []
    
    for i in range(nb_branches):
        nom_b = branches_config[i]["nom"]
        params = {"t0": t0, "ts": ts} if mode_expert else {}
        capa_e = calculer_capacite_girabase(
            list_q_genant[i], 
            branches_config[i]["largeur"], 
            branches_config[i]["voies"], 
            diametre,
            **params
        )
        capa_s = calculer_capacite_sortie(3.5, 1)
        q_e = list_q_entrant[i]
        taux_charge = (q_e / capa_e if capa_e > 0 else 1.0) * 100
        couleur = get_color(taux_charge / 100)
        
        # Calcul des files et retards
        perf = calculer_files_et_retards(q_e, capa_e)
        
        structure_resultats.append({
            'Branche': i+1,
            'Nom': nom_b,
            'Taux de charge': taux_charge,
            'LOS': perf['los'],
            'Couleur': couleur,
            'Largeur': branches_config[i]["largeur"],
            "Entrée (Réel/Capa)": f"{q_e} / {capa_e}",
            "Sortie (Réel/Capa)": f"{q_sortant[i]} / {capa_s}",
            "Charge (%)": round(taux_charge, 1),
            "capa": capa_e, 
            "flux": q_e, 
            "qg": list_q_genant[i]
        })
        
        data_recap_table.append({
            "Branche": nom_b,
            "Flux Entrant (uvp/h)": q_e,
            "Flux Gênant (uvp/h)": list_q_genant[i],
            "Capacité (uvp/h)": capa_e,
            "Taux de charge (%)": round(taux_charge, 1),
            "Réserve (uvp/h)": max(0, capa_e - q_e),
            "Retard Moyen (s/uvp)": perf["retard_s"],
            "File Moyenne (uvp)": perf["file_moyenne_uvp"],
            "File L95 (uvp)": perf["file_l95_uvp"],
            "File L95 (mètres)": f"{perf['file_l95_m']} m",
            "Niveau de Service (LOS)": perf["los"]
        })

    st.write("---")
    
    # --- VISUALISATIONS ---
    col_map, col_schema = st.columns([1, 1.2])
    
    with col_map:
        st.subheader("Carte de chaleur de la matrice OD")
        fig_heat = generer_heatmap_od(od_values, noms_actuels)
        st.pyplot(fig_heat)
        
    with col_schema:
        st.subheader("État de charge du carrefour")
        fig_schema = dessiner_schema_giratoire(
            structure_resultats, 
            diametre, 
            matrice_saisie.values
        )
        st.pyplot(fig_schema)

    st.plotly_chart(
        plot_comparaison_barres(
            [r['Nom'] for r in structure_resultats], 
            [r['flux'] for r in structure_resultats], 
            [r['capa'] for r in structure_resultats]
        ),
        use_container_width=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(plot_chord_diagram(matrice_saisie.values, noms_actuels), use_container_width=True)
    with col2:
        critique = max(structure_resultats, key=lambda x: x['Charge (%)'])
        A = (3600/ts) if mode_expert else 1350
        B = (t0 - ts/2)/3600 if mode_expert else 0.0007
        st.pyplot(plot_saturation_curve(A, B, critique['qg'], critique['flux'], critique['Nom']))

    # --- TABLEAU DÉTAILLÉ DE SYNTHÈSE ---
    st.write("### 📊 Résultats détaillés (Capacité, Files d'attente et Retards)")
    st.dataframe(pd.DataFrame(data_recap_table), use_container_width=True, hide_index=True)