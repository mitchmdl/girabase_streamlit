import numpy as np

def calculer_capacite_girabase(Q_genant, largeur_entree, nb_voies_entree, diametre_exterieur, t0=None, ts=None):
    """Calcule la capacité d'entrée selon l'approche SETRA/CEREMA."""
    nb_voies_entree = int(nb_voies_entree)
    
    if t0 and ts:
        A = 3600 / ts
        B = (t0 - (ts / 2)) / 3600
        capacite = A * np.exp(-B * Q_genant)
    else:
        if nb_voies_entree == 1:
            A = 1350 + 10 * (largeur_entree - 3.5)
            B = 0.0007
        else:
            A = 2100 + 15 * (largeur_entree - 7.0)
            B = 0.0006
            
        if diametre_exterieur < 25: A *= 0.85
        elif diametre_exterieur > 50: A *= 1.05
        capacite = A * np.exp(-B * Q_genant)
    
    return max(1, round(float(capacite)))

def calculer_capacite_sortie(largeur_sortie, nb_voies_sortie):
    return int(nb_voies_sortie) * 1500 + (100 * (largeur_sortie - (int(nb_voies_sortie) * 3.5)))

def calculer_flux_circulant(matrice_od):
    n = len(matrice_od)
    q_genant = [0] * n
    q_sortant = [0] * n
    
    for i in range(n):
        flux_cumule = 0
        for j in range(n):
            for k in range(n):
                if j == k:
                    continue
                if k == i:
                    q_sortant[i] += matrice_od[j][k]
                
                if j < k:
                    if j < i < k:
                        flux_cumule += matrice_od[j][k]
                else:
                    if i > j or i < k:
                        flux_cumule += matrice_od[j][k]
                    
        q_genant[i] = flux_cumule
        
    return q_genant, q_sortant

def calculer_files_et_retards(debit_entrant, capacite, duree_h=1.0):
    """
    Calcule le retard moyen (s/uvp), la file d'attente moyenne (uvp)
    et la file au 95e percentile (L95 en uvp et m) selon la formulation Akçelik / Kimber-Hollis.
    """
    if capacite <= 0:
        capacite = 1
    
    rho = debit_entrant / capacite
    T = duree_h
    C = capacite
    
    # Formule dépendant du temps (HCM / Kimber-Hollis / Akçelik)
    terme_racine = (rho - 1)**2 + ( (3600 / C) * rho ) / (450 * T)
    d_attente = (3600 / C) + 900 * T * ( (rho - 1) + np.sqrt(max(0.0, terme_racine)) )
    retard_total_s = max(5.0, round(float(d_attente + 5.0), 1))  # +5s de retard géométrique
    
    # File moyenne (Loi de Little)
    file_moyenne_uvp = (debit_entrant * (retard_total_s - 5.0)) / 3600.0
    file_moyenne_uvp = max(0.0, round(float(file_moyenne_uvp), 1))
    
    # File L95 (percentile 95)
    file_l95_uvp = round(float(file_moyenne_uvp + 1.96 * np.sqrt(max(0.1, file_moyenne_uvp))))
    longueur_file_metres = int(file_l95_uvp * 6.0)  # ~6.0 m d'encombrement par uvp en file
    
    # Niveau de service (LOS : Level of Service)
    if retard_total_s <= 10:
        los = "A"
    elif retard_total_s <= 15:
        los = "B"
    elif retard_total_s <= 25:
        los = "C"
    elif retard_total_s <= 35:
        los = "D"
    elif retard_total_s <= 50:
        los = "E"
    else:
        los = "F"
        
    return {
        "retard_s": retard_total_s,
        "file_moyenne_uvp": file_moyenne_uvp,
        "file_l95_uvp": file_l95_uvp,
        "file_l95_m": longueur_file_metres,
        "los": los
    }