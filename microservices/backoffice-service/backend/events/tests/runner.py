"""
Custom test runner che produce output tabellare per i test API.

Uso:
    docker exec -w /app/backend events-backoffice \
      python manage.py test events.tests.test_staging_api \
      --testrunner events.tests.runner.TableTestRunner
"""
import unittest
from django.test.runner import DiscoverRunner

# Colori ANSI
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BOLD = '\033[1m'
RESET = '\033[0m'


class TableTestResult(unittest.TextTestResult):
    """Raccoglie i risultati dei test con i dettagli delle chiamate API."""

    def __init__(self, *args, **kwargs):
        """Inizializza il result con la lista righe per la tabella."""
        super().__init__(*args, **kwargs)
        self.table_rows = []

    def _record(self, test, result, error_msg=''):
        """Registra il risultato di un test con le relative chiamate API."""
        api_calls = getattr(test, '_api_calls', [])
        test_name = str(test).split(' ')[0]
        if api_calls:
            for call in api_calls:
                self.table_rows.append({
                    'test': test_name,
                    'endpoint': call['path'],
                    'method': call['method'],
                    'status': str(call['status_code']),
                    'result': result,
                    'error': error_msg,
                })
        else:
            self.table_rows.append({
                'test': test_name,
                'endpoint': '-',
                'method': '-',
                'status': '-',
                'result': result,
                'error': error_msg,
            })

    def addSuccess(self, test):
        """Registra un test superato."""
        super().addSuccess(test)
        self._record(test, 'PASS')

    def addFailure(self, test, err):
        """Registra un test fallito con il messaggio di errore."""
        super().addFailure(test, err)
        msg = str(err[1]).split('\n')[0][:100]
        self._record(test, 'FAIL', msg)

    def addError(self, test, err):
        """Registra un test con errore imprevisto."""
        super().addError(test, err)
        msg = str(err[1]).split('\n')[0][:100]
        self._record(test, 'ERROR', msg)

    def addSkip(self, test, reason):
        """Registra un test saltato con la motivazione."""
        super().addSkip(test, reason)
        self._record(test, 'SKIP', reason[:100])

    def print_table(self):
        """Stampa la tabella riassuntiva dei test con colori ANSI e riepilogo finale."""
        stream = self.stream
        rows = self.table_rows
        if not rows:
            return

        # Colonne: Metodo, Endpoint, Status, Esito, Test, Errore
        headers = ['Metodo', 'Endpoint', 'Status', 'Esito', 'Test', 'Errore']
        col_widths = [len(h) for h in headers]

        for r in rows:
            vals = [r['method'], r['endpoint'], r['status'], r['result'], r['test'], r['error']]
            for i, v in enumerate(vals):
                col_widths[i] = max(col_widths[i], len(v))

        # Limita colonne troppo larghe
        MAX_WIDTHS = [8, 50, 6, 5, 45, 70]
        col_widths = [min(cw, mx) for cw, mx in zip(col_widths, MAX_WIDTHS)]

        def pad(val, width):
            """Tronca e allinea a sinistra il valore alla larghezza specificata."""
            return val[:width].ljust(width)

        def fmt_row(vals):
            """Formatta una riga della tabella con separatori '|'."""
            return ' | '.join(pad(v, col_widths[i]) for i, v in enumerate(vals))

        sep = '-+-'.join('-' * w for w in col_widths)
        total_width = len(sep)

        # Ordina: per endpoint, poi per metodo HTTP
        method_order = {'GET': 0, 'POST': 1, 'PUT': 2, 'PATCH': 3, 'DELETE': 4, '-': 9}
        sorted_rows = sorted(
            rows,
            key=lambda r: (r['endpoint'], method_order.get(r['method'], 5)),
        )

        stream.write('\n')
        stream.write(f'{BOLD}{"=" * total_width}{RESET}\n')
        stream.write(f'{BOLD}  REPORT TEST API - Staging Events{RESET}\n')
        stream.write(f'{BOLD}{"=" * total_width}{RESET}\n')
        stream.write(f'{BOLD}{fmt_row(headers)}{RESET}\n')
        stream.write(f'{sep}\n')

        for r in sorted_rows:
            result_plain = r['result']
            vals = [r['method'], r['endpoint'], r['status'], result_plain, r['test'], r['error']]
            line = fmt_row(vals)

            # Applica colore alla riga intera in base al risultato
            if result_plain == 'PASS':
                # Colora solo la colonna Esito
                line = line.replace(
                    pad('PASS', col_widths[3]),
                    f'{GREEN}{pad("PASS", col_widths[3])}{RESET}',
                    1,
                )
            elif result_plain in ('FAIL', 'ERROR'):
                line = line.replace(
                    pad(result_plain, col_widths[3]),
                    f'{RED}{pad(result_plain, col_widths[3])}{RESET}',
                    1,
                )
                # Colora anche errore in rosso se presente
                if r['error']:
                    err_padded = pad(r['error'], col_widths[5])
                    line = line.replace(err_padded, f'{RED}{err_padded}{RESET}', 1)
            elif result_plain == 'SKIP':
                line = line.replace(
                    pad('SKIP', col_widths[3]),
                    f'{YELLOW}{pad("SKIP", col_widths[3])}{RESET}',
                    1,
                )

            stream.write(f'{line}\n')

        stream.write(f'{sep}\n')

        # Riepilogo
        total = len(rows)
        passed = sum(1 for r in rows if r['result'] == 'PASS')
        failed = sum(1 for r in rows if r['result'] == 'FAIL')
        errors = sum(1 for r in rows if r['result'] == 'ERROR')
        skipped = sum(1 for r in rows if r['result'] == 'SKIP')

        parts = [f'{BOLD}Totale: {total}{RESET}']
        parts.append(f'{GREEN}Pass: {passed}{RESET}')
        if failed:
            parts.append(f'{RED}Fail: {failed}{RESET}')
        if errors:
            parts.append(f'{RED}Errori: {errors}{RESET}')
        if skipped:
            parts.append(f'{YELLOW}Skip: {skipped}{RESET}')

        stream.write('\n' + '  |  '.join(parts) + '\n\n')


class TableTestRunner(DiscoverRunner):
    """Test runner Django che stampa una tabella riassuntiva a fine esecuzione."""

    def run_suite(self, suite, **kwargs):
        """Esegue la suite di test usando TableTestResult e stampa la tabella finale."""
        runner_kwargs = self.get_test_runner_kwargs()
        runner_kwargs['resultclass'] = TableTestResult
        runner = unittest.TextTestRunner(**runner_kwargs)
        result = runner.run(suite)

        if hasattr(result, 'print_table'):
            result.print_table()

        return result
