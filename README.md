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

Accanto all'eseguibile viene creato `catalogo_dispositivi.json`, il catalogo dei
dispositivi con risoluzioni e rectangle. Copiando insieme `.exe` e `.json`
si condivide il catalogo con i colleghi.

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

## Regole di calcolo

- Schermo 1920×1080 (in HD tutto viene scalato a 1280×720); slot 1 = in alto a sinistra, 2 = destra, 3+ = sotto a sinistra.
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
