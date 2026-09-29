# Accettazione esterna — Registratore di Cassa (requisiti finali: v1 + v2 + v3)

Scritta **prima** del run, dai requisiti e dall'oracolo di `sim-policy.md`, senza guardare il codice.
Si applica all'app rilasciata all'ultimo tag. Ogni scenario: PASS · FAIL · BLOCKED (non eseguibile:
dire perché). 🔴 = deriva da un requisito ad alta priorità: devono passare tutti.

Dati di prova (creati dall'app stessa, via Gestione prodotti, se non presenti): Caffè 1,20 € (Bevande
calde), Acqua 1,00 € (Bevande fredde), Birra 3,00 € (Alcolici), Patatine 1,50 € (Snack).

## Vendita (R0)
| id | 🔴 | req | scenario |
|----|:--:|-----|----------|
| A01 | 🔴 | RF1.1, RB5 | All'avvio l'app chiede il turno (Mattino/Pomeriggio/Sera); la cassa non è usabile prima della scelta. |
| A02 | 🔴 | RF2.1, RF2.2 | La cassa mostra solo i prodotti attivi, raggruppati per categoria, ogni categoria con un colore distinto. |
| A03 | 🔴 | RF2.3 | Toccare due volte Caffè → una sola riga, quantità 2. |
| A04 | 🔴 | RF2.4 | Incrementa, decrementa, rimuovi, svuota funzionano; decrementare a 0 toglie la riga. |
| A05 | 🔴 | RF2.5 | Il totale si aggiorna a ogni modifica del carrello (2 Caffè + 1 Acqua = 3,40 €). |
| A06 | 🔴 | RF3.2 | Contanti: totale 3,40 €, ricevuti 5,00 € → resto 1,60 €. |
| A07 |  | RF3.3 | Contanti insufficienti (2,00 € su 3,40 €) → conferma impedita, messaggio chiaro. |
| A08 | 🔴 | RF3.4 | Carta/Bancomat: la vendita si conferma senza contante. |
| A09 | 🔴 | RF3.5, RF1.3, RF5.1 | Conferma senza stampa → nel DB, tabella vendite dell'anno: una riga per prodotto con nome e prezzo al momento, quantità, categoria, turno corrente, data odierna. |
| A10 | 🔴 | RF6.3, RB1 | Cambiare il prezzo di Caffè dopo una vendita: le vendite passate restano al prezzo vecchio, le nuove usano il nuovo. |
| A11 | 🔴 | RF6.1 | Aggiungere un prodotto (nome, prezzo, categoria) → compare in cassa. |
| A12 | 🔴 | RF6.6, RB3 | Disattivare Patatine: sparisce dalla cassa, resta nel DB e nei report storici; riattivandolo ritorna. |
| A13 | 🔴 | RF7.1, RF7.2, RF7.6 | Report "oggi": per prodotto quantità, incasso, categoria; l'incasso totale è la somma. |
| A14 | 🔴 | RNF1 | Il DB rifiuta una vendita con un prodotto inesistente (integrità referenziale attiva). |
| A15 | 🔴 | RNF6 | Un errore del DB a metà registrazione di un carrello di più righe non lascia righe parziali. |
| A16 |  | RNF4 | Tutti i testi visibili delle schermate sono in italiano. |

## Completamento (R1)
| id | 🔴 | req | scenario |
|----|:--:|-----|----------|
| A17 |  | RF1.2 | Cambio turno durante l'uso: le vendite successive portano il nuovo turno. |
| A18 |  | RF4.1, RF4.4 | Stampa scontrino unico: intestazione, righe, totale, resto; la vendita risulta registrata. |
| A19 |  | RF4.2 | Scontrino per reparto: Caffè + Birra + Patatine → uno scontrino Bevande (Caffè, Birra) e uno Cibo (Patatine). |
| A20 | 🔴 | RF5.2, RF5.3 | Vendita manuale con data di ieri: accettata; con data di domani: rifiutata. |
| A21 |  | RF5.4 | Vendita manuale con data malformata: rifiutata con messaggio. |
| A22 |  | RF6.2 | Aggiungere una categoria nuova; un nome già esistente è rifiutato. |
| A23 |  | RF6.4 | Rinominare un prodotto: il nuovo nome appare anche nelle vendite passate. |
| A24 |  | RF6.5 | Cambiare la categoria di un prodotto: in cassa compare sotto la nuova categoria. |
| A25 |  | RF7.3–RF7.5 | Report: oggi per turno; giorno specifico (gg/mm/aaaa); mese (mm/aaaa) — ciascuno filtra correttamente. |

## Modifica v2 (IVA per categoria, R1)
| id | 🔴 | req | scenario |
|----|:--:|-----|----------|
| A26 | 🔴 | RB4 v2, RF3.1 v2 | Carrello 1 Caffè + 1 Birra (4,20 €): il pagamento mostra 10% → imponibile 1,09, IVA 0,11; 22% → imponibile 2,46, IVA 0,54. |
| A27 |  | RF4.5 | Lo scontrino dello stesso carrello riporta imponibile e IVA per aliquota. |
| A28 |  | RF6.2 v2 | Una categoria nuova senza aliquota scelta ha il 22%. |
| A29 | 🔴 | RNF9 | Un DB creato dalla versione R0 (dal tag di R0, con alcune vendite) si apre con l'ultima versione: categorie iniziali alle aliquote v2, vendite passate invariate. |

## Magazzino (v3)
| id | 🔴 | req | scenario |
|----|:--:|-----|----------|
| A30 | 🔴 | RM1 | Acqua segnata come gestita: giacenza 0; un prodotto non gestito non ha giacenza. |
| A31 | 🔴 | RM2 | Carico +10 Acqua → giacenza 10, movimento "carico" con data e quantità. |
| A32 | 🔴 | RM3 | Vendita di 3 Acqua → giacenza 7; una vendita manuale di 1 → 6; ciascuna un movimento "scarico". |
| A33 | 🔴 | RM4 | Con giacenza 0 il bottone Acqua è disabilitato; con giacenza 2 il carrello non supera 2. |
| A34 |  | RM5 | Soglia 5, giacenza 4 → evidenziato sotto soglia. |
| A35 | 🔴 | RM6 | La schermata Magazzino elenca i gestiti con giacenza, soglia e stato (ok / sotto soglia / esaurito). |
| A36 |  | RM7 | Rettifica a 8 con motivo → giacenza 8, movimento "rettifica"; senza motivo rifiutata. |
| A37 | 🔴 | RB6 | Una vendita manuale che porterebbe la giacenza sotto 0 è rifiutata. |
| A38 | 🔴 | RM1 | Un prodotto non gestito si vende senza alcun vincolo di giacenza. |

## Prodotto
| id | 🔴 | req | scenario |
|----|:--:|-----|----------|
| A39 | 🔴 | — | L'app si avvia su questa macchina con il comando documentato nel repository. |
| A40 | 🔴 | RNF8 | La suite di test del progetto (il gate del profilo) è verde all'ultimo tag. |
