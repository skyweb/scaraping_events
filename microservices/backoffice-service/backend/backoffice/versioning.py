"""
Versioning custom per le API interne.

Accetta il formato:
    Accept: application/vnd.todayevents.v1+json

Se l'header non è presente o non matcha, usa la versione di default (v1).
"""

import re

from rest_framework.versioning import BaseVersioning


_VENDOR_RE = re.compile(
    r'application/vnd\.todayevents\.(?P<version>v\d+)\+json'
)


class VendorHeaderVersioning(BaseVersioning):
    """Versioning via Accept header con media type vendor."""

    def determine_version(self, request, *args, **kwargs):
        accept = request.META.get('HTTP_ACCEPT', '')
        match = _VENDOR_RE.search(accept)
        if match:
            version = match.group('version')
            if version in (self.allowed_versions or []):
                return version
            self.raise_invalid_version(version)
        return self.default_version

    def raise_invalid_version(self, version: str):
        from rest_framework.exceptions import NotAcceptable
        raise NotAcceptable(
            f"Versione '{version}' non supportata. "
            f"Versioni disponibili: {', '.join(self.allowed_versions or [])}"
        )
