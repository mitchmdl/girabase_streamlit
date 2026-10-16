import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
import seaborn as sns
import numpy as np
import pandas as pd
from matplotlib.patches import Circle, Wedge, Rectangle
import matplotlib.transforms as transforms
import matplotlib as mpl

def generer_heatmap_od(matrice_od):
    """Génère une heatmap Seaborn à partir de la matrice O/D."""
    n = len(matrice_od)
    cols = [f"Vers B{i+1}" for i in range(n)]
    idx = [f"Depuis B{i+1}" for i in range(n)]
    df = pd.DataFrame(matrice_od, columns=cols, index=idx)
    
    fig, ax = plt.subplots(figsize=(6, 4))
    sns.heatmap(df, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax, cbar_kws={'label': 'uvp/h'})
    ax.set_title("Intensité des flux Origine-Destination")
    plt.tight_layout()
    return fig

def dessiner_schema_giratoire(donnees_branches, diametre_exterieur, matrice_od):
    """
    Génère un schéma vectoriel du giratoire coloré selon la charge,
    avec des flèches courbes montrant les flux O/D.
    """
    nb_branches = len(donnees_branches)
    fig, ax = plt.subplots(figsize=(8, 8))
    
    # --- Paramètres de dessin fixes ---
    r_ext = diametre_exterieur / 4  # Rayon graphique de l'anneau extérieur
    largeur_chaussee_annulaire = 8.0 
    r_int = max(2.0, r_ext - largeur_chaussee_annulaire)  # Rayon graphique de l'îlot central
    largeur_couloir = largeur_chaussee_annulaire / nb_branches
    longueur_branche_graphique = 4.0 # Longueur visuelle des branches
    
    # --- Facteur d'échelle pour la largeur ---
    Echelle_Largeur = 1.0 / 3.5 
    
    # Palette moderne compatible toutes versions Matplotlib
    try:
        base_colors = mpl.colormaps['tab10'].resampled(nb_branches)
    except AttributeError:
        # Fallback pour anciennes versions < 3.7
        base_colors = plt.get_cmap('tab10', nb_branches)
    
    # --- 1. Dessin de l'anneau (gris clair) ---
    anneau = Wedge((0, 0), r_ext, 0, 360, width=largeur_chaussee_annulaire, 
                   facecolor='#ecf0f1', edgecolor='#34495e', linewidth=2, zorder=1)
    ax.add_patch(anneau)
    
    ilot_central = Circle((0, 0), r_int, facecolor='#bdc3c7', 
                          edgecolor='#34495e', linewidth=1, zorder=2)
    ax.add_patch(ilot_central)

    # --- 2. Dessin et coloration des branches (zorder 10, dessus) ---
    angles = np.linspace(0, 360, nb_branches, endpoint=False)

    for i_ori in range(nb_branches):
        # Couleur spécifique pour l'origine avec un léger dégradé selon l'indice
        couleur_base = base_colors(i_ori)
        
        # Calcul du rayon pour ce couloir spécifique (du plus externe au plus interne)
        r_couloir_ext = r_ext - (i_ori * largeur_couloir)
        
        for i_des in range(nb_branches):
            if i_ori == i_des: continue
            
            flux = matrice_od[i_ori][i_des]
            if flux <= 0: continue
            
            # Épaisseur proportionnelle au volume dans la limite du couloir
            max_flux_branche = max(matrice_od[i_ori]) if max(matrice_od[i_ori]) > 0 else 1
            epaisseur_flux = (flux / max_flux_branche) * largeur_couloir * 0.8
            
            # Angles (Sens anti-horaire pour les giratoires dans Matplotlib)
            a_start = angles[i_ori]
            a_end = angles[i_des]
            if a_end < a_start: a_end += 360
            
            # Dessin de l'arc avec dégradé
            alpha_val = 0.8 - (i_des * 0.05) 
            
            arc_flux = Wedge((0, 0), r_couloir_ext, a_start, a_end, 
                             width=epaisseur_flux, 
                             facecolor=couleur_base, alpha=max(0.3, alpha_val),
                             edgecolor='none', zorder=3)
            ax.add_patch(arc_flux)
            
            # Ajout d'une flèche directionnelle à la fin de l'arc
            rad_end = np.deg2rad(a_end)
            ax.annotate("", xy=(r_couloir_ext * np.cos(rad_end), r_couloir_ext * np.sin(rad_end)),
                        xytext=((r_couloir_ext - 0.1) * np.cos(rad_end - 0.1), (r_couloir_ext - 0.1) * np.sin(rad_end - 0.1)),
                        arrowprops=dict(arrowstyle="->", color=couleur_base, lw=2, alpha=0.8),
                        zorder=4)

    # --- 3. Dessin des Branches ---
    for i, angle_deg in enumerate(angles):
        info = donnees_branches[i]
        rect = Rectangle((r_ext, -info['Largeur']/7), 5, info['Largeur']/3.5, 
                         facecolor=info['Couleur'], edgecolor='#2c3e50', zorder=10)
        t = transforms.Affine2D().rotate_deg(angle_deg) + ax.transData
        rect.set_transform(t)
        ax.add_patch(rect)
        
        # Labels
        rad = np.deg2rad(angle_deg)
        dist = r_ext + 7
        ax.text(dist * np.cos(rad), dist * np.sin(rad), f"B{i+1}\n{info['Taux de charge']:.1f}%", 
                ha='center', va='center', fontweight='bold', bbox=dict(facecolor='white', alpha=0.7))

    ax.set_xlim(-r_ext-10, r_ext+10)
    ax.set_ylim(-r_ext-10, r_ext+10)
    ax.set_aspect('equal')
    ax.axis('off')
    return fig

def plot_saturation_curve(A, B, q_g, q_e, nom_branche):
    fig, ax = plt.subplots(figsize=(5, 3))
    x = np.linspace(0, 2000, 100)
    y = A * np.exp(-B * x)
    ax.plot(x, y, color='#3498db', label="Courbe de capacité théorique")
    ax.scatter(q_g, q_e, color='red', s=50, zorder=5, label="Point de fonctionnement actuel")
    ax.set_title(f"Saturation de la branche {nom_branche}", fontsize=10)
    ax.set_xlabel("Flux gênant Qg (uvp/h)", fontsize=8)
    ax.set_ylabel("Capacité d'entrée (uvp/h)", fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.legend(prop={'size': 7})
    return fig

def plot_comparaison_barres(labels, flux, capacites):
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Flux Réel', x=labels, y=flux, marker_color='#34495e'))
    fig.add_trace(go.Bar(name='Capacité Totale', x=labels, y=capacites, marker_color='#2ecc71'))
    fig.update_layout(barmode='group', height=300, margin=dict(l=20, r=20, t=30, b=20))
    return fig

def plot_chord_diagram(matrice_od):
    n = len(matrice_od)
    sources, targets, values, colors_links = [], [], [], []
    
    palette = px.colors.qualitative.Plotly 

    for i in range(n): # Origines
        for j in range(n): # Destinations
            if matrice_od[i][j] > 0:
                sources.append(i)
                targets.append(j + n)
                values.append(matrice_od[i][j])
                
                base_color = palette[i % len(palette)]
                if base_color.startswith('#'):
                    colors_links.append(base_color) 
                else:
                    rgba_color = base_color.replace('rgb', 'rgba').replace(')', ', 0.4)')
                    colors_links.append(rgba_color)

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="white", width=0.5),
            label=[f"Entrée B{i+1}" for i in range(n)] + [f"Sortie B{i+1}" for i in range(n)],
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
        title_text="Répartition des transferts (Entrées vers Sorties)",
        font=dict(size=12, color="white"),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return fig
