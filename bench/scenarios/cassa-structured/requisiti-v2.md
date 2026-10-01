
---

## 8. Modifiche v2 (richiesta di modifica — da recepire in R1)

**Motivo:** il commercialista dell'oratorio segnala che bevande analcoliche, snack e gelati vanno a
IVA agevolata; solo gli alcolici restano al 22%.

| ID | Requisito | Priorità | Sostituisce |
|------|-----------|:--------:|-------------|
| RB4 (v2) | **IVA per categoria.** Ogni categoria ha un'aliquota IVA: Bevande calde, Bevande fredde, Snack, Gelati **10%**; Alcolici **22%**. Lo scorporo si calcola per aliquota. | 🔴 | RB4 (IVA fissa 22%) |
| RF3.1 (v2) | La finestra di pagamento mostra il totale e, **per ciascuna aliquota presente nel carrello**, imponibile e IVA. | 🔴 | RF3.1 |
| RF4.5 | Lo scontrino (unico e per reparto) riporta imponibile e IVA per aliquota. | 🟡 | — |
| RF6.2 (v2) | Aggiungendo una categoria se ne sceglie l'aliquota (10% o 22%, predefinita 22%). | 🟡 | RF6.2 |
| RNF9 | Un database già in uso con la versione precedente si aggiorna all'avvio senza perdita di dati: le categorie iniziali ricevono le aliquote sopra, le vendite passate restano invariate. | 🔴 | — |

Modello dati: la tabella `categorie` acquisisce `aliquota_iva` DECIMAL(4,2) NOT NULL.
