import streamlit as st
import pandas as pd
import numpy as np
from parameters import get_color
from engine import calculer_flux_circulant, calculer_capacite_girabase, calculer_capacite_sortie
from visualizations import generer_heatmap_od, dessiner_schema_giratoire, plot_saturation_curve, plot_comparaison_barres, plot_chord_diagram
from io_xml import exporter_xml, importer_xml

st.set_page_config(
    page_title="Girabase", 
    page_icon="🚗",
    layout="wide"
)

# --- GESTION DE L'ÉTAT INITIAL ---
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
if "df_od" not in st.session_state:
    n = st.session_state.nb_branches
    st.session_state.df_od = pd.DataFrame(
        np.zeros((n, n)),
        columns=[f"Vers B{i+1}" for i in range(n)],
        index=[f"Depuis B{i+1}" for i in range(n)]
    )

st.title("🔄🛣️ Estimation de la capacité d'un carrefour giratoire")

st.markdown("""
            Bienvenue dans cette application interactive dédiée à l'analyse de la capacité 
            des carrefours giratoires selon la méthode **Girabase** du Cerema.  
            
            Le logiciel Girabase est un outil de référence en ingénierie routière pour valider 
            la **faisabilité technique** de projets d'aménagement ou pour établir le **diagnostic 
            d'un carrefour existant**.
            """)

# --- SIDEBAR : SAUVEGARDE & IMPORTATION XML ---
st.sidebar.image("BlocMarque_RF-Cerema_horizontal.jpg", use_container_width=True)
st.sidebar.header("💾 Gestion de configuration")

with st.sidebar.expander("📂 Importer / Exporter (XML)", expanded=True):
    # Import XML
    uploaded_xml = st.file_uploader("Charger une configuration", type=["xml"])
    if uploaded_xml is not None:
        try:
            config_chargee = importer_xml(uploaded_xml)
            st.session_state.nb_branches = config_chargee["nb_branches"]
            st.session_state.diametre = config_chargee["diametre"]
            st.session_state.mode_expert = config_chargee["mode_expert"]
            st.session_state.t0 = config_chargee["t0"]
            st.session_state.ts = config_chargee["ts"]
            st.session_state.df_od = config_chargee["df_od"]
            
            # Stocke les caractéristiques des branches chargées
            for idx, b in enumerate(config_chargee["branches_config"]):
                st.session_state[f"v_{idx}"] = b["voies"]
                st.session_state[f"l_{idx}"] = b["largeur"]
                
            st.success("Configuration importée avec succès !")
            st.rerun()
        except Exception as e:
            st.error(f"Erreur lors de la lecture du fichier : {e}")

# --- SIDEBAR : GEOMETRIE ---
st.sidebar.header("📐 Géométrie du carrefour")

def update_branches_count():
    """Adapte la matrice OD si le nombre de branches change manuellement."""
    n_new = st.session_state.nb_branches_input
    n_old = len(st.session_state.df_od)
    if n_new != n_old:
        new_mat = np.zeros((n_new, n_new))
        min_n = min(n_new, n_old)
        new_mat[:min_n, :min_n] = st.session_state.df_od.values[:min_n, :min_n]
        st.session_state.df_od = pd.DataFrame(
            new_mat,
            columns=[f"Vers B{i+1}" for i in range(n_new)],
            index=[f"Depuis B{i+1}" for i in range(n_new)]
        )
    st.session_state.nb_branches = n_new

nb_branches = st.sidebar.slider(
    "Nombre de branches", 3, 6, 
    value=st.session_state.nb_branches, 
    key="nb_branches_input",
    on_change=update_branches_count
)

diametre = st.sidebar.number_input(
    "Diamètre extérieur (m)", 20.0, 100.0, 
    value=float(st.session_state.diametre),
    step=1.0,
    help="Distance entre les bords extérieurs de la chaussée."
)
st.session_state.diametre = diametre

branches_config = []
for i in range(nb_branches):
    st.sidebar.subheader(f"Branche {i+1}")
    voies_default = st.session_state.get(f"v_{i}", 1)
    voies = st.sidebar.selectbox(f"Voies B{i+1}", [1, 2], index=0 if voies_default == 1 else 1, key=f"v_{i}")
    
    largeur_default = st.session_state.get(f"l_{i}", 3.5 if voies == 1 else 7.0)
    largeur = st.sidebar.slider(f"Largeur B{i+1} (m)", 3.0, 8.0, float(largeur_default), key=f"l_{i}")
    branches_config.append({"voies": voies, "largeur": largeur})

# --- PARAMÈTRES AVANCÉS ---
with st.sidebar.expander("⚙️ Paramètres avancés (Expert)"):
    mode_expert = st.checkbox("Utiliser modèle théorique (t0/ts)", value=st.session_state.mode_expert)
    st.session_state.mode_expert = mode_expert
    t0 = st.slider("Intervalle critique (t0) en s", 2.0, 6.0, float(st.session_state.t0))
    st.session_state.t0 = t0
    ts = st.slider("Temps de suivi (ts) en s", 1.0, 4.0, float(st.session_state.ts))
    st.session_state.ts = ts

# --- CELLULE D'INFORMATION PÉDAGOGIQUE ---
with st.expander("ℹ️ Comprendre la méthode de calcul (Girabase / Cerema)", expanded=False):
    st.markdown("""
    ### Qu'est-ce que la capacité d'un giratoire ?
    La capacité d'une entrée de giratoire est le débit maximal de véhicules qui peuvent s'y insérer en une heure. Elle dépend de deux facteurs principaux :
    1. **La géométrie :** Largeur de l'entrée et diamètre du carrefour.
    2. **Le flux gênant ($Q_g$) :** Le trafic circulant prioritaire sur l'anneau devant l'entrée.
    """)
    st.latex(r"C = A \cdot e^{-B \cdot Q_g}")

# --- CORPS : MATRICE O/D ---
st.header("📝 Matrice Origine-Destination (uvp/h)")
st.info("Saisissez les flux horaires. Les lignes sont les Origines, les colonnes les Destinations.")

# Éditeur de données interactif
matrice_saisie = st.data_editor(st.session_state.df_od, hide_index=False, use_container_width=True)
st.session_state.df_od = matrice_saisie

# Export XML disponible directement
xml_data = exporter_xml(diametre, branches_config, mode_expert, t0, ts, matrice_saisie.values)
st.sidebar.download_button(
    label="💾 Télécharger configuration (XML)",
    data=xml_data,
    file_name="giratoire_config.xml",
    mime="application/xml"
)

# --- ALERTES DE SÉCURITÉ ---
if (matrice_saisie.values < 0).any():
    st.error("⚠️ Alerte : La matrice contient des valeurs négatives. Veuillez corriger les flux.")
    st.stop()

flux_total = matrice_saisie.values.sum()
if flux_total > 10000:
    st.warning(f"⚠️ Volume absurde : {flux_total} uvp/h. Ce carrefour est physiquement incapable de traiter ce flux.")

if st.button("Lancer l'analyse", type="primary"):
    
    # 1. Traitement des données
    od_values = matrice_saisie.values.tolist()
    list_q_genant, q_sortant = calculer_flux_circulant(od_values)
    list_q_entrant = [sum(row) for row in od_values]
    
    structure_resultats = []
    data_recap_table = []
    
    for i in range(nb_branches):
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
        
        structure_resultats.append({
            'Branche': i+1,
            'Taux de charge': taux_charge,
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
            "Branche": i+1,
            "Flux Entrant (Qe)": q_e,
            "Flux Gênant (Qg)": list_q_genant[i],
            "Capacité (C)": capa_e,
            "Taux de charge (%)": round(taux_charge, 1),
            "Réserve (uvp/h)": max(0, capa_e - q_e)
        })

    st.write("---")
    
    # --- 2. Zone des Visualisations ---
    col_map, col_schema = st.columns([1, 1.2])
    
    with col_map:
        st.subheader("Carte de chaleur de la matrice OD")
        fig_heat = generer_heatmap_od(od_values)
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
            [f"B{r['Branche']}" for r in structure_resultats], 
            [r['flux'] for r in structure_resultats], 
            [r['capa'] for r in structure_resultats]
        ),
        use_container_width=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(plot_chord_diagram(matrice_saisie.values), use_container_width=True)
    with col2:
        critique = max(structure_resultats, key=lambda x: x['Charge (%)'])
        A = (3600/ts) if mode_expert else 1350
        B = (t0 - ts/2)/3600 if mode_expert else 0.0007
        st.pyplot(plot_saturation_curve(A, B, critique['qg'], critique['flux'], f"B{critique['Branche']}"))

    st.table(pd.DataFrame(structure_resultats).drop(columns=['capa', 'flux', 'qg', 'Couleur', 'Largeur']))

    # --- 3. Tableau de synthèse ---
    st.write("### Données détaillées")
    st.dataframe(pd.DataFrame(data_recap_table), use_container_width=True, hide_index=True)
