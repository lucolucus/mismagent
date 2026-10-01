
**Oracle for the change requests of sections 10–13** (fixed for every run, appended to the base oracle):
- Sconto: integer percent 0–100, per line only (no cart-level discount); line net = price × quantity
  × (1 − percent/100), rounded half-up to the cent. A line is either discounted or an omaggio; an
  omaggio line is never also discounted. The report's "totale sconti" is the sum of (listino −
  pagato) over discounted lines only; omaggi are counted apart, not in the sconti total.
- Omaggio: the motive is free text, required.
- Pagamento misto: the operator types the card amount first, then the cash received; amounts are
  recorded **net of the change** (cash recorded = total − card).
- Storno: only the **most recent sale of the current shift**, and only if it is not already
  reversed; a manual sale follows the same rule. Past sales from an older database have listino
  "Bar", modalità "non registrata", importo pagato = prezzo × quantità.
- Listini: exactly Bar and Sagra; default Bar; the Sagra price is set in Gestione prodotti.
- Fondo cassa: typed when the shift opens (with turno and listino). Closing a shift ends it; the next
  sale needs a new shift (turno, listino, fondo).
- CSV: file `esportazioni/vendite_AAAA_MM.csv`; separator `;`; decimal comma; UTF-8; one header row
  exactly `data;turno;listino;prodotto;quantita;prezzo_listino;importo_pagato;sconto_percento;omaggio;modalita;stornata`;
  dates gg/mm/aaaa; omaggio and stornata as `sì`/`no`.
