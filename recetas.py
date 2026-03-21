import customtkinter as ctk
from tkinter import messagebox, filedialog, ttk
import sqlite3
import os
import json
import shutil
import sys
import zipfile
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
import win32print
import win32api


def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR         = get_base_path()
DB_NAME          = os.path.join(BASE_DIR, "medical_data.db")
MEDIA_FOLDER     = os.path.join(BASE_DIR, "patient_media")

LETTER_WIDTH     = 21.59 * cm
LETTER_HEIGHT    = 27.94 * cm
LETTER_PAGE_SIZE = (LETTER_WIDTH, LETTER_HEIGHT)

MARGIN_LEFT      = 2.0 * cm
MARGIN_RIGHT     = 2.0 * cm
TOP_MARGIN       = 3.65 * cm
NAME_X           = 3.3 * cm
AGE_X            = 2.0 * cm + 11.5 * cm
DATE_X           = 3.5 * cm + 11.2 * cm + 3.0 * cm
HEADER_BODY_GAP  = 1.0 * cm
MEDS_X           = 7.0 * cm

if not os.path.exists(MEDIA_FOLDER):
    os.makedirs(MEDIA_FOLDER)


class RecetasApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Recetas Medicas")
        self.root.geometry("1200x950")

        self.current_patient_id  = None
        self.current_receta_id   = None
        self.show_labels_var     = ctk.BooleanVar(value=False)
        self.pdf_font_size       = ctk.IntVar(value=11)

        self.init_db()
        self.setup_ui()
        self.refresh_records_table()

        # Maximizar despues de que la UI termine de cargar
        self.root.after(100, lambda: self.root.state('zoomed'))

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
            conn.execute(
                '''CREATE TABLE IF NOT EXISTS recetas (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id  INTEGER NOT NULL,
                    fecha       TEXT,
                    meds        TEXT,
                    notes       TEXT,
                    FOREIGN KEY (patient_id) REFERENCES patients(id)
                )'''
            )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def setup_ui(self):
        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_form    = self.tabs.add("Nueva Receta")
        self.tab_records = self.tabs.add("Registros de Pacientes")
        self._build_tab_form()
        self._build_tab_records()

    # ------------------------------------------------------------------
    # PESTANA 1 - RECETA
    # ------------------------------------------------------------------
    def _build_tab_form(self):
        name_frame = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        name_frame.pack(fill="x", padx=20, pady=(15, 0))
        ctk.CTkLabel(
            name_frame, text="Nombre del Paciente",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.ent_name = ctk.CTkEntry(
            name_frame, placeholder_text="Ej: Juan Perez", width=400
        )
        self.ent_name.pack(anchor="w", pady=(2, 0))

        row2 = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(10, 0))

        dob_frame = ctk.CTkFrame(row2, fg_color="transparent")
        dob_frame.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(
            dob_frame, text="Ano de Nacimiento",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.ent_birth_year = ctk.CTkEntry(
            dob_frame, placeholder_text="Ej: 1990", width=120
        )
        self.ent_birth_year.pack(anchor="w", pady=(2, 0))
        self.ent_birth_year.bind("<KeyRelease>", self._auto_calc_age)

        age_frame = ctk.CTkFrame(row2, fg_color="transparent")
        age_frame.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(
            age_frame, text="Edad",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.ent_age = ctk.CTkEntry(
            age_frame, placeholder_text="Auto / Manual", width=120
        )
        self.ent_age.pack(anchor="w", pady=(2, 0))

        date_frame = ctk.CTkFrame(row2, fg_color="transparent")
        date_frame.pack(side="left")
        ctk.CTkLabel(
            date_frame, text="Fecha",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.ent_date = ctk.CTkEntry(date_frame, width=150)
        self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.ent_date.pack(anchor="w", pady=(2, 0))

        # ---- Selector de receta activa ----
        receta_bar = ctk.CTkFrame(self.tab_form, fg_color="#2b2b2b")
        receta_bar.pack(fill="x", padx=20, pady=(12, 0))

        ctk.CTkLabel(
            receta_bar,
            text="Receta:",
            font=("Helvetica", 12, "bold")
        ).pack(side="left", padx=(10, 6), pady=8)

        self.receta_selector = ctk.CTkOptionMenu(
            receta_bar,
            values=["-- Sin recetas --"],
            width=220,
            command=self._on_receta_selected
        )
        self.receta_selector.pack(side="left", padx=(0, 10), pady=8)

        ctk.CTkButton(
            receta_bar,
            text="+ Nueva Receta",
            fg_color="#27ae60",
            width=140,
            command=self.nueva_receta
        ).pack(side="left", padx=4, pady=8)

        ctk.CTkButton(
            receta_bar,
            text="Eliminar Receta",
            fg_color="#c0392b",
            width=140,
            command=self.eliminar_receta
        ).pack(side="left", padx=4, pady=8)

        self.lbl_receta_info = ctk.CTkLabel(
            receta_bar,
            text="",
            font=("Helvetica", 11),
            text_color="#aaaaaa"
        )
        self.lbl_receta_info.pack(side="left", padx=10, pady=8)

        # ---- Medicamentos ----
        meds_frame = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        meds_frame.pack(fill="x", padx=20, pady=(12, 0))
        ctk.CTkLabel(
            meds_frame, text="Medicamentos e Indicaciones",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.txt_meds = ctk.CTkTextbox(meds_frame, height=220)
        self.txt_meds.pack(fill="x", pady=(2, 0))

        # ---- Notas privadas ----
        notes_frame = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        notes_frame.pack(fill="x", padx=20, pady=(12, 0))
        ctk.CTkLabel(
            notes_frame, text="Notas Privadas (Solo Uso Interno)",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.txt_notes = ctk.CTkTextbox(notes_frame, height=70)
        self.txt_notes.pack(fill="x", pady=(2, 0))

        # ---- Opciones PDF ----
        pdf_options_frame = ctk.CTkFrame(self.tab_form)
        pdf_options_frame.pack(fill="x", padx=20, pady=(12, 0))
        ctk.CTkLabel(
            pdf_options_frame, text="Opciones de PDF",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w", padx=10, pady=(8, 4))

        opts_row = ctk.CTkFrame(pdf_options_frame, fg_color="transparent")
        opts_row.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkSwitch(
            opts_row,
            text="Mostrar etiquetas en cabecera  (Nombre: / Edad: / Fecha:)",
            variable=self.show_labels_var,
            onvalue=True,
            offvalue=False
        ).pack(side="left", padx=(0, 30))

        font_frame = ctk.CTkFrame(opts_row, fg_color="transparent")
        font_frame.pack(side="left")
        ctk.CTkLabel(font_frame, text="Tamano de fuente:").pack(
            side="left", padx=(0, 6)
        )
        ctk.CTkOptionMenu(
            font_frame,
            values=["8", "9", "10", "11", "12", "13", "14", "16", "18"],
            variable=self.pdf_font_size,
            width=70,
            command=lambda v: self.pdf_font_size.set(int(v))
        ).pack(side="left")

        # ---- Botones principales ----
        btn_row = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        btn_row.pack(pady=15)
        ctk.CTkButton(
            btn_row, text="Guardar Receta",
            fg_color="#27ae60", width=150,
            command=self.save_patient
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btn_row, text="Imprimir PDF",
            fg_color="#2980b9", width=150,
            command=self.generate_patient_pdf
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btn_row, text="Limpiar Formulario",
            fg_color="#c0392b", width=150,
            command=self.clear_form
        ).pack(side="left", padx=10)

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

        self.tree = ttk.Treeview(
            self.tab_records,
            columns=("ID", "Nombre", "Edad", "Fecha", "Recetas", "Estudio"),
            show="headings"
        )
        self.tree.heading("ID",      text="ID")
        self.tree.heading("Nombre",  text="Nombre")
        self.tree.heading("Edad",    text="Edad")
        self.tree.heading("Fecha",   text="Fecha")
        self.tree.heading("Recetas", text="Recetas")
        self.tree.heading("Estudio", text="Estudio Colposcopia")

        self.tree.column("ID",      width=50,  anchor="center")
        self.tree.column("Nombre",  width=220)
        self.tree.column("Edad",    width=70,  anchor="center")
        self.tree.column("Fecha",   width=110, anchor="center")
        self.tree.column("Recetas", width=80,  anchor="center")
        self.tree.column("Estudio", width=150, anchor="center")

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkButton(
            self.tab_records,
            text="Cargar Paciente Seleccionado",
            height=50, fg_color="#27ae60",
            command=self.load_selected
        ).pack(pady=10)

    # ------------------------------------------------------------------
    # HISTORIAL DE RECETAS
    # ------------------------------------------------------------------
    def _get_recetas(self, patient_id):
        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute(
                "SELECT id, fecha, meds, notes FROM recetas "
                "WHERE patient_id=? ORDER BY id DESC",
                (patient_id,)
            ).fetchall()
        return rows

    def _make_option_label(self, receta_row):
        """
        Genera el texto que se muestra en el selector.
        Solo muestra la fecha. Si hay duplicados agrega un indice.
        receta_row = (id, fecha, meds, notes)
        """
        return receta_row[1]   # solo la fecha

    def _refresh_receta_selector(self, patient_id, select_id=None):
        recetas = self._get_recetas(patient_id)
        self._recetas_cache = recetas

        if not recetas:
            self.receta_selector.configure(values=["-- Sin recetas --"])
            self.receta_selector.set("-- Sin recetas --")
            self.current_receta_id = None
            self.lbl_receta_info.configure(text="Sin recetas guardadas")
            return

        # Construir etiquetas unicas: si hay fechas repetidas
        # se agrega un sufijo (#2, #3...) para distinguirlas
        fecha_count = {}
        for r in recetas:
            fecha_count[r[1]] = fecha_count.get(r[1], 0) + 1

        fecha_seen  = {}
        opciones    = []
        for r in recetas:
            fecha = r[1]
            if fecha_count[fecha] > 1:
                fecha_seen[fecha] = fecha_seen.get(fecha, 0) + 1
                label = f"{fecha}  (#{fecha_seen[fecha]})"
            else:
                label = fecha
            opciones.append((r[0], label))   # (id, label)

        self._opciones_map = opciones        # [(id, label), ...]
        labels = [o[1] for o in opciones]

        self.receta_selector.configure(values=labels)

        if select_id:
            target = next(
                (lbl for rid, lbl in opciones if rid == select_id),
                labels[0]
            )
        else:
            target = labels[0]

        self.receta_selector.set(target)
        self._load_receta_by_label(target)

    def _on_receta_selected(self, value):
        self._load_receta_by_label(value)

    def _load_receta_by_label(self, label):
        """Carga la receta cuyo label coincide en _opciones_map."""
        if not hasattr(self, '_opciones_map') or not self._opciones_map:
            return
        for rid, lbl in self._opciones_map:
            if lbl == label:
                self.current_receta_id = rid
                # Buscar datos en cache
                for r in self._recetas_cache:
                    if r[0] == rid:
                        self.txt_meds.delete("1.0", "end")
                        self.txt_meds.insert("1.0", r[2] if r[2] else "")
                        self.txt_notes.delete("1.0", "end")
                        self.txt_notes.insert("1.0", r[3] if r[3] else "")
                        self.lbl_receta_info.configure(
                            text=f"Editando receta del {r[1]}"
                        )
                        break
                break

    def nueva_receta(self):
        if not self.current_patient_id:
            messagebox.showwarning(
                "Aviso",
                "Primero carga o guarda un paciente antes de crear "
                "una nueva receta."
            )
            return
        self._save_current_receta_silent()
        self.txt_meds.delete("1.0", "end")
        self.txt_notes.delete("1.0", "end")
        self.ent_date.delete(0, "end")
        fecha = datetime.now().strftime("%d/%m/%Y")
        self.ent_date.insert(0, fecha)

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.execute(
                "INSERT INTO recetas (patient_id, fecha, meds, notes) "
                "VALUES (?,?,?,?)",
                (self.current_patient_id, fecha, "", "")
            )
            new_id = cursor.lastrowid

        self.current_receta_id = new_id
        self._refresh_receta_selector(
            self.current_patient_id, select_id=new_id
        )
        self.lbl_receta_info.configure(
            text=f"Nueva receta  |  {fecha}"
        )

    def eliminar_receta(self):
        if not self.current_receta_id:
            messagebox.showwarning("Aviso", "No hay receta seleccionada.")
            return
        recetas = self._get_recetas(self.current_patient_id)
        if len(recetas) <= 1:
            messagebox.showwarning(
                "Aviso",
                "No se puede eliminar la unica receta del paciente."
            )
            return
        if not messagebox.askyesno(
            "Confirmar",
            f"¿Eliminar la receta del {self.receta_selector.get()}?\n"
            "Esta accion no se puede deshacer."
        ):
            return
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                "DELETE FROM recetas WHERE id=?",
                (self.current_receta_id,)
            )
        self.current_receta_id = None
        self._refresh_receta_selector(self.current_patient_id)

    def _save_current_receta_silent(self):
        if not self.current_patient_id:
            return
        meds  = self.txt_meds.get("1.0", "end-1c")
        notes = self.txt_notes.get("1.0", "end-1c")
        fecha = self.ent_date.get()
        if self.current_receta_id:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(
                    "UPDATE recetas SET fecha=?, meds=?, notes=? WHERE id=?",
                    (fecha, meds, notes, self.current_receta_id)
                )
        else:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.execute(
                    "INSERT INTO recetas (patient_id, fecha, meds, notes) "
                    "VALUES (?,?,?,?)",
                    (self.current_patient_id, fecha, meds, notes)
                )
                self.current_receta_id = cursor.lastrowid

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
        try:
            with sqlite3.connect(DB_NAME) as conn:
                rows = conn.execute(
                    "SELECT id, name FROM patients"
                ).fetchall()
            lineas.append(f"Pacientes en BD: {len(rows)}")
            for pid, pname in rows:
                with sqlite3.connect(DB_NAME) as conn2:
                    n_recetas = conn2.execute(
                        "SELECT COUNT(*) FROM recetas WHERE patient_id=?",
                        (pid,)
                    ).fetchone()[0]
                lineas.append(
                    f"   ID {pid} | {pname} | recetas: {n_recetas}"
                )
        except Exception as e:
            lineas.append(f"Error leyendo BD: {e}")
        messagebox.showinfo("Diagnostico del Sistema", "\n".join(lineas))

    # ------------------------------------------------------------------
    # LOGICA
    # ------------------------------------------------------------------
    def _auto_calc_age(self, event=None):
        birth_str = self.ent_birth_year.get().strip()
        if len(birth_str) == 4 and birth_str.isdigit():
            birth_year   = int(birth_str)
            current_year = datetime.now().year
            if 1900 <= birth_year <= current_year:
                self.ent_age.delete(0, "end")
                self.ent_age.insert(0, str(current_year - birth_year))
            else:
                self.ent_age.delete(0, "end")
        elif birth_str == "":
            self.ent_age.delete(0, "end")

    def save_patient(self):
        name = self.ent_name.get()
        if not name:
            return messagebox.showerror("Error", "El nombre es obligatorio")

        meds  = self.txt_meds.get("1.0", "end-1c")
        notes = self.txt_notes.get("1.0", "end-1c")
        fecha = self.ent_date.get()

        with sqlite3.connect(DB_NAME) as conn:
            if self.current_patient_id:
                conn.execute(
                    "UPDATE patients SET name=?, age=?, date=? WHERE id=?",
                    (name, self.ent_age.get(), fecha,
                     self.current_patient_id)
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO patients "
                    "(name, age, date, meds, notes, images, image_desc) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (name, self.ent_age.get(), fecha,
                     meds, notes,
                     json.dumps([None, None, None, None]), "")
                )
                self.current_patient_id = cursor.lastrowid

            if self.current_receta_id:
                conn.execute(
                    "UPDATE recetas SET fecha=?, meds=?, notes=? WHERE id=?",
                    (fecha, meds, notes, self.current_receta_id)
                )
            else:
                cursor2 = conn.execute(
                    "INSERT INTO recetas (patient_id, fecha, meds, notes) "
                    "VALUES (?,?,?,?)",
                    (self.current_patient_id, fecha, meds, notes)
                )
                self.current_receta_id = cursor2.lastrowid

        self._refresh_receta_selector(
            self.current_patient_id,
            select_id=self.current_receta_id
        )
        self.refresh_records_table()
        messagebox.showinfo("Guardado", "Receta guardada correctamente.")

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
        self.clear_form()
        (self.current_patient_id, name, age, date,
         meds, notes, imgs, img_desc) = row
        self.ent_name.insert(0,  str(name) if name else "")
        self.ent_age.insert(0,   str(age)  if age  else "")
        self.ent_date.delete(0, "end")
        self.ent_date.insert(0,  str(date) if date else "")

        recetas = self._get_recetas(self.current_patient_id)
        if recetas:
            self._recetas_cache = recetas
            self._refresh_receta_selector(
                self.current_patient_id, select_id=recetas[0][0]
            )
        else:
            self._recetas_cache = []
            if meds or notes:
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.execute(
                        "INSERT INTO recetas (patient_id, fecha, meds, notes) "
                        "VALUES (?,?,?,?)",
                        (self.current_patient_id,
                         date or datetime.now().strftime("%d/%m/%Y"),
                         meds or "", notes or "")
                    )
                    new_id = cursor.lastrowid
                self._refresh_receta_selector(
                    self.current_patient_id, select_id=new_id
                )
            else:
                self.receta_selector.configure(
                    values=["-- Sin recetas --"]
                )
                self.receta_selector.set("-- Sin recetas --")
                self.lbl_receta_info.configure(text="Sin recetas")

        self.tabs.set("Nueva Receta")

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
                nombres  = z.namelist()
                tiene_db = "medical_data.db" in nombres
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
            self.init_db()
            self.refresh_records_table()
            messagebox.showinfo(
                "Importar",
                f"Datos importados correctamente.\n"
                f"Base de datos: {'OK' if tiene_db else 'No encontrada'}\n"
                f"Imagenes copiadas: {imgs_copiadas}"
            )
        except Exception as e:
            messagebox.showerror(
                "Error al importar", f"Detalle:\n{str(e)}"
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
            "Los pacientes del ZIP se agregaran a los existentes.\n\n"
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
                    "Aviso", "No se encontro la BD en el ZIP."
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
                        "SELECT id FROM patients WHERE name=? AND date=?",
                        (row[0], row[2])
                    ).fetchone()
                    if not existe:
                        dst_conn.execute(
                            "INSERT INTO patients "
                            "(name, age, date, meds, notes, "
                            "images, image_desc) VALUES (?,?,?,?,?,?,?)",
                            row
                        )
                        pacientes_agregados += 1
            self.refresh_records_table()
            messagebox.showinfo(
                "Fusionar",
                f"Fusion completada.\n"
                f"Pacientes nuevos: {pacientes_agregados}\n"
                f"Imagenes copiadas: {imgs_copiadas}"
            )
        except Exception as e:
            messagebox.showerror(
                "Error al fusionar", f"Detalle:\n{str(e)}"
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
                        full = os.path.join(MEDIA_FOLDER, p)
                        if os.path.exists(full):
                            fixed.append(p)
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
            f"No encontradas:  {no_hallados}"
        )

    # ------------------------------------------------------------------
    # HELPERS PDF
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
                        y = page_h - TOP_MARGIN
                    c.drawString(x, y, line_buf)
                    y        -= line_height
                    line_buf  = word
            if line_buf:
                if y < 1 * cm:
                    c.showPage()
                    c.setFont(font_name, font_size)
                    y = page_h - TOP_MARGIN
                c.drawString(x, y, line_buf)
                y -= line_height
        return y

    def _draw_header_p1(self, c, h):
        fs   = self.pdf_font_size.get()
        show = self.show_labels_var.get()
        y    = h - TOP_MARGIN
        c.setFont("Helvetica", fs)
        name = self.ent_name.get()
        age  = self.ent_age.get()
        date = self.ent_date.get()
        if show:
            c.drawString(NAME_X, y, f"Nombre: {name}")
            if age:  c.drawString(AGE_X,  y, f"Edad: {age}")
            if date: c.drawString(DATE_X, y, f"Fecha: {date}")
        else:
            c.drawString(NAME_X, y, name)
            if age:  c.drawString(AGE_X,  y, age)
            if date: c.drawString(DATE_X, y, date)
        return y - HEADER_BODY_GAP

    def generate_patient_pdf(self):
        name     = self.ent_name.get()
        meds_txt = self.txt_meds.get("1.0", "end-1c")
        fs       = self.pdf_font_size.get()
        line_h   = fs * 1.4

        filename = os.path.join(BASE_DIR, f"Registro_{name}.pdf")
        c = canvas.Canvas(filename, pagesize=LETTER_PAGE_SIZE)
        w, h = LETTER_PAGE_SIZE

        y         = self._draw_header_p1(c, h)
        max_width = w - MEDS_X - MARGIN_RIGHT

        self._draw_wrapped_text(
            c, meds_txt, MEDS_X, y,
            max_width, "Helvetica", fs, line_h, h
        )
        c.save()
        os.startfile(filename)

    # ------------------------------------------------------------------
    # LIMPIAR / REFRESCAR
    # ------------------------------------------------------------------
    def clear_form(self):
        self.current_patient_id = None
        self.current_receta_id  = None
        self._recetas_cache     = []
        self._opciones_map      = []
        self.ent_name.delete(0, "end")
        self.ent_birth_year.delete(0, "end")
        self.ent_age.delete(0, "end")
        self.ent_date.delete(0, "end")
        self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.txt_meds.delete("1.0", "end")
        self.txt_notes.delete("1.0", "end")
        self.receta_selector.configure(values=["-- Sin recetas --"])
        self.receta_selector.set("-- Sin recetas --")
        self.lbl_receta_info.configure(text="")

    def refresh_records_table(self, event=None):
        for i in self.tree.get_children():
            self.tree.delete(i)
        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute(
                "SELECT id, name, age, date, images FROM patients "
                "WHERE name LIKE ?",
                (f"%{self.ent_search.get()}%",)
            ).fetchall()
            for r in rows:
                p_id, name, age, date, imgs = r
                try:
                    paths = json.loads(imgs) if imgs else []
                except Exception:
                    paths = []
                total   = sum(1 for p in paths if p)
                estudio = "Sin estudio" if total == 0 \
                    else f"{total} / 4 imagenes"
                n_rec = conn.execute(
                    "SELECT COUNT(*) FROM recetas WHERE patient_id=?",
                    (p_id,)
                ).fetchone()[0]
                self.tree.insert(
                    "", "end",
                    values=(p_id, name, age, date, n_rec, estudio)
                )


if __name__ == "__main__":
    root = ctk.CTk()
    app  = RecetasApp(root)
    root.mainloop()