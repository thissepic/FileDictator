# Image Processing in FileDictator

## 📖 Overview

FileDictator scales images (from files or rasterized pages) to a **maximum of 1024 px on the longest edge** before passing them to the AI models.
This reduces **latency, memory usage, and API costs**.

---

## ✨ Features

* **Max dimension:** 1024 px (configurable)
* Aspect ratio preserved, **LANCZOS resampling**
* Supported sources: **JPG/JPEG/PNG, rasterized PDF pages, DOCX/PPTX images**
* JPEG re-encode quality: **95**
* Max **3 images/pages per document**

---

## 📂 Processed Types

### 1) Direct Images (`.jpg`, `.jpeg`, `.png`)

* Scaled if needed, passed directly to the model

### 2) DOCX (`.docx`)

* Extracts up to 3 images with `docx2txt`, scales them
* Text content extracted separately

### 3) PDF (`.pdf`)

* First **3 pages rasterized at 200 DPI** with PyMuPDF, then scaled
* Native text extracted in parallel; fallback to *unstructured* on errors

### 4) PowerPoint (`.pptx`)

* Embedded images (max 3) extracted & scaled
* Collects title, body text, and notes

⚠️ Note: `*.doc`, `*.odt`, `*.ppt` are handled via *unstructured* (text only, no image extraction).

---

## ⚙️ Technical Details

* **Libraries:** Pillow (PIL), PyMuPDF (`fitz`), python-pptx, docx2txt
* **Scaling:** `Image.Resampling.LANCZOS`
* **Temp files:** cleaned up via combined cleanup functions
* **Failure case:** if scaling fails → original image used (with warning)

### Relevant Constants (`ingest.py`)

```python
MAX_IMAGE_DIMENSION = 1024  # Max dimension in px
MAX_IMAGES = 3              # Max images/pages per document
PDF_RASTER_DPI = 200        # DPI for PDF rendering
```

### Implementation

* `image_utils.py`: `resize_image_to_max_dimension`, `resize_images_batch`
* `ingest.py`: calls `resize_images_batch` for IMG/DOCX/PDF/PPTX
* `classify.py`: consumes scaled images as optional multimodal input

---

## ✅ Benefits

* Faster local model inference
* Lower network/API usage with OpenAI
* Reduced token/costs via smaller images
* High quality preserved with LANCZOS resampling

---

## 📊 Example

Original: **4000×3000 px (\~8 MB)**
Scaled: **1024×768 px (\~200 KB)**
➡ Aspect ratio preserved

---

## 🧹 Cleanup & Robustness

* All temp files are removed after processing (best effort)
* Fallback parsing (*unstructured*) does **not** generate extra images
