import customtkinter as ctk
from tkinter import messagebox, filedialog, ttk
import sqlite3
import os
import json
import shutil
import sys
import zipfile
from datetime import datetime
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth

# ------------------------------------------------------------------
# RUTAS BASE
# ------------------------------------------------------------------
def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR     = get_base_path()
DB_NAME      = os.path.join(BASE_DIR, "medical_data.db")
MEDIA_FOLDER = os.path.join(BASE_DIR, "patient_media")

LETTER_WIDTH     = 21.59 * cm
LETTER_HEIGHT    = 27.94 * cm
LETTER_PAGE_SIZE = (LETTER_WIDTH, LETTER_HEIGHT)

IMG_W      = 7.5 * cm
IMG_H      = 6.0 * cm
COLS       = 2
ROWS       = 2
NUM_IMAGES = COLS * ROWS

if not os.path.exists(MEDIA_FOLDER):
    os.makedirs(MEDIA_FOLDER)


class ColposcopiaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Colposcopia")
        self.root.geometry("1200x950")

        self.current_patient_id = None
        self.image_paths        = [None] * NUM_IMAGES
        self._image_store       = {}
        self.pdf_font_size      = ctk.IntVar(value=11)

        self.init_db()
        self.setup_ui()
        self.refresh_records_table()

        # Maximizar despues de que la UI termine de cargar
        self.root.after(100, lambda: self.root.state('zoomed'))

    # ------------------------------------------------------------------
    # BUSCAR IMAGEN EN MULTIPLES UBICACIONES
    # ------------------------------------------------------------------
    def _resolve_image_path(self, fname):
        if not fname:
            return None
        basename = os.path.basename(fname)
        search_dirs = [
            MEDIA_FOLDER,
            BASE_DIR,
            os.path.join(BASE_DIR, "patient_media"),
            os.path.dirname(fname) if os.path.dirname(fname) else None,
        ]
        try:
            for entry in os.scandir(BASE_DIR):
                if entry.is_dir():
                    search_dirs.append(entry.path)
        except Exception:
            pass
        for d in search_dirs:
            if not d:
                continue
            candidate = os.path.join(d, basename)
            if os.path.exists(candidate):
                return candidate
        try:
            for root_dir, dirs, files in os.walk(BASE_DIR):
                if basename in files:
                    return os.path.join(root_dir, basename)
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # BASE DE DATOS
    # ------------------------------------------------------------------
    def init_db(self):
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                '''CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT, age TEXT, date TEXT,
                    meds TEXT, notes TEXT, images TEXT,
                    image_desc TEXT
                )'''
            )
            # Crear tabla recetas si existe en la BD compartida
            # (creada por el modulo de recetas)
            conn.execute(
                '''CREATE TABLE IF NOT EXISTS recetas (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    fecha      TEXT,
                    meds       TEXT,
                    notes      TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(id)
                )'''
            )

    def _get_receta_count(self, conn, patient_id):
        """Devuelve el numero de recetas de un paciente. 0 si no existe la tabla."""
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM recetas WHERE patient_id=?",
                (patient_id,)
            ).fetchone()[0]
            return n
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def setup_ui(self):
        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_images  = self.tabs.add("Estudio de Colposcopia")
        self.tab_records = self.tabs.add("Registros de Pacientes")
        self._build_tab_images()
        self._build_tab_records()

    # ------------------------------------------------------------------
    # PESTANA 1 - IMAGENES
    # ------------------------------------------------------------------
    def _build_tab_images(self):
        img_info_bar = ctk.CTkFrame(self.tab_images, fg_color="#333")
        img_info_bar.pack(fill="x", padx=20, pady=10)

        self.lbl_img_patient = ctk.CTkLabel(
            img_info_bar,
            text="Paciente Actual: Ninguno Seleccionado",
            font=("Helvetica", 14, "bold")
        )
        self.lbl_img_patient.pack(side="left", padx=20, pady=10)

        ctk.CTkButton(
            img_info_bar, text="Guardar Estudio",
            fg_color="#27ae60", width=140,
            command=self.save_patient
        ).pack(side="right", padx=10)

        data_frame = ctk.CTkFrame(self.tab_images, fg_color="transparent")
        data_frame.pack(fill="x", padx=20, pady=(5, 0))

        name_f = ctk.CTkFrame(data_frame, fg_color="transparent")
        name_f.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(
            name_f, text="Nombre del Paciente",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.ent_name = ctk.CTkEntry(
            name_f, placeholder_text="Ej: Juan Perez", width=300
        )
        self.ent_name.pack(anchor="w", pady=(2, 0))

        age_f = ctk.CTkFrame(data_frame, fg_color="transparent")
        age_f.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(
            age_f, text="Edad",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.ent_age = ctk.CTkEntry(
            age_f, placeholder_text="Edad", width=100
        )
        self.ent_age.pack(anchor="w", pady=(2, 0))

        date_f = ctk.CTkFrame(data_frame, fg_color="transparent")
        date_f.pack(side="left")
        ctk.CTkLabel(
            date_f, text="Fecha",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.ent_date = ctk.CTkEntry(date_f, width=150)
        self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.ent_date.pack(anchor="w", pady=(2, 0))

        ctk.CTkLabel(
            self.tab_images,
            text="Imagenes del Estudio  -  2 x 2",
            font=("Helvetica", 13, "bold")
        ).pack(anchor="w", padx=20, pady=(8, 4))

        self.img_grid_container = ctk.CTkFrame(
            self.tab_images, fg_color="transparent"
        )
        self.img_grid_container.pack(
            pady=5, padx=20, fill="both", expand=True
        )

        self._build_image_grid()

        obs_frame = ctk.CTkFrame(self.tab_images, fg_color="transparent")
        obs_frame.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(
            obs_frame, text="Observaciones del Estudio",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.txt_img_desc = ctk.CTkTextbox(obs_frame, height=70)
        self.txt_img_desc.pack(fill="x", pady=(2, 0))

        btn_row = ctk.CTkFrame(self.tab_images, fg_color="transparent")
        btn_row.pack(pady=12)
        ctk.CTkButton(
            btn_row,
            text="Imprimir PDF  -  Estudio de Colposcopia",
            fg_color="#2980b9", width=300,
            command=self.generate_image_pdf
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btn_row, text="Limpiar Formulario",
            fg_color="#c0392b", width=150,
            command=self.clear_form
        ).pack(side="left", padx=10)

    def _build_image_grid(self):
        self._image_store = {}

        for widget in self.img_grid_container.winfo_children():
            widget.destroy()

        self.img_grid = ctk.CTkFrame(self.img_grid_container)
        self.img_grid.pack(fill="both", expand=True)

        self.image_labels = []
        self.slot_frames  = []

        for i in range(NUM_IMAGES):
            r, c = divmod(i, COLS)
            slot = ctk.CTkFrame(
                self.img_grid, border_width=2, border_color="#555"
            )
            slot.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")
            self.slot_frames.append(slot)

            lbl = ctk.CTkLabel(
                slot, text=f"Vacio ({r+1},{c+1})", image=None
            )
            lbl.pack(expand=True, pady=8)
            self.image_labels.append(lbl)

            b_frame = ctk.CTkFrame(slot, fg_color="transparent")
            b_frame.pack(side="bottom", fill="x", padx=4, pady=4)
            ctk.CTkButton(
                b_frame, text="Agregar", width=90,
                command=lambda idx=i: self.add_image(idx)
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                b_frame, text="Eliminar", width=90,
                fg_color="#c0392b",
                command=lambda idx=i: self.remove_image(idx)
            ).pack(side="right", padx=2)

        self.img_grid.grid_columnconfigure((0, 1), weight=1)
        self.img_grid.grid_rowconfigure((0, 1), weight=1)

    # ------------------------------------------------------------------
    # PESTANA 2 - REGISTROS
    # ------------------------------------------------------------------
    def _build_tab_records(self):
        top_bar = ctk.CTkFrame(self.tab_records)
        top_bar.pack(fill="x", padx=10, pady=10)

        self.ent_search = ctk.CTkEntry(
            top_bar, placeholder_text="Buscar por nombre...", width=300
        )
        self.ent_search.pack(side="left", padx=10)
        self.ent_search.bind("<KeyRelease>", self.refresh_records_table)

        ctk.CTkButton(
            top_bar, text="Exportar Datos",
            fg_color="#8e44ad", command=self.export_data
        ).pack(side="right", padx=5)
        ctk.CTkButton(
            top_bar, text="Importar y Fusionar",
            fg_color="#d35400", command=self.import_data_merge
        ).pack(side="right", padx=5)
        ctk.CTkButton(
            top_bar, text="Importar y Reemplazar",
            fg_color="#c0392b", command=self.import_data_replace
        ).pack(side="right", padx=5)
        ctk.CTkButton(
            top_bar, text="Reparar BD",
            fg_color="#e67e22", command=self.repair_database
        ).pack(side="right", padx=5)
        ctk.CTkButton(
            top_bar, text="Diagnostico",
            fg_color="#16a085", command=self.diagnostico
        ).pack(side="right", padx=5)

        # --- Columna Recetas agregada ---
        self.tree = ttk.Treeview(
            self.tab_records,
            columns=("ID", "Nombre", "Edad", "Fecha", "Recetas", "Imagenes"),
            show="headings"
        )
        self.tree.heading("ID",       text="ID")
        self.tree.heading("Nombre",   text="Nombre")
        self.tree.heading("Edad",     text="Edad")
        self.tree.heading("Fecha",    text="Fecha")
        self.tree.heading("Recetas",  text="Recetas")
        self.tree.heading("Imagenes", text="Imagenes")

        self.tree.column("ID",       width=50,  anchor="center")
        self.tree.column("Nombre",   width=220)
        self.tree.column("Edad",     width=70,  anchor="center")
        self.tree.column("Fecha",    width=110, anchor="center")
        self.tree.column("Recetas",  width=80,  anchor="center")
        self.tree.column("Imagenes", width=100, anchor="center")

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkButton(
            self.tab_records,
            text="Cargar Paciente Seleccionado",
            height=50, fg_color="#27ae60",
            command=self.load_selected
        ).pack(pady=10)

    # ------------------------------------------------------------------
    # DIAGNOSTICO
    # ------------------------------------------------------------------
    def diagnostico(self):
        lineas = []
        lineas.append(f"BASE_DIR:      {BASE_DIR}")
        lineas.append(f"DB_NAME:       {DB_NAME}")
        lineas.append(f"MEDIA_FOLDER:  {MEDIA_FOLDER}")
        lineas.append(f"DB existe:     {os.path.exists(DB_NAME)}")
        lineas.append(f"MEDIA existe:  {os.path.exists(MEDIA_FOLDER)}")
        lineas.append("")
        if os.path.exists(MEDIA_FOLDER):
            archivos = os.listdir(MEDIA_FOLDER)
            lineas.append(f"Archivos en patient_media: {len(archivos)}")
            for f in archivos[:10]:
                lineas.append(f"   {f}")
            if len(archivos) > 10:
                lineas.append(f"   ... y {len(archivos)-10} mas")
        else:
            lineas.append("Carpeta patient_media NO existe")
        lineas.append("")
        try:
            with sqlite3.connect(DB_NAME) as conn:
                rows = conn.execute(
                    "SELECT id, name, images FROM patients"
                ).fetchall()
            lineas.append(f"Pacientes en BD: {len(rows)}")
            for pid, pname, imgs in rows:
                try:
                    paths = json.loads(imgs) if imgs else []
                except Exception:
                    paths = []
                encontradas = sum(
                    1 for p in paths
                    if p and self._resolve_image_path(p)
                )
                total    = sum(1 for p in paths if p)
                n_recetas = 0
                try:
                    with sqlite3.connect(DB_NAME) as conn2:
                        n_recetas = conn2.execute(
                            "SELECT COUNT(*) FROM recetas WHERE patient_id=?",
                            (pid,)
                        ).fetchone()[0]
                except Exception:
                    pass
                lineas.append(
                    f"   ID {pid} | {pname} | "
                    f"imagenes: {encontradas}/{total} | "
                    f"recetas: {n_recetas}"
                )
        except Exception as e:
            lineas.append(f"Error leyendo BD: {e}")
        messagebox.showinfo("Diagnostico del Sistema", "\n".join(lineas))

    # ------------------------------------------------------------------
    # LOGICA DE IMAGENES
    # ------------------------------------------------------------------
    def add_image(self, idx):
        path = filedialog.askopenfilename(
            filetypes=[("Imagenes", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff")]
        )
        if path:
            filename = (
                f"IMG_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                f"_{idx}_{os.path.basename(path)}"
            )
            dest = os.path.join(MEDIA_FOLDER, filename)
            shutil.copy2(path, dest)
            self.image_paths[idx] = filename
            self._set_thumbnail(idx, dest)

    def remove_image(self, idx):
        self.image_paths[idx] = None
        if idx in self._image_store:
            del self._image_store[idx]
        lbl = self.image_labels[idx]
        lbl.configure(image=None, text="Vacio")
        lbl.image = None

    def _set_thumbnail(self, idx, path):
        try:
            pil_img = Image.open(path).copy()
            ctk_img = ctk.CTkImage(
                light_image=pil_img,
                dark_image=pil_img,
                size=(220, 170)
            )
            self._image_store[idx] = ctk_img
            lbl       = self.image_labels[idx]
            lbl.image = ctk_img
            lbl.configure(image=ctk_img, text="")
        except Exception as e:
            self.image_labels[idx].configure(
                text=f"Error: {str(e)[:30]}", image=None
            )

    # ------------------------------------------------------------------
    # GUARDAR
    # ------------------------------------------------------------------
    def save_patient(self):
        name = self.ent_name.get()
        if not name:
            return messagebox.showerror("Error", "El nombre es obligatorio")

        while len(self.image_paths) < NUM_IMAGES:
            self.image_paths.append(None)
        self.image_paths = self.image_paths[:NUM_IMAGES]

        paths_to_save = [
            os.path.basename(p) if p else None
            for p in self.image_paths
        ]

        with sqlite3.connect(DB_NAME) as conn:
            if self.current_patient_id:
                conn.execute(
                    "UPDATE patients SET name=?, age=?, date=?, "
                    "images=?, image_desc=? WHERE id=?",
                    (name, self.ent_age.get(), self.ent_date.get(),
                     json.dumps(paths_to_save),
                     self.txt_img_desc.get("1.0", "end-1c"),
                     self.current_patient_id)
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO patients (name, age, date, meds, notes, "
                    "images, image_desc) VALUES (?,?,?,?,?,?,?)",
                    (name, self.ent_age.get(), self.ent_date.get(),
                     "", "",
                     json.dumps(paths_to_save),
                     self.txt_img_desc.get("1.0", "end-1c"))
                )
                self.current_patient_id = cursor.lastrowid

        self.lbl_img_patient.configure(
            text=f"Paciente Actual: {name} ({self.ent_age.get()})"
        )
        messagebox.showinfo("Guardado", "Estudio guardado correctamente.")
        self.refresh_records_table()

    # ------------------------------------------------------------------
    # CARGAR
    # ------------------------------------------------------------------
    def load_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
        p_id = self.tree.item(selection[0])['values'][0]

        with sqlite3.connect(DB_NAME) as conn:
            row = conn.execute(
                "SELECT * FROM patients WHERE id=?", (p_id,)
            ).fetchone()
        if not row:
            return

        (self.current_patient_id, name, age, date,
         meds, notes, imgs, img_desc) = row

        try:
            loaded = json.loads(imgs) if imgs else []
        except (json.JSONDecodeError, TypeError):
            loaded = []
        loaded = (loaded + [None] * NUM_IMAGES)[:NUM_IMAGES]
        self.image_paths = [
            os.path.basename(p) if p else None for p in loaded
        ]

        self._build_image_grid()
        self.root.update_idletasks()

        self.ent_name.delete(0, "end")
        self.ent_name.insert(0, str(name) if name else "")
        self.ent_age.delete(0, "end")
        self.ent_age.insert(0,  str(age)  if age  else "")
        self.ent_date.delete(0, "end")
        self.ent_date.insert(0, str(date) if date else "")
        self.txt_img_desc.delete("1.0", "end")
        self.txt_img_desc.insert("1.0", img_desc if img_desc else "")
        self.lbl_img_patient.configure(
            text=f"Paciente Actual: {name} ({age})"
        )

        self.tabs.set("Estudio de Colposcopia")
        self.root.update_idletasks()
        self.root.update()
        self.root.after(300, lambda: self._load_images_deferred(name, age))

    def _load_images_deferred(self, name, age):
        images_found   = 0
        images_missing = []

        for i, fname in enumerate(self.image_paths):
            if fname:
                resolved = self._resolve_image_path(fname)
                if resolved:
                    self.image_paths[i] = os.path.basename(resolved)
                    self._set_thumbnail(i, resolved)
                    images_found += 1
                    self.root.update_idletasks()
                else:
                    self.image_paths[i] = None
                    self.image_labels[i].configure(
                        text="No encontrada", image=None
                    )
                    images_missing.append(fname)

        self.root.update_idletasks()

        if images_missing:
            messagebox.showwarning(
                "Imagenes no encontradas",
                f"Paciente: {name} ({age})\n"
                f"Encontradas: {images_found}\n"
                f"No encontradas: {len(images_missing)}\n\n"
                f"Archivos faltantes:\n" +
                "\n".join(images_missing) +
                "\n\nUsa Diagnostico para mas detalles."
            )
        else:
            messagebox.showinfo(
                "Cargado",
                f"Paciente: {name} ({age})\n"
                f"{images_found} imagen(es) cargada(s) correctamente."
            )

    # ------------------------------------------------------------------
    # EXPORTAR
    # ------------------------------------------------------------------
    def export_data(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            initialdir=BASE_DIR,
            initialfile=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        )
        if not path:
            return

        count_imgs = 0
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
            if os.path.exists(DB_NAME):
                z.write(DB_NAME, arcname="medical_data.db")
            if os.path.exists(MEDIA_FOLDER):
                for f in os.listdir(MEDIA_FOLDER):
                    full = os.path.join(MEDIA_FOLDER, f)
                    if os.path.isfile(full):
                        z.write(full, arcname=f"patient_media/{f}")
                        count_imgs += 1

        messagebox.showinfo(
            "Exportar",
            f"Backup creado correctamente.\n"
            f"Base de datos: OK\n"
            f"Imagenes exportadas: {count_imgs}\n\n"
            f"Archivo: {os.path.basename(path)}"
        )

    # ------------------------------------------------------------------
    # IMPORTAR - REEMPLAZAR
    # ------------------------------------------------------------------
    def import_data_replace(self):
        path = filedialog.askopenfilename(
            filetypes=[("Zip", "*.zip")], initialdir=BASE_DIR
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Confirmar Reemplazar",
            "Esto BORRARA todos los datos actuales y los reemplazara "
            "con los del ZIP.\n\nContinuar?"
        ):
            return

        import_dir = os.path.join(BASE_DIR, "temp_import")
        try:
            if os.path.exists(import_dir):
                shutil.rmtree(import_dir)
            os.makedirs(import_dir)

            with zipfile.ZipFile(path, 'r') as z:
                nombres    = z.namelist()
                tiene_db   = "medical_data.db" in nombres
                tiene_imgs = any(
                    n.startswith("patient_media/") for n in nombres
                )
                for item in nombres:
                    if item.endswith("/") or item.endswith("\\"):
                        continue
                    item_clean = item.replace("\\", "/")
                    parts      = [p for p in item_clean.split("/") if p]
                    dest_path  = import_dir
                    for part in parts:
                        dest_path = os.path.join(dest_path, part)
                    dest_dir = os.path.dirname(dest_path)
                    if dest_dir and not os.path.exists(dest_dir):
                        os.makedirs(dest_dir, exist_ok=True)
                    if not os.path.isdir(dest_path):
                        with z.open(item) as src, \
                             open(dest_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)

            tmp_db = os.path.join(import_dir, "medical_data.db")
            if os.path.exists(tmp_db):
                shutil.copy2(tmp_db, DB_NAME)

            tmp_media     = os.path.join(import_dir, "patient_media")
            imgs_copiadas = 0
            if os.path.exists(tmp_media):
                for f in os.listdir(tmp_media):
                    src  = os.path.join(tmp_media, f)
                    dest = os.path.join(MEDIA_FOLDER, f)
                    if os.path.isfile(src):
                        shutil.copy2(src, dest)
                        imgs_copiadas += 1

            self.refresh_records_table()
            messagebox.showinfo(
                "Importar",
                f"Datos importados correctamente.\n"
                f"Base de datos: {'OK' if tiene_db else 'No encontrada'}\n"
                f"Imagenes copiadas: {imgs_copiadas}"
            )
        except Exception as e:
            messagebox.showerror(
                "Error al importar",
                f"Detalle del error:\n{str(e)}\n\n"
                f"Carpeta usada: {import_dir}"
            )
        finally:
            if os.path.exists(import_dir):
                try:
                    shutil.rmtree(import_dir)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # IMPORTAR - FUSIONAR
    # ------------------------------------------------------------------
    def import_data_merge(self):
        path = filedialog.askopenfilename(
            filetypes=[("Zip", "*.zip")], initialdir=BASE_DIR
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Confirmar Fusionar",
            "Los pacientes del ZIP se agregaran a los existentes.\n"
            "Las imagenes se copiaran sin borrar las actuales.\n\n"
            "Continuar?"
        ):
            return

        import_dir = os.path.join(BASE_DIR, "temp_import")
        try:
            if os.path.exists(import_dir):
                shutil.rmtree(import_dir)
            os.makedirs(import_dir)

            with zipfile.ZipFile(path, 'r') as z:
                for item in z.namelist():
                    if item.endswith("/") or item.endswith("\\"):
                        continue
                    item_clean = item.replace("\\", "/")
                    parts      = [p for p in item_clean.split("/") if p]
                    dest_path  = import_dir
                    for part in parts:
                        dest_path = os.path.join(dest_path, part)
                    dest_dir = os.path.dirname(dest_path)
                    if dest_dir and not os.path.exists(dest_dir):
                        os.makedirs(dest_dir, exist_ok=True)
                    if not os.path.isdir(dest_path):
                        with z.open(item) as src, \
                             open(dest_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)

            tmp_media     = os.path.join(import_dir, "patient_media")
            imgs_copiadas = 0
            if os.path.exists(tmp_media):
                for f in os.listdir(tmp_media):
                    src  = os.path.join(tmp_media, f)
                    dest = os.path.join(MEDIA_FOLDER, f)
                    if os.path.isfile(src) and not os.path.exists(dest):
                        shutil.copy2(src, dest)
                        imgs_copiadas += 1

            tmp_db              = os.path.join(import_dir, "medical_data.db")
            pacientes_agregados = 0

            if not os.path.exists(tmp_db):
                messagebox.showwarning(
                    "Aviso",
                    f"No se encontro medical_data.db en el ZIP.\n"
                    f"Carpeta de extraccion: {import_dir}"
                )
                return

            with sqlite3.connect(tmp_db) as src_conn:
                src_rows = src_conn.execute(
                    "SELECT name, age, date, meds, notes, "
                    "images, image_desc FROM patients"
                ).fetchall()

            with sqlite3.connect(DB_NAME) as dst_conn:
                for row in src_rows:
                    existe = dst_conn.execute(
                        "SELECT id FROM patients "
                        "WHERE name=? AND date=?",
                        (row[0], row[2])
                    ).fetchone()
                    if not existe:
                        dst_conn.execute(
                            "INSERT INTO patients "
                            "(name, age, date, meds, notes, "
                            "images, image_desc) "
                            "VALUES (?,?,?,?,?,?,?)",
                            row
                        )
                        pacientes_agregados += 1

            self.refresh_records_table()
            messagebox.showinfo(
                "Fusionar",
                f"Fusion completada.\n"
                f"Pacientes nuevos agregados: {pacientes_agregados}\n"
                f"Imagenes nuevas copiadas:   {imgs_copiadas}"
            )
        except Exception as e:
            messagebox.showerror(
                "Error al fusionar",
                f"Detalle del error:\n{str(e)}\n\n"
                f"Carpeta usada: {import_dir}"
            )
        finally:
            if os.path.exists(import_dir):
                try:
                    shutil.rmtree(import_dir)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # REPARAR BD
    # ------------------------------------------------------------------
    def repair_database(self):
        reparados   = 0
        no_hallados = 0
        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute(
                "SELECT id, images FROM patients"
            ).fetchall()
            for r_id, img_json in rows:
                try:
                    paths = json.loads(img_json) if img_json else []
                except Exception:
                    paths = []
                fixed = []
                for p in paths:
                    if p:
                        resolved = self._resolve_image_path(p)
                        if resolved:
                            fixed.append(os.path.basename(resolved))
                            reparados += 1
                        else:
                            fixed.append(None)
                            no_hallados += 1
                    else:
                        fixed.append(None)
                conn.execute(
                    "UPDATE patients SET images=? WHERE id=?",
                    (json.dumps(fixed), r_id)
                )
        messagebox.showinfo(
            "Reparar BD",
            f"Sincronizacion completa.\n"
            f"Rutas reparadas: {reparados}\n"
            f"No encontradas:  {no_hallados}\n\n"
            f"Usa Diagnostico si persisten los problemas."
        )

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------
    def _draw_wrapped_text(self, c, text, x, y, max_width,
                           font_name, font_size, line_height, page_h):
        c.setFont(font_name, font_size)
        for paragraph in text.split('\n'):
            words    = paragraph.split(' ') if paragraph.strip() else ['']
            line_buf = ""
            for word in words:
                test = (line_buf + " " + word).strip()
                if stringWidth(test, font_name, font_size) <= max_width:
                    line_buf = test
                else:
                    if y < 1 * cm:
                        c.showPage()
                        c.setFont(font_name, font_size)
                        y = page_h - 4.0 * cm
                    c.drawString(x, y, line_buf)
                    y        -= line_height
                    line_buf  = word
            if line_buf:
                if y < 1 * cm:
                    c.showPage()
                    c.setFont(font_name, font_size)
                    y = page_h - 4.0 * cm
                c.drawString(x, y, line_buf)
                y -= line_height
        return y

    def generate_image_pdf(self):
        name     = self.ent_name.get()
        date     = self.ent_date.get()
        desc_txt = self.txt_img_desc.get("1.0", "end-1c")
        fs       = self.pdf_font_size.get()
        line_h   = fs * 1.4

        filename = os.path.join(BASE_DIR, f"Colposcopia_{name}.pdf")
        c = canvas.Canvas(filename, pagesize=LETTER_PAGE_SIZE)
        w, h = LETTER_PAGE_SIZE

        x_left     = 3.3 * cm
        y_name     = h - (6.9 * cm)
        y_date     = h - (7.9 * cm)
        y_grid_top = h - (10.5 * cm)

        c.setFont("Helvetica", fs)
        c.drawString(x_left, y_name, name)
        c.setFont("Helvetica", fs)
        c.drawString(x_left, y_date, date)

        total_grid_w = COLS * IMG_W
        grid_x       = (w - total_grid_w) / 2
        grid_top     = y_grid_top

        valid = []
        for fname in self.image_paths:
            if fname:
                resolved = self._resolve_image_path(fname)
                valid.append(resolved)
            else:
                valid.append(None)

        for idx in range(NUM_IMAGES):
            row = idx // COLS
            col = idx %  COLS
            ix  = grid_x + col * IMG_W
            iy  = grid_top - (row + 1) * IMG_H

            if valid[idx]:
                c.drawImage(
                    valid[idx], ix, iy,
                    width=IMG_W, height=IMG_H,
                    preserveAspectRatio=False
                )
            else:
                c.setFillColorRGB(1, 1, 1)
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(1.5)
                c.rect(ix, iy, IMG_W, IMG_H, fill=1, stroke=0)

            c.setFillColorRGB(0, 0, 0)
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(1.5)
            c.rect(ix, iy, IMG_W, IMG_H, fill=0, stroke=1)
            c.setLineWidth(1)

        block_width = 10.0 * cm
        x_obs       = (w - block_width) / 2
        y_obs_start = grid_top - ROWS * IMG_H - 0.5 * cm

        if desc_txt.strip():
            self._draw_wrapped_text(
                c, desc_txt, x_obs, y_obs_start,
                block_width, "Helvetica", fs, line_h, h
            )

        c.save()
        os.startfile(filename)

    # ------------------------------------------------------------------
    # LIMPIAR / REFRESCAR
    # ------------------------------------------------------------------
    def clear_form(self):
        self.current_patient_id = None
        self.ent_name.delete(0, "end")
        self.ent_age.delete(0, "end")
        self.ent_date.delete(0, "end")
        self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.txt_img_desc.delete("1.0", "end")
        self.lbl_img_patient.configure(
            text="Paciente Actual: Ninguno Seleccionado"
        )
        self.image_paths = [None] * NUM_IMAGES
        self._build_image_grid()

    def refresh_records_table(self, event=None):
        for i in self.tree.get_children():
            self.tree.delete(i)
        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute(
                "SELECT id, name, age, date, images "
                "FROM patients WHERE name LIKE ?",
                (f"%{self.ent_search.get()}%",)
            ).fetchall()
            for r in rows:
                p_id, name, age, date, imgs = r
                try:
                    paths = json.loads(imgs) if imgs else []
                except Exception:
                    paths = []
                total     = sum(1 for p in paths if p)
                n_recetas = self._get_receta_count(conn, p_id)
                self.tree.insert(
                    "", "end",
                    values=(p_id, name, age, date, n_recetas, f"{total} / 4")
                )


if __name__ == "__main__":
    root = ctk.CTk()
    app  = ColposcopiaApp(root)
    root.mainloop()