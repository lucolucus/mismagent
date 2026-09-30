
---

## 10. Sconti e omaggi (v4 — richiesta di modifica, release R3)

**Motivo:** ai volontari si offre la consumazione e nelle serate di festa si fanno sconti; oggi la
cassa li registra a prezzo pieno e l'incasso non torna.

| ID | Requisito | Priorità |
|------|-----------|:--------:|
| RS1 | **Sconto di riga:** a una riga del carrello si applica uno sconto percentuale intero da 0 a 100; il totale della riga diventa il prezzo × quantità scontato. | 🔴 |
| RS2 | **Omaggio:** una riga si può segnare come omaggio (importo 0) con un motivo obbligatorio; il magazzino scarica comunque la merce. | 🔴 |
| RS3 | Lo scorporo IVA si calcola sugli importi scontati, per aliquota. | 🔴 |
| RS4 | Lo scontrino riporta per ogni riga scontata il prezzo pieno, lo sconto e l'importo netto; le righe omaggio sono indicate come OMAGGIO. | 🟡 |
| RS5 | La vendita registra il prezzo di listino e l'importo pagato; l'incasso dei report usa l'importo pagato; il report mostra il totale degli sconti e il numero di omaggi del periodo. | 🔴 |

Modello dati: le righe di vendita acquisiscono `importo_pagato`, `sconto_percento`, `omaggio`, `motivo_omaggio`.
