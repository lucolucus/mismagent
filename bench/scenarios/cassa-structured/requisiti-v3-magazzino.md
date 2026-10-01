
---

## 9. Magazzino (v3 — nuova funzionalità, dopo il rilascio di R1)

**Motivo:** durante le sagre finiscono i prodotti senza che la cassa se ne accorga. Realizza RFU4.

| ID | Requisito | Priorità |
|------|-----------|:--------:|
| RM1 | Un prodotto può essere **gestito a magazzino** (sì/no, predefinito no). Solo i prodotti gestiti hanno una giacenza (intero ≥ 0, iniziale 0). | 🔴 |
| RM2 | **Carico merce:** si aumenta la giacenza di un prodotto gestito di una quantità > 0; il carico è registrato come movimento con data e quantità. | 🔴 |
| RM3 | **Scarico automatico:** ogni vendita registrata (anche manuale, RF5.2) diminuisce la giacenza dei prodotti gestiti della quantità venduta, come movimento. | 🔴 |
| RM4 | Un prodotto gestito con giacenza 0 **non è vendibile** (bottone disabilitato); il carrello non può superare la giacenza disponibile. | 🔴 |
| RM5 | Ogni prodotto gestito ha una **soglia minima** (predefinita 0); sotto soglia è evidenziato. | 🟡 |
| RM6 | **Schermata Magazzino:** elenco dei prodotti gestiti con giacenza, soglia e stato (ok / sotto soglia / esaurito); da qui carico e rettifica. | 🔴 |
| RM7 | **Rettifica inventario:** si imposta la giacenza al valore contato, con un motivo obbligatorio; registrata come movimento. | 🟡 |
| RB6 | La giacenza non è mai negativa: una vendita (anche manuale) che la renderebbe negativa è rifiutata. | 🔴 |

Modello dati: `prodotti` acquisisce `gestito_magazzino` INTEGER DEFAULT 0, `giacenza` INTEGER,
`soglia_minima` INTEGER DEFAULT 0; nuova tabella `movimenti_magazzino` (`ID_Movimento` PK,
`ID_Prodotto` FK, `data`, `tipo` carico|scarico|rettifica, `quantita`, `motivo`).
