
---

## 13. Chiusura cassa ed esportazione (v7 — richiesta di modifica, release R6)

**Motivo:** a fine turno nessuno sa quanti contanti dovrebbero esserci nel cassetto, e il tesoriere
ricopia a mano le vendite del mese nel suo foglio di calcolo.

| ID | Requisito | Priorità |
|------|-----------|:--------:|
| RC1 | **Fondo cassa:** all'apertura del turno si inserisce il fondo cassa iniziale (≥ 0, predefinito 0). | 🔴 |
| RC2 | **Chiusura turno:** la cassa calcola il contante atteso = fondo cassa + contanti incassati nel turno (compresa la parte in contanti dei pagamenti misti, al netto degli storni); l'operatore inserisce il contante contato; la chiusura registra atteso, contato e differenza. | 🔴 |
| RC3 | Dopo la chiusura non si può vendere finché non si apre un nuovo turno. | 🔴 |
| RC4 | Un elenco delle chiusure mostra data, turno, listino, fondo, atteso, contato e differenza. | 🟡 |
| RC5 | **Esportazione del mese** (mm/aaaa) in CSV per il tesoriere: una riga per ogni riga di vendita, con data, turno, listino, prodotto, quantità, prezzo di listino, importo pagato, sconto, omaggio, modalità di pagamento, stornata. | 🔴 |
