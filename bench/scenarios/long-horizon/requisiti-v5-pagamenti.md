
---

## 11. Pagamento misto e storno (v5 — richiesta di modifica, release R4)

**Motivo:** molti pagano un po' con la carta e il resto in contanti; e quando l'operatore sbaglia
una vendita oggi non c'è modo di annullarla senza falsare incasso e magazzino.

| ID | Requisito | Priorità |
|------|-----------|:--------:|
| RP1 | **Pagamento misto:** una parte con carta e il resto in contanti; la somma deve coprire il totale; il resto si calcola solo sulla parte in contanti. | 🔴 |
| RP2 | La vendita registra la modalità di pagamento (contanti, carta, misto) e l'importo incassato per modalità. | 🔴 |
| RP3 | **Storno:** l'ultima vendita del turno si può stornare con un motivo obbligatorio. La vendita originale resta registrata e marcata come stornata; la merce dei prodotti gestiti torna in giacenza (movimento di magazzino). Una vendita si storna una volta sola. | 🔴 |
| RP4 | I report sono al netto degli storni e mostrano l'incasso per modalità (contanti, carta). | 🔴 |
| RP5 | Un database già in uso si aggiorna all'avvio senza perdita di dati; le vendite passate hanno modalità «non registrata» e incassi invariati. | 🔴 |
