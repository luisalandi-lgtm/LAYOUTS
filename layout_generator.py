"""OneView Layout Generator - interfaccia grafica."""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import layout_engine as E

POSITIONS = ["Grande a destra", "In alto a sinistra", "Sotto a sinistra", "Ancora sotto (4ª)"]
KIND_COLORS = {E.KIND_SCOPIA: "#4a78c2", E.KIND_DEVICE: "#3f9a6b", E.KIND_CAMERA: "#c98a2e"}
NONE = "—"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OneView Layout Generator")
        self.geometry("1180x720")
        self.minsize(1000, 620)
        self.lib = E.load_library()
        self.project = E.Project()
        self.cur_view = None
        self._loading = False

        self._build_header()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._build_areas_tab()
        self._build_views_tab()
        self._build_library_tab()
        self._build_output_tab()
        self.nb.bind("<<NotebookTabChanged>>", lambda e: self._on_tab())
        self._load_project_into_ui()

    # ------------------------------------------------------------ header
    def _build_header(self):
        f = ttk.Frame(self, padding=8)
        f.pack(fill="x")
        self.v_name = tk.StringVar(value=self.project.name)
        self.v_audio = tk.StringVar(value=self.project.audio)
        self.v_parse = tk.StringVar(value=self.project.parse_mode)
        ttk.Label(f, text="Nome layout:").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.v_name, width=28).grid(row=0, column=1, padx=4)
        ttk.Label(f, text="AudioSourceName:").grid(row=0, column=2, sticky="w")
        ttk.Entry(f, textvariable=self.v_audio, width=22).grid(row=0, column=3, padx=4)
        ttk.Label(f, text="ParseMode:").grid(row=0, column=4, sticky="w")
        ttk.Entry(f, textvariable=self.v_parse, width=24).grid(row=0, column=5, padx=4)
        bf = ttk.Frame(f)
        bf.grid(row=0, column=6, sticky="e", padx=(12, 0))
        f.columnconfigure(6, weight=1)
        ttk.Button(bf, text="Nuovo", command=self.new_project).pack(side="left", padx=2)
        ttk.Button(bf, text="Apri .ini esistente…", command=self.import_ini).pack(side="left", padx=2)
        ttk.Button(bf, text="Salva .ini…", command=self.save_ini).pack(side="left", padx=2)

    def _sync_header(self):
        self.project.name = self.v_name.get().strip()
        self.project.audio = self.v_audio.get().strip()
        self.project.parse_mode = self.v_parse.get().strip()

    # ------------------------------------------------------------ tab 1: aree
    def _build_areas_tab(self):
        t = ttk.Frame(self.nb, padding=12)
        self.nb.add(t, text="1. Aree (collegamenti)")
        ttk.Label(t, text="Per ogni area indica il dispositivo collegato e lo slot della scheda di acquisizione. "
                          "Lascia vuoto il dispositivo per le aree non usate.",
                  foreground="#555").grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 10))
        heads = ["Area", "Dispositivo", "Risoluzione", "Sorgente (slot)", "Commento", "Etichetta nelle viste"]
        for c, h in enumerate(heads):
            ttk.Label(t, text=h, font=("Segoe UI", 9, "bold")).grid(row=1, column=c, sticky="w", padx=4)
        self.area_rows = []
        for i in range(5):
            r = i + 2
            ttk.Label(t, text=f"Area{i + 1}").grid(row=r, column=0, sticky="w", padx=4, pady=3)
            dev = tk.StringVar()
            res = tk.StringVar()
            src = tk.StringVar()
            com = tk.StringVar()
            lab = tk.StringVar()
            cb = ttk.Combobox(t, textvariable=dev, state="readonly", width=22)
            cb.grid(row=r, column=1, padx=4)
            ttk.Label(t, textvariable=res, width=11).grid(row=r, column=2, padx=4)
            ttk.Entry(t, textvariable=src, width=30).grid(row=r, column=3, padx=4)
            ttk.Entry(t, textvariable=com, width=24).grid(row=r, column=4, padx=4)
            ttk.Entry(t, textvariable=lab, width=14).grid(row=r, column=5, padx=4)
            row = dict(dev=dev, res=res, src=src, com=com, lab=lab, cb=cb)
            cb.bind("<<ComboboxSelected>>", lambda e, idx=i: self._on_area_device(idx))
            for v in (src, com, lab):
                v.trace_add("write", lambda *a: self._areas_to_project())
            self.area_rows.append(row)
        ttk.Label(t, text="Esempi di sorgente: HD Video 1, SLOTDEV_06BC USBMI_02, SN:2024386000060.\n"
                          "L'etichetta (es. Cam1, Cam2, Fluoro, IVUS) è quella che userai per scrivere le viste.",
                  foreground="#555").grid(row=8, column=0, columnspan=6, sticky="w", pady=(14, 0))
        self._refresh_area_device_lists()

    def _refresh_area_device_lists(self):
        names = [""] + [d.name for d in self.lib]
        for row in self.area_rows:
            row["cb"]["values"] = names

    def _on_area_device(self, idx):
        row = self.area_rows[idx]
        d = E.find_device(self.lib, row["dev"].get())
        self._loading = True
        if d:
            row["res"].set(d.resolution)
            if not row["com"].get():
                row["com"].set(d.name)
            if not row["lab"].get():
                if d.is_camera:
                    ncam = sum(1 for j, r in enumerate(self.area_rows)
                               if j != idx and (E.find_device(self.lib, r["dev"].get()) or E.Device("", "", "", "1x1")).is_camera)
                    row["lab"].set(f"Cam{ncam + 1}")
                else:
                    row["lab"].set(d.sigla)
        else:
            row["res"].set("")
        self._loading = False
        self._areas_to_project()

    def _areas_to_project(self):
        if self._loading:
            return
        for i, row in enumerate(self.area_rows):
            a = self.project.areas[i]
            a.device = row["dev"].get()
            a.source = row["src"].get().strip()
            a.comment = row["com"].get().strip()
            a.label = row["lab"].get().strip()

    # ------------------------------------------------------------ tab 2: viste
    def _build_views_tab(self):
        t = ttk.Frame(self.nb, padding=12)
        self.nb.add(t, text="2. Viste")

        q = ttk.Frame(t)
        q.pack(fill="x", pady=(0, 10))
        ttk.Label(q, text="Scrivi una vista (la prima sorgente va grande a destra):").pack(side="left")
        self.v_quick = tk.StringVar()
        e = ttk.Entry(q, textvariable=self.v_quick, width=40)
        e.pack(side="left", padx=6)
        e.bind("<Return>", lambda ev: self.quick_add())
        ttk.Button(q, text="Aggiungi", command=self.quick_add).pack(side="left")
        ttk.Label(q, text="es.  Fluoro + IVUS + Cam1   ·   IVUS + Fluoro + Cam2   ·   Cam1",
                  foreground="#777").pack(side="left", padx=10)

        body = ttk.Frame(t)
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body)
        left.pack(side="left", fill="y")
        self.lb_views = tk.Listbox(left, width=34, height=20, exportselection=False, activestyle="none")
        self.lb_views.pack(fill="y", expand=True)
        self.lb_views.bind("<<ListboxSelect>>", lambda e: self._select_view())
        bb = ttk.Frame(left)
        bb.pack(fill="x", pady=4)
        ttk.Button(bb, text="Nuova", width=7, command=self.new_view).pack(side="left")
        ttk.Button(bb, text="Duplica", width=7, command=self.dup_view).pack(side="left")
        ttk.Button(bb, text="▲", width=3, command=lambda: self.move_view(-1)).pack(side="left")
        ttk.Button(bb, text="▼", width=3, command=lambda: self.move_view(1)).pack(side="left")
        ttk.Button(bb, text="Elimina", width=7, command=self.del_view).pack(side="left")

        right = ttk.Frame(body, padding=(16, 0, 0, 0))
        right.pack(side="left", fill="both", expand=True)
        nf = ttk.Frame(right)
        nf.pack(fill="x")
        ttk.Label(nf, text="Nome vista:").pack(side="left")
        self.v_vname = tk.StringVar()
        self.v_vname.trace_add("write", lambda *a: self._editor_to_view())
        ttk.Entry(nf, textvariable=self.v_vname, width=34).pack(side="left", padx=6)
        self.lbl_autoname = ttk.Label(nf, text="", foreground="#777")
        self.lbl_autoname.pack(side="left")

        grid = ttk.Frame(right)
        grid.pack(fill="x", pady=10)
        ttk.Label(grid, text="Posizione", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(grid, text="Area", font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(grid, text="Profilo (rectangle)", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=6)
        self.pos_rows = []
        for i, p in enumerate(POSITIONS):
            ttk.Label(grid, text=p).grid(row=i + 1, column=0, sticky="w", pady=2)
            va, vp = tk.StringVar(), tk.StringVar()
            ca = ttk.Combobox(grid, textvariable=va, state="readonly", width=26)
            cp = ttk.Combobox(grid, textvariable=vp, state="readonly", width=26)
            ca.grid(row=i + 1, column=1, padx=6)
            cp.grid(row=i + 1, column=2, padx=6)
            ca.bind("<<ComboboxSelected>>", lambda e, k=i: self._on_pos_area(k))
            cp.bind("<<ComboboxSelected>>", lambda e: self._editor_to_view())
            self.pos_rows.append(dict(va=va, vp=vp, ca=ca, cp=cp))

        self.canvas = tk.Canvas(right, width=480, height=270, bg="#1e1e1e", highlightthickness=1,
                                highlightbackground="#888")
        self.canvas.pack(anchor="w", pady=(4, 6))
        self.lbl_calc = ttk.Label(right, text="", font=("Consolas", 9), justify="left")
        self.lbl_calc.pack(anchor="w")
        self.lbl_warn = ttk.Label(right, text="", foreground="#b25a00", justify="left", wraplength=640)
        self.lbl_warn.pack(anchor="w", pady=(4, 0))
        self._set_editor_state(False)

    def _area_choices(self):
        out = [NONE]
        for a in self.project.areas:
            if a.device:
                out.append(f"Area{a.index} – {a.label or a.device}")
        return out

    @staticmethod
    def _area_from_choice(s):
        if not s or s == NONE:
            return None
        return int(s.split("–")[0].strip().replace("Area", ""))

    def _profiles_for_area(self, idx):
        a = self.project.area(idx)
        base = E.find_device(self.lib, a.device) if a else None
        if not base:
            return []
        return [d.name for d in self.lib
                if d.resolution == base.resolution and d.is_camera == base.is_camera]

    def _set_editor_state(self, on):
        st = "readonly" if on else "disabled"
        for r in self.pos_rows:
            r["ca"]["state"] = st
            r["cp"]["state"] = st

    def _refresh_view_list(self, select=None):
        self.lb_views.delete(0, "end")
        for i, v in enumerate(self.project.views, start=1):
            try:
                nm = v.name or E.auto_view_name(self.project, self.lib, v)
            except ValueError:
                nm = v.name or "(vista incompleta)"
            self.lb_views.insert("end", f"View{i}  {nm}")
        if select is not None and 0 <= select < len(self.project.views):
            self.lb_views.selection_set(select)
            self.lb_views.see(select)
        self._select_view()

    def _select_view(self):
        sel = self.lb_views.curselection()
        self.cur_view = sel[0] if sel else None
        self._loading = True
        choices = self._area_choices()
        for r in self.pos_rows:
            r["ca"]["values"] = choices
            r["va"].set(NONE)
            r["vp"].set("")
            r["cp"]["values"] = []
        if self.cur_view is None:
            self.v_vname.set("")
            self._set_editor_state(False)
            self._loading = False
            self._draw_preview()
            return
        self._set_editor_state(True)
        v = self.project.views[self.cur_view]
        self.v_vname.set(v.name)
        for r, it in zip(self.pos_rows, v.items):
            a = self.project.area(it.area)
            r["va"].set(f"Area{it.area} – {a.label or a.device}" if a and a.device else NONE)
            r["cp"]["values"] = self._profiles_for_area(it.area)
            r["vp"].set(it.profile or (a.device if a else ""))
        self._loading = False
        self._draw_preview()

    def _on_pos_area(self, k):
        r = self.pos_rows[k]
        idx = self._area_from_choice(r["va"].get())
        if idx is None:
            r["cp"]["values"] = []
            r["vp"].set("")
        else:
            r["cp"]["values"] = self._profiles_for_area(idx)
            r["vp"].set(self.project.area(idx).device)
        self._editor_to_view()

    def _editor_to_view(self):
        if self._loading or self.cur_view is None:
            return
        v = self.project.views[self.cur_view]
        v.name = self.v_vname.get().strip()
        items = []
        for r in self.pos_rows:
            idx = self._area_from_choice(r["va"].get())
            if idx is None:
                continue
            a = self.project.area(idx)
            prof = r["vp"].get()
            items.append(E.ViewItem(idx, "" if prof == a.device else prof))
        v.items = items
        sel = self.cur_view
        try:
            nm = v.name or E.auto_view_name(self.project, self.lib, v)
        except ValueError:
            nm = v.name or "(vista incompleta)"
        self.lb_views.delete(sel)
        self.lb_views.insert(sel, f"View{sel + 1}  {nm}")
        self.lb_views.selection_set(sel)
        self._draw_preview()

    def _draw_preview(self):
        c = self.canvas
        c.delete("all")
        self.lbl_calc["text"] = ""
        self.lbl_warn["text"] = ""
        self.lbl_autoname["text"] = ""
        if self.cur_view is None:
            c.create_text(240, 135, text="Seleziona o aggiungi una vista", fill="#aaa")
            return
        v = self.project.views[self.cur_view]
        if not v.items:
            c.create_text(240, 135, text="Scegli le aree nelle posizioni", fill="#aaa")
            return
        try:
            res = E.compute_view(self.project, self.lib, v)
            self.lbl_autoname["text"] = "automatico: " + E.auto_view_name(self.project, self.lib, v)
        except ValueError as e:
            c.create_text(240, 135, text=str(e), fill="#f88", width=440)
            return
        s = 0.25
        names = {}
        for it in v.items:
            a, _, prof = E.resolve_item(self.project, self.lib, it)
            names[a.index] = (E.item_name(self.project, self.lib, it), prof.kind)
        lines = []
        for pl, slot in zip(res.placements, res.slots):
            x, y, w, h = slot
            nm, kind = names[pl.area]
            c.create_rectangle(x * s, y * s, (x + w) * s, (y + h) * s,
                               fill=KIND_COLORS.get(kind, "#666"), outline="#111", width=2)
            c.create_text((x + w / 2) * s, (y + h / 2) * s, text=f"{nm}\n{w}×{h}",
                          fill="white", justify="center", font=("Segoe UI", 9, "bold"))
            rect = ",".join(map(str, pl.rect)) if pl.rect else "(intero)"
            lines.append(f"Slot {pl.slot}: Area{pl.area} {nm:<8} Layout {x},{y},{w},{h}   Rectangle {rect}")
        n = len(res.slots)
        lines.insert(0, f"Layout{n}=" + ",".join(",".join(map(str, sl)) for sl in res.slots))
        self.lbl_calc["text"] = "\n".join(lines)
        self.lbl_warn["text"] = "\n".join("⚠ " + w for w in res.warnings)

    def _parse_quick(self, text):
        parts = [p.strip() for p in text.split("+") if p.strip()]
        if not parts:
            raise ValueError("Scrivi almeno una sorgente")
        items = []
        used = set()
        active = [a for a in self.project.areas if a.device]
        for part in parts:
            pl = part.lower()
            it = None
            for a in active:
                if a.index not in used and a.label.lower() == pl:
                    it = E.ViewItem(a.index)
                    break
            if it is None:
                cands = [d for d in self.lib if pl in (d.sigla.lower(), d.name.lower())]
                for d in cands:
                    a = next((a for a in active if a.index not in used and a.device == d.name), None)
                    if a:
                        it = E.ViewItem(a.index)
                        break
                if it is None:
                    for d in cands:
                        a = next((a for a in active if a.index not in used
                                  and (E.find_device(self.lib, a.device).resolution == d.resolution)
                                  and E.find_device(self.lib, a.device).is_camera == d.is_camera), None)
                        if a:
                            it = E.ViewItem(a.index, d.name)
                            break
            if it is None:
                raise ValueError(f"'{part}' non corrisponde a nessuna area configurata.\n"
                                 "Usa le etichette del tab Aree (es. Cam1, Fluoro) o la sigla di un dispositivo del catalogo.")
            used.add(it.area)
            items.append(it)
        if len(items) > 4:
            raise ValueError("Massimo 4 sorgenti per vista")
        return items

    def quick_add(self):
        self._areas_to_project()
        try:
            items = self._parse_quick(self.v_quick.get())
        except ValueError as e:
            messagebox.showerror("Vista non riconosciuta", str(e))
            return
        self.project.views.append(E.View("", items))
        self.v_quick.set("")
        self._refresh_view_list(len(self.project.views) - 1)

    def new_view(self):
        self.project.views.append(E.View())
        self._refresh_view_list(len(self.project.views) - 1)

    def dup_view(self):
        if self.cur_view is None:
            return
        v = self.project.views[self.cur_view]
        self.project.views.insert(self.cur_view + 1,
                                  E.View(v.name, [E.ViewItem(i.area, i.profile) for i in v.items]))
        self._refresh_view_list(self.cur_view + 1)

    def move_view(self, d):
        i = self.cur_view
        if i is None or not (0 <= i + d < len(self.project.views)):
            return
        vs = self.project.views
        vs[i], vs[i + d] = vs[i + d], vs[i]
        self._refresh_view_list(i + d)

    def del_view(self):
        if self.cur_view is None:
            return
        del self.project.views[self.cur_view]
        self._refresh_view_list(min(self.cur_view, len(self.project.views) - 1))

    # ------------------------------------------------------------ tab 3: catalogo
    def _build_library_tab(self):
        t = ttk.Frame(self.nb, padding=12)
        self.nb.add(t, text="3. Catalogo dispositivi")
        ttk.Label(t, text="Il catalogo viene salvato automaticamente e ricordato alle prossime aperture. "
                          "Aprendo un .ini esistente, i rectangle sconosciuti vengono aggiunti qui.",
                  foreground="#555").pack(anchor="w", pady=(0, 8))
        cols = ("nome", "sigla", "tipo", "ris", "rect")
        self.tv = ttk.Treeview(t, columns=cols, show="headings", height=14)
        for c, h, w in zip(cols, ["Nome", "Sigla", "Tipo", "Risoluzione", "Rectangle (x,y,w,h)"],
                           [200, 90, 100, 110, 220]):
            self.tv.heading(c, text=h)
            self.tv.column(c, width=w, anchor="w")
        self.tv.pack(fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self._lib_select())

        f = ttk.LabelFrame(t, text="Dispositivo", padding=8)
        f.pack(fill="x", pady=8)
        self.l_name, self.l_sigla, self.l_kind, self.l_res, self.l_rect = (tk.StringVar() for _ in range(5))
        fields = [("Nome", self.l_name, 22), ("Sigla", self.l_sigla, 10), ("Risoluzione", self.l_res, 12),
                  ("Rectangle", self.l_rect, 22)]
        col = 0
        for lab, var, w in fields:
            ttk.Label(f, text=lab).grid(row=0, column=col, sticky="w")
            ttk.Entry(f, textvariable=var, width=w).grid(row=0, column=col + 1, padx=(4, 12))
            col += 2
        ttk.Label(f, text="Tipo").grid(row=0, column=col, sticky="w")
        ttk.Combobox(f, textvariable=self.l_kind, values=E.KINDS, state="readonly", width=12).grid(
            row=0, column=col + 1, padx=4)
        self.l_kind.set(E.KIND_DEVICE)
        bf = ttk.Frame(t)
        bf.pack(fill="x")
        ttk.Button(bf, text="Aggiungi / Aggiorna", command=self.lib_save).pack(side="left")
        ttk.Button(bf, text="Elimina", command=self.lib_delete).pack(side="left", padx=6)
        ttk.Label(bf, text="Rectangle vuoto = segnale intero. Per le telecamere il rectangle viene calcolato.",
                  foreground="#777").pack(side="left", padx=10)
        ttk.Label(t, text="File catalogo: " + E.library_path(), foreground="#999").pack(anchor="w", pady=(8, 0))
        self._refresh_lib()

    def _refresh_lib(self):
        self.tv.delete(*self.tv.get_children())
        for d in self.lib:
            self.tv.insert("", "end", iid=d.name, values=(
                d.name, d.sigla, d.kind, d.resolution,
                "(calcolato)" if d.is_camera else (",".join(map(str, d.rect)) if d.rect else "(intero)")))
        self._refresh_area_device_lists()

    def _lib_select(self):
        sel = self.tv.selection()
        if not sel:
            return
        d = E.find_device(self.lib, sel[0])
        self.l_name.set(d.name)
        self.l_sigla.set(d.sigla)
        self.l_kind.set(d.kind)
        self.l_res.set(d.resolution)
        self.l_rect.set(",".join(map(str, d.rect)) if d.rect else "")

    def lib_save(self):
        name = self.l_name.get().strip()
        try:
            if not name:
                raise ValueError("Inserisci un nome")
            res = self.l_res.get().strip().lower()
            rw, rh = E.parse_res(res)
            kind = self.l_kind.get()
            rect = None if kind == E.KIND_CAMERA else E.parse_rect(self.l_rect.get())
            if rect and (rect[0] + rect[2] > rw or rect[1] + rect[3] > rh):
                raise ValueError("Il rectangle esce dalla risoluzione del segnale")
        except ValueError as e:
            messagebox.showerror("Dati non validi", str(e))
            return
        d = E.Device(name, self.l_sigla.get().strip() or name, kind, f"{rw}x{rh}", rect)
        old = E.find_device(self.lib, name)
        if old:
            self.lib[self.lib.index(old)] = d
        else:
            self.lib.append(d)
        E.save_library(self.lib)
        self._refresh_lib()
        self.tv.selection_set(name)

    def lib_delete(self):
        sel = self.tv.selection()
        if not sel:
            return
        if any(a.device == sel[0] for a in self.project.areas):
            messagebox.showwarning("In uso", "Il dispositivo è assegnato a un'area del layout corrente.")
            return
        if messagebox.askyesno("Elimina", f"Eliminare '{sel[0]}' dal catalogo?"):
            self.lib = [d for d in self.lib if d.name != sel[0]]
            E.save_library(self.lib)
            self._refresh_lib()

    # ------------------------------------------------------------ tab 4: output
    def _build_output_tab(self):
        t = ttk.Frame(self.nb, padding=12)
        self.nb.add(t, text="4. File .ini")
        bf = ttk.Frame(t)
        bf.pack(fill="x", pady=(0, 6))
        ttk.Button(bf, text="Rigenera", command=self.regenerate).pack(side="left")
        ttk.Button(bf, text="Salva .ini…", command=self.save_ini).pack(side="left", padx=6)
        ttk.Label(bf, text="Puoi ritoccare il testo a mano prima di salvare (Rigenera annulla le modifiche).",
                  foreground="#777").pack(side="left", padx=10)
        self.lbl_out_warn = ttk.Label(t, text="", foreground="#b25a00", justify="left", wraplength=1100)
        self.lbl_out_warn.pack(anchor="w")
        fr = ttk.Frame(t)
        fr.pack(fill="both", expand=True)
        self.txt = tk.Text(fr, font=("Consolas", 10), wrap="none", undo=True)
        sb = ttk.Scrollbar(fr, command=self.txt.yview)
        self.txt["yscrollcommand"] = sb.set
        sb.pack(side="right", fill="y")
        self.txt.pack(fill="both", expand=True)

    def regenerate(self):
        self._sync_header()
        self._areas_to_project()
        text, warns = E.generate_ini(self.project, self.lib)
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", text)
        self.lbl_out_warn["text"] = "\n".join("⚠ " + w for w in warns)
        return warns

    def _on_tab(self):
        idx = self.nb.index(self.nb.select())
        self._areas_to_project()
        if idx == 1:
            self._refresh_view_list(self.cur_view)
        elif idx == 3:
            self.regenerate()

    # ------------------------------------------------------------ file
    def new_project(self):
        if self.project.views and not messagebox.askyesno("Nuovo", "Scartare il layout corrente?"):
            return
        self.project = E.Project()
        self._load_project_into_ui()

    def _load_project_into_ui(self):
        self._loading = True
        self.v_name.set(self.project.name)
        self.v_audio.set(self.project.audio)
        self.v_parse.set(self.project.parse_mode)
        for row, a in zip(self.area_rows, self.project.areas):
            row["dev"].set(a.device)
            d = E.find_device(self.lib, a.device)
            row["res"].set(d.resolution if d else "")
            row["src"].set(a.source)
            row["com"].set(a.comment)
            row["lab"].set(a.label)
        self._loading = False
        self._refresh_lib()
        self._refresh_view_list(0 if self.project.views else None)

    def import_ini(self):
        path = filedialog.askopenfilename(filetypes=[("Layout OneView", "*.ini"), ("Tutti i file", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            n_before = len(self.lib)
            self.project, notes = E.import_ini(text, self.lib)
            if len(self.lib) != n_before:
                E.save_library(self.lib)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Errore", f"Impossibile leggere il file:\n{e}")
            return
        self._load_project_into_ui()
        self.nb.select(0)
        msg = "Layout caricato. Le viste verranno ricalcolate con le regole attuali."
        if notes:
            msg += "\n\n" + "\n".join("• " + n for n in notes)
        messagebox.showinfo("Importazione", msg)

    def save_ini(self):
        if self.nb.index(self.nb.select()) != 3:
            warns = self.regenerate()
        else:
            warns = []
        text = self.txt.get("1.0", "end").rstrip() + "\n"
        if warns and not messagebox.askyesno(
                "Avvisi", "Ci sono avvisi:\n\n" + "\n".join(warns[:12]) + "\n\nSalvare comunque?"):
            self.nb.select(3)
            return
        path = filedialog.asksaveasfilename(defaultextension=".ini", initialfile="Layout.ini",
                                            filetypes=[("Layout OneView", "*.ini")])
        if not path:
            return
        with open(path, "w", encoding="cp1252", errors="replace", newline="\r\n") as f:
            f.write(text)
        messagebox.showinfo("Salvato", f"File salvato:\n{os.path.basename(path)}")


if __name__ == "__main__":
    App().mainloop()
