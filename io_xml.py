import xml.etree.ElementTree as ET
from xml.dom import minidom
import pandas as pd
import numpy as np

def exporter_xml(diametre, branches_config, mode_expert, t0, ts, matrice_od):
    """Exporte la configuration incluant les noms personnalisés."""
    root = ET.Element("girabase_configuration", version="1.1")
    
    geom = ET.SubElement(root, "geometrie")
    ET.SubElement(geom, "diametre_exterieur").text = str(float(diametre))
    
    branches_elem = ET.SubElement(geom, "branches", count=str(len(branches_config)))
    for i, b in enumerate(branches_config):
        ET.SubElement(
            branches_elem, 
            "branche", 
            id=str(i + 1),
            nom=str(b.get("nom", f"Branche {i+1}")),
            voies=str(int(b["voies"])),
            largeur=str(round(float(b["largeur"]), 2))
        )
        
    expert_elem = ET.SubElement(root, "parametres_avances")
    ET.SubElement(expert_elem, "mode_expert").text = str(mode_expert).lower()
    ET.SubElement(expert_elem, "t0").text = str(float(t0))
    ET.SubElement(expert_elem, "ts").text = str(float(ts))
    
    n = len(matrice_od)
    od_elem = ET.SubElement(root, "matrice_od", dimensions=f"{n}x{n}")
    for i in range(n):
        for j in range(n):
            val = float(matrice_od[i][j])
            ET.SubElement(
                od_elem, 
                "flux", 
                origine=str(i + 1), 
                destination=str(j + 1)
            ).text = str(int(val) if val.is_integer() else val)
                
    raw_xml = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(raw_xml)
    return parsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def importer_xml(fichier_xml):
    """Importe la configuration avec extraction des noms de branches."""
    tree = ET.parse(fichier_xml)
    root = tree.getroot()
    
    if root.tag != "girabase_configuration":
        raise ValueError("Le fichier XML n'est pas une configuration Girabase valide.")
    
    geom = root.find("geometrie")
    diametre = float(geom.find("diametre_exterieur").text)
    
    branches_elem = geom.find("branches")
    branches_list = branches_elem.findall("branche")
    nb_branches = len(branches_list)
    
    branches_config = []
    for idx, b in enumerate(branches_list):
        branches_config.append({
            "nom": b.attrib.get("nom", f"Branche {idx+1}"),
            "voies": int(b.attrib.get("voies", 1)),
            "largeur": float(b.attrib.get("largeur", 3.5))
        })
        
    expert_elem = root.find("parametres_avances")
    mode_expert = expert_elem.find("mode_expert").text.strip().lower() in ["true", "1"]
    t0 = float(expert_elem.find("t0").text)
    ts = float(expert_elem.find("ts").text)
    
    matrice = np.zeros((nb_branches, nb_branches), dtype=int)
    od_elem = root.find("matrice_od")
    if od_elem is not None:
        for flux in od_elem.findall("flux"):
            i = int(flux.attrib["origine"]) - 1
            j = int(flux.attrib["destination"]) - 1
            if 0 <= i < nb_branches and 0 <= j < nb_branches:
                matrice[i][j] = int(float(flux.text))
                
    noms = [b["nom"] for b in branches_config]
    cols = [f"Vers {n}" for n in noms]
    idx = [f"Depuis {n}" for n in noms]
    df_od = pd.DataFrame(matrice, columns=cols, index=idx)
    
    return {
        "nb_branches": nb_branches,
        "diametre": diametre,
        "branches_config": branches_config,
        "mode_expert": mode_expert,
        "t0": t0,
        "ts": ts,
        "df_od": df_od
    }