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
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

SCREEN_W, SCREEN_H = 1920, 1080   # i calcoli si fanno sempre in Full HD e poi si scalano
SCREENS = {"Full HD 1920×1080": "1920x1080", "HD 1280×720": "1280x720"}
MIN_SCOPIA = 600
MIN_CAM_H = 400
MIN_SLOT = 100   # dimensione minima di uno slot spostando i divisori a mano
MIN_CAM_H_BG = 250   # con lo sfondo la cornice toglie spazio: la telecamera può scendere fino a qui
# cornice con lo sfondo, nelle unità dello schermo: (margine alto, cornice lati/basso/tra i segnali)
BG_DEFAULTS = {"1920x1080": (80, 30), "1280x720": (50, 20)}
BG_FILE = "Sfondo.png"

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
    # righe da aggiungere in [Info] sotto ParseMode quando il dispositivo è usato,
    # separate da ";" (es. "PelcoCamera2Source=Y"); {area} = numero dell'area
    info_lines: str = ""

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
    Device("Scopia", "LIVE", KIND_SCOPIA, "1920x1080", [0, 32, 960, 960]),
    Device("Poligrafo", "POLY", KIND_DEVICE, "1600x1200", [10, 290, 1556, 822]),
    Device("Ecografo GE", "ECHO", KIND_DEVICE, "1600x1200", [0, 64, 1600, 1136]),
    Device("IVUS Volcano", "IVUS", KIND_DEVICE, "1280x1024", [14, 84, 1186, 866]),
    Device("FFR Volcano", "FFR", KIND_DEVICE, "1280x1024", [0, 78, 1280, 946]),
    Device("SyncVision", "SYNC", KIND_DEVICE, "1280x1024", None),
    Device("OCT", "OCT", KIND_DEVICE, "1280x1024", [0, 60, 1280, 964]),
    Device("IVUS Boston", "IVUS", KIND_DEVICE, "1920x1080", [316, 0, 1350, 1080]),
    Device("Camera 1080p", "CAM", KIND_CAMERA, "1920x1080", None),
    Device("Camera 720p", "CAM", KIND_CAMERA, "1280x720", None),
]


OBSBOT_INFO = "PelcoCamera2Source=Y"


def device_info_lines(d: "Device", area_index: int) -> List[str]:
    return [ln.strip().replace("{area}", str(area_index))
            for ln in (d.info_lines or "").replace("\n", ";").split(";") if ln.strip()]


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


LIB_NAME = "catalogo_dispositivi.ini"
OLD_LIB_NAME = "catalogo_dispositivi.json"   # formato delle versioni precedenti: convertito in automatico
LIB_HEADER = """\
; Catalogo dispositivi di OneView Layout Generator
; Si può modificare anche con il Blocco note: il programma lo ricarica da solo.
; Un dispositivo per sezione: [Nome del dispositivo]
;   Sigla       = nome breve (LIVE, POLY, ECHO, IVUS, OCT, CAM...)
;   Tipo        = dispositivo, scopia oppure camera
;   Risoluzione = larghezza x altezza del segnale, es. 1920x1080
;   Rectangle   = x,y,larghezza,altezza della parte utile del segnale
;                 (vuoto = segnale intero; per le camere resta vuoto, viene calcolato)
;   RigheInfo   = righe da aggiungere in [Info] quando il dispositivo è usato
;                 (più righe separate da ; oppure ripetendo RigheInfo=; {area} = numero dell'area)
; Le righe che iniziano con ; sono commenti.
"""

_known_mtime: Optional[float] = None   # ultima versione del file letta o scritta dal programma
last_load_errors: List[str] = []       # problemi trovati nell'ultima lettura del file


def library_path() -> str:
    """Catalogo accanto all'eseguibile; se la cartella non è scrivibile, in %APPDATA%."""
    p = os.path.join(app_dir(), LIB_NAME)
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
        return os.path.join(d, LIB_NAME)


def library_to_text(lib: List[Device]) -> str:
    out = [LIB_HEADER]
    for d in lib:
        out.append(f"[{d.name}]")
        out.append(f"Sigla={d.sigla}")
        out.append(f"Tipo={d.kind}")
        out.append(f"Risoluzione={d.resolution}")
        out.append("Rectangle=" + (",".join(map(str, d.rect)) if d.rect and not d.is_camera else ""))
        out.append(f"RigheInfo={d.info_lines}")
        out.append("")
    return "\n".join(out)


def library_from_text(text: str) -> Tuple[List[Device], List[str]]:
    """Legge il catalogo in formato .ini. Restituisce (dispositivi, errori);
    un dispositivo con dati non validi viene saltato e segnalato con il numero di riga."""
    lib: List[Device] = []
    errors: List[str] = []
    cur = None   # [nome, riga, {chiave: valore}, [righe info]]
    blocks = []
    for no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = [line[1:-1].strip(), no, {}, []]
            blocks.append(cur)
            continue
        if cur is None:
            errors.append(f"Riga {no}: «{line}» fuori da una sezione [Nome]")
            continue
        if "=" not in line:
            errors.append(f"Riga {no} ({cur[0]}): manca il segno = in «{line}»")
            continue
        k, v = (x.strip() for x in line.split("=", 1))
        k = k.lower().replace(" ", "")
        if k in ("righeinfo", "info"):
            if v:
                cur[3].append(v)
        else:
            cur[2][k] = v
    kinds = {"dispositivo": KIND_DEVICE, "device": KIND_DEVICE, "scopia": KIND_SCOPIA,
             "camera": KIND_CAMERA, "telecamera": KIND_CAMERA, "cam": KIND_CAMERA}
    for name, no, kv, info in blocks:
        where = f"[{name}] (riga {no})"
        try:
            if not name:
                raise ValueError("nome vuoto")
            if find_device(lib, name):
                raise ValueError("nome già usato da un altro dispositivo")
            kind = kinds.get(kv.get("tipo", "dispositivo").lower())
            if kind is None:
                raise ValueError(f"Tipo «{kv.get('tipo')}» non valido (dispositivo, scopia o camera)")
            res = kv.get("risoluzione", "").lower().replace(" ", "")
            try:
                rw, rh = parse_res(res)
            except ValueError:
                raise ValueError(f"Risoluzione «{kv.get('risoluzione', '')}» non valida (es. 1920x1080)")
            rect = None
            if kind != KIND_CAMERA:
                try:
                    rect = parse_rect(kv.get("rectangle", ""))
                except ValueError:
                    raise ValueError(f"Rectangle «{kv.get('rectangle')}» non valido (x,y,larghezza,altezza)")
                if rect and (rect[2] <= 0 or rect[3] <= 0 or rect[0] + rect[2] > rw or rect[1] + rect[3] > rh):
                    raise ValueError(f"Rectangle {kv.get('rectangle')} esce dalla risoluzione {rw}x{rh}")
            lib.append(Device(name, kv.get("sigla", "") or name, kind, f"{rw}x{rh}", rect, ";".join(info)))
        except ValueError as e:
            errors.append(f"{where}: {e} — dispositivo non caricato")
    return lib, errors


def _read_text(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    for enc in ("utf-8", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def library_changed_outside() -> bool:
    """True se il file del catalogo è stato modificato fuori dal programma."""
    try:
        return os.path.getmtime(library_path()) != _known_mtime
    except OSError:
        return False


def load_library() -> List[Device]:
    """Legge il catalogo. Se il file ha errori i dispositivi validi vengono caricati,
    gli altri segnalati in last_load_errors e il file viene copiato per non perdere nulla."""
    global _known_mtime, last_load_errors
    last_load_errors = []
    p = library_path()
    if not os.path.exists(p):
        old = os.path.join(os.path.dirname(p), OLD_LIB_NAME)
        lib = None
        if os.path.exists(old):   # conversione dal vecchio catalogo .json
            try:
                with open(old, encoding="utf-8") as f:
                    lib = [Device(**d) for d in json.load(f)]
                os.replace(old, old + ".vecchio")
            except (OSError, ValueError, TypeError):
                lib = None
        if lib is None:
            lib = [Device(**asdict(d)) for d in DEFAULT_DEVICES]
        save_library(lib)
        return lib
    try:
        text = _read_text(p)
    except OSError as e:
        last_load_errors = [f"Impossibile leggere {p}: {e}"]
        return [Device(**asdict(d)) for d in DEFAULT_DEVICES]
    lib, errors = library_from_text(text)
    _known_mtime = os.path.getmtime(p)
    if errors:
        last_load_errors = errors
        # copia del file così com'è: le correzioni fatte nel programma non fanno perdere i dati
        try:
            with open(os.path.splitext(p)[0] + " (copia con errori).ini", "w", encoding="utf-8-sig") as f:
                f.write(text)
        except OSError:
            pass
        return lib
    changed = False
    for d in lib:
        if "obsbot" in d.name.lower() and not d.info_lines:
            d.info_lines = OBSBOT_INFO
            changed = True
    if changed:
        save_library(lib)
    return lib


def save_library(lib: List[Device]) -> None:
    global _known_mtime
    p = library_path()
    with open(p, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(library_to_text(lib))
    _known_mtime = os.path.getmtime(p)


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
    alias: str = ""      # nome forzato nella vista (es. "HEMO")


@dataclass
class View:
    name: str = ""
    items: List[ViewItem] = field(default_factory=list)
    col_width: int = 0          # larghezza colonna sinistra impostata a mano (0 = automatica)
    heights: List[int] = field(default_factory=list)  # altezze in colonna a mano ([] = automatiche)

    @property
    def is_manual(self) -> bool:
        return bool(self.col_width or self.heights)

    def reset_geometry(self) -> None:
        self.col_width = 0
        self.heights = []


@dataclass
class Project:
    name: str = "Nuovo layout"
    audio: str = "VoiceMeeter Output"
    parse_mode: str = "GeneraleParse.dll,0"   # i dispositivi possono sostituirlo (es. censoringdinamico)
    parse_mode_commented: str = ""
    screen: str = "1920x1080"    # schermo OneView: "1920x1080" (Full HD) o "1280x720" (HD)
    background: bool = False     # sfondo: riga BackgroundBitMap + segnali separati da una cornice
    background_file: str = BG_FILE
    bg_top: int = 80             # margine alto (unità dello schermo scelto)
    bg_frame: int = 30           # cornice lati/basso e spazio tra i segnali
    extra_info: List[str] = field(default_factory=list)  # altre righe [Info] lette da un .ini
    areas: List[Area] = field(default_factory=lambda: [Area(i) for i in range(1, 6)])
    views: List[View] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)

    @staticmethod
    def from_json(text: str) -> "Project":
        d = json.loads(text)
        p = Project(**{k: v for k, v in d.items() if k not in ("areas", "views")})
        p.areas = [Area(**a) for a in d.get("areas", [])]
        p.views = [View(v.get("name", ""), [ViewItem(**i) for i in v.get("items", [])],
                        v.get("col_width", 0), v.get("heights", []))
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
    info: List[str] = field(default_factory=list)   # note solo per l'anteprima (deformazioni)
    slots_fhd: List[Tuple[int, int, int, int]] = field(default_factory=list)  # stessi slot in Full HD


def screen_scale(project: "Project") -> float:
    return parse_res(project.screen or "1920x1080")[0] / SCREEN_W


def frame_box(project: "Project"):
    """Spazio utile in Full HD: (x0, y0, larghezza, altezza, spazio tra i segnali).
    Senza sfondo è lo schermo intero; con lo sfondo si tolgono margine alto e cornice."""
    if not project.background:
        return 0, 0, SCREEN_W, SCREEN_H, 0
    k = screen_scale(project)
    top = int(round(max(0, project.bg_top) / k))
    fr = int(round(max(0, project.bg_frame) / k))
    return fr, top, SCREEN_W - 2 * fr, SCREEN_H - top - fr, fr


def convert_frame(project: "Project", new_screen: str) -> None:
    """Passando da Full HD a HD (o viceversa) la cornice segue lo schermo: i valori
    predefiniti diventano quelli dell'altro schermo, quelli personalizzati si riscalano."""
    old = BG_DEFAULTS.get(project.screen)
    new = BG_DEFAULTS.get(new_screen)
    ox, oy, ocw, och, og = frame_box(project)
    if old and new and (project.bg_top, project.bg_frame) == old:
        project.bg_top, project.bg_frame = new
    else:
        k = parse_res(new_screen)[0] / parse_res(project.screen)[0]
        project.bg_top, project.bg_frame = int(round(project.bg_top * k)), int(round(project.bg_frame * k))
    project.screen = new_screen
    # le misure fissate a mano seguono lo spazio utile (che può cambiare di qualche pixel)
    nx, ny, ncw, nch, ng = frame_box(project)
    for v in project.views:
        if v.col_width and ocw - og > 0:
            v.col_width = ev(v.col_width * (ncw - ng) / (ocw - og))
        m = len(v.heights)
        oc, nc = och - og * (m - 1), nch - ng * (m - 1)
        if m and oc > 0 and oc != nc:
            total = int(round(sum(v.heights) * nc / oc))
            hs = [ev(h * nc / oc) for h in v.heights[:-1]]
            v.heights = hs + [total - sum(hs)]


def scale_slots(slots, k: float):
    """Scala gli slot spostando i bordi, così restano contigui e senza buchi."""
    if k == 1:
        return [tuple(sl) for sl in slots]
    out = []
    for x, y, w, h in slots:
        x0, y0, x1, y1 = ev(x * k), ev(y * k), ev((x + w) * k), ev((y + h) * k)
        out.append((x0, y0, x1 - x0, y1 - y0))
    return out


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


def dev_class(d: Device) -> str:
    """Nome standard del tipo di sorgente: LIVE, CAM, POLY, ECHO, IVUS, OCT, FFR, SYNC..."""
    if d.is_camera:
        return "CAM"
    if d.kind == KIND_SCOPIA:
        return "LIVE"
    n = (d.name + " " + d.sigla).lower()
    for rx, cls in [(r"\b(ffr|ifr)", "FFR"), (r"sync", "SYNC"), (r"\boct\b", "OCT"),
                    (r"ivus|volcano|boston", "IVUS"), (r"poly|polig|hemo|emodin|maclab", "POLY"),
                    (r"\beco|echo|ultras", "ECHO"), (r"scopia|fluoro|angio|live", "LIVE")]:
        if re.search(rx, n):
            return cls
    return (d.sigla or d.name).upper()


def item_name(project: Project, lib: List[Device], item: ViewItem) -> str:
    a, area_dev, prof = resolve_item(project, lib, item)
    if item.alias:
        return item.alias
    if prof.is_camera:
        cams = [x for x in project.areas
                if x.device and find_device(lib, x.device) and find_device(lib, x.device).is_camera]
        if len(cams) <= 1:
            return "CAM"
        num = re.sub(r"\D", "", a.label or "") or str([c.index for c in cams].index(a.index) + 1)
        return f"CAM{num}"
    return dev_class(prof)


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
    # spazio utile (con lo sfondo: dentro la cornice) e spazio tra i segnali
    X0, Y0, CW, CH, G = frame_box(project)

    # ---- vista singola: schermo intero (con lo sfondo: tutto lo spazio dentro la cornice)
    if n == 1:
        a, _, prof = resolved[0]
        if prof.is_camera:
            pl = Placement(a.index, 1, None, "16:9")
        else:
            pl = Placement(a.index, 1, rect_or_none(prof), "1:1")
        full = [(X0, Y0, CW, CH)]
        if prof.is_camera and project.background:
            # camera 16:9 centrata nello spazio dentro la cornice
            w, h = (ev(CH * 16 / 9), CH) if CW / CH > 16 / 9 else (CW, ev(CW * 9 / 16))
            full = [(X0 + int(round((CW - w) / 2)), Y0 + int(round((CH - h) / 2)), w, h)]
        return ViewResult(scale_slots(full, screen_scale(project)), [pl], warnings, [], full)

    # ---- sorgente grande a destra + colonna a sinistra
    right = resolved[0]
    col = resolved[1:]
    r_prof = right[2]
    colH = CH - G * (len(col) - 1)   # altezza della colonna senza gli spazi tra i segnali

    col_has_scopia = any(p.kind == KIND_SCOPIA for _, _, p in col)
    if r_prof.is_camera:
        # camera grande a destra: la colonna è larga quanto serve (scopia 600x600)
        L = MIN_SCOPIA if col_has_scopia else CW - G - CH
    else:
        L = ev(CW - G - CH * r_prof.aspect())

    if col_has_scopia and L < MIN_SCOPIA:
        L = MIN_SCOPIA
    L = max(200, min(L, CW - G - 400))
    manual_w = bool(view.col_width)
    if manual_w:
        L = max(MIN_SLOT, min(ev(view.col_width), CW - G - MIN_SLOT))

    ncam = sum(1 for _, _, p in col if p.is_camera)
    cam_min = MIN_CAM_H_BG if project.background else MIN_CAM_H
    avail = colH - cam_min * ncam if ncam else colH

    def fixed_heights(width):
        return [None if p.is_camera else width / p.aspect() for _, _, p in col]

    hs = fixed_heights(L)
    tot = sum(h for h in hs if h is not None)
    if ncam and tot > avail:
        if r_prof.kind == KIND_SCOPIA or r_prof.is_camera or manual_w:
            # scopia grande a destra (o colonna fissata a mano): si mantiene la colonna, si comprimono i dispositivi
            k = avail / tot
            hs = [None if h is None else h * k for h in hs]
            warnings.append("Dispositivo in colonna compresso in altezza per lasciare "
                            f"almeno {ev(cam_min * screen_scale(project))} px alla telecamera")
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
        # senza telecamere in colonna: le proporzioni si mantengono e la colonna
        # viene centrata in verticale; si comprime solo se non entra nello schermo
        tot = sum(hs)
        if tot > colH:
            k = colH / tot
            hs = [h * k for h in hs]
            warnings.append("Dispositivi in colonna compressi in altezza per stare nello schermo")

    # altezze intere pari; le telecamere si dividono lo spazio rimanente
    fixed = [None if h is None else fev(h) for h in hs]
    rem = colH - sum(h for h in fixed if h is not None)
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
    y0 = 0
    if not ncam:
        gap = colH - sum(heights)
        if gap > 0:
            y0 = fev(gap / 2)
        else:
            heights[-1] += gap

    if view.heights and len(view.heights) == len(col):
        heights = [max(MIN_SLOT, ev(h)) for h in view.heights]
        tot = sum(heights)
        if tot > colH:
            heights[-1] = max(MIN_SLOT, heights[-1] - (tot - colH))
            tot = sum(heights)
        y0 = fev((colH - tot) / 2) if tot < colH else 0
    elif ncam and manual_w:
        pass  # altezze automatiche sulla nuova larghezza

    W = CW - G - L
    if r_prof.kind == KIND_SCOPIA and abs(W - CH) > 2 and not view.is_manual:
        warnings.append(f"Scopia a destra non quadrata ({W}x{CH})")

    # slot in senso antiorario: 1 = in alto a sinistra, poi in giù lungo la colonna,
    # ultimo = grande a destra (es. 3 segnali: 1 alto sx, 2 basso sx, 3 destra)
    col_slots = []
    y = Y0 + y0
    for h in heights:
        col_slots.append((X0, y, L, h))
        y += h + G
    slots = col_slots + [(X0 + L + G, Y0, W, CH)]
    n_slots = len(slots)

    k = screen_scale(project)
    out_slots = scale_slots(slots, k)
    placements = []
    order = list(col) + [right]
    for slot_no, ((a, _, prof), s, so) in enumerate(zip(order, slots, out_slots), start=1):
        if prof.is_camera:
            rect = camera_crop(so[2], so[3], prof.resolution)
            if s[3] < cam_min - 1:
                warnings.append(f"Telecamera (Area {a.index}) alta solo {so[3]} px")
        else:
            rect = rect_or_none(prof)
            if prof.kind == KIND_SCOPIA and slot_no != n_slots and min(s[2], s[3]) < MIN_SCOPIA:
                m = ev(MIN_SCOPIA * k)
                warnings.append(f"Scopia (Area {a.index}) più piccola di {m}x{m}")
        placements.append(Placement(a.index, slot_no, rect, "1:1"))

    info = []
    for (a, _, prof), s, it in zip(order, slots, list(items[1:]) + [items[0]]):
        if prof.is_camera:
            continue
        d = (s[2] / s[3]) / prof.aspect() - 1
        if abs(d) > 0.03:
            verso = "allargato" if d > 0 else "stretto"
            info.append(f"{item_name(project, lib, it)}: {verso} del {abs(d) * 100:.0f}% (proporzioni non rispettate)")
    return ViewResult(out_slots, placements, warnings, info, slots)


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
    if project.background:
        out.append(f"BackgroundBitMap='{project.background_file.strip().strip(chr(39)) or BG_FILE}'")

    def key(ln):
        return ln.split("=", 1)[0].strip().lower()

    def value(ln):
        return ln.split("=", 1)[1].strip() if "=" in ln else ""

    # le chiavi gestite da un dispositivo del catalogo compaiono solo se quel dispositivo è usato
    managed = {key(ln) for d in lib for ln in device_info_lines(d, 0)}
    extra = [ln for ln in project.extra_info if key(ln) not in managed and key(ln) != "backgroundbitmap"]
    for a in project.areas:
        d = find_device(lib, a.device) if a.device else None
        if d:
            extra += device_info_lines(d, a.index)
    lines, seen = [], set()
    for ln in extra:
        if key(ln) not in seen:  # una sola riga per chiave (prima quella del file, poi dei dispositivi)
            seen.add(key(ln))
            lines.append(ln)

    # ParseMode: un dispositivo che ne indica uno (es. censoringdinamico) sostituisce quello
    # predefinito, che resta nel file come commento
    dev_parse = next((ln for ln in lines if key(ln) == "parsemode"), None)
    commented = [project.parse_mode_commented] if project.parse_mode_commented else []
    active = project.parse_mode
    if dev_parse and active and active != value(dev_parse):
        commented.append(active)
    if dev_parse:
        active = value(dev_parse)
    for c in dict.fromkeys(commented):
        if c != active:
            out.append(f";ParseMode={c}")
    if active:
        out.append(f"ParseMode={active}")
    out += [ln for ln in lines if key(ln) != "parsemode"]
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


def _keep_file_geometry(view: View, file_slots: List[tuple], project: Project, lib: List[Device]) -> None:
    """Se le misure del file sono diverse da quelle automatiche ma rappresentabili
    (colonna a sinistra + sorgente a destra), le conserva come impostazioni manuali.
    file_slots è già nell'ordine del programma: [colonna dall'alto in basso..., destra]."""
    n = len(view.items)
    if n < 2 or len(file_slots) != n:
        return
    try:
        if [tuple(x) for x in compute_view(project, lib, view).slots] == file_slots:
            return  # coincide con il calcolo automatico (confronto nelle unità del file)
    except ValueError:
        return
    k = screen_scale(project)
    g = project.bg_frame if project.background else 0
    x0, L = file_slots[0][0], file_slots[0][2]
    col = file_slots[:-1]
    if file_slots[-1][0] < x0 + L or any(abs(c[0] - x0) > 2 or abs(c[2] - L) > 2 for c in col):
        return
    if any(abs(col[i][1] + col[i][3] + g - col[i + 1][1]) > 2 for i in range(len(col) - 1)):
        return
    # misure manuali salvate in Full HD (i calcoli interni sono sempre in Full HD)
    view.col_width = ev(L / k)
    view.heights = [ev(c[3] / k) for c in col]


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
            if cur == "Info" and k.lower() not in ("name", "audiosourcename", "parsemode"):
                sections[cur].setdefault("__extra__", []).append(f"{k}={v.strip()}")
            if pending_comment:
                sections[cur]["__comments__"][k.lower()] = pending_comment
            pending_comment = ""
    return sections, order


def _match_camera(lib: List[Device], res: str, area: "Area", file_info: List[str]) -> Optional[Device]:
    """Sceglie la telecamera del catalogo per un'area: quella nominata nel commento dell'area
    (es. ";Minicam OBSBOT"), altrimenti la prima con la stessa risoluzione senza righe [Info]."""
    cams = [d for d in lib if d.is_camera and d.resolution == res]
    if not cams:
        return None
    comment = (area.comment or "").lower()
    for d in cams:
        if d.name.lower() in comment or (comment and comment in d.name.lower()):
            return d
    plain = [d for d in cams if not d.info_lines]
    return (plain or cams)[0]


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
        extra_info=list(info.get("__extra__", [])),
    )
    src = secs.get("Sources", {})
    resl = secs.get("Resolutions", {})
    for a in p.areas:
        a.source = src.get(f"area{a.index}", "")
        a.comment = src["__comments__"].get(f"area{a.index}", "")

    view_names = [v.strip() for v in secs.get("Views", {}).get("view", "").split(",") if v.strip()]
    right_edge = 0
    for sname, sec in secs.items():
        for k, v in sec.items():
            if sname.lower().startswith("view") and k.startswith("layout") and k[6:].isdigit():
                try:
                    nums = [int(x) for x in v.split(",")]
                    right_edge = max(right_edge, max(nums[i] + nums[i + 2] for i in range(0, len(nums) - 3, 4)))
                except ValueError:
                    pass
    if 0 < right_edge <= 1280:
        p.screen = "1280x720"
        notes.append("Layout per schermo HD 1280×720")
    # sfondo: riga BackgroundBitMap; cornice dedotta dalle viste del file
    bg = next((ln for ln in p.extra_info if ln.lower().startswith("backgroundbitmap=")), None)
    if bg:
        p.extra_info.remove(bg)
        p.background = True
        p.background_file = bg.split("=", 1)[1].strip().strip("'\"") or BG_FILE
        p.bg_top, p.bg_frame = BG_DEFAULTS[p.screen]
        xs, ys = [], []
        for sname, sec in secs.items():
            if not sname.lower().startswith("view"):
                continue
            for k, v in sec.items():
                if k.startswith("layout") and k[6:].isdigit() and int(k[6:]) > 1:
                    try:
                        nums = [int(x) for x in v.split(",")]
                    except ValueError:
                        continue
                    xs += nums[0::4]
                    ys += nums[1::4]
        if xs and ys and min(xs) > 0 and min(ys) > 0:
            p.bg_top, p.bg_frame = min(ys), min(xs)
        notes.append(f"Sfondo {p.background_file}: margine alto {p.bg_top}, cornice {p.bg_frame}")
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
        file_slots = []
        try:
            vals = [int(x) for x in sec.get(f"layout{n}", "").split(",")]
            if n > 1 and len(vals) == 4 * n:
                geo = [tuple(vals[i:i + 4]) for i in range(0, len(vals), 4)]
                # la sorgente grande è quella più a destra (a parità, la più alta);
                # le altre formano la colonna dall'alto in basso, qualunque sia la numerazione del file
                big = max(range(n), key=lambda i: (geo[i][0], geo[i][3]))
                rest = sorted((i for i in range(n) if i != big), key=lambda i: geo[i][1])
                slot_order = [big + 1] + [i + 1 for i in rest]
                file_slots = [geo[i] for i in rest] + [geo[big]]
        except ValueError:
            pass
        raw_views.append((sec.get("name", vn).strip(), locs, slot_order, parts, file_slots))

    learned = []
    for vname, locs, slot_order, parts, file_slots in raw_views:
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
                dev = _match_camera(lib, res, a, p.extra_info)
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
                    words = re.findall(r"[\w-]+", f"{a.comment} {part}")
                    is_live = eff[2] == eff[3] or any(word_class(w) == "LIVE" for w in words)
                    kind = KIND_SCOPIA if is_live else KIND_DEVICE
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
        view = View("", items)  # nomi standard (LIVE, CAM, POLY...) ricalcolati
        if len(items) == len(file_slots):
            _keep_file_geometry(view, file_slots, p, lib)
        p.views.append(view)

    for a in p.areas:
        # aree non usate in nessuna vista: si riconosce il dispositivo dal commento
        if a.source and not a.device and a.comment:
            res = resl.get(f"resolution{a.index}", "")
            c = a.comment.lower()
            hit = [d for d in lib if d.resolution == res and (d.name.lower() in c or c in d.name.lower())]
            if hit:
                a.device = hit[0].name
                if hit[0].is_camera:
                    n = 1 + sum(1 for b in p.areas if b.index < a.index and b.device
                                and find_device(lib, b.device) and find_device(lib, b.device).is_camera)
                    a.label = a.label or f"CAM{n}"
                else:
                    a.label = a.label or dev_class(hit[0])
    for a in p.areas:
        if (a.source or a.comment) and not a.device:
            notes.append(f"Area {a.index} non usata in nessuna vista: scegli il dispositivo a mano")
    if learned:
        notes.append("Aggiunti al catalogo: " + ", ".join(learned))
    return p, notes


# ----------------------------------------------------------------- vista da testo
# Separatori ammessi tra le sorgenti: + , ; & / "e" "and" "con"
_SEP_RE = re.compile(r"\s*(?:\+|,|;|&|/|\be\b|\bed\b|\band\b|\bcon\b)\s*", re.IGNORECASE)
# Parole che indicano la sorgente grande (va a destra)
_BIG_RE = re.compile(r"\b(grande|grandi|big|large|principale|intero|intera|full|destra)\b", re.IGNORECASE)
# Parole di contorno da ignorare
_NOISE_RE = re.compile(
    r"\b(grande|grandi|piccol[aoie]|big|small|large|principale|intero|intera|full|schermo|"
    r"in|a|al|alla|da|di|del|della|destra|sinistra|alto|basso|sopra|sotto|solo|sola|"
    r"il|lo|la|le|i|gli|l)\b", re.IGNORECASE)

_CAMERA_RE = re.compile(r"^(?:cam|camera|cams|telecamera|videocamera|tele|webcam|telecam|room|sala)(\d*)$")

# parola scritta (normalizzata) -> nome standard
_WORD_CLASSES = [
    (re.compile(r"^(scopia|scopie|fluoro\w*|live|angio\w*|x-?rays?|rx|raggi\w*|cathlab|radioscopia)$"), "LIVE"),
    (re.compile(r"^(ffr|ifr|pressure|pressione)$"), "FFR"),
    (re.compile(r"^(sync\w*)$"), "SYNC"),
    (re.compile(r"^(oct|optis)$"), "OCT"),
    (re.compile(r"^(ivus\w*|volcano\w*|boston\w*|philips\w*)$"), "IVUS"),
    (re.compile(r"^(hemo\w*|haemo\w*|emo|emodinamic\w*)$"), "HEMO"),
    (re.compile(r"^(poly\w*|polig\w*|poli|mac-?lab|monitor\w*)$"), "POLY"),
    (re.compile(r"^(eco\w*|echo\w*|ultrasound\w*|ultrasuon\w*|us)$"), "ECHO"),
]


def _norm(s: str) -> str:
    return re.sub(r"[\s_\.']+", "", s.lower())


def word_class(token: str) -> Optional[str]:
    t = _norm(token)
    if _CAMERA_RE.match(t):
        return "CAM"
    for rx, cls in _WORD_CLASSES:
        if rx.match(t):
            return cls
    return None


def _same_family(a: "Device", b: "Device") -> bool:
    """Due profili dello stesso apparecchio condividono una parola del nome (es. 'Volcano')."""
    wa = set(re.findall(r"[a-z0-9]{3,}", a.name.lower()))
    wb = set(re.findall(r"[a-z0-9]{3,}", b.name.lower()))
    return bool(wa & wb)


def parse_view_text(project: Project, lib: List[Device], text: str) -> List[ViewItem]:
    """Interpreta una descrizione libera della vista, es.
    'Fluoro + IVUS + Cam1', 'cam e scopia', 'cam grande e live piccola', 'hemo, x-rays, cam 2'.
    La sorgente indicata come 'grande' (o, se nessuna lo è, la prima) va a destra.
    Nei nomi delle viste le sorgenti diventano LIVE, CAM, POLY/HEMO, ECHO, IVUS, OCT..."""
    raw_parts = [p for p in _SEP_RE.split(text.strip()) if p and p.strip()]
    if not raw_parts:
        raise ValueError("Scrivi almeno una sorgente")

    active = [a for a in project.areas if a.device and find_device(lib, a.device)]
    dev_of = {a.index: find_device(lib, a.device) for a in active}
    used = set()
    parsed = []  # (is_big, ViewItem)

    def free(pred):
        return [a for a in active if a.index not in used and pred(a)]

    for part in raw_parts:
        big = bool(_BIG_RE.search(part))
        token = _norm(_NOISE_RE.sub(" ", part)) or _norm(part)
        cls = word_class(token)
        item = None

        # 1) telecamera, eventualmente numerata
        if cls == "CAM":
            num = _CAMERA_RE.match(token).group(1)
            cams = [a for a in active if dev_of[a.index].is_camera]
            if num:
                n = int(num)
                hit = [a for a in cams if a.index not in used and re.sub(r"\D", "", a.label) == num]
                if not hit and 0 < n <= len(cams) and cams[n - 1].index not in used:
                    hit = [cams[n - 1]]
            else:
                hit = [a for a in cams if a.index not in used]
            if not hit:
                raise ValueError(f"'{part.strip()}': nessuna telecamera libera nelle aree configurate")
            item = ViewItem(hit[0].index)

        # 2) etichetta dell'area scritta esattamente
        if item is None:
            hit = free(lambda a: a.label and _norm(a.label) == token)
            if hit:
                item = ViewItem(hit[0].index)

        # 3) tipo di dispositivo (LIVE, POLY/HEMO, ECHO, IVUS, OCT, FFR, SYNC)
        if item is None and cls:
            want = "POLY" if cls == "HEMO" else cls
            hit = free(lambda a: dev_class(dev_of[a.index]) == want)
            if hit:
                item = ViewItem(hit[0].index)
            else:  # profilo dello stesso apparecchio su un'altra area (es. FFR sull'area IVUS Volcano)
                for d in [d for d in lib if dev_class(d) == want]:
                    hit = free(lambda a: not dev_of[a.index].is_camera
                               and dev_of[a.index].kind != KIND_SCOPIA
                               and dev_of[a.index].resolution == d.resolution
                               and _same_family(dev_of[a.index], d))
                    if hit:
                        item = ViewItem(hit[0].index, d.name)
                        break
            if item is None:
                raise ValueError(f"'{part.strip()}' ({cls}): nessuna area configurata con questo dispositivo")
            if cls == "HEMO":
                item.alias = "HEMO"

        # 4) nome o sigla di un dispositivo del catalogo
        if item is None:
            cands = [d for d in lib if not d.is_camera and token in (_norm(d.sigla), _norm(d.name))]
            if not cands and len(token) >= 3:
                cands = [d for d in lib if not d.is_camera and token in _norm(d.name)]
            for d in cands:
                hit = free(lambda a: a.device == d.name)
                if hit:
                    item = ViewItem(hit[0].index)
                    break

        if item is None:
            raise ValueError(f"'{part.strip()}' non corrisponde a nessuna area configurata.\n"
                             "Usa parole come live, scopia, cam, poly, hemo, echo, ivus, oct, "
                             "oppure le etichette del tab Aree.")
        used.add(item.area)
        parsed.append((big, item))

    if len(parsed) > 4:
        raise ValueError("Massimo 4 sorgenti per vista")
    if sum(1 for b, _ in parsed if b) > 1:
        raise ValueError("Solo una sorgente può essere 'grande'")
    parsed.sort(key=lambda t: not t[0])  # la sorgente 'grande' va per prima (a destra)
    return [it for _, it in parsed]
