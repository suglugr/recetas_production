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

# --- EXE PATH LOGIC ---
def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR     = get_base_path()
DB_NAME      = os.path.join(BASE_DIR, "medical_data.db")
MEDIA_FOLDER = os.path.join(BASE_DIR, "patient_media")

# --- PDF CONFIG ---
FONT_SIZE        = 10

# Hoja carta: 21.59 x 27.94 cm
LETTER_WIDTH     = 21.59 * cm
LETTER_HEIGHT    = 27.94 * cm
LETTER_PAGE_SIZE = (LETTER_WIDTH, LETTER_HEIGHT)

# Margen superior: 4 cm
TOP_MARGIN = 4 * cm

# Posiciones horizontales de cabecera (desde borde izquierdo)
MARGIN_LEFT  = 1.5  * cm           # margen izquierdo general
NAME_X       = 2.0  * cm           # nombre arranca aquí
AGE_X        = 2.0  * cm + 11.5 * cm   # edad a 10 cm del margen izq
DATE_X       = 2.5  * cm + 11  * cm + 3.5 * cm   # fecha a 13 cm del margen izq
MARGIN_RIGHT = 1.5  * cm           # margen derecho general

# Espacio entre línea de cabecera y cuerpo: 1 cm
HEADER_BODY_GAP = 1 * cm

if not os.path.exists(MEDIA_FOLDER):
    os.makedirs(MEDIA_FOLDER)


class MedicalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Gestión Médica Pro")
        self.root.geometry("1200x900")

        self.current_patient_id = None
        self.image_paths        = [None] * 9
        self._ctk_images        = [None] * 9

        self.init_db()
        self.setup_ui()
        self.refresh_records_table()

    # ── BASE DE DATOS ─────────────────────────────────────────────────────────
    def init_db(self):
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, age TEXT, date TEXT,
                meds TEXT, notes TEXT, images TEXT,
                image_desc TEXT
            )''')

    # ── INTERFAZ ──────────────────────────────────────────────────────────────
    def setup_ui(self):
        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_form    = self.tabs.add("Nuevo Paciente")
        self.tab_images  = self.tabs.add("Imágenes del Paciente")
        self.tab_records = self.tabs.add("Registros de Pacientes")

        self._build_tab_form()
        self._build_tab_images()
        self._build_tab_records()

    def _build_tab_form(self):
        header_frame = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=20)

        self.ent_name = ctk.CTkEntry(header_frame, placeholder_text="Nombre", width=400)
        self.ent_name.pack(side="left", padx=(0, 20))

        self.ent_age = ctk.CTkEntry(header_frame, placeholder_text="Edad", width=100)
        self.ent_age.pack(side="left", padx=(0, 20))

        self.ent_date = ctk.CTkEntry(header_frame, width=150)
        self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.ent_date.pack(side="right")

        ctk.CTkLabel(self.tab_form,
                     text="Medicamentos e Indicaciones").pack(anchor="w", padx=20)
        self.txt_meds = ctk.CTkTextbox(self.tab_form, height=300)
        self.txt_meds.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(self.tab_form,
                     text="Notas Privadas (Solo Uso Interno)").pack(anchor="w", padx=20)
        self.txt_notes = ctk.CTkTextbox(self.tab_form, height=100)
        self.txt_notes.pack(fill="x", padx=20, pady=5)

        btn_row = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        btn_row.pack(pady=20)
        ctk.CTkButton(btn_row, text="Guardar Paciente",
                      fg_color="#27ae60",
                      command=self.save_patient).pack(side="left", padx=10)
        ctk.CTkButton(btn_row, text="Imprimir PDF",
                      fg_color="#2980b9",
                      command=self.generate_patient_pdf).pack(side="left", padx=10)
        ctk.CTkButton(btn_row, text="Limpiar Formulario",
                      fg_color="#c0392b",
                      command=self.clear_form).pack(side="left", padx=10)

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

        self.img_grid = ctk.CTkFrame(self.tab_images)
        self.img_grid.pack(pady=5, padx=20, fill="both", expand=True)

        self.image_labels = []
        for i in range(9):
            r, c = divmod(i, 3)
            slot = ctk.CTkFrame(self.img_grid, border_width=1, border_color="#555")
            slot.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")

            lbl = ctk.CTkLabel(slot, text=f"Vacío ({r+1},{c+1})", image=None)
            lbl.pack(expand=True, pady=5)
            self.image_labels.append(lbl)

            b_frame = ctk.CTkFrame(slot, fg_color="transparent")
            b_frame.pack(side="bottom", fill="x")
            ctk.CTkButton(b_frame, text="Agregar", width=55,
                          command=lambda idx=i: self.add_image(idx)).pack(
                              side="left", padx=2, pady=2)
            ctk.CTkButton(b_frame, text="Eliminar", width=55,
                          fg_color="#c0392b",
                          command=lambda idx=i: self.remove_image(idx)).pack(
                              side="right", padx=2, pady=2)

        self.img_grid.grid_columnconfigure((0, 1, 2), weight=1)
        self.img_grid.grid_rowconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(self.tab_images,
                     text="Análisis de Imagen / Observaciones").pack(
                         anchor="w", padx=20)
        self.txt_img_desc = ctk.CTkTextbox(self.tab_images, height=100)
        self.txt_img_desc.pack(fill="x", padx=20, pady=5)

        ctk.CTkButton(
            self.tab_images, text="Imprimir PDF de Imágenes",
            fg_color="#2980b9", command=self.generate_image_pdf
        ).pack(pady=10)

    def _build_tab_records(self):
        top_bar = ctk.CTkFrame(self.tab_records)
        top_bar.pack(fill="x", padx=10, pady=10)

        self.ent_search = ctk.CTkEntry(
            top_bar, placeholder_text="Buscar por nombre...", width=300)
        self.ent_search.pack(side="left", padx=10)
        self.ent_search.bind("<KeyRelease>", self.refresh_records_table)

        ctk.CTkButton(top_bar, text="Exportar Datos",
                      fg_color="#8e44ad",
                      command=self.export_data).pack(side="right", padx=5)
        ctk.CTkButton(top_bar, text="Importar Datos",
                      fg_color="#d35400",
                      command=self.import_data).pack(side="right", padx=5)
        ctk.CTkButton(top_bar, text="Reparar BD",
                      fg_color="#e67e22",
                      command=self.repair_database).pack(side="right", padx=5)

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

    # ── IMÁGENES ──────────────────────────────────────────────────────────────
    def add_image(self, idx):
        path = filedialog.askopenfilename(
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff")]
        )
        if path:
            filename = (f"IMG_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        f"_{idx}_{os.path.basename(path)}")
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
            size=(110, 110)
        )
        self._ctk_images[idx] = ctk_img
        self.image_labels[idx].configure(image=ctk_img, text="")

    # ── GUARDAR / CARGAR ──────────────────────────────────────────────────────
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
            self.current_patient_id, name, age, date, \
                meds, notes, imgs, img_desc = row
            self.ent_name.insert(0, str(name))
            self.ent_age.insert(0, str(age))
            self.ent_date.delete(0, "end")
            self.ent_date.insert(0, str(date))
            self.txt_meds.insert("1.0",     meds     if meds     else "")
            self.txt_notes.insert("1.0",    notes    if notes    else "")
            self.txt_img_desc.insert("1.0", img_desc if img_desc else "")
            self.lbl_img_patient.configure(
                text=f"Paciente Actual: {name} ({age})")
            self.image_paths = json.loads(imgs)
            for i, fname in enumerate(self.image_paths):
                if fname:
                    fpath = os.path.join(MEDIA_FOLDER, fname)
                    if os.path.exists(fpath):
                        self.update_thumbnail(i, fpath)
            self.tabs.set("Nuevo Paciente")

    # ── EXPORTAR / IMPORTAR / REPARAR ─────────────────────────────────────────
    def export_data(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".zip", initialdir=BASE_DIR)
        if not path:
            return
        with zipfile.ZipFile(path, 'w') as z:
            if os.path.exists(DB_NAME):
                z.write(DB_NAME, arcname=os.path.basename(DB_NAME))
            for f in os.listdir(MEDIA_FOLDER):
                z.write(os.path.join(MEDIA_FOLDER, f),
                        arcname=os.path.join("patient_media", f))
        messagebox.showinfo("Exportar",
                            "Datos e imágenes exportados correctamente.")

    def import_data(self):
        path = filedialog.askopenfilename(
            filetypes=[("Zip", "*.zip")], initialdir=BASE_DIR)
        if path and messagebox.askyesno("Confirmar",
                                        "¿Sobreescribir los datos actuales?"):
            with zipfile.ZipFile(path, 'r') as z:
                z.extractall(BASE_DIR)
            self.refresh_records_table()
            messagebox.showinfo("Importar", "Datos importados correctamente.")

    def repair_database(self):
        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute(
                "SELECT id, images FROM patients").fetchall()
            for r_id, img_json in rows:
                paths = json.loads(img_json)
                fixed = [
                    p if p and os.path.exists(
                        os.path.join(MEDIA_FOLDER, p)) else None
                    for p in paths
                ]
                conn.execute("UPDATE patients SET images=? WHERE id=?",
                             (json.dumps(fixed), r_id))
        messagebox.showinfo("Reparar", "Sincronización completa.")

    # ── CABECERA COMÚN ────────────────────────────────────────────────────────
    def _draw_header(self, c, h):
        """
        Cabecera con medidas corregidas:
          - Margen superior : 4 cm
          - Nombre  → NAME_X = 2.0 cm
          - Edad    → AGE_X  = 2.0 + 11.5 = 13.5 cm
          - Fecha   → DATE_X = 2.5 + 10 + 3 = 15.5 cm
          - Gap cabecera → cuerpo: 1 cm exacto
        """
        y = h - TOP_MARGIN              # Y de la línea de cabecera

        c.setFont("Helvetica", FONT_SIZE)

        # Nombre
        c.drawString(NAME_X, y, self.ent_name.get())

        # Edad
        if self.ent_age.get():
            c.drawString(AGE_X, y, self.ent_age.get())

        # Fecha
        if self.ent_date.get():
            c.drawString(DATE_X, y, self.ent_date.get())

        # 1 cm de espacio después de la cabecera antes del cuerpo
        return y - HEADER_BODY_GAP

    # ── PDF PESTAÑA 1: Medicamentos ───────────────────────────────────────────
    def generate_patient_pdf(self):
        name     = self.ent_name.get()
        meds_txt = self.txt_meds.get("1.0", "end-1c")

        filename = os.path.join(BASE_DIR, f"Registro_{name}.pdf")
        c = canvas.Canvas(filename, pagesize=LETTER_PAGE_SIZE)
        w, h = LETTER_PAGE_SIZE

        # Cabecera + 1 cm de gap
        y = self._draw_header(c, h)

        # Cuerpo: medicamentos / indicaciones
        c.setFont("Helvetica", FONT_SIZE)
        for line in meds_txt.split('\n'):
            if y < 1 * cm:
                c.showPage()
                c.setFont("Helvetica", FONT_SIZE)
                y = h - TOP_MARGIN - HEADER_BODY_GAP
            c.drawString(NAME_X, y, line)
            y -= 15

        c.save()
        os.startfile(filename)

    # ── PDF PESTAÑA 2: Imágenes ───────────────────────────────────────────────
    def generate_image_pdf(self):
        name     = self.ent_name.get()
        desc_txt = self.txt_img_desc.get("1.0", "end-1c")

        filename = os.path.join(BASE_DIR, f"Analisis_{name}.pdf")
        c = canvas.Canvas(filename, pagesize=LETTER_PAGE_SIZE)
        w, h = LETTER_PAGE_SIZE

        # Cabecera + 1 cm de gap
        y = self._draw_header(c, h)

        # Título "Estudios" centrado en negrita
        c.setFont("Helvetica-Bold", FONT_SIZE + 2)
        c.drawCentredString(w / 2, y, "Estudios")
        y -= 20

        # Texto de observaciones
        c.setFont("Helvetica", FONT_SIZE)
        for line in desc_txt.split('\n'):
            if y < 1 * cm:
                c.showPage()
                c.setFont("Helvetica", FONT_SIZE)
                y = h - TOP_MARGIN - HEADER_BODY_GAP
            c.drawString(NAME_X, y, line)
            y -= 15

        # Grilla de imágenes
        usable_w = w - NAME_X - MARGIN_RIGHT
        h_gap    = 0.4 * cm
        v_gap    = 0.4 * cm
        img_w    = (usable_w - 2 * h_gap) / 3
        img_h    = img_w * 0.75
        y_grid   = y - 0.5 * cm

        for i, fname in enumerate(self.image_paths):
            if fname:
                fpath = os.path.join(MEDIA_FOLDER, fname)
                if os.path.exists(fpath):
                    row, col = divmod(i, 3)
                    ix = NAME_X + col * (img_w + h_gap)
                    iy = y_grid - img_h - row * (img_h + v_gap)

                    if iy < 1 * cm:
                        c.showPage()
                        y_grid = h - TOP_MARGIN - HEADER_BODY_GAP
                        iy     = y_grid - img_h

                    c.drawImage(fpath, ix, iy,
                                width=img_w, height=img_h,
                                preserveAspectRatio=True)

        c.save()
        os.startfile(filename)

    # ── LIMPIAR / REFRESCAR ───────────────────────────────────────────────────
    def clear_form(self):
        self.current_patient_id = None
        self.ent_name.delete(0, "end")
        self.ent_age.delete(0, "end")
        self.txt_meds.delete("1.0", "end")
        self.txt_notes.delete("1.0", "end")
        self.txt_img_desc.delete("1.0", "end")
        self.lbl_img_patient.configure(
            text="Paciente Actual: Ninguno Seleccionado")
        self.image_paths = [None] * 9
        self._ctk_images = [None] * 9
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