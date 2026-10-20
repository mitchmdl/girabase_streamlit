import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns
import numpy as np
import pandas as pd
from matplotlib.patches import Circle, Wedge, Rectangle
import matplotlib.transforms as transforms
import matplotlib as mpl

def generer_heatmap_od(matrice_od, noms_branches):
    """Génère une heatmap Seaborn avec les vrais noms de branches."""
    cols = [f"Vers {nom}" for nom in noms_branches]
    idx = [f"Depuis {nom}" for nom in noms_branches]
    df = pd.DataFrame(matrice_od, columns=cols, index=idx)
    
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.heatmap(df, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax, cbar_kws={'label': 'uvp/h'})
    ax.set_title("Intensité des flux Origine-Destination")
    plt.tight_layout()
    return fig

def dessiner_schema_giratoire(donnees_branches, diametre_exterieur, matrice_od):
    """Schéma vectoriel du giratoire avec noms personnalisés."""
    nb_branches = len(donnees_branches)
    fig, ax = plt.subplots(figsize=(8, 8))
    
    r_ext = diametre_exterieur / 4
    largeur_chaussee_annulaire = 8.0 
    r_int = max(2.0, r_ext - largeur_chaussee_annulaire)
    largeur_couloir = largeur_chaussee_annulaire / nb_branches
    
    try:
        base_colors = mpl.colormaps['tab10'].resampled(nb_branches)
    except AttributeError:
        base_colors = plt.get_cmap('tab10', nb_branches)
    
    anneau = Wedge((0, 0), r_ext, 0, 360, width=largeur_chaussee_annulaire, 
                   facecolor='#ecf0f1', edgecolor='#34495e', linewidth=2, zorder=1)
    ax.add_patch(anneau)
    
    ilot_central = Circle((0, 0), r_int, facecolor='#bdc3c7', 
                          edgecolor='#34495e', linewidth=1, zorder=2)
    ax.add_patch(ilot_central)

    angles = np.linspace(0, 360, nb_branches, endpoint=False)

    for i_ori in range(nb_branches):
        couleur_base = base_colors(i_ori)
        r_couloir_ext = r_ext - (i_ori * largeur_couloir)
        
        for i_des in range(nb_branches):
            if i_ori == i_des: continue
            flux = matrice_od[i_ori][i_des]
            if flux <= 0: continue
            
            max_flux = max(matrice_od[i_ori]) if max(matrice_od[i_ori]) > 0 else 1
            epaisseur = (flux / max_flux) * largeur_couloir * 0.8
            
            a_start = angles[i_ori]
            a_end = angles[i_des]
            if a_end < a_start: a_end += 360
            
            arc = Wedge((0, 0), r_couloir_ext, a_start, a_end, 
                        width=epaisseur, facecolor=couleur_base, alpha=0.6,
                        edgecolor='none', zorder=3)
            ax.add_patch(arc)

    # Branches & Étiquettes
    for i, angle_deg in enumerate(angles):
        info = donnees_branches[i]
        nom = info.get("Nom", f"B{i+1}")
        # Tronquer le nom sur le schéma s'il est très long
        nom_affiche = nom if len(nom) <= 15 else nom[:13] + ".."
        
        rect = Rectangle((r_ext, -info['Largeur']/7), 5, info['Largeur']/3.5, 
                         facecolor=info['Couleur'], edgecolor='#2c3e50', zorder=10)
        t = transforms.Affine2D().rotate_deg(angle_deg) + ax.transData
        rect.set_transform(t)
        ax.add_patch(rect)
        
        rad = np.deg2rad(angle_deg)
        dist = r_ext + 7.5
        ax.text(
            dist * np.cos(rad), dist * np.sin(rad), 
            f"{nom_affiche}\n{info['Taux de charge']:.1f}%\nLOS {info.get('LOS', '')}", 
            ha='center', va='center', fontweight='bold', fontsize=8,
            bbox=dict(facecolor='white', alpha=0.85, edgecolor='#95a5a6', boxstyle='round,pad=0.3')
        )

    ax.set_xlim(-r_ext-11, r_ext+11)
    ax.set_ylim(-r_ext-11, r_ext+11)
    ax.set_aspect('equal')
    ax.axis('off')
    return fig

def plot_saturation_curve(A, B, q_g, q_e, nom_branche):
    fig, ax = plt.subplots(figsize=(5, 3))
    x = np.linspace(0, 2000, 100)
    y = A * np.exp(-B * x)
    ax.plot(x, y, color='#3498db', label="Courbe théorique")
    ax.scatter(q_g, q_e, color='red', s=50, zorder=5, label="Point actuel")
    ax.set_title(f"Saturation - {nom_branche}", fontsize=10)
    ax.set_xlabel("Flux gênant Qg (uvp/h)", fontsize=8)
    ax.set_ylabel("Capacité d'entrée (uvp/h)", fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.legend(prop={'size': 7})
    return fig

def plot_comparaison_barres(labels, flux, capacites):
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Flux Réel (uvp/h)', x=labels, y=flux, marker_color='#34495e'))
    fig.add_trace(go.Bar(name='Capacité (uvp/h)', x=labels, y=capacites, marker_color='#2ecc71'))
    fig.update_layout(barmode='group', height=300, margin=dict(l=20, r=20, t=30, b=20))
    return fig

def plot_chord_diagram(matrice_od, noms_branches):
    n = len(matrice_od)
    sources, targets, values, colors_links = [], [], [], []
    palette = px.colors.qualitative.Plotly 

    for i in range(n):
        for j in range(n):
            if matrice_od[i][j] > 0:
                sources.append(i)
                targets.append(j + n)
                values.append(matrice_od[i][j])
                base_color = palette[i % len(palette)]
                colors_links.append(base_color)

    labels = [f"Entrée : {nom}" for nom in noms_branches] + [f"Sortie : {nom}" for nom in noms_branches]

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=18,
            line=dict(color="white", width=0.5),
            label=labels,
            color=palette[:n] + ["#bdc3c7"] * n 
        ),
        link=dict(
            source=sources, 
            target=targets, 
            value=values,
            color=colors_links
        )
    )])

    fig.update_layout(
        title_text="Répartition des transferts",
        font=dict(size=11, color="white"),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig