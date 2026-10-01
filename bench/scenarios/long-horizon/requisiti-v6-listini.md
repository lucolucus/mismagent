
---

## 12. Listini evento (v6 — richiesta di modifica, release R5)

**Motivo:** alla sagra i prezzi sono diversi da quelli del bar, e oggi si cambiano a mano prima e
dopo ogni evento.

| ID | Requisito | Priorità |
|------|-----------|:--------:|
| RL1 | Esistono due listini, **Bar** e **Sagra**. Il prezzo attuale di ogni prodotto è il prezzo Bar; ogni prodotto può avere un prezzo Sagra facoltativo. Un prodotto senza prezzo Sagra non è vendibile con il listino Sagra. | 🔴 |
| RL2 | All'avvio, insieme al turno, si sceglie il listino (predefinito Bar); cambiando turno si può cambiare listino. | 🔴 |
| RL3 | Ogni vendita registra il listino con cui è stata fatta; vale lo storico dei prezzi (RB1) anche per il listino Sagra. | 🔴 |
| RL4 | Il report vendite si può filtrare per listino. | 🟡 |
| RL5 | Sconti, omaggi, pagamento misto, storno e magazzino valgono con entrambi i listini; il magazzino è unico. | 🔴 |
