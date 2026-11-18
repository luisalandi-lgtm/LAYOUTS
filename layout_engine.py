"""Motore di calcolo dei layout OneView.

Convenzioni (ricavate dai layout esistenti):
- Schermo 1920x1080.
- In una vista, la PRIMA sorgente indicata va grande a destra; le altre vanno
  impilate nella colonna di sinistra, dall'alto verso il basso.
- Slot: 1 = in alto a sinistra, 2 = grande a destra, 3.. = sotto a sinistra.
- I dispositivi mantengono il rectangle fisso del catalogo; le telecamere
  vengono ritagliate e centrate in base allo spazio che resta libero.
- Regole: scopia in colonna mai meno di 600x600, telecamera mai meno di 400 px di altezza.
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

SCREEN_W, SCREEN_H = 1920, 1080
MIN_SCOPIA = 600
MIN_CAM_H = 400

KIND_CAMERA = "camera"
KIND_SCOPIA = "scopia"
KIND_DEVICE = "dispositivo"
KINDS = [KIND_DEVICE, KIND_SCOPIA, KIND_CAMERA]


def ev(x: float) -> int:
    """Arrotonda al numero pari più vicino."""
    return int(round(x / 2.0)) * 2


def fev(x: float) -> int:
    """Arrotonda per difetto al numero pari."""
    return int(x // 2) * 2


def parse_res(res: str) -> Tuple[int, int]:
    w, h = res.lower().replace(" ", "").split("x")
    return int(w), int(h)


def parse_rect(rect: str) -> Optional[List[int]]:
    rect = (rect or "").strip()
    if not rect:
        return None
    vals = [int(v.strip()) for v in rect.split(",")]
    if len(vals) != 4:
        raise ValueError("Il rectangle deve avere 4 valori: x,y,larghezza,altezza")
    return vals


# ----------------------------------------------------------------- catalogo
@dataclass
class Device:
    name: str            # es. "Poligrafo"
    sigla: str           # es. "Poly" (usata nei nomi delle viste)
    kind: str            # dispositivo / scopia / camera
    resolution: str      # es. "1600x1200"
    rect: Optional[List[int]] = None  # x,y,w,h (None per le camere)

    @property
    def is_camera(self) -> bool:
        return self.kind == KIND_CAMERA

    def effective_rect(self) -> List[int]:
        if self.rect:
            return list(self.rect)
        w, h = parse_res(self.resolution)
        return [0, 0, w, h]

    def aspect(self) -> float:
        r = self.effective_rect()
        return r[2] / r[3]


DEFAULT_DEVICES = [
    Device("Scopia", "Fluoro", KIND_SCOPIA, "1920x1080", [0, 32, 960, 960]),
    Device("Poligrafo", "Poly", KIND_DEVICE, "1600x1200", [10, 290, 1556, 822]),
    Device("Ecografo GE", "EcoGE", KIND_DEVICE, "1600x1200", [0, 64, 1600, 1136]),
    Device("IVUS Volcano", "IVUS", KIND_DEVICE, "1280x1024", [14, 84, 1186, 866]),
    Device("FFR Volcano", "FFR", KIND_DEVICE, "1280x1024", [0, 78, 1280, 946]),
    Device("SyncVision", "SYNC", KIND_DEVICE, "1280x1024", None),
    Device("OCT", "OCT", KIND_DEVICE, "1280x1024", [0, 60, 1280, 964]),
    Device("IVUS Boston", "IVUS", KIND_DEVICE, "1920x1080", [316, 0, 1350, 1080]),
    Device("Camera 1080p", "Cam", KIND_CAMERA, "1920x1080", None),
    Device("Camera 720p", "Cam", KIND_CAMERA, "1280x720", None),
]


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def library_path() -> str:
    """Catalogo accanto all'eseguibile; se la cartella non è scrivibile, in %APPDATA%."""
    p = os.path.join(app_dir(), "catalogo_dispositivi.json")
    try:
        if os.path.exists(p):
            with open(p, "a", encoding="utf-8"):
                pass
        else:
            test = p + ".tmp"
            with open(test, "w", encoding="utf-8") as f:
                f.write("")
            os.remove(test)
        return p
    except OSError:
        d = os.path.join(os.environ.get("APPDATA", app_dir()), "OneViewLayoutGenerator")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, "catalogo_dispositivi.json")


def load_library() -> List[Device]:
    p = library_path()
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return [Device(**d) for d in json.load(f)]
        except (OSError, ValueError, TypeError):
            pass
    lib = [Device(**asdict(d)) for d in DEFAULT_DEVICES]
    save_library(lib)
    return lib


def save_library(lib: List[Device]) -> None:
    with open(library_path(), "w", encoding="utf-8") as f:
        json.dump([asdict(d) for d in lib], f, indent=2, ensure_ascii=False)


def find_device(lib: List[Device], name: str) -> Optional[Device]:
    for d in lib:
        if d.name == name:
            return d
    return None


# ----------------------------------------------------------------- progetto
@dataclass
class Area:
    index: int           # 1..5
    device: str = ""     # nome dispositivo nel catalogo ("" = area non usata)
    source: str = ""     # es. "SLOTDEV_06BC USBMI_02" o "HD Video 1"
    comment: str = ""    # es. "Scopia"
    label: str = ""      # es. "Cam1" / "Fluoro" (usata nei nomi delle viste)


@dataclass
class ViewItem:
    area: int            # numero area
    profile: str = ""    # dispositivo del catalogo (vuoto = quello dell'area)


@dataclass
class View:
    name: str = ""
    items: List[ViewItem] = field(default_factory=list)


@dataclass
class Project:
    name: str = "Nuovo layout"
    audio: str = "VoiceMeeter Output"
    parse_mode: str = "censoringdinamico.dll,0"
    parse_mode_commented: str = "GeneraleParse.dll,0"
    areas: List[Area] = field(default_factory=lambda: [Area(i) for i in range(1, 6)])
    views: List[View] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @staticmethod
    def from_json(text: str) -> "Project":
        d = json.loads(text)
        p = Project(**{k: v for k, v in d.items() if k not in ("areas", "views")})
        p.areas = [Area(**a) for a in d.get("areas", [])]
        p.views = [View(v.get("name", ""), [ViewItem(**i) for i in v.get("items", [])])
                   for v in d.get("views", [])]
        return p

    def area(self, idx: int) -> Optional[Area]:
        for a in self.areas:
            if a.index == idx:
                return a
        return None


# ----------------------------------------------------------------- calcolo
@dataclass
class Placement:
    area: int
    slot: int
    rect: Optional[List[int]]   # None = nessuna riga Rectangle
    ratio: str


@dataclass
class ViewResult:
    slots: List[Tuple[int, int, int, int]]      # in ordine di slot (1..n)
    placements: List[Placement]                 # in ordine di slot
    warnings: List[str] = field(default_factory=list)


def resolve_item(project: Project, lib: List[Device], item: ViewItem):
    a = project.area(item.area)
    if a is None or not a.device:
        raise ValueError(f"Area {item.area} non configurata")
    area_dev = find_device(lib, a.device)
    if area_dev is None:
        raise ValueError(f"Dispositivo '{a.device}' (Area {a.index}) non presente nel catalogo")
    prof = find_device(lib, item.profile) if item.profile else area_dev
    if prof is None:
        raise ValueError(f"Profilo '{item.profile}' non presente nel catalogo")
    return a, area_dev, prof


def camera_crop(slot_w: int, slot_h: int, res: str) -> List[int]:
    """Ritaglio massimo con le proporzioni dello slot, centrato."""
    cw, ch = parse_res(res)
    if slot_w / slot_h <= cw / ch:
        h = ch
        w = min(cw, fev(ch * slot_w / slot_h))
        return [fev((cw - w) / 2), 0, w, h]
    w = cw
    h = min(ch, fev(cw * slot_h / slot_w))
    return [0, fev((ch - h) / 2), w, h]


def item_name(project: Project, lib: List[Device], item: ViewItem) -> str:
    a, area_dev, prof = resolve_item(project, lib, item)
    if prof.is_camera:
        return a.label or f"Cam{a.index}"
    if prof.name == area_dev.name and a.label:
        return a.label
    return prof.sigla or prof.name


def auto_view_name(project: Project, lib: List[Device], view: View) -> str:
    return " + ".join(item_name(project, lib, it) for it in view.items)


def compute_view(project: Project, lib: List[Device], view: View) -> ViewResult:
    items = view.items
    n = len(items)
    if n == 0:
        raise ValueError("Vista vuota")
    if n > 4:
        raise ValueError("Massimo 4 sorgenti per vista")
    areas_used = [it.area for it in items]
    if len(set(areas_used)) != n:
        raise ValueError("La stessa area non può comparire due volte nella stessa vista")

    resolved = [resolve_item(project, lib, it) for it in items]
    warnings: List[str] = []

    # ---- vista singola: schermo intero
    if n == 1:
        a, _, prof = resolved[0]
        if prof.is_camera:
            pl = Placement(a.index, 1, None, "16:9")
        else:
            pl = Placement(a.index, 1, rect_or_none(prof), "1:1")
        return ViewResult([(0, 0, SCREEN_W, SCREEN_H)], [pl], warnings)

    # ---- sorgente grande a destra + colonna a sinistra
    right = resolved[0]
    col = resolved[1:]
    r_prof = right[2]

    if r_prof.is_camera:
        L = SCREEN_W - SCREEN_H  # camera a destra: area 1080x1080
    else:
        L = ev(SCREEN_W - SCREEN_H * r_prof.aspect())

    col_has_scopia = any(p.kind == KIND_SCOPIA for _, _, p in col)
    if col_has_scopia and L < MIN_SCOPIA:
        L = MIN_SCOPIA
    L = max(200, min(L, SCREEN_W - 400))

    ncam = sum(1 for _, _, p in col if p.is_camera)
    avail = SCREEN_H - MIN_CAM_H * ncam if ncam else SCREEN_H

    def fixed_heights(width):
        return [None if p.is_camera else width / p.aspect() for _, _, p in col]

    hs = fixed_heights(L)
    tot = sum(h for h in hs if h is not None)
    if ncam and tot > avail:
        if r_prof.kind == KIND_SCOPIA or r_prof.is_camera:
            # scopia grande a destra: si mantiene la colonna, si comprimono i dispositivi
            k = avail / tot
            hs = [None if h is None else h * k for h in hs]
            warnings.append("Dispositivo in colonna compresso in altezza per lasciare "
                            f"almeno {MIN_CAM_H} px alla telecamera")
        else:
            # dispositivo grande a destra: si restringe la colonna mantenendo le proporzioni
            newL = ev(L * avail / tot)
            if col_has_scopia and newL < MIN_SCOPIA:
                k = avail / tot
                hs = [None if h is None else h * k for h in hs]
                warnings.append("Colonna compressa in altezza (vincoli scopia/camera)")
            else:
                L = newL
                hs = fixed_heights(L)
    elif not ncam:
        tot = sum(hs)
        if abs(tot - SCREEN_H) > 1:
            k = SCREEN_H / tot
            hs = [h * k for h in hs]
            if k < 1:
                warnings.append("Dispositivi in colonna compressi in altezza per stare nello schermo")

    # altezze intere pari; le telecamere si dividono lo spazio rimanente
    fixed = [None if h is None else fev(h) for h in hs]
    rem = SCREEN_H - sum(h for h in fixed if h is not None)
    heights: List[int] = []
    cams_left = ncam
    for h in fixed:
        if h is None:
            ch = rem if cams_left == 1 else ev(rem / cams_left)
            rem -= ch
            cams_left -= 1
            heights.append(ch)
        else:
            heights.append(h)
    if not ncam:
        heights[-1] += SCREEN_H - sum(heights)

    W = SCREEN_W - L
    if r_prof.kind == KIND_SCOPIA and W != SCREEN_H:
        warnings.append(f"Scopia a destra non quadrata ({W}x{SCREEN_H})")

    # slot: 1 = in alto a sinistra, 2 = destra, 3.. = sotto a sinistra
    col_slots = []
    y = 0
    for h in heights:
        col_slots.append((0, y, L, h))
        y += h
    slots = [col_slots[0], (L, 0, W, SCREEN_H)] + col_slots[1:]

    placements = []
    order = [col[0], right] + col[1:]
    for slot_no, ((a, _, prof), s) in enumerate(zip(order, slots), start=1):
        if prof.is_camera:
            rect = camera_crop(s[2], s[3], prof.resolution)
            if s[3] < MIN_CAM_H:
                warnings.append(f"Telecamera (Area {a.index}) alta solo {s[3]} px")
        else:
            rect = rect_or_none(prof)
            if prof.kind == KIND_SCOPIA and slot_no != 2 and min(s[2], s[3]) < MIN_SCOPIA:
                warnings.append(f"Scopia (Area {a.index}) più piccola di {MIN_SCOPIA}x{MIN_SCOPIA}")
        placements.append(Placement(a.index, slot_no, rect, "1:1"))

    return ViewResult(slots, placements, warnings)


def rect_or_none(prof: Device) -> Optional[List[int]]:
    """Il rectangle si omette se coincide con l'intero segnale (come per SyncVision)."""
    if not prof.rect:
        return None
    w, h = parse_res(prof.resolution)
    if list(prof.rect) == [0, 0, w, h]:
        return None
    return list(prof.rect)


# ----------------------------------------------------------------- scrittura .ini
def generate_ini(project: Project, lib: List[Device]) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    out = ["[Info]", f"Name={project.name}", f"AudioSourceName={project.audio}"]
    if project.parse_mode_commented:
        out.append(f";ParseMode={project.parse_mode_commented}")
    if project.parse_mode:
        out.append(f"ParseMode={project.parse_mode}")
    out += ["", "[Sources]"]

    used = [a for a in project.areas if a.device]
    for a in used:
        if a.comment:
            out.append(f";{a.comment}")
        out.append(f"Area{a.index}={a.source}")
        out.append("")
        if not a.source:
            warnings.append(f"Area {a.index}: sorgente (slot) non indicata")

    out.append("[Resolutions]")
    for a in used:
        d = find_device(lib, a.device)
        res = d.resolution if d else "1920x1080"
        out.append(f"Resolution{a.index}={res}")
    out += ["", "[Censoring]", "", "[Views]"]

    names = [f"View{i}" for i in range(1, len(project.views) + 1)]
    out.append("View=" + ",".join(names))
    out.append("")

    for i, v in enumerate(project.views, start=1):
        try:
            res = compute_view(project, lib, v)
        except ValueError as e:
            warnings.append(f"View{i}: {e}")
            continue
        name = v.name.strip() or auto_view_name(project, lib, v)
        for w in res.warnings:
            warnings.append(f"View{i} ({name}): {w}")
        n = len(res.slots)
        out.append(f"[View{i}]")
        out.append(f"Name={name}")
        out.append(f"Locations={n}")
        out.append(f"Layout{n}=" + ",".join(",".join(str(c) for c in s) for s in res.slots))
        if n > 1:
            out.append("")
        for pl in res.placements:
            out.append(f"Location{pl.area}={pl.slot}")
            if pl.rect:
                out.append(f"Rectangle{pl.area}=" + ",".join(str(c) for c in pl.rect))
            out.append(f"Ratio{pl.area}={pl.ratio}")
            if n > 1:
                out.append("")
        if n == 1:
            out.append("")
    return "\n".join(out).rstrip() + "\n", warnings


# ----------------------------------------------------------------- import .ini
def _parse_ini(text: str):
    sections = {}
    order = []
    cur = None
    pending_comment = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1].strip()
            sections[cur] = {"__comments__": {}}
            order.append(cur)
            pending_comment = ""
            continue
        if cur is None:
            continue
        if line.startswith(";"):
            pending_comment = line[1:].strip()
            if cur == "Info" and line[1:].lower().startswith("parsemode="):
                sections[cur]["__parsemode_commented__"] = line.split("=", 1)[1].strip()
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            sections[cur][k.lower()] = v.strip()
            if pending_comment:
                sections[cur]["__comments__"][k.lower()] = pending_comment
            pending_comment = ""
    return sections, order


def import_ini(text: str, lib: List[Device]) -> Tuple[Project, List[str]]:
    """Legge un layout esistente: ricostruisce aree e viste e impara nel catalogo
    i rectangle dei dispositivi che non conosce ancora. Restituisce (progetto, note)."""
    secs, _ = _parse_ini(text)
    notes: List[str] = []
    info = secs.get("Info", {})
    p = Project(
        name=info.get("name", "Layout importato"),
        audio=info.get("audiosourcename", ""),
        parse_mode=info.get("parsemode", ""),
        parse_mode_commented=info.get("__parsemode_commented__", ""),
    )
    src = secs.get("Sources", {})
    resl = secs.get("Resolutions", {})
    for a in p.areas:
        a.source = src.get(f"area{a.index}", "")
        a.comment = src["__comments__"].get(f"area{a.index}", "")

    view_names = [v.strip() for v in secs.get("Views", {}).get("view", "").split(",") if v.strip()]
    for s in secs:
        if s.lower().startswith("view") and s not in view_names and s != "Views":
            view_names.append(s)
            notes.append(f"{s} presente nel file ma non elencata in [Views]: importata comunque")

    def is_cam_area(idx: int) -> bool:
        a = p.area(idx)
        txt = (a.comment + " " + a.source).lower()
        return "cam" in txt or "hd video" in txt

    # raccoglie per ogni area i rectangle usati e i nomi
    raw_views = []
    for vn in view_names:
        sec = secs.get(vn)
        if not sec:
            continue
        locs = {}
        for k, v in sec.items():
            if k.startswith("location") and k[8:].isdigit():
                ai = int(k[8:])
                rect = sec.get(f"rectangle{ai}")
                locs[int(v)] = (ai, parse_rect(rect) if rect else None, sec.get(f"ratio{ai}", "1:1"))
        n = len(locs)
        parts = [x.strip() for x in sec.get("name", "").split("+")]
        slot_order = [1] if n == 1 else [2, 1] + list(range(3, n + 1))
        raw_views.append((sec.get("name", vn).strip(), locs, slot_order, parts))

    learned = []
    for vname, locs, slot_order, parts in raw_views:
        items = []
        for pos, slot in enumerate(slot_order):
            if slot not in locs:
                continue
            ai, rect, ratio = locs[slot]
            a = p.area(ai)
            part = parts[pos] if pos < len(parts) else f"Area{ai}"
            res = resl.get(f"resolution{ai}", "1920x1080")
            cam = is_cam_area(ai) or (ratio == "16:9" and rect is None)
            if cam:
                dev = next((d for d in lib if d.is_camera and d.resolution == res), None)
                if dev is None:
                    dev = Device(f"Camera {res}", "Cam", KIND_CAMERA, res, None)
                    lib.append(dev)
                    learned.append(dev.name)
                if not a.label:
                    a.label = part
            else:
                full = [0, 0] + list(parse_res(res))
                eff = rect or full
                dev = next((d for d in lib if not d.is_camera and d.resolution == res
                            and d.effective_rect() == eff), None)
                if dev is None:
                    kind = KIND_SCOPIA if eff[2] == eff[3] else KIND_DEVICE
                    base = (a.comment or part).strip() or f"Dispositivo Area{ai}"
                    nm, k = base, 2
                    while find_device(lib, nm):
                        nm = f"{base} ({k})"
                        k += 1
                    dev = Device(nm, part, kind, res, rect)
                    lib.append(dev)
                    learned.append(nm)
            if not a.device:
                a.device = dev.name
                if not a.label and not dev.is_camera:
                    a.label = part
            items.append(ViewItem(ai, "" if dev.name == a.device else dev.name))
        p.views.append(View(vname, items))

    for a in p.areas:
        if (a.source or a.comment) and not a.device:
            notes.append(f"Area {a.index} non usata in nessuna vista: scegli il dispositivo a mano")
    if learned:
        notes.append("Aggiunti al catalogo: " + ", ".join(learned))
    return p, notes
