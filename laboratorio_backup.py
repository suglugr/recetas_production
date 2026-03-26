import customtkinter as ctk
from tkinter import messagebox, filedialog, ttk
import sqlite3
import os
import json
import sys
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
HEADER_IMG   = os.path.join(BASE_DIR, "header.png")

LETTER_WIDTH, LETTER_HEIGHT = 21.59 * cm, 27.94 * cm
NAME_X, AGE_X, DATE_X, TEXT_X = 3.3 * cm, 14.5 * cm, 17.7 * cm, 3.3 * cm

TEXTO_PRECARGADO = "- Biometría Hemática Completa\n- Química Sanguínea de 6 elementos\n- Examen General de Orina"

class LaboratorioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Solicitud de Laboratorio")
        self.root.geometry("1100x850")
        self.current_patient_id = None
        self._lab_cache = []
        self.init_db()
        self.setup_ui()
        self.refresh_records_table()

    def init_db(self):
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS laboratorio (
                id INTEGER PRIMARY KEY AUTOINCREMENT, patient_id INTEGER, 
                fecha TEXT, estudios TEXT, notas_internas TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id))''')

    def setup_ui(self):
        self.tabs = ctk.CTkTabview(self.root)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_form = self.tabs.add("Nueva Solicitud")
        self.tab_records = self.tabs.add("Registros de Pacientes")
        
        # Formulario
        header = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=10)
        self.ent_name = ctk.CTkEntry(header, width=400, placeholder_text="Nombre del Paciente")
        self.ent_name.grid(row=0, column=0, padx=5)
        self.ent_age = ctk.CTkEntry(header, width=80, placeholder_text="Edad")
        self.ent_age.grid(row=0, column=1, padx=5)
        self.ent_date = ctk.CTkEntry(header, width=120)
        self.ent_date.grid(row=0, column=2, padx=5)
        self.ent_date.insert(0, datetime.now().strftime("%d/%m/%Y"))

        # Config PDF
        config = ctk.CTkFrame(self.tab_form)
        config.pack(fill="x", padx=20, pady=5)
        self.opt_font = ctk.CTkOptionMenu(config, values=["Helvetica", "Times-Roman", "Courier"], width=120)
        self.opt_font.pack(side="left", padx=10)
        self.opt_size = ctk.CTkOptionMenu(config, values=["10", "12", "14"], width=70)
        self.opt_size.set("12"); self.opt_size.pack(side="left")
        self.check_labels = ctk.CTkCheckBox(config, text="Imprimir Etiquetas"); self.check_labels.pack(side="left", padx=10); self.check_labels.select()

        # Botones
        btns = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(btns, text="GUARDAR E IMPRIMIR", fg_color="#16a085", command=self.save_and_print).pack(side="left", padx=5)
        ctk.CTkButton(btns, text="NUEVA", fg_color="#7f8c8d", command=self.new_request).pack(side="left", padx=5)
        
        self.lab_selector = ctk.CTkOptionMenu(self.tab_form, values=["-- Historial --"], command=self._on_lab_selected)
        self.lab_selector.pack(fill="x", padx=20, pady=5)

        # Textos
        txt_f = ctk.CTkFrame(self.tab_form, fg_color="transparent")
        txt_f.pack(fill="both", expand=True, padx=20, pady=5)
        self.txt_estudios = ctk.CTkTextbox(txt_f); self.txt_estudios.pack(side="left", fill="both", expand=True, padx=5)
        self.txt_estudios.insert("1.0", TEXTO_PRECARGADO)
        self.txt_notes = ctk.CTkTextbox(txt_f, fg_color="#1a1a1a"); self.txt_notes.pack(side="right", fill="both", expand=True, padx=5)

        # Tabla Registros
        self.tree = ttk.Treeview(self.tab_records, columns=("ID", "Nombre", "Edad", "Fecha", "Imágenes", "Recetas"), show="headings")
        for c in ("ID", "Nombre", "Edad", "Fecha", "Imágenes", "Recetas"): self.tree.heading(c, text=c)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkButton(self.tab_records, text="Cargar Paciente", command=self.load_selected).pack(pady=5)

    def refresh_records_table(self, e=None):
        for i in self.tree.get_children(): self.tree.delete(i)
        with sqlite3.connect(DB_NAME) as conn:
            rows = conn.execute("SELECT id, name, age, date, images FROM patients").fetchall()
            for r in rows:
                p_id, name, age, date, imgs = r
                n_imgs = len(json.loads(imgs)) if imgs else 0
                n_recs = conn.execute("SELECT COUNT(*) FROM recetas WHERE patient_id=?", (p_id,)).fetchone()[0]
                self.tree.insert("", "end", values=(p_id, name, age, date, n_imgs, n_recs))

    def load_selected(self):
        sel = self.tree.selection()
        if not sel: return
        p_id = self.tree.item(sel[0])['values'][0]
        with sqlite3.connect(DB_NAME) as conn:
            p = conn.execute("SELECT * FROM patients WHERE id=?", (p_id,)).fetchone()
        self.new_request()
        self.current_patient_id = p[0]
        self.ent_name.insert(0, p[1]); self.ent_age.insert(0, p[2])
        self._refresh_lab_selector(p_id); self.tabs.set("Nueva Solicitud")

    def save_and_print(self):
        name = self.ent_name.get()
        if not name: return
        with sqlite3.connect(DB_NAME) as conn:
            if not self.current_patient_id:
                self.current_patient_id = conn.execute("INSERT INTO patients (name, age, date) VALUES (?,?,?)", (name, self.ent_age.get(), self.ent_date.get())).lastrowid
            conn.execute("INSERT INTO laboratorio (patient_id, fecha, estudios, notas_internas) VALUES (?,?,?,?)", (self.current_patient_id, self.ent_date.get(), self.txt_estudios.get("1.0", "end-1c"), self.txt_notes.get("1.0", "end-1c")))
        self.generate_pdf(name, self.ent_age.get(), self.ent_date.get(), self.txt_estudios.get("1.0", "end-1c"))
        self.refresh_records_table()

    def generate_pdf(self, name, age, date, estudios):
        fn = os.path.join(BASE_DIR, f"Lab_{name}.pdf")
        c = canvas.Canvas(fn, pagesize=(LETTER_WIDTH, LETTER_HEIGHT))
        if os.path.exists(HEADER_IMG): c.drawImage(HEADER_IMG, (LETTER_WIDTH-17*cm)/2, LETTER_HEIGHT-2.8*cm, width=17*cm, height=2.5*cm, preserveAspectRatio=True)
        c.setFont(f"{self.opt_font.get()}-Bold", 14)
        c.drawCentredString(LETTER_WIDTH/2, LETTER_HEIGHT-4.2*cm, "SOLICITUD DE LABORATORIO")
        c.setFont(self.opt_font.get(), 11)
        lbl = self.check_labels.get()
        c.drawString(NAME_X, LETTER_HEIGHT-5.5*cm, f"PACIENTE: {name}" if lbl else name)
        c.drawString(AGE_X, LETTER_HEIGHT-5.5*cm, f"EDAD: {age}" if lbl else age)
        c.drawString(DATE_X, LETTER_HEIGHT-5.5*cm, f"FECHA: {date}" if lbl else date)
        t = c.beginText(TEXT_X, LETTER_HEIGHT-7*cm)
        t.setFont(self.opt_font.get(), int(self.opt_size.get()))
        for l in estudios.split('\n'): t.textLine(l)
        c.drawText(t); c.save(); os.startfile(fn)

    def _refresh_lab_selector(self, pid):
        with sqlite3.connect(DB_NAME) as conn:
            regs = conn.execute("SELECT fecha, estudios FROM laboratorio WHERE patient_id=? ORDER BY id DESC", (pid,)).fetchall()
        self._lab_cache = regs
        self.lab_selector.configure(values=[r[0] for r in regs] if regs else ["-- Vacío --"])

    def _on_lab_selected(self, val):
        for r in self._lab_cache:
            if r[0] == val:
                self.txt_estudios.delete("1.0", "end"); self.txt_estudios.insert("1.0", r[1]); break

    def new_request(self):
        self.current_patient_id = None
        self.ent_name.delete(0, "end"); self.txt_estudios.delete("1.0", "end"); self.txt_estudios.insert("1.0", TEXTO_PRECARGADO)

if __name__ == "__main__":
    root = ctk.CTk()
    app = LaboratorioApp(root)
    if len(sys.argv) > 1:
        app.ent_name.insert(0, sys.argv[1])
    root.mainloop()