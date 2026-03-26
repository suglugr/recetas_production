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
import subprocess

# --- Configuracion de Rutas y PDF ---
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

# Margenes PDF
EXTRA_TEXT_X     = 1.0 * cm   
EXTRA_TEXT_W     = 2.5 * cm   
MEDS_X           = 4.0 * cm   
TOP_MARGIN       = 3.65 * cm
NAME_X           = 3.3 * cm
AGE_X            = 13.5 * cm
DATE_X           = 17.7 * cm

if not os.path.exists(MEDIA_FOLDER):
    os.makedirs(MEDIA_FOLDER)

class RecetasApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Recetas Medicas")
        self.root.geometry("1200x950")

        self.current_patient_id  = None
        self.current_receta_id   = None
        
        # Variables de configuracion restauradas
        self.show_labels_var     = ctk.BooleanVar(value=False)
        self.pdf_font_size       = ctk.IntVar(value=11)
        
        self._recetas_cache      = []

        self.init_db()
        self.setup_ui()
        self.refresh_records_table()
        self.root.after(100, lambda: self.root.state('zoomed'))

    def init_db(self):
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, age TEXT, date TEXT,
                meds TEXT, notes TEXT, images TEXT, image_desc TEXT, extra_pdf_text TEXT)''')
            conn.execute('''CREATE TABLE IF NOT EXISTS recetas (
                id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, fecha TEXT,
                meds TEXT, notes TEXT, extra_pdf_text TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id))''')
            
            # Asegurar columnas necesarias
            for table in ["recetas", "patients"]:
                cursor = conn.execute(f"PRAGMA table_info({table})")
                cols = [info[1] for info in cursor.fetchall()]
                if "extra_pdf_text" not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN extra_pdf_text TEXT")

    def setup_ui(self):
        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_form    = self.tabs.add("Nueva Receta")
        self.tab_records = self.tabs.add("Registros de Pacientes")
        self._build_tab_form()
        self._build_tab_records()
        

    def _build_tab_form(self):
        # 1. Datos Paciente
        header = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(10, 5))

        ctk.CTkLabel(header, text="Nombre del Paciente", font=("Helvetica", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.ent_name = ctk.CTkEntry(header, width=400); self.ent_name.grid(row=1, column=0, pady=2, sticky="w")

        data_row = ctk.CTkFrame(header, fg_color="transparent")
        data_row.grid(row=2, column=0, sticky="w", pady=5)

        ctk.CTkLabel(data_row, text="Ano Nacimiento", font=("Helvetica", 11)).pack(side="left")
        self.ent_birth_year = ctk.CTkEntry(data_row, width=70); self.ent_birth_year.pack(side="left", padx=5)
        self.ent_birth_year.bind("<KeyRelease>", self._auto_calc_age)

        ctk.CTkLabel(data_row, text="Edad", font=("Helvetica", 11)).pack(side="left", padx=(15, 5))
        self.ent_age = ctk.CTkEntry(data_row, width=50); self.ent_age.pack(side="left")

        ctk.CTkLabel(data_row, text="Fecha", font=("Helvetica", 11)).pack(side="left", padx=(15, 5))
        self.ent_date = ctk.CTkEntry(data_row, width=110); self.ent_date.pack(side="left")
        self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))

        # 2. Botones Superiores y Configuracion PDF
        top_bar = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(top_bar, text="IMPRIMIR Y GUARDAR", fg_color="#2980b9", width=180, height=40, font=("Helvetica", 12, "bold"),
                      command=self.print_and_save_action).pack(side="left", padx=(0, 10))
        ctk.CTkButton(top_bar, text="LIMPIAR", fg_color="#c0392b", width=100, height=40, command=self.clear_form).pack(side="left", padx=(0, 20))

        # Restauracion de Controles: Etiquetas y Fuente
        config_f = ctk.CTkFrame(top_bar, fg_color="#2b2b2b", corner_radius=8)
        config_f.pack(side="left", fill="y", padx=10)
        
        ctk.CTkSwitch(config_f, text="Mostrar Etiquetas", variable=self.show_labels_var, font=("Helvetica", 11)).pack(side="left", padx=15)
        ctk.CTkLabel(config_f, text="Fuente:", font=("Helvetica", 11)).pack(side="left", padx=(10, 5))
        ctk.CTkOptionMenu(config_f, values=["9", "10", "11", "12", "14"], variable=self.pdf_font_size, width=70).pack(side="left", padx=10)

        # 3. Texto Extra (Columna Izquierda)
        ctk.CTkLabel(self.tab_form, text="Informacion Adicional (Peso, TA, etc. - Izquierda PDF)", font=("Helvetica", 11, "bold"), text_color="#3498db").pack(anchor="w", padx=25)
        self.txt_extra_pdf = ctk.CTkTextbox(self.tab_form, height=70)
        self.txt_extra_pdf.pack(fill="x", padx=20, pady=(2, 10))

        # 4. Historial
        hist_f = ctk.CTkFrame(self.tab_form, fg_color="#333333")
        hist_f.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(hist_f, text="Recetas anteriores:", font=("Helvetica", 11, "bold")).pack(side="left", padx=10)
        self.receta_selector = ctk.CTkOptionMenu(hist_f, values=["-- Sin recetas --"], width=200, command=self._on_receta_selected)
        self.receta_selector.pack(side="left", pady=5)
        ctk.CTkButton(hist_f, text="+ Nueva", fg_color="#27ae60", width=80, command=self.nueva_receta).pack(side="left", padx=10)
        ctk.CTkButton(hist_f, text="Borrar", fg_color="#e74c3c", width=80, command=self.eliminar_receta).pack(side="left")

        # 5. Columnas Principales (Scroll habilitado por defecto en CTkTextbox)
        cols = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        cols.pack(fill="both", expand=True, padx=20, pady=10)
        cols.grid_columnconfigure(0, weight=2)
        cols.grid_columnconfigure(1, weight=1)
        cols.grid_rowconfigure(0, weight=1)

        f1 = ctk.CTkFrame(cols, fg_color="transparent")
        f1.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ctk.CTkLabel(f1, text="Medicamentos e Indicaciones", font=("Helvetica", 12, "bold")).pack(anchor="w")
        self.txt_meds = ctk.CTkTextbox(f1, font=("Helvetica", 13))
        self.txt_meds.pack(fill="both", expand=True, pady=2)

        f2 = ctk.CTkFrame(cols, fg_color="transparent")
        f2.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(f2, text="Notas Internas", font=("Helvetica", 12, "bold")).pack(anchor="w")
        self.txt_notes = ctk.CTkTextbox(f2, font=("Helvetica", 13))
        self.txt_notes.pack(fill="both", expand=True, pady=2)

    def _build_tab_records(self):
        top = ctk.CTkFrame(self.tab_records)
        top.pack(fill="x", padx=10, pady=10)
        self.ent_search = ctk.CTkEntry(top, placeholder_text="Buscar paciente...", width=300)
        self.ent_search.pack(side="left", padx=10)
        self.ent_search.bind("<KeyRelease>", self.refresh_records_table)

        self.tree = ttk.Treeview(self.tab_records, columns=("ID", "Nombre", "Edad", "Fecha", "Recetas", "Estudio"), show="headings")
        self.tree.heading("ID", text="ID"); self.tree.heading("Nombre", text="Nombre")
        self.tree.heading("Edad", text="Edad"); self.tree.heading("Fecha", text="Fecha")
        self.tree.heading("Recetas", text="Recetas"); self.tree.heading("Estudio", text="Estudio")
        self.tree.column("ID", width=50); self.tree.column("Nombre", width=300)
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

        ctk.CTkButton(self.tab_records, text="Cargar Paciente Seleccionado", height=40, fg_color="#27ae60", command=self.load_selected).pack(pady=10)

    # --- Logica de PDF y Datos ---
    def print_and_save_action(self):
        if not self.ent_name.get():
            return messagebox.showerror("Error", "Ingrese nombre")
        self._save_patient_logic()
        self.generate_pdf()

    def generate_pdf(self):
        name = self.ent_name.get()
        meds = self.txt_meds.get("1.0", "end-1c")
        extra = self.txt_extra_pdf.get("1.0", "end-1c")
        fs = self.pdf_font_size.get()
        show_lbl = self.show_labels_var.get()
        
        filename = os.path.join(BASE_DIR, f"Receta_{name.replace(' ','_')}.pdf")
        c = canvas.Canvas(filename, pagesize=LETTER_PAGE_SIZE)
        
        y = LETTER_HEIGHT - TOP_MARGIN
        c.setFont("Helvetica", fs)
        
        # Cabecera con o sin etiquetas
        n_txt = f"Nombre: {name}" if show_lbl else name
        e_txt = f"Edad: {self.ent_age.get()}" if show_lbl else self.ent_age.get()
        f_txt = f"Fecha: {self.ent_date.get()}" if show_lbl else self.ent_date.get()
        
        c.drawString(NAME_X, y, n_txt)
        c.drawString(AGE_X, y, e_txt)
        c.drawString(DATE_X, y, f_txt)

        y -= 1.5 * cm
        line_h = fs * 1.4
        
        # Columna Izquierda (Extra) y Derecha (Meds)
        self._draw_wrapped_text(c, extra, EXTRA_TEXT_X, y, EXTRA_TEXT_W, fs, line_h)
        self._draw_wrapped_text(c, meds, MEDS_X, y, LETTER_WIDTH - MEDS_X - 1.5*cm, fs, line_h)
        
        c.save()
        os.startfile(filename)

    def _draw_wrapped_text(self, c, text, x, cur_y, max_w, size, leading):
        c.setFont("Helvetica", size)
        for line in text.split('\n'):
            words = line.split(' ')
            line_str = ""
            for w in words:
                if stringWidth(line_str + " " + w, "Helvetica", size) <= max_w:
                    line_str = (line_str + " " + w).strip()
                else:
                    c.drawString(x, cur_y, line_str)
                    cur_y -= leading
                    line_str = w
            c.drawString(x, cur_y, line_str)
            cur_y -= leading

    def _save_patient_logic(self):
        name = self.ent_name.get(); age = self.ent_age.get(); date = self.ent_date.get()
        m = self.txt_meds.get("1.0", "end-1c"); n = self.txt_notes.get("1.0", "end-1c")
        ex = self.txt_extra_pdf.get("1.0", "end-1c")
        
        with sqlite3.connect(DB_NAME) as conn:
            if not self.current_patient_id:
                cursor = conn.execute("INSERT INTO patients (name, age, date, images) VALUES (?,?,?,?)", (name, age, date, "[]"))
                self.current_patient_id = cursor.lastrowid
            else:
                conn.execute("UPDATE patients SET name=?, age=?, date=? WHERE id=?", (name, age, date, self.current_patient_id))

            if self.current_receta_id:
                conn.execute("UPDATE recetas SET fecha=?, meds=?, notes=?, extra_pdf_text=? WHERE id=?", (date, m, n, ex, self.current_receta_id))
            else:
                cursor = conn.execute("INSERT INTO recetas (patient_id, fecha, meds, notes, extra_pdf_text) VALUES (?,?,?,?,?)",
                                      (self.current_patient_id, date, m, n, ex))
                self.current_receta_id = cursor.lastrowid
        self._refresh_receta_selector(self.current_patient_id, self.current_receta_id)
        self.refresh_records_table()

    # --- Helpers ---
    def refresh_records_table(self, e=None):
        for i in self.tree.get_children(): self.tree.delete(i)
        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute("SELECT id, name, age, date, images FROM patients WHERE name LIKE ?", (f"%{self.ent_search.get()}%",)).fetchall()
            for r in rows:
                n_rec = conn.execute("SELECT COUNT(*) FROM recetas WHERE patient_id=?", (r[0],)).fetchone()[0]
                img_c = len(json.loads(r[4])) if r[4] else 0
                self.tree.insert("", "end", values=(r[0], r[1], r[2], r[3], n_rec, f"{img_c} img"))

    def load_selected(self):
        sel = self.tree.selection()
        if not sel: return
        p_id = self.tree.item(sel[0])['values'][0]
        with sqlite3.connect(DB_NAME) as conn:
            p = conn.execute("SELECT * FROM patients WHERE id=?", (p_id,)).fetchone()
        if p:
            self.clear_form()
            self.current_patient_id = p[0]
            self.ent_name.insert(0, p[1]); self.ent_age.insert(0, p[2])
            self._refresh_receta_selector(p_id)
            self.tabs.set("Nueva Receta")

    def _refresh_receta_selector(self, pid, select_id=None):
        with sqlite3.connect(DB_NAME) as conn:
            recetas = conn.execute("SELECT id, fecha, meds, notes, extra_pdf_text FROM recetas WHERE patient_id=? ORDER BY id DESC", (pid,)).fetchall()
        self._recetas_cache = recetas
        vals = [r[1] for r in recetas] if recetas else ["-- Sin recetas --"]
        self.receta_selector.configure(values=vals)
        if recetas:
            idx = 0
            if select_id:
                for i, r in enumerate(recetas):
                    if r[0] == select_id: idx = i; break
            self.receta_selector.set(recetas[idx][1])
            self._on_receta_selected(recetas[idx][1])

    def _on_receta_selected(self, val):
        for r in self._recetas_cache:
            if r[1] == val:
                self.current_receta_id = r[0]
                self.txt_meds.delete("1.0", "end"); self.txt_meds.insert("1.0", r[2] or "")
                self.txt_notes.delete("1.0", "end"); self.txt_notes.insert("1.0", r[3] or "")
                self.txt_extra_pdf.delete("1.0", "end"); self.txt_extra_pdf.insert("1.0", r[4] or "")
                break

    def nueva_receta(self):
        if not self.current_patient_id: return
        self.current_receta_id = None
        self.txt_meds.delete("1.0", "end"); self.txt_notes.delete("1.0", "end"); self.txt_extra_pdf.delete("1.0", "end")
        self.ent_date.delete(0, "end"); self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))

    def eliminar_receta(self):
        if not self.current_receta_id: return
        if messagebox.askyesno("Confirmar", "Borrar receta?"):
            with sqlite3.connect(DB_NAME) as conn: conn.execute("DELETE FROM recetas WHERE id=?", (self.current_receta_id,))
            self.clear_form(); self.refresh_records_table()

    def _auto_calc_age(self, e=None):
        b = self.ent_birth_year.get()
        if len(b) == 4 and b.isdigit():
            self.ent_age.delete(0, "end"); self.ent_age.insert(0, str(datetime.now().year - int(b)))

    def clear_form(self):
        self.current_patient_id = self.current_receta_id = None
        for e in [self.ent_name, self.ent_birth_year, self.ent_age]: e.delete(0, "end")
        self.txt_meds.delete("1.0", "end"); self.txt_notes.delete("1.0", "end"); self.txt_extra_pdf.delete("1.0", "end")
        self.receta_selector.configure(values=["-- Sin recetas --"]); self.receta_selector.set("-- Sin recetas --")

if __name__ == "__main__":
    root = ctk.CTk()
    app = RecetasApp(root)
    root.mainloop()