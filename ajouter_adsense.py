#!/usr/bin/env python3
"""
Script pour ajouter automatiquement le tag AdSense Google
dans toutes les pages HTML d'un dossier (et sous-dossiers).

Le script :
- Cherche tous les fichiers .html / .htm dans le dossier indiqué
- Vérifie si le tag AdSense est déjà présent (pour éviter les doublons)
- Insère le tag juste avant la balise </head> (ou au début du <body> si pas de <head>)

Usage :
    python ajouter_adsense.py /chemin/vers/dossier
"""

import sys
import re
from pathlib import Path

ADSENSE_TAG = '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4853981456641483" crossorigin="anonymous"></script>'

# Identifiant unique pour vérifier si le tag est déjà présent
ADSENSE_CLIENT_ID = "ca-pub-4853981456641483"


def inserer_tag(contenu: str) -> tuple[str, bool]:
    """Insère le tag AdSense dans le HTML si absent. Retourne (nouveau_contenu, modifie)."""

    if ADSENSE_CLIENT_ID in contenu:
        return contenu, False

    # Cherche la balise </head> (insensible à la casse)
    match_head = re.search(r"</head>", contenu, flags=re.IGNORECASE)
    if match_head:
        index = match_head.start()
        nouveau_contenu = contenu[:index] + "    " + ADSENSE_TAG + "\n" + contenu[index:]
        return nouveau_contenu, True

    # Si pas de </head>, on essaie d'insérer juste après <body ...>
    match_body = re.search(r"<body[^>]*>", contenu, flags=re.IGNORECASE)
    if match_body:
        index = match_body.end()
        nouveau_contenu = contenu[:index] + "\n    " + ADSENSE_TAG + contenu[index:]
        return nouveau_contenu, True

    # En dernier recours, on ajoute le tag au tout début du fichier
    nouveau_contenu = ADSENSE_TAG + "\n" + contenu
    return nouveau_contenu, True


def traiter_dossier(dossier: Path):
    fichiers_html = list(dossier.rglob("*.html")) + list(dossier.rglob("*.htm"))

    if not fichiers_html:
        print(f"Aucun fichier .html/.htm trouvé dans {dossier}")
        return

    modifies = 0
    deja_present = 0

    for fichier in fichiers_html:
        try:
            contenu = fichier.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            contenu = fichier.read_text(encoding="latin-1")

        nouveau_contenu, modifie = inserer_tag(contenu)

        if modifie:
            fichier.write_text(nouveau_contenu, encoding="utf-8")
            print(f"✔ Tag ajouté : {fichier}")
            modifies += 1
        else:
            print(f"— Déjà présent : {fichier}")
            deja_present += 1

    print("\nRésumé :")
    print(f"  Fichiers modifiés      : {modifies}")
    print(f"  Déjà à jour            : {deja_present}")
    print(f"  Total fichiers traités : {len(fichiers_html)}")


def main():
    if len(sys.argv) != 2:
        print("Usage : python ajouter_adsense.py /chemin/vers/dossier")
        sys.exit(1)

    dossier = Path(sys.argv[1])

    if not dossier.is_dir():
        print(f"Erreur : {dossier} n'est pas un dossier valide.")
        sys.exit(1)

    traiter_dossier(dossier)


if __name__ == "__main__":
    main()