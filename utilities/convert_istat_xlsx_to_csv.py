#!/usr/bin/env python3
"""
Converte il file Excel ISTAT in CSV compatibile con lo script rebuild-from-istat.
Mantiene la popolazione dai dati comuni.json esistenti.

Uso: python3 convert_istat_xlsx_to_csv.py
"""

import pandas as pd
import json
import os

# Percorsi
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
XLSX_FILE = os.path.join(SCRIPT_DIR, 'Elenco-comuni-italiani.xlsx')
JSON_FILE = os.path.join(SCRIPT_DIR, 'comuni-json/comuni.json')
OUTPUT_CSV = os.path.join(SCRIPT_DIR, 'comuni-json/scripts/rebuild-from-istat/istat20260101.csv')

def main():
    print("=" * 60)
    print("Conversione Excel ISTAT -> CSV per rebuild-from-istat")
    print("=" * 60)

    # Carica popolazione esistente da comuni.json
    print("\n[1/3] Caricamento popolazione da comuni.json...")
    popolazione_map = {}
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            comuni_json = json.load(f)
            for c in comuni_json:
                # Chiave: codice ISTAT a 6 cifre
                popolazione_map[c['codice']] = c.get('popolazione', 0)
        print(f"      Caricati {len(popolazione_map)} comuni con popolazione")
    else:
        print("      File comuni.json non trovato, popolazione = 0")

    # Leggi Excel
    print("\n[2/3] Lettura Excel ISTAT...")
    df = pd.read_excel(XLSX_FILE, sheet_name=0, header=0)
    print(f"      Letti {len(df)} comuni")

    # Mappa colonne Excel -> CSV atteso dallo script
    # Lo script si aspetta queste posizioni (0-indexed):
    # [0] codice regione, [2] codice provincia, [4] codice ISTAT,
    # [6] nome comune, [8] codice zona, [9] nome zona, [10] nome regione,
    # [11] nome provincia, [13] sigla, [18] codice catastale, [19] popolazione

    print("\n[3/3] Generazione CSV...")

    rows = []
    missing_pop = 0

    for _, row in df.iterrows():
        codice_istat = str(row['Codice Comune formato alfanumerico']).zfill(6)

        # Cerca popolazione nei dati esistenti
        popolazione = popolazione_map.get(codice_istat, 0)
        if popolazione == 0:
            missing_pop += 1

        # Formatta popolazione con punto come separatore migliaia (come nel CSV originale)
        pop_str = f"{popolazione:,}".replace(',', '.')

        # Costruisci riga CSV con 20 colonne (indici 0-19)
        # Inserisco valori vuoti per le colonne non usate
        csv_row = [
            str(row['Codice Regione']).zfill(2),                    # [0] codice regione
            '',                                                      # [1]
            str(row['Codice Provincia (Storico)(1)']).zfill(3),     # [2] codice provincia
            '',                                                      # [3]
            codice_istat,                                           # [4] codice ISTAT
            '',                                                      # [5]
            str(row['Denominazione in italiano']),                  # [6] nome comune
            '',                                                      # [7]
            str(row['Codice Ripartizione Geografica']),             # [8] codice zona
            str(row['Ripartizione geografica']),                    # [9] nome zona
            str(row['Denominazione Regione']),                      # [10] nome regione
            str(row.iloc[11]).replace('\n', ' '),                   # [11] nome UTS/provincia
            '',                                                      # [12]
            str(row['Sigla automobilistica']),                      # [13] sigla
            '',                                                      # [14]
            '',                                                      # [15]
            '',                                                      # [16]
            '',                                                      # [17]
            str(row['Codice Catastale del Comune']),                # [18] codice catastale
            pop_str                                                  # [19] popolazione
        ]
        rows.append(csv_row)

    # Scrivi CSV
    with open(OUTPUT_CSV, 'w', encoding='utf-8') as f:
        # Header (20 colonne)
        header = ['CodReg', '', 'CodProv', '', 'CodCom', '', 'Comune', '',
                  'CodZona', 'Zona', 'Regione', 'Provincia', '', 'Sigla',
                  '', '', '', '', 'CodCatastale', 'Popolazione']
        f.write(';'.join(header) + '\n')

        for row in rows:
            f.write(';'.join(row) + '\n')

    print(f"      Scritti {len(rows)} comuni in {OUTPUT_CSV}")
    print(f"      Comuni senza popolazione (nuovi): {missing_pop}")

    print("\n" + "=" * 60)
    print("Conversione completata!")
    print("=" * 60)
    print(f"\nOra puoi eseguire lo script rebuild-from-istat:")
    print(f"  cd {os.path.dirname(OUTPUT_CSV)}")
    print(f"  mkdir -p tmp")
    print(f"  # Modifica __main__.py per usare 'istat20260101.csv'")
    print(f"  python3 .")

if __name__ == '__main__':
    main()
