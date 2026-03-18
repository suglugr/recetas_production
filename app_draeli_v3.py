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

MARGIN_LEFT     = 2.0 * cm
MARGIN_RIGHT    = 2.0 * cm
TOP_MARGIN      = 4.0 * cm
NAME_X          = 2.0 * cm
AGE_X           = 2.0 * cm + 11.5 * cm
DATE_X          = 2.5 * cm + 10.0 * cm + 3.0 * cm
HEADER_BODY_GAP = 1.0 * cm

IMG_W      = 7.5 * cm
IMG_H      = 6.0 * cm
COLS       = 2
ROWS       = 2
NUM_IMAGES = COLS * ROWS

if not os.path.exists(MEDIA_FOLDER):
    os.makedirs(MEDIA_FOLDER)


class MedicalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Gestión Médica Pro")
        self.root.geometry("1200x950")

        self.current_patient_id = None
        self.image_paths        = [None] * NUM_IMAGES
        self._ctk_images        = [None] * NUM_IMAGES

        self.show_labels_var = ctk.BooleanVar(value=False)
        self.pdf_font_size   = ctk.IntVar(value=11)

        self.init_db()
        self.setup_ui()
        self.refresh_records_table()

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

    def setup_ui(self):
        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_form    = self.tabs.add("Nuevo Paciente")
        self.tab_images  = self.tabs.add("Imágenes del Paciente")
        self.tab_records = self.tabs.add("Registros de Pacientes")
        self._build_tab_form()
        self._build_tab_images()
        self._build_tab_records()

    # ------------------------------------------------------------------
    # PESTAÑA 1
    # ------------------------------------------------------------------
    def _build_tab_form(self):
        name_frame = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        name_frame.pack(fill="x", padx=20, pady=(15, 0))
        ctk.CTkLabel(
            name_frame, text="Nombre del Paciente",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.ent_name = ctk.CTkEntry(
            name_frame, placeholder_text="Ej: Juan Pérez", width=400
        )
        self.ent_name.pack(anchor="w", pady=(2, 0))

        row2 = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(10, 0))

        dob_frame = ctk.CTkFrame(row2, fg_color="transparent")
        dob_frame.pack(side="left", padx=(0, 20))
        ctk.CTkLabel(
            dob_frame, text="Año de Nacimiento",
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

        meds_frame = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        meds_frame.pack(fill="x", padx=20, pady=(15, 0))
        ctk.CTkLabel(
            meds_frame, text="Medicamentos e Indicaciones",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.txt_meds = ctk.CTkTextbox(meds_frame, height=220)
        self.txt_meds.pack(fill="x", pady=(2, 0))

        notes_frame = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        notes_frame.pack(fill="x", padx=20, pady=(15, 0))
        ctk.CTkLabel(
            notes_frame, text="Notas Privadas (Solo Uso Interno)",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.txt_notes = ctk.CTkTextbox(notes_frame, height=80)
        self.txt_notes.pack(fill="x", pady=(2, 0))

        pdf_options_frame = ctk.CTkFrame(self.tab_form)
        pdf_options_frame.pack(fill="x", padx=20, pady=(15, 0))
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
        ctk.CTkLabel(font_frame, text="Tamaño de fuente:").pack(
            side="left", padx=(0, 6)
        )
        ctk.CTkOptionMenu(
            font_frame,
            values=["8", "9", "10", "11", "12", "13", "14", "16", "18"],
            variable=self.pdf_font_size,
            width=70,
            command=lambda v: self.pdf_font_size.set(int(v))
        ).pack(side="left")

        btn_row = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        btn_row.pack(pady=15)
        ctk.CTkButton(
            btn_row, text="Guardar Paciente",
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
    # PESTAÑA 2
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
            img_info_bar, text="Guardar Análisis",
            fg_color="#27ae60", width=140,
            command=self.save_patient
        ).pack(side="right", padx=10)

        ctk.CTkLabel(
            self.tab_images,
            text="Estudio de Colposcopia  —  4 imágenes (2 × 2)",
            font=("Helvetica", 13, "bold")
        ).pack(anchor="w", padx=20, pady=(8, 4))

        self.img_grid = ctk.CTkFrame(self.tab_images)
        self.img_grid.pack(pady=5, padx=20, fill="both", expand=True)

        self.image_labels = []
        for i in range(NUM_IMAGES):
            r, c = divmod(i, COLS)
            slot = ctk.CTkFrame(
                self.img_grid, border_width=2, border_color="#555"
            )
            slot.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")

            lbl = ctk.CTkLabel(
                slot, text=f"Vacío ({r+1},{c+1})", image=None
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

        obs_frame = ctk.CTkFrame(self.tab_images, fg_color="transparent")
        obs_frame.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(
            obs_frame, text="Observaciones del Estudio",
            font=("Helvetica", 12, "bold")
        ).pack(anchor="w")
        self.txt_img_desc = ctk.CTkTextbox(obs_frame, height=70)
        self.txt_img_desc.pack(fill="x", pady=(2, 0))

        ctk.CTkButton(
            self.tab_images,
            text="Imprimir PDF  —  Estudio de Colposcopia",
            fg_color="#2980b9", width=300,
            command=self.generate_image_pdf
        ).pack(pady=12)

    # ------------------------------------------------------------------
    # PESTAÑA 3
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
            top_bar, text="Importar Datos",
            fg_color="#d35400", command=self.import_data
        ).pack(side="right", padx=5)
        ctk.CTkButton(
            top_bar, text="Reparar BD",
            fg_color="#e67e22", command=self.repair_database
        ).pack(side="right", padx=5)

        self.tree = ttk.Treeview(
            self.tab_records,
            columns=("ID", "Nombre", "Edad", "Fecha"),
            show="headings"
        )
        for col in ("ID", "Nombre", "Edad", "Fecha"):
            self.tree.heading(col, text=col)
        self.tree.column("ID", width=50)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkButton(
            self.tab_records,
            text="Cargar Paciente Seleccionado",
            height=50, fg_color="#27ae60",
            command=self.load_selected
        ).pack(pady=10)

    # ------------------------------------------------------------------
    # LÓGICA
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

    def add_image(self, idx):
        path = filedialog.askopenfilename(
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff")]
        )
        if path:
            filename = (
                f"IMG_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                f"_{idx}_{os.path.basename(path)}"
            )
            dest = os.path.join(MEDIA_FOLDER, filename)
            shutil.copy2(path, dest)
            self.image_paths[idx] = filename
            self.update_thumbnail(idx, dest)

    def remove_image(self, idx):
        self.image_paths[idx] = None
        self._ctk_images[idx] = None
        self.image_labels[idx].configure(text="Vacío", image=None)

    def update_thumbnail(self, idx, path):
        pil_img = Image.open(path)
        ctk_img = ctk.CTkImage(
            light_image=pil_img,
            dark_image=pil_img,
            size=(220, 170)
        )
        self._ctk_images[idx] = ctk_img
        self.image_labels[idx].configure(image=ctk_img, text="")

    def save_patient(self):
        name = self.ent_name.get()
        if not name:
            return messagebox.showerror("Error", "El nombre es obligatorio")
        data = (
            name,
            self.ent_age.get(),
            self.ent_date.get(),
            self.txt_meds.get("1.0", "end-1c"),
            self.txt_notes.get("1.0", "end-1c"),
            json.dumps(self.image_paths),
            self.txt_img_desc.get("1.0", "end-1c")
        )
        with sqlite3.connect(DB_NAME) as conn:
            if self.current_patient_id:
                conn.execute(
                    "UPDATE patients SET name=?, age=?, date=?, meds=?, "
                    "notes=?, images=?, image_desc=? WHERE id=?",
                    (*data, self.current_patient_id)
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO patients (name, age, date, meds, notes, "
                    "images, image_desc) VALUES (?,?,?,?,?,?,?)",
                    data
                )
                self.current_patient_id = cursor.lastrowid
        self.lbl_img_patient.configure(
            text=f"Paciente Actual: {name} ({self.ent_age.get()})"
        )
        messagebox.showinfo("Guardado", "Base de datos actualizada.")
        self.refresh_records_table()

    def load_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
        p_id = self.tree.item(selection[0])['values'][0]
        with sqlite3.connect(DB_NAME) as conn:
            row = conn.execute(
                "SELECT * FROM patients WHERE id=?", (p_id,)
            ).fetchone()
        if row:
            self.clear_form()
            (self.current_patient_id, name, age, date,
             meds, notes, imgs, img_desc) = row
            self.ent_name.insert(0, str(name))
            self.ent_age.insert(0, str(age))
            self.ent_date.delete(0, "end")
            self.ent_date.insert(0, str(date))
            self.txt_meds.insert("1.0",     meds     if meds     else "")
            self.txt_notes.insert("1.0",    notes    if notes    else "")
            self.txt_img_desc.insert("1.0", img_desc if img_desc else "")
            self.lbl_img_patient.configure(
                text=f"Paciente Actual: {name} ({age})"
            )
            loaded = json.loads(imgs)
            self.image_paths = (loaded + [None] * NUM_IMAGES)[:NUM_IMAGES]
            for i, fname in enumerate(self.image_paths):
                if fname:
                    fpath = os.path.join(MEDIA_FOLDER, fname)
                    if os.path.exists(fpath):
                        self.update_thumbnail(i, fpath)
            self.tabs.set("Nuevo Paciente")

    def export_data(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".zip", initialdir=BASE_DIR
        )
        if not path:
            return
        with zipfile.ZipFile(path, 'w') as z:
            if os.path.exists(DB_NAME):
                z.write(DB_NAME, arcname=os.path.basename(DB_NAME))
            for f in os.listdir(MEDIA_FOLDER):
                z.write(
                    os.path.join(MEDIA_FOLDER, f),
                    arcname=os.path.join("patient_media", f)
                )
        messagebox.showinfo("Exportar",
                            "Datos e imágenes exportados correctamente.")

    def import_data(self):
        path = filedialog.askopenfilename(
            filetypes=[("Zip", "*.zip")], initialdir=BASE_DIR
        )
        if path and messagebox.askyesno(
            "Confirmar", "¿Sobreescribir los datos actuales?"
        ):
            with zipfile.ZipFile(path, 'r') as z:
                z.extractall(BASE_DIR)
            self.refresh_records_table()
            messagebox.showinfo("Importar", "Datos importados correctamente.")

    def repair_database(self):
        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute(
                "SELECT id, images FROM patients"
            ).fetchall()
            for r_id, img_json in rows:
                paths = json.loads(img_json)
                fixed = [
                    p if p and os.path.exists(
                        os.path.join(MEDIA_FOLDER, p)
                    ) else None
                    for p in paths
                ]
                conn.execute(
                    "UPDATE patients SET images=? WHERE id=?",
                    (json.dumps(fixed), r_id)
                )
        messagebox.showinfo("Reparar", "Sincronización completa.")

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

    # ------------------------------------------------------------------
    # PDF PESTAÑA 1
    # ------------------------------------------------------------------
    def generate_patient_pdf(self):
        name     = self.ent_name.get()
        meds_txt = self.txt_meds.get("1.0", "end-1c")
        fs       = self.pdf_font_size.get()
        line_h   = fs * 1.4

        filename = os.path.join(BASE_DIR, f"Registro_{name}.pdf")
        c = canvas.Canvas(filename, pagesize=LETTER_PAGE_SIZE)
        w, h = LETTER_PAGE_SIZE

        y         = self._draw_header_p1(c, h)
        max_width = w - NAME_X - MARGIN_RIGHT

        self._draw_wrapped_text(
            c, meds_txt, NAME_X, y,
            max_width, "Helvetica", fs, line_h, h
        )
        c.save()
        os.startfile(filename)

    # ------------------------------------------------------------------
    # PDF PESTAÑA 2 — Estudio de Colposcopia
    # ------------------------------------------------------------------
    def generate_image_pdf(self):
        name     = self.ent_name.get()
        date     = self.ent_date.get()
        desc_txt = self.txt_img_desc.get("1.0", "end-1c")
        fs       = self.pdf_font_size.get()
        line_h   = fs * 1.4

        filename = os.path.join(BASE_DIR, f"Colposcopia_{name}.pdf")
        c = canvas.Canvas(filename, pagesize=LETTER_PAGE_SIZE)
        w, h = LETTER_PAGE_SIZE

        # ── Posiciones fijas según imagen de referencia ───────────────
        x_left  = 3.3 * cm       # margen izquierdo nombre y fecha
        y_name  = h - (7.3 * cm) # nombre a 7.3 cm del borde superior
        y_date  = h - (8.3 * cm) # fecha  a 8.3 cm del borde superior

        # ── 1. Nombre ─────────────────────────────────────────────────
        c.setFont("Helvetica", fs)
        c.drawString(x_left, y_name, name)

        # ── 2. Fecha ──────────────────────────────────────────────────
        c.setFont("Helvetica", fs)
        c.drawString(x_left, y_date, date)

        # ── 3. Observaciones centradas en página, alineadas izquierda ─
        block_width = 10.0 * cm
        x_obs       = (w - block_width) / 2   # bloque centrado en hoja
        y_obs_start = h - (11.0 * cm)         # empieza a 11 cm del borde
        y_grid_top  = h - (14.0 * cm)         # grilla a 14 cm del borde

        if desc_txt.strip():
            self._draw_wrapped_text(
                c, desc_txt,
                x_obs, y_obs_start,
                block_width, "Helvetica", fs, line_h, h
            )

        # ── 4. Grilla 2×2 comienza exactamente a 14 cm del borde ──────
        total_grid_w = COLS * IMG_W
        grid_x       = (w - total_grid_w) / 2  # grilla centrada en hoja
        grid_top     = y_grid_top

        valid = []
        for fname in self.image_paths:
            fpath = os.path.join(MEDIA_FOLDER, fname) if fname else None
            valid.append(
                fpath if fpath and os.path.exists(fpath) else None
            )

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

            # Borde negro sobre cada celda
            c.setFillColorRGB(0, 0, 0)
            c.setStrokeColorRGB(0, 0, 0)
            c.setLineWidth(1.5)
            c.rect(ix, iy, IMG_W, IMG_H, fill=0, stroke=1)
            c.setLineWidth(1)

        c.save()
        os.startfile(filename)

    # ------------------------------------------------------------------
    # LIMPIAR / REFRESCAR
    # ------------------------------------------------------------------
    def clear_form(self):
        self.current_patient_id = None
        self.ent_name.delete(0, "end")
        self.ent_birth_year.delete(0, "end")
        self.ent_age.delete(0, "end")
        self.ent_date.delete(0, "end")
        self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.txt_meds.delete("1.0", "end")
        self.txt_notes.delete("1.0", "end")
        self.txt_img_desc.delete("1.0", "end")
        self.lbl_img_patient.configure(
            text="Paciente Actual: Ninguno Seleccionado"
        )
        self.image_paths = [None] * NUM_IMAGES
        self._ctk_images = [None] * NUM_IMAGES
        for lbl in self.image_labels:
            lbl.configure(text="Vacío", image=None)

    def refresh_records_table(self, event=None):
        for i in self.tree.get_children():
            self.tree.delete(i)
        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute(
                "SELECT id, name, age, date FROM patients WHERE name LIKE ?",
                (f"%{self.ent_search.get()}%",)
            ).fetchall()
            for r in rows:
                self.tree.insert("", "end", values=r)


if __name__ == "__main__":
    root = ctk.CTk()
    app  = MedicalApp(root)
    root.mainloop()