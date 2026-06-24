"""Coalesce free-text callflow language values into the new Selection.

Before 19.0.3.1.2 ``connect.callflow.language`` was a plain ``Char`` and could
hold anything. With this version it becomes a ``Selection``. Any value that is
not part of the new Selection list (returned by ``_get_language_selection``)
would make the form crash with ``ValueError`` on load, so we coalesce stray
values to ``'en-US'``.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        SELECT DISTINCT language
          FROM connect_callflow
         WHERE language IS NOT NULL
        """
    )
    existing = {row[0] for row in cr.fetchall()}
    if not existing:
        return

    # Mirror the selection from connect.callflow._get_language_selection.
    # Kept literal here so the migration is independent of model load order.
    allowed = {
        'ca-ES', 'cs-CZ', 'da-DK', 'de-DE', 'en-GB', 'en-US', 'es-ES',
        'es-MX', 'fi-FI', 'fr-FR', 'hu-HU', 'is-IS', 'it-IT', 'nl-BE',
        'nl-NL', 'pl-PL', 'pt-BR', 'pt-PT', 'ro-RO', 'ru-RU', 'sk-SK',
        'sv-SE', 'tr-TR', 'uk-UA', 'vi-VN', 'zh-CN',
    }
    stale = existing - allowed
    if not stale:
        return

    _logger.warning(
        "connect post-migration: coalescing %s out-of-selection callflow "
        "language value(s) to 'en-US': %s",
        len(stale), sorted(stale),
    )
    cr.execute(
        """
        UPDATE connect_callflow
           SET language = 'en-US'
         WHERE language = ANY(%s)
        """,
        (list(stale),),
    )
