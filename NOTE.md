Ingestion: Crawler o API che scaricano il JSON/HTML.
Standardizzazione: Convertiamo tutto in uno schema base (titolo, descrizione, data, coordinate, sorgente).
Deduplicazione

2. Strategia di Classificazione (Data Science Layer)

A. Pre-processing del Testo
 Prima di darlo in pasto a un modello, dobbiamo "pulire" le descrizioni degli eventi:

Rimozione stop-words e punteggiatura.

Lemmatizzazione: Trasformare "mostre", "mostrerà", "mostra" nella radice "mostra".

NER (Named Entity Recognition): Estrarre nomi di artisti, location o quartieri.

Approccio,Quando usarlo,Pro/Contro
Heuristic (Regex),"Categorie ovvie (es. ""Cinema"", ""Teatro"").","Veloce, ma rigido."
Machine Learning (SVM/Random Forest),Classificazione multiclasse standard.,"Richiede un dataset etichettato, ma è leggerissimo in produzione."
LLM (GPT-4 / Gemini / Llama 3),Casi ambigui o descrizioni colloquiali.,"Precisissimo, ma costoso e lento per grandi volumi."