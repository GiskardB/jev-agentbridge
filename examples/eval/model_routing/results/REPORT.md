# Model routing evaluation

Generated 2026-09-23 21:14. Dataset: `model_routing.jsonl`.

| Run | Samples | Failed | Accuracy | Acc. en | Acc. it | Acc. large | Acc. medium | Acc. small | Rec. threshold | Coverage at rec. | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| laya-en | 240 | 0 | 59.6% | 70.0% | 49.2% | 43.8% | 90.0% | 45.0% | 0.55 | 12.1% | 970.648 |
| laya-multilingual | 240 | 0 | 34.6% | 37.5% | 31.7% | 20.0% | 10.0% | 73.8% | - | - | 289.332 |
| semif-v1 | 240 | 0 | 37.5% | 41.7% | 33.3% | 96.2% | 1.2% | 15.0% | 0.65 | 7.1% | 1423.964 |
| semif-v2 | 240 | 0 | 51.7% | 56.7% | 46.7% | 45.0% | 96.2% | 13.8% | - | - | 1427.025 |

Recommended threshold = lowest threshold whose accuracy on accepted decisions is >= 95%; coverage = share of requests JEV would route on its own.

## laya-en

Confusion matrix (rows = expected, columns = predicted):

| expected \ predicted | large | medium | small |
|---|---|---|---|
| large | 35 | 44 | 1 |
| medium | 1 | 72 | 7 |
| small | 1 | 43 | 36 |

Confident errors (p >= 0.8): 0


## laya-multilingual

Confusion matrix (rows = expected, columns = predicted):

| expected \ predicted | large | medium | small |
|---|---|---|---|
| large | 16 | 5 | 59 |
| medium | 5 | 8 | 67 |
| small | 8 | 13 | 59 |

Confident errors (p >= 0.8): 11

- `en-small-03` expected **small**, got **large** (p=0.99): How many ounces are in a pound?
- `it-small-04` expected **small**, got **large** (p=0.98): Quanti grammi ci sono in un'oncia?
- `en-medium-12` expected **medium**, got **small** (p=0.96): Convert this short Python script that reads a JSON file into Node.js.
- `it-small-32` expected **small**, got **large** (p=0.88): Quanti metri sono 3 miglia?
- `it-small-08` expected **small**, got **medium** (p=0.87): Converti 72 gradi Fahrenheit in Celsius.
- `en-large-08` expected **large**, got **small** (p=0.87): Go through these 10,000 lines of application logs and find the root cause of the intermittent 502 errors.
- `en-small-06` expected **small**, got **large** (p=0.87): Convert 10 kilometers to miles.
- `en-medium-23` expected **medium**, got **small** (p=0.86): Reply to this customer complaint about a late refund, apologizing and explaining the next steps.
- `it-large-15` expected **large**, got **small** (p=0.85): Spiega la differenza tra consistenza forte ed eventuale e decidi quale serve a ciascuno dei nostri 6 microservizi, motivando.
- `en-medium-02` expected **medium**, got **small** (p=0.84): Summarize this one-page memo about the new travel policy into five bullet points.
- `en-medium-16` expected **medium**, got **small** (p=0.84): Give me 8 icebreaker questions for a team workshop.

## semif-v1

Confusion matrix (rows = expected, columns = predicted):

| expected \ predicted | large | medium | small |
|---|---|---|---|
| large | 77 | 0 | 3 |
| medium | 71 | 1 | 8 |
| small | 68 | 0 | 12 |

Confident errors (p >= 0.8): 0


## semif-v2

Confusion matrix (rows = expected, columns = predicted):

| expected \ predicted | large | medium | small |
|---|---|---|---|
| large | 36 | 40 | 4 |
| medium | 0 | 77 | 3 |
| small | 10 | 59 | 11 |

Confident errors (p >= 0.8): 9

- `en-small-21` expected **small**, got **medium** (p=0.96): Rephrase more politely: "Answer my email now."
- `en-large-26` expected **large**, got **medium** (p=0.91): Explain how Paxos works and walk through what happens when two proposers compete during a network partition.
- `it-large-10` expected **large**, got **medium** (p=0.91): Rifattorizza questo modulo di 2000 righe in classi coese, spiegando i passaggi e come evitare regressioni.
- `it-large-18` expected **large**, got **medium** (p=0.87): Individua le vulnerabilità di questo flusso di autenticazione OAuth2 personalizzato e proponi le correzioni.
- `it-small-22` expected **small**, got **medium** (p=0.87): Come si scrive la data 5 marzo 2026 in formato ISO?
- `it-large-26` expected **large**, got **medium** (p=0.85): Spiega come funziona il consenso Raft e simula cosa succede con una partizione di rete tra 5 nodi.
- `it-small-40` expected **small**, got **medium** (p=0.84): Riassumi in tre parole: "La riunione è spostata a giovedì".
- `it-large-01` expected **large**, got **medium** (p=0.83): Analizza questi tre anni di bilanci, spiega le cause del calo di marginalità e proponi tre interventi con stima dell'impatto.
- `en-small-39` expected **small**, got **large** (p=0.80): What's the maximum file size for uploads?
