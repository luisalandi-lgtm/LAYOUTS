"""OneView Layout Generator - interfaccia grafica."""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import layout_engine as E

POSITIONS = ["Grande a destra", "In alto a sinistra", "Sotto a sinistra", "Ancora sotto (4ª)"]
KIND_COLORS = {E.KIND_SCOPIA: "#4a78c2", E.KIND_DEVICE: "#3f9a6b", E.KIND_CAMERA: "#c98a2e"}
NONE = "—"
SC = 0.3                                     # scala dell'anteprima (1920x1080 -> 576x324)
PW, PH = int(E.SCREEN_W * SC), int(E.SCREEN_H * SC)
GRAB = 6                                     # tolleranza in pixel per afferrare una linea


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OneView Layout Generator")
        self.geometry("1260x790")
        self.minsize(1100, 700)
        self.lib = E.load_library()
        self.project = E.Project(screen=getattr(getattr(self, "project", None), "screen", "1920x1080"))
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
        ttk.Button(bf, text="Copia negli appunti", command=self.copy_ini).pack(side="left", padx=2)
        sf = ttk.Frame(f)
        sf.grid(row=1, column=0, columnspan=7, sticky="ew", pady=(8, 0))
        ttk.Label(sf, text="Schermo OneView:", font=("Segoe UI", 9, "bold")).pack(side="left")
        self.v_screen = tk.StringVar(value=self.project.screen)
        for label, res in E.SCREENS.items():
            ttk.Radiobutton(sf, text=label, value=res, variable=self.v_screen,
                            command=self._on_screen_change).pack(side="left", padx=(8, 0))
        self.btn_convert = ttk.Button(sf, text="", command=self.toggle_screen)
        self.btn_convert.pack(side="left", padx=(16, 0))
        # sfondo: riga BackgroundBitMap + segnali separati da una cornice
        ttk.Separator(sf, orient="vertical").pack(side="left", fill="y", padx=14)
        self.v_bg = tk.BooleanVar(value=self.project.background)
        self.v_bg_file = tk.StringVar(value=self.project.background_file)
        self.v_bg_top = tk.StringVar(value=str(self.project.bg_top))
        self.v_bg_frame = tk.StringVar(value=str(self.project.bg_frame))
        ttk.Checkbutton(sf, text="Sfondo", variable=self.v_bg,
                        command=self._on_bg_change).pack(side="left")
        self.bg_widgets = [ttk.Entry(sf, textvariable=self.v_bg_file, width=14)]
        self.bg_widgets[0].pack(side="left", padx=(4, 0))
        for text, var in (("margine alto", self.v_bg_top), ("cornice", self.v_bg_frame)):
            ttk.Label(sf, text=text).pack(side="left", padx=(10, 2))
            sp = ttk.Spinbox(sf, from_=0, to=300, increment=2, width=4, textvariable=var,
                             command=self._on_bg_change)
            sp.pack(side="left")
            sp.bind("<KeyRelease>", lambda e: self._on_bg_change())
            self.bg_widgets.append(sp)
        self.bg_widgets[0].bind("<KeyRelease>", lambda e: self._on_bg_change())
        self._update_bg_widgets()
        self.lbl_status = ttk.Label(sf, text="", foreground="#2e7d32")
        self.lbl_status.pack(side="right", padx=(12, 0))
        self._update_convert_button()

    def _update_convert_button(self):
        hd = self.v_screen.get() == "1280x720"
        self.btn_convert["text"] = "⇄ Converti in Full HD 1920×1080" if hd else "⇄ Converti in HD 1280×720"

    def toggle_screen(self):
        self.v_screen.set("1920x1080" if self.v_screen.get() == "1280x720" else "1280x720")
        self._on_screen_change()

    def _on_screen_change(self):
        """Cambia lo schermo di destinazione: stessa disposizione e stesse proporzioni, valori riscalati."""
        if self.project.screen == self.v_screen.get():
            return
        self._sync_bg()
        E.convert_frame(self.project, self.v_screen.get())  # cambia schermo e adegua la cornice
        self.v_bg_top.set(str(self.project.bg_top))
        self.v_bg_frame.set(str(self.project.bg_frame))
        self._update_convert_button()
        nome = next(k for k, v in E.SCREENS.items() if v == self.project.screen)
        self._status(f"✓ Layout convertito in {nome}")
        self._draw_preview()
        if self.nb.index(self.nb.select()) == 3:
            self.regenerate()

    def _update_bg_widgets(self):
        for w in self.bg_widgets:
            w.state(["!disabled"] if self.v_bg.get() else ["disabled"])

    def _sync_bg(self):
        p = self.project
        p.background = self.v_bg.get()
        p.background_file = self.v_bg_file.get().strip() or E.BG_FILE
        for attr, var in (("bg_top", self.v_bg_top), ("bg_frame", self.v_bg_frame)):
            try:
                setattr(p, attr, max(0, min(300, int(var.get()))))
            except ValueError:
                pass  # campo vuoto o in corso di scrittura: si tiene il valore precedente

    def _on_bg_change(self):
        if getattr(self, "_loading", False):
            return
        self._sync_bg()
        self._update_bg_widgets()
        self._draw_preview()
        if self.nb.index(self.nb.select()) == 3:
            self.regenerate()

    def _status(self, text):
        self.lbl_status["text"] = text
        self.after(3500, lambda: self.lbl_status.configure(text=""))

    def _sync_header(self):
        self.project.name = self.v_name.get().strip()
        self.project.audio = self.v_audio.get().strip()
        self.project.parse_mode = self.v_parse.get().strip()
        self._sync_bg()

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
            row = dict(dev=dev, res=res, src=src, com=com, lab=lab, cb=cb, auto_com="", auto_lab="")
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

    def _auto_values(self, idx, d):
        """Commento ed etichetta proposti automaticamente per il dispositivo d nell'area idx."""
        if d is None:
            return "", ""
        if d.is_camera:
            n = 1 + sum(1 for j, r in enumerate(self.area_rows[:idx])
                        if (E.find_device(self.lib, r["dev"].get()) or d).is_camera
                        and E.find_device(self.lib, r["dev"].get()) is not None)
            return d.name, f"CAM{n}"
        return d.name, E.dev_class(d)

    def _on_area_device(self, idx):
        row = self.area_rows[idx]
        d = E.find_device(self.lib, row["dev"].get())
        new_com, new_lab = self._auto_values(idx, d)
        self._loading = True
        row["res"].set(d.resolution if d else "")
        # i campi compilati in automatico (o vuoti) seguono il nuovo dispositivo;
        # quelli modificati a mano restano come sono
        if not row["com"].get().strip() or row["com"].get() == row["auto_com"]:
            row["com"].set(new_com)
        if not row["lab"].get().strip() or row["lab"].get() == row["auto_lab"]:
            row["lab"].set(new_lab)
        row["auto_com"], row["auto_lab"] = new_com, new_lab
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
        q.pack(fill="x", pady=(0, 2))
        ttk.Label(q, text="Scrivi una vista:").pack(side="left")
        self.v_quick = tk.StringVar()
        e = ttk.Entry(q, textvariable=self.v_quick, width=48)
        e.pack(side="left", padx=6)
        e.bind("<Return>", lambda ev: self.quick_add())
        ttk.Button(q, text="Aggiungi", command=self.quick_add).pack(side="left")
        ttk.Label(t, text="La sorgente indicata come «grande» (oppure la prima) va a destra. Separatori: + , e    "
                          "es.  live + ivus + cam  ·  x-rays, hemo, camera  ·  cam grande e live piccola  ·  "
                          "echo e scopia e cam 2\n"
                          "Nomi nelle viste: LIVE · CAM · POLY/HEMO · ECHO · IVUS · OCT · FFR · SYNC",
                  foreground="#777").pack(anchor="w", pady=(0, 10))

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

        tb = ttk.Frame(right)
        tb.pack(fill="x", pady=(2, 2))
        self.lbl_geom = ttk.Label(tb, text="", font=("Segoe UI", 9, "bold"))
        self.lbl_geom.pack(side="left")
        ttk.Button(tb, text="↺ Tutte automatiche", command=self.reset_all_geometry).pack(side="right")
        ttk.Button(tb, text="↺ Misure automatiche", command=self.reset_geometry).pack(side="right", padx=4)
        ttk.Label(right, text="Trascina le linee di divisione per ridimensionare · trascina un segnale sopra "
                              "un altro per scambiarli · doppio clic su una linea = torna automatica",
                  foreground="#777").pack(anchor="w")
        cv_row = ttk.Frame(right)
        cv_row.pack(fill="both", expand=True, pady=(4, 0))
        self.canvas = tk.Canvas(cv_row, width=PW, height=PH, bg="#1e1e1e", highlightthickness=1,
                                highlightbackground="#888")
        self.canvas.pack(side="left", anchor="n")
        side = ttk.Frame(cv_row, padding=(10, 0, 0, 0))
        side.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Motion>", self._cv_motion)
        self.canvas.bind("<ButtonPress-1>", self._cv_press)
        self.canvas.bind("<B1-Motion>", self._cv_drag)
        self.canvas.bind("<ButtonRelease-1>", self._cv_release)
        self.canvas.bind("<Double-Button-1>", self._cv_double)
        self._res = None
        self._drag = None
        self.lbl_calc = ttk.Label(side, text="", font=("Consolas", 9), justify="left", wraplength=330)
        self.lbl_calc.pack(anchor="w")
        self.lbl_warn = ttk.Label(side, text="", foreground="#b25a00", justify="left", wraplength=330)
        self.lbl_warn.pack(anchor="w", pady=(6, 0))
        self.lbl_info = ttk.Label(side, text="", foreground="#666", justify="left", wraplength=330)
        self.lbl_info.pack(anchor="w", pady=(4, 0))
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
        for i, v in enumerate(self.project.views):
            self.lb_views.insert("end", self._view_label(i, v))
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
            prof = "" if r["vp"].get() == a.device else r["vp"].get()
            # il nome forzato (es. HEMO) resta finché la sorgente non cambia
            alias = next((o.alias for o in v.items if o.area == idx and o.profile == prof), "")
            items.append(E.ViewItem(idx, prof, alias))
        if [(o.area, o.profile) for o in v.items] != [(o.area, o.profile) for o in items]:
            v.reset_geometry()  # sorgenti cambiate: misure di nuovo automatiche
        v.items = items
        self._update_list_row()
        self._draw_preview()

    # -------------------------------------------------- anteprima interattiva
    def _view_label(self, i, v):
        try:
            nm = v.name or E.auto_view_name(self.project, self.lib, v)
        except ValueError:
            nm = v.name or "(vista incompleta)"
        return f"View{i + 1}  {nm}" + ("   ✎" if v.is_manual else "")

    def _update_list_row(self):
        sel = self.cur_view
        if sel is None:
            return
        self.lb_views.delete(sel)
        self.lb_views.insert(sel, self._view_label(sel, self.project.views[sel]))
        self.lb_views.selection_set(sel)

    def _draw_preview(self, highlight=None):
        c = self.canvas
        c.delete("all")
        if self.project.background:
            # sfondo: si vede nella cornice attorno ai segnali
            c.create_rectangle(0, 0, PW, PH, fill="#3b4f66", outline="")
            c.create_text(8, 6, text=f"sfondo {self.project.background_file}", anchor="nw",
                          fill="#b8c7d9", font=("Segoe UI", 8))
        self._res = None
        for lbl in (self.lbl_calc, self.lbl_warn, self.lbl_info, self.lbl_autoname, self.lbl_geom):
            lbl["text"] = ""
        if self.cur_view is None:
            c.create_text(PW / 2, PH / 2, text="Seleziona o aggiungi una vista", fill="#aaa")
            return
        v = self.project.views[self.cur_view]
        if not v.items:
            c.create_text(PW / 2, PH / 2, text="Scegli le aree nelle posizioni", fill="#aaa")
            return
        try:
            res = E.compute_view(self.project, self.lib, v)
            self.lbl_autoname["text"] = "automatico: " + E.auto_view_name(self.project, self.lib, v)
        except ValueError as e:
            c.create_text(PW / 2, PH / 2, text=str(e), fill="#f88", width=PW - 40)
            return
        self._res = res
        self.lbl_geom["text"] = ("Misure: impostate a mano ✎" if v.is_manual else "Misure: automatiche")
        names = {}
        for it in v.items:
            a, _, prof = E.resolve_item(self.project, self.lib, it)
            names[a.index] = (E.item_name(self.project, self.lib, it), prof.kind)
        lines = []
        # il disegno usa le misure Full HD interne, i testi quelle dello schermo scelto
        for k, (pl, slot, sf) in enumerate(zip(res.placements, res.slots, res.slots_fhd)):
            x, y, w, h = slot
            fx, fy, fw, fh = sf
            nm, kind = names[pl.area]
            hl = highlight is not None and highlight == k
            c.create_rectangle(fx * SC, fy * SC, (fx + fw) * SC, (fy + fh) * SC,
                               fill=KIND_COLORS.get(kind, "#666"),
                               outline="#ffd54a" if hl else "#111", width=4 if hl else 2)
            c.create_text((fx + fw / 2) * SC, (fy + fh / 2) * SC, text=f"{nm}\n{w}×{h}",
                          fill="white", justify="center", font=("Segoe UI", 10, "bold"))
            rect = ",".join(map(str, pl.rect)) if pl.rect else "(intero)"
            lines.append(f"Slot {pl.slot} · Area{pl.area} {nm}\n  Layout    {x},{y},{w},{h}\n  Rectangle {rect}")
        # linee di divisione afferrabili
        for kind, pos, a, b, *_ in self._dividers():
            if kind == "v":
                c.create_line(pos * SC, a * SC, pos * SC, b * SC, fill="#e0e0e0", width=3, dash=(4, 3))
            else:
                c.create_line(a * SC, pos * SC, b * SC, pos * SC, fill="#e0e0e0", width=3, dash=(4, 3))
        if self._drag and self._drag["type"] == "slot" and self._drag.get("moved"):
            src = self._drag["k"]
            x, y = self._drag["xy"]
            nm = names[res.placements[src].area][0]
            c.create_text(x, y - 12, text=f"↔ {nm}", fill="#ffd54a", font=("Segoe UI", 11, "bold"))
        n = len(res.slots)
        lines.insert(0, f"Layout{n}=" + ",".join(",".join(map(str, sl)) for sl in res.slots))
        self.lbl_calc["text"] = "\n".join(lines)
        self.lbl_warn["text"] = "\n".join("⚠ " + w for w in res.warnings)
        self.lbl_info["text"] = "\n".join("ℹ " + i for i in res.info)

    def _col_slots(self):
        s = self._res.slots_fhd
        return list(s[:-1])   # colonna a sinistra; l'ultimo slot è quello grande a destra

    def _dividers(self):
        """Linee spostabili: ('v', x, y0, y1) tra colonna e destra, ('h', y, x0, x1, i) tra slot in colonna."""
        if not self._res or len(self._res.slots_fhd) < 2:
            return []
        col = self._col_slots()
        X0, Y0, CW, CH, G = E.frame_box(self.project)
        L = col[0][2]
        # con la cornice le linee stanno a metà dello spazio tra i segnali
        out = [("v", X0 + L + G / 2, Y0, Y0 + CH)]
        for i in range(len(col) - 1):
            out.append(("h", col[i][1] + col[i][3] + G / 2, X0, X0 + L, i))
        return out

    def _hit_divider(self, cx, cy):
        for d in self._dividers():
            if d[0] == "v" and abs(cx - d[1] * SC) <= GRAB:
                return d
            if d[0] == "h" and abs(cy - d[1] * SC) <= GRAB and cx <= d[3] * SC + GRAB:
                return d
        return None

    def _hit_slot(self, cx, cy):
        if not self._res:
            return None
        x, y = cx / SC, cy / SC
        for k, (sx, sy, sw, sh) in enumerate(self._res.slots_fhd):
            if sx <= x < sx + sw and sy <= y < sy + sh:
                return k
        return None

    def _slot_to_item(self, k):
        # slot in senso antiorario: 0..n-2 = colonna (items[1:]), ultimo = destra (items[0])
        return 0 if k == len(self._res.slots_fhd) - 1 else k + 1

    def _cv_motion(self, e):
        d = self._hit_divider(e.x, e.y)
        if d:
            self.canvas["cursor"] = "sb_h_double_arrow" if d[0] == "v" else "sb_v_double_arrow"
        elif self._hit_slot(e.x, e.y) is not None and len(self._res.slots_fhd) > 1:
            self.canvas["cursor"] = "fleur"
        else:
            self.canvas["cursor"] = ""

    def _cv_press(self, e):
        self._drag = None
        if self.cur_view is None or not self._res:
            return
        d = self._hit_divider(e.x, e.y)
        if d:
            self._drag = {"type": d[0], "div": d}
            return
        k = self._hit_slot(e.x, e.y)
        if k is not None and len(self._res.slots_fhd) > 1:
            self._drag = {"type": "slot", "k": k, "xy": (e.x, e.y), "moved": False}

    def _cv_drag(self, e):
        if not self._drag or self.cur_view is None:
            return
        v = self.project.views[self.cur_view]
        X0, Y0, CW, CH, G = E.frame_box(self.project)
        if self._drag["type"] == "v":
            v.col_width = max(E.MIN_SLOT, min(E.ev(e.x / SC - X0 - G / 2), CW - G - E.MIN_SLOT))
            self._draw_preview()
        elif self._drag["type"] == "h":
            i = self._drag["div"][4]
            col = self._col_slots()
            if not v.heights or len(v.heights) != len(col):
                v.heights = [c[3] for c in col]
            top = col[i][1]
            bottom = col[i + 1][1] + col[i + 1][3]
            y = E.ev(e.y / SC - G / 2)   # nuovo bordo inferiore dello slot di sopra
            y = max(top + E.MIN_SLOT, min(y, bottom - G - E.MIN_SLOT))
            v.heights[i] = y - top
            v.heights[i + 1] = bottom - (y + G)
            self._draw_preview()
        else:
            self._drag["xy"] = (e.x, e.y)
            self._drag["moved"] = True
            tgt = self._hit_slot(e.x, e.y)
            self._draw_preview(highlight=tgt if tgt != self._drag["k"] else None)
        self._update_list_row()

    def _cv_release(self, e):
        drag, self._drag = self._drag, None
        if not drag or self.cur_view is None:
            return
        if drag["type"] == "slot":
            tgt = self._hit_slot(e.x, e.y)
            if drag.get("moved") and tgt is not None and tgt != drag["k"]:
                self.swap_slots(drag["k"], tgt)
                return
        self._draw_preview()

    def _cv_double(self, e):
        if self.cur_view is None:
            return
        d = self._hit_divider(e.x, e.y)
        if not d:
            return
        v = self.project.views[self.cur_view]
        if d[0] == "v":
            v.col_width = 0
        else:
            v.heights = []
        self._drag = None
        self._draw_preview()
        self._update_list_row()

    def swap_slots(self, k1, k2):
        v = self.project.views[self.cur_view]
        i, j = self._slot_to_item(k1), self._slot_to_item(k2)
        v.items[i], v.items[j] = v.items[j], v.items[i]
        v.reset_geometry()  # nuova disposizione: si riparte dalle misure automatiche
        self._refresh_view_list(self.cur_view)

    def reset_geometry(self):
        if self.cur_view is None:
            return
        self.project.views[self.cur_view].reset_geometry()
        self._draw_preview()
        self._update_list_row()

    def reset_all_geometry(self):
        manual = [v for v in self.project.views if v.is_manual]
        if not manual:
            return
        if messagebox.askyesno("Misure automatiche",
                               f"Ricalcolare in automatico le misure di {len(manual)} viste impostate a mano?"):
            for v in manual:
                v.reset_geometry()
            self._refresh_view_list(self.cur_view)

    def quick_add(self):
        self._areas_to_project()
        try:
            items = E.parse_view_text(self.project, self.lib, self.v_quick.get())
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
                                  E.View(v.name, [E.ViewItem(i.area, i.profile, i.alias) for i in v.items],
                                         v.col_width, list(v.heights)))
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
        cols = ("nome", "sigla", "tipo", "ris", "rect", "info")
        self.tv = ttk.Treeview(t, columns=cols, show="headings", height=14)
        for c, h, w in zip(cols, ["Nome", "Sigla", "Tipo", "Risoluzione", "Rectangle (x,y,w,h)",
                            "Righe in [Info]"],
                           [190, 80, 95, 100, 180, 200]):
            self.tv.heading(c, text=h)
            self.tv.column(c, width=w, anchor="w")
        self.tv.pack(fill="both", expand=True)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self._lib_select())

        f = ttk.LabelFrame(t, text="Dispositivo", padding=8)
        f.pack(fill="x", pady=8)
        self.l_name, self.l_sigla, self.l_kind, self.l_res, self.l_rect, self.l_info = (
            tk.StringVar() for _ in range(6))
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
        ttk.Label(f, text="Righe in [Info]").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(f, textvariable=self.l_info, width=60).grid(row=1, column=1, columnspan=5, sticky="w",
                                                             padx=(4, 12), pady=(8, 0))
        ttk.Label(f, text="aggiunte sotto ParseMode se il dispositivo è usato · più righe separate da ;  "
                          "· {area} = numero dell'area", foreground="#777").grid(
            row=1, column=6, columnspan=4, sticky="w", pady=(8, 0))
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
                "(calcolato)" if d.is_camera else (",".join(map(str, d.rect)) if d.rect else "(intero)"),
                d.info_lines))
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
        self.l_info.set(d.info_lines)

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
        info = self.l_info.get().strip()
        if not info and "obsbot" in name.lower():
            info = E.OBSBOT_INFO
        d = E.Device(name, self.l_sigla.get().strip() or name, kind, f"{rw}x{rh}", rect, info)
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
        ttk.Button(bf, text="Copia negli appunti", command=self.copy_ini).pack(side="left")
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
        old = self.project
        # il nuovo layout mantiene schermo e impostazioni dello sfondo
        self.project = E.Project(screen=old.screen, background=old.background,
                                 background_file=old.background_file,
                                 bg_top=old.bg_top, bg_frame=old.bg_frame)
        self._load_project_into_ui()

    def _load_project_into_ui(self):
        self._loading = True
        self.v_name.set(self.project.name)
        self.v_audio.set(self.project.audio)
        self.v_parse.set(self.project.parse_mode)
        self.v_screen.set(self.project.screen)
        self._update_convert_button()
        self.v_bg.set(self.project.background)
        self.v_bg_file.set(self.project.background_file)
        self.v_bg_top.set(str(self.project.bg_top))
        self.v_bg_frame.set(str(self.project.bg_frame))
        self._update_bg_widgets()
        for row, a in zip(self.area_rows, self.project.areas):
            row["dev"].set(a.device)
            d = E.find_device(self.lib, a.device)
            row["res"].set(d.resolution if d else "")
            row["src"].set(a.source)
            row["com"].set(a.comment)
            row["lab"].set(a.label)
            row["auto_com"], row["auto_lab"] = "", ""
        for i, row in enumerate(self.area_rows):
            # i valori che coincidono con quelli automatici continueranno ad aggiornarsi
            ac, al = self._auto_values(i, E.find_device(self.lib, row["dev"].get()))
            row["auto_com"] = ac if row["com"].get() == ac else ""
            row["auto_lab"] = al if row["lab"].get() == al else ""
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
        msg = ("Layout caricato. Le misure del file sono state conservate (viste segnate con ✎);\n"
               "usa «↺ Tutte automatiche» nel tab Viste per ricalcolarle con le regole attuali.")
        if notes:
            msg += "\n\n" + "\n".join("• " + n for n in notes)
        messagebox.showinfo("Importazione", msg)

    def copy_ini(self):
        # nel tab "File .ini" si copia il testo così com'è (con eventuali ritocchi a mano)
        if self.nb.index(self.nb.select()) != 3:
            self.regenerate()
        text = self.txt.get("1.0", "end").rstrip() + "\n"
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self._status("✓ Testo del layout copiato negli appunti")

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
