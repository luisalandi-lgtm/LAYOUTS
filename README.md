# OneView Layout Generator

Programma Windows che scrive in automatico i file di layout (`LayoutN.ini`) per OneView:
si configurano le aree (collegamenti fisici), si scrivono le viste
(es. `Fluoro + IVUS + Cam1`) e il programma calcola `LayoutN=`, i `Rectangle`
delle telecamere e tutto il resto del file.

## Download e avvio

Scarica [`release/OneViewLayoutGenerator.exe`](release/OneViewLayoutGenerator.exe)
(pulsante *Download raw file*), mettilo in una cartella a tua scelta e fai doppio clic.
Non serve installare nulla. Al primo avvio Windows SmartScreen può mostrare
"Windows ha protetto il PC": clic su *Ulteriori informazioni* → *Esegui comunque*.

Accanto all'eseguibile viene creato `catalogo_dispositivi.ini`, il catalogo dei
dispositivi con risoluzioni e rectangle. Copiando insieme `.exe` e `.ini`
si condivide il catalogo con i colleghi.

### Catalogo modificabile a mano

Il catalogo è un file di testo nello stesso stile dei layout, apribile con il Blocco note
(nel programma: tab *Catalogo dispositivi* → **Apri con Blocco note**):

```ini
[Poligrafo]
Sigla=POLY
Tipo=dispositivo
Risoluzione=1600x1200
Rectangle=10,290,1556,822
RigheInfo=
```

- `Tipo`: `dispositivo`, `scopia` o `camera`; `Rectangle` vuoto = segnale intero (per le camere resta vuoto).
- `RigheInfo`: righe da aggiungere in `[Info]` quando il dispositivo è usato (più righe separate da `;`
  oppure ripetendo `RigheInfo=`).
- Salvato il file, tornando al programma il catalogo si ricarica da solo (o con **Ricarica dal file**).
- Se un dispositivo ha dati sbagliati il programma lo salta, indica la riga da correggere e salva
  una copia del file com'era (`catalogo_dispositivi (copia con errori).ini`).
- Il vecchio `catalogo_dispositivi.json` viene convertito in automatico al primo avvio.

### Catalogo condiviso tra più PC

Il catalogo può stare in una cartella condivisa (cartella di rete, OneDrive/SharePoint,
Google Drive per desktop...) ed essere usato da tutti:

1. tab *Catalogo dispositivi* → **Usa un catalogo condiviso…** e scegli il file nella cartella condivisa
   (se non esiste viene creato con il catalogo attuale; se esiste si usa quello, con la possibilità
   di aggiungere i dispositivi che ci sono solo sul tuo PC);
2. ogni collega fa lo stesso una volta, scegliendo lo stesso file.

Oppure, per impostarlo per tutti in una volta, metti accanto a `OneViewLayoutGenerator.exe`
un file `impostazioni.ini` con:

```ini
CatalogoCondiviso=\\server\cartella\catalogo_dispositivi.ini
```

- Il programma controlla il file ogni 3 secondi: le modifiche fatte da altri (dal programma o
  con il Blocco note) compaiono da sole.
- Salvando un dispositivo il programma rilegge prima il file e cambia solo quel dispositivo,
  così le modifiche degli altri non vanno perse.
- Se la cartella condivisa non è raggiungibile si usa l'ultima copia letta (le modifiche al catalogo
  sono bloccate finché non torna disponibile, poi si ricarica da solo).
- Se qualcuno lascia un errore nel file, il programma non lo sovrascrive e indica la riga da correggere.
- **Torna al catalogo locale** riporta il PC al catalogo personale.

## Uso

1. **Aree (collegamenti)** – per ogni area: dispositivo, slot della scheda
   (es. `SLOTDEV_06BC USBMI_02`, `HD Video 1`, `SN:...`), commento, etichetta
   (Cam1, Cam2, Fluoro, IVUS…).
   Cambiando dispositivo, commento ed etichetta compilati in automatico si
   aggiornano; quelli modificati a mano restano.
2. **Viste** – scrivi la vista e premi Invio. La sorgente indicata come
   **grande** (oppure, se nessuna lo è, la **prima**) va a destra, le altre in
   colonna a sinistra dall'alto verso il basso. Separatori: `+` `,` `e`.
   - `live, poligrafo, cam` → `LIVE + POLY + CAM`: scopia grande a destra, poligrafo in alto, camera sotto
   - `IVUS e scopia e cam 2` → `IVUS + LIVE + CAM2`: IVUS grande a destra, scopia in alto a sinistra
   - `cam grande e live piccola` → `CAM + LIVE`: camera grande a destra, scopia 600×600 a sinistra
   - `solo cam`, `camera 2` → camera a schermo intero (16:9)
   - `FFR` usa l'area dell'IVUS Volcano con il rectangle dell'FFR (stesso apparecchio).

   Nei nomi delle viste le sorgenti diventano sempre:

   | Scrivi (maiuscole/minuscole indifferenti) | Nome nella vista |
   |---|---|
   | scopia, fluoro, live, angio, x-rays, xray, rx… | `LIVE` |
   | cam, camera, telecamera (+ numero) | `CAM` (`CAM1`/`CAM2` se il layout ha due camere) |
   | poly, poligrafo / hemo, emodinamica | `POLY` / `HEMO` |
   | eco, ecografo, echo, ultrasound, ultrasuoni | `ECHO` |
   | ivus, volcano, boston, philips | `IVUS` |
   | oct | `OCT` |
   | ffr, ifr / sync | `FFR` / `SYNC` |

   Anche i layout aperti con *Apri .ini esistente…* prendono questi nomi.

   **Modifica con il mouse nell'anteprima:**
   - trascina la **linea verticale** per cambiare la larghezza della colonna sinistra;
   - trascina una **linea orizzontale** per cambiare le altezze in colonna;
   - trascina un **segnale sopra un altro** per scambiarli di posto
     (le misure tornano automatiche per la nuova disposizione);
   - **doppio clic** su una linea la riporta al valore automatico;
     *↺ Misure automatiche* / *↺ Tutte automatiche* annullano le modifiche a mano.

   Le viste modificate a mano sono segnate con ✎. I rectangle delle telecamere
   si ricalcolano sempre sullo spazio nuovo; se un dispositivo viene deformato
   l'anteprima indica di quanto. Aprendo un `.ini` esistente le misure del file
   vengono conservate.

   L'anteprima mostra la disposizione e i valori calcolati.
3. **Catalogo dispositivi** – aggiungi/modifica dispositivi (nome, sigla, tipo,
   risoluzione, rectangle). Viene salvato automaticamente.
   Il campo **Righe in [Info]** contiene righe da aggiungere sotto `ParseMode=`
   quando il dispositivo è assegnato a un'area (più righe separate da `;`,
   `{area}` = numero dell'area). Ogni dispositivo con "OBSBOT" nel nome riceve
   in automatico `PelcoCamera2Source=Y`.
   Di predefinito il layout ha `ParseMode=GeneraleParse.dll,0`; se un dispositivo
   usato ha una riga `ParseMode=...` (es. `ParseMode=censoringdinamico.dll,0`),
   quella diventa attiva e la predefinita resta come commento
   `;ParseMode=GeneraleParse.dll,0`.
4. **File .ini** – testo generato, ritoccabile a mano, poi *Salva .ini…* oppure
   *Copia negli appunti* (anche dalla barra in alto).

*Apri .ini esistente…* carica un layout già fatto; i rectangle sconosciuti
vengono aggiunti al catalogo.

## Schermo Full HD o HD

In alto, **Schermo OneView** sceglie se il layout è per uno schermo
Full HD 1920×1080 o HD 1280×720; il pulsante **⇄ Converti** passa dall'uno
all'altro. La conversione mantiene ordine e proporzioni di tutte le viste
(anche quelle modificate a mano): cambiano solo i valori di `Layout`
(×2/3 o ×3/2) e i rectangle delle telecamere, ricalcolati sullo spazio nuovo.
I rectangle dei dispositivi non cambiano (dipendono dal segnale, non dallo schermo).
Un `.ini` HD viene riconosciuto in apertura. *Nuovo* mantiene lo schermo scelto.

## Sfondo

Spuntando **Sfondo** (in alto, accanto allo schermo) il layout riceve in `[Info]`
la riga `BackgroundBitMap='Sfondo.png'` (nome del file modificabile) e i segnali
non occupano più tutto lo schermo: restano separati da una cornice in cui si vede lo sfondo.

| Schermo | margine alto | cornice (lati, basso e tra i segnali) |
|---|---|---|
| Full HD 1920×1080 | 80 | 30 |
| HD 1280×720 | 50 | 20 |

I due valori si possono cambiare; con *⇄ Converti* passano a quelli dell'altro schermo.
Con la sola camera, la camera 16:9 è centrata nello spazio dentro la cornice.
Con lo sfondo la telecamera in colonna può scendere fino a 250 px (in Full HD),
perché la cornice toglie spazio. Aprendo un `.ini` con `BackgroundBitMap` lo sfondo
viene riconosciuto e margine e cornice vengono letti dalle viste del file.

## Regole di calcolo

- Schermo 1920×1080 (in HD tutto viene scalato a 1280×720); slot numerati sempre in senso antiorario: 1 = in alto a sinistra, poi in giù lungo la colonna, l'ultimo = grande a destra
  (3 segnali: 1 alto sx, 2 basso sx, 3 destra; 2 segnali: 1 sinistra, 2 destra). Anche i `Location`
  sono scritti in quest'ordine. Aprendo un `.ini` con un'altra numerazione la posizione si riconosce dalle misure.
- Larghezza della sorgente a destra = 1080 × proporzioni del suo rectangle.
- Altezza dei dispositivi in colonna = larghezza colonna ÷ proporzioni del rectangle.
- Scopia in colonna mai sotto **600×600**; telecamera mai sotto **400 px** di altezza.
- Telecamera: ritaglio più grande possibile con le proporzioni dello spazio libero,
  centrato; valori arrotondati per difetto a numeri pari.
- `Ratio` 16:9 solo per le viste con la sola camera, altrimenti 1:1.
- `[Censoring]` resta vuoto (da compilare a mano).

## Sviluppo

Codice in Python 3.9+ (solo libreria standard, interfaccia tkinter):

- `layout_engine.py` – calcolo, lettura e scrittura dei `.ini`
- `layout_generator.py` – interfaccia grafica

Avvio da sorgente: `py layout_generator.py`
Ricostruzione dell'eseguibile: `build.bat` (richiede `pip install pyinstaller`).
