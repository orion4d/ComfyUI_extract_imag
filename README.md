# ComfyUI Custom Node: Extract & Save Images From Document

Ce node ComfyUI permet d’extraire toutes les images trouvées dans divers types de documents et de les sauvegarder sur le disque. Il offre également un aperçu de la première image extraite.

**Formats de documents supportés :**
-   PDF (.pdf)
-   Document Word (.docx)
-   Page HTML (.html, .htm) - Images locales et encodées en base64.
-   Fichier Markdown (.md, .markdown) - Images locales (relatives au fichier .md) et encodées en base64.

## Fonctionnalités

*   Extraction d'images depuis les formats PDF, DOCX, HTML, et Markdown.
*   Filtrage des images extraites par **dimensions minimales** (largeur et hauteur).
*   Sauvegarde automatique des images filtrées dans un sous-dossier dédié au sein du répertoire `output` de ComfyUI.
    *   Les dossiers de sortie sont nommés pour éviter les conflits (nom du document + timestamp).
    *   Les images sauvegardées sont nommées avec leur numéro de page et leur index pour une identification facile.
*   Retourne un **aperçu** de la première image sauvegardée.
*   Retourne le **chemin du dossier** où les images ont été sauvegardées.

## Installation

1.  **Cloner ou télécharger le dépôt :**
    Si vous gérez ce projet avec Git, clonez-le dans votre dossier `ComfyUI/custom_nodes/` :
    ```bash
    cd ComfyUI/custom_nodes/
    git clone https://github.com/orion4d/ComfyUI_extract_imag.git
    ```
2.  **Installer les dépendances :**
    Ouvrez une invite de commande (ou un terminal) et naviguez jusqu'au dossier de votre node :
    ```bash
    cd ComfyUI/custom_nodes/ComfyUI-ExtractAndSaveImages/
    ```
    Installez les dépendances nécessaires en utilisant le fichier `requirements.txt` :
    ```bash
    pip install -r requirements.txt
    ```
    *Assurez-vous que cela est fait dans l'environnement Python utilisé par ComfyUI (par exemple, votre venv si vous en utilisez un).*

3.  **Redémarrer ComfyUI :**
    Après avoir placé les fichiers et installé les dépendances, redémarrez complètement ComfyUI.

## Utilisation dans ComfyUI

1.  Après le redémarrage, le node **"Extract & Save Images From Document"** devrait apparaître dans ComfyUI.
    *   Faites un clic droit sur le canevas -> Add Node -> `document_processing` -> `Extract & Save Images From Document`.
    *   Ou double-cliquez sur le canevas et recherchez "Extract & Save Images From Document".

2.  **Paramètres du node (Entrées) :**
    *   `document_path` (STRING) : Chemin complet vers le fichier document à traiter (ex : `"C:/docs/mon_rapport.pdf"`).
    *   `min_width` (INT) : Largeur minimale (en pixels) pour qu'une image soit extraite et sauvegardée. (Défaut : 256)
    *   `min_height` (INT) : Hauteur minimale (en pixels) pour qu'une image soit extraite et sauvegardée. (Défaut : 256)
    *   `filename_prefix` (STRING) : Préfixe utilisé pour nommer le dossier de sortie et les fichiers image. (Défaut : "extracted_doc_img")

3.  **Sorties du node :**
    *   `first_saved_image_preview` (IMAGE) : Un tenseur image (BHWC) de la première image qui a été extraite et sauvegardée avec succès. Peut être connecté à un nœud "Preview Image". Si aucune image n'est sauvegardée, un placeholder noir est retourné.
    *   `output_folder_path` (STRING) : Le chemin complet du dossier où les images extraites ont été sauvegardées. Vous pouvez l'utiliser avec des nodes qui manipulent des chemins de fichiers ou pour votre information.
