import os
import io
import base64
import numpy as np
import torch
from PIL import Image
import folder_paths # Nécessaire pour obtenir le dossier output de ComfyUI
import datetime

# Gardez vos imports try-except pour les dépendances
try:
    import fitz  # PyMuPDF
except ImportError:
    print("AVERTISSEMENT: PyMuPDF (fitz) n'est pas installé. L'extraction PDF ne fonctionnera pas.")
    fitz = None
# ... (autres imports de dépendances) ...
try:
    from docx import Document
except ImportError:
    print("AVERTISSEMENT: python-docx n'est pas installé. L'extraction DOCX ne fonctionnera pas.")
    Document = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("AVERTISSEMENT: beautifulsoup4 n'est pas installé. L'extraction HTML/Markdown ne fonctionnera pas.")
    BeautifulSoup = None

try:
    from markdown import markdown
except ImportError:
    print("AVERTISSEMENT: markdown n'est pas installé. L'extraction Markdown ne fonctionnera pas.")
    markdown = None


class ExtractAndSaveImagesFromDocument: # Renommé pour plus de clarté
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "document_path": ("STRING", {"default": ""}),
                "min_width": ("INT", {"default": 256, "min": 1, "max": 8192, "step": 1}),
                "min_height": ("INT", {"default": 256, "min": 1, "max": 8192, "step": 1}),
                "filename_prefix": ("STRING", {"default": "extracted_doc_img"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING") # On retourne la première image et le chemin du dossier
    RETURN_NAMES = ("first_saved_image_preview", "output_folder_path")
    FUNCTION = "extract_and_save_images"
    CATEGORY = "document_processing"
    OUTPUT_NODE = True # Indique que ce node sauvegarde des fichiers

    def _pil_to_rgb_if_needed(self, image_pil):
        """Convertit une image PIL en RGB si nécessaire, gère la transparence."""
        try:
            if image_pil is None: return None
            
            original_mode = image_pil.mode
            
            if image_pil.mode == "P": # Palette
                image_pil = image_pil.convert("RGBA") # Convertir en RGBA pour gérer la transparence de la palette
            
            if image_pil.mode == "LA" or (original_mode == "P" and "transparency" in image_pil.info):
                 image_pil = image_pil.convert("RGBA")

            if image_pil.mode == "RGBA":
                background = Image.new("RGB", image_pil.size, (255, 255, 255))
                if image_pil.splitAlpha(): # Vérifie s'il y a un canal alpha
                     background.paste(image_pil, mask=image_pil.splitAlpha())
                else: # Pas de canal alpha, on peut juste convertir
                     background.paste(image_pil)
                image_pil = background
            elif image_pil.mode == "CMYK":
                image_pil = image_pil.convert("RGB")
            elif image_pil.mode == "L": # Grayscale
                image_pil = image_pil.convert("RGB")
            elif image_pil.mode != "RGB":
                image_pil = image_pil.convert("RGB")
            
            # Vérification finale
            if image_pil.mode != "RGB":
                print(f"[ExtractAndSaveImages] AVERTISSEMENT: L'image n'a pas pu être convertie en RGB. Mode final: {image_pil.mode}")
                return None
            return image_pil
        except Exception as e:
            print(f"[ExtractAndSaveImages] ERREUR _pil_to_rgb_if_needed: {e}")
            return None


    def _process_pil_image(self, pil_image, min_width, min_height):
        """Filtre l'image PIL par taille et la convertit en RGB."""
        if pil_image is None: return None

        if pil_image.width < min_width or pil_image.height < min_height:
            # print(f"[ExtractAndSaveImages] DEBUG: Image {pil_image.size} ignorée (trop petite pour {min_width}x{min_height}).")
            return None
        
        rgb_pil_image = self._pil_to_rgb_if_needed(pil_image)
        return rgb_pil_image


    def _extract_pil_images_from_pdf(self, pdf_path, min_width, min_height):
        if fitz is None: raise ImportError("PyMuPDF (fitz) requis.")
        pil_images_list = []
        doc = fitz.open(pdf_path)
        # print(f"[ExtractAndSaveImages] INFO: PDF ouvert: {os.path.basename(pdf_path)}, Pages: {len(doc)}")
        for page_num, page in enumerate(doc, 1):
            for img_index, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image and base_image.get("image"):
                        pil_img = Image.open(io.BytesIO(base_image["image"]))
                        processed_pil_img = self._process_pil_image(pil_img, min_width, min_height)
                        if processed_pil_img:
                            pil_images_list.append({"pil_image": processed_pil_img, "page": page_num, "index_on_page": img_index})
                except Exception as e:
                    print(f"[ExtractAndSaveImages] ERREUR extraction image PDF p.{page_num} #{img_index}: {e}")
        doc.close()
        return pil_images_list

    def _extract_pil_images_from_docx(self, docx_path, min_width, min_height):
        if Document is None: raise ImportError("python-docx requis.")
        pil_images_list = []
        doc = Document(docx_path)
        for rel_idx, rel in enumerate(doc.part.rels.values()):
            if "image" in rel.target_ref and hasattr(rel.target_part, 'blob'):
                try:
                    pil_img = Image.open(io.BytesIO(rel.target_part.blob))
                    processed_pil_img = self._process_pil_image(pil_img, min_width, min_height)
                    if processed_pil_img:
                       pil_images_list.append({"pil_image": processed_pil_img, "page": 0, "index_on_page": rel_idx}) # page 0 pour docx
                except Exception as e:
                    print(f"[ExtractAndSaveImages] ERREUR extraction image DOCX rel #{rel_idx}: {e}")
        return pil_images_list

    def _extract_pil_images_from_html(self, html_path_or_filelike, min_width, min_height, base_path_for_relative_imgs=None):
        if BeautifulSoup is None: raise ImportError("BeautifulSoup4 requis.")
        pil_images_list = []
        html_content = ""
        
        if hasattr(html_path_or_filelike, "read"): # Vient de Markdown (StringIO)
            html_content = html_path_or_filelike.read()
            # base_path_for_relative_imgs doit être fourni par l'appelant (_extract_pil_images_from_markdown)
        else: # C'est un chemin de fichier HTML
            if base_path_for_relative_imgs is None: # Si non fourni, déduire du chemin html
                base_path_for_relative_imgs = os.path.dirname(html_path_or_filelike)
            with open(html_path_or_filelike, "r", encoding="utf-8") as f:
                html_content = f.read()
        
        soup = BeautifulSoup(html_content, "lxml")
        for idx, img_tag in enumerate(soup.find_all("img")):
            src = img_tag.get("src")
            if not src: continue
            
            pil_img = None
            try:
                if src.startswith("data:image/"):
                    header, encoded = src.split(",", 1)
                    image_bytes = base64.b64decode(encoded)
                    pil_img = Image.open(io.BytesIO(image_bytes))
                elif not (src.startswith("http://") or src.startswith("https://")):
                    local_image_path = src
                    if base_path_for_relative_imgs and not os.path.isabs(src):
                        local_image_path = os.path.normpath(os.path.join(base_path_for_relative_imgs, src))
                    
                    if os.path.exists(local_image_path):
                        pil_img = Image.open(local_image_path)
                    # else:
                        # print(f"[ExtractAndSaveImages] DEBUG: Image locale HTML non trouvée: {local_image_path}")
                
                if pil_img:
                    processed_pil_img = self._process_pil_image(pil_img, min_width, min_height)
                    if processed_pil_img:
                        pil_images_list.append({"pil_image": processed_pil_img, "page": 0, "index_on_page": idx}) # page 0 pour html
            except Exception as e:
                print(f"[ExtractAndSaveImages] ERREUR extraction image HTML #{idx} src: {src[:60]}: {e}")
        return pil_images_list

    def _extract_pil_images_from_markdown(self, md_path, min_width, min_height):
        if markdown is None: raise ImportError("markdown requis.")
        md_base_dir = os.path.dirname(md_path)
        with open(md_path, "r", encoding="utf-8") as f:
            html_from_md = markdown(f.read())
        # Passe le base_dir du markdown pour résoudre les images relatives dans le HTML généré
        return self._extract_pil_images_from_html(io.StringIO(html_from_md), min_width, min_height, base_path_for_relative_imgs=md_base_dir)

    def pil_to_tensor(self, pil_image_rgb):
        if pil_image_rgb is None: return None
        try:
            arr = np.array(pil_image_rgb, dtype=np.uint8) # Doit être RGB HWC uint8
            if arr.ndim != 3 or arr.shape[2] != 3: return None # Vérif finale
            
            arr_float = arr.astype(np.float32) / 255.0
            tensor = torch.from_numpy(arr_float).unsqueeze(0) # BHWC, B=1
            return tensor
        except Exception as e:
            print(f"[ExtractAndSaveImages] ERREUR pil_to_tensor: {e}")
            return None

    def extract_and_save_images(self, document_path, min_width, min_height, filename_prefix):
        if not document_path or not os.path.isfile(document_path):
            print(f"[ExtractAndSaveImages] ERREUR: Fichier introuvable: {document_path}")
            return (torch.zeros((1, 64, 64, 3), dtype=torch.float32), "error: file not found",)

        print(f"[ExtractAndSaveImages] INFO: Début extraction pour: {document_path} (min size: {min_width}x{min_height})")
        ext = os.path.splitext(document_path)[1].lower()
        
        # Liste pour stocker les objets PIL.Image valides et leurs métadonnées
        valid_pil_images_with_meta = [] 

        try:
            if ext == ".pdf":
                valid_pil_images_with_meta = self._extract_pil_images_from_pdf(document_path, min_width, min_height)
            elif ext == ".docx":
                valid_pil_images_with_meta = self._extract_pil_images_from_docx(document_path, min_width, min_height)
            elif ext in [".html", ".htm"]:
                valid_pil_images_with_meta = self._extract_pil_images_from_html(document_path, min_width, min_height)
            elif ext in [".md", ".markdown"]:
                valid_pil_images_with_meta = self._extract_pil_images_from_markdown(document_path, min_width, min_height)
            else:
                print(f"[ExtractAndSaveImages] ERREUR: Format non supporté: {ext}")
                return (torch.zeros((1, 64, 64, 3), dtype=torch.float32), f"error: unsupported format {ext}",)
        except ImportError as e:
             print(f"[ExtractAndSaveImages] ERREUR: Dépendance manquante: {e}")
             return (torch.zeros((1, 64, 64, 3), dtype=torch.float32), f"error: missing dependency {e}",)
        except Exception as e:
            print(f"[ExtractAndSaveImages] ERREUR inattendue pendant extraction: {e}")
            import traceback; traceback.print_exc()
            return (torch.zeros((1, 64, 64, 3), dtype=torch.float32), f"error: extraction failed {e}",)

        if not valid_pil_images_with_meta:
            print(f"[ExtractAndSaveImages] INFO: Aucune image trouvée/valide pour les critères de taille dans {os.path.basename(document_path)}.")
            return (torch.zeros((1, 64, 64, 3), dtype=torch.float32), "no images found or matching criteria",)

        # Création du sous-dossier de sortie
        doc_basename = os.path.splitext(os.path.basename(document_path))[0]
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        # Utiliser folder_paths pour le dossier output de ComfyUI
        output_dir_base = folder_paths.get_output_directory()
        # Créer un sous-dossier spécifique pour ce document et cette exécution
        # pour éviter d'écraser des fichiers si le même document est traité plusieurs fois.
        specific_output_folder_name = f"{filename_prefix}_{doc_basename}_{ts}"
        full_output_folder_path = os.path.join(output_dir_base, specific_output_folder_name)
        
        if not os.path.exists(full_output_folder_path):
            os.makedirs(full_output_folder_path)
        
        print(f"[ExtractAndSaveImages] INFO: Sauvegarde de {len(valid_pil_images_with_meta)} images dans: {full_output_folder_path}")

        first_saved_pil_image = None
        saved_count = 0

        for i, img_data in enumerate(valid_pil_images_with_meta):
            pil_image_to_save = img_data["pil_image"]
            page_num = img_data["page"]
            idx_on_page = img_data["index_on_page"]
            
            try:
                # Nom de fichier : prefix_docname_pXXX_idxYYY_numZZZ.png
                # numZZZ est un compteur global pour s'assurer de l'unicité si page/index se répètent
                image_filename = f"{filename_prefix}_p{page_num:03d}_idx{idx_on_page:03d}_num{i:03d}.png"
                full_save_path = os.path.join(full_output_folder_path, image_filename)
                pil_image_to_save.save(full_save_path, "PNG")
                # print(f"[ExtractAndSaveImages] DEBUG: Image sauvegardée: {full_save_path}")
                if first_saved_pil_image is None:
                    first_saved_pil_image = pil_image_to_save
                saved_count += 1
            except Exception as e:
                print(f"[ExtractAndSaveImages] ERREUR sauvegarde image #{i}: {e}")
        
        print(f"[ExtractAndSaveImages] INFO: {saved_count} images sauvegardées avec succès.")

        preview_tensor = torch.zeros((1, 64, 64, 3), dtype=torch.float32) # Placeholder
        if first_saved_pil_image:
            tensor = self.pil_to_tensor(first_saved_pil_image)
            if tensor is not None:
                preview_tensor = tensor
        
        return (preview_tensor, full_output_folder_path,)


NODE_CLASS_MAPPINGS = {
    "ExtractAndSaveImagesFromDocument": ExtractAndSaveImagesFromDocument,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ExtractAndSaveImagesFromDocument": "Extract & Save Images From Document",
}