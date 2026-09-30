
Sections of this file apply only when the matching section of REQUISITI.md exists (10 → R3, 11 → R4,
12 → R5, 13 → R6); skip the others. Oracle facts used here: `oracle-s2.md`. Every scenario starts
from a fresh database unless it says otherwise; test data as above.

## Sconti e omaggi (sezione 10, R3)
| id | 🔴 | req | scenario |
|----|:--:|-----|----------|
| A41 | 🔴 | RS1 | Caffè ×2 con sconto 50% sulla riga → totale 1,20. Sconto 101 o −5 rifiutato. |
| A42 | 🔴 | RS2 | Birra omaggio senza motivo → rifiutato; con motivo "volontari" → riga a 0,00; se Birra è gestita con giacenza 5, dopo la vendita è 4. |
| A43 | 🔴 | RS3 | Caffè ×1 sconto 10% + Birra ×1: totale 4,08; IVA 10%: imponibile 0,98, IVA 0,10; IVA 22%: imponibile 2,46, IVA 0,54. |
| A44 |  | RS4 | Nello scontrino della vendita A43 la riga Caffè mostra prezzo pieno 1,20, sconto 10% e netto 1,08; una riga omaggio è indicata OMAGGIO. |
| A45 | 🔴 | RS5 | Caffè ×2 sconto 50% + Birra omaggio; report di oggi: incasso 1,20, totale sconti 1,20, omaggi 1. |
| A46 | 🔴 | RS5, RB1 | Nel DB la riga Caffè di A45 ha prezzo di listino 1,20, importo pagato 1,20, sconto 50; dopo aver portato il prezzo Caffè a 1,50 la riga resta invariata. |

## Pagamento misto e storno (sezione 11, R4)
| id | 🔴 | req | scenario |
|----|:--:|-----|----------|
| A47 | 🔴 | RP1 | Birra + Acqua ×2 (totale 5,00): carta 3,00 + contanti 5,00 → resto 3,00, vendita registrata; carta 3,00 + contanti 1,00 → rifiutata. |
| A48 | 🔴 | RP2 | Nel DB la vendita di A47 ha modalità misto, carta 3,00, contanti 2,00. Una vendita tutta in contanti ha modalità contanti; tutta con carta, carta. |
| A49 | 🔴 | RP3 | Acqua gestita, giacenza 10; vendita Acqua ×2 → 8; storno senza motivo rifiutato; storno con motivo → giacenza 10, la vendita resta nel DB marcata stornata; un secondo storno della stessa vendita è impossibile. |
| A50 | 🔴 | RP3 | Due vendite nel turno: la prima (non l'ultima) non si può stornare. |
| A51 | 🔴 | RP4 | Nel turno: vendita 5,00 in contanti, vendita 3,00 con carta, vendita Acqua 1,00 in contanti poi stornata. Report di oggi: incasso 8,00; contanti 5,00; carta 3,00. |
| A52 | 🔴 | RP5 | Un DB creato dal tag R2 con alcune vendite si apre con l'ultima versione: le vendite passate hanno modalità «non registrata» e il report dà lo stesso incasso di prima. |

## Listini evento (sezione 12, R5)
| id | 🔴 | req | scenario |
|----|:--:|-----|----------|
| A53 | 🔴 | RL1 | Caffè con prezzo Sagra 1,50, Acqua senza: con listino Sagra il Caffè costa 1,50 e l'Acqua non è vendibile; con listino Bar il Caffè costa 1,20. |
| A54 | 🔴 | RL2 | All'avvio si scelgono turno e listino (predefinito Bar); con il cambio turno si può passare a Sagra. |
| A55 | 🔴 | RL3 | Vendita Caffè con listino Sagra → nel DB listino Sagra, prezzo 1,50; portato il prezzo Sagra a 2,00, la vendita resta a 1,50. |
| A56 |  | RL4 | Una vendita Bar e una Sagra: il report filtrato per Sagra mostra solo quella Sagra. |
| A57 | 🔴 | RL5 | Caffè gestito, giacenza 5, listino Sagra: Caffè ×1 con sconto 50% → pagato 0,75, giacenza 4; stornata → giacenza 5. |

## Chiusura cassa ed esportazione (sezione 13, R6)
| id | 🔴 | req | scenario |
|----|:--:|-----|----------|
| A58 | 🔴 | RC1 | Aprendo il turno si inserisce il fondo cassa 50,00; un fondo negativo è rifiutato. |
| A59 | 🔴 | RC2 | Fondo 50,00; vendite: 5,00 contanti; misto carta 3,00 + contanti 2,00; 4,00 carta; 1,00 contanti poi stornata. Chiusura: atteso 57,00; contato 56,50 → differenza −0,50, registrata. |
| A60 | 🔴 | RC3 | Dopo la chiusura di A59 non si può vendere (bottoni disabilitati o vendita rifiutata) finché non si apre un nuovo turno. |
| A61 |  | RC4 | L'elenco delle chiusure mostra la chiusura di A59: data, turno, listino, fondo 50,00, atteso 57,00, contato 56,50, differenza −0,50. |
| A62 | 🔴 | RC5 | L'esportazione del mese corrente crea `esportazioni/vendite_AAAA_MM.csv`, UTF-8, separatore `;`, decimali con la virgola, intestazione esatta `data;turno;listino;prodotto;quantita;prezzo_listino;importo_pagato;sconto_percento;omaggio;modalita;stornata`. |
| A63 | 🔴 | RC5 | Nel CSV di A62, dopo le vendite di A59 più un omaggio: una riga per riga di vendita; la riga stornata ha `stornata` = sì; l'omaggio ha `omaggio` = sì e importo 0,00; le date sono gg/mm/aaaa. |
