"""Paquete dashboard: panel local del dueño (``python -m dashboard``) y API de servicio (``python -m dashboard.api``).

Backend (P1) en la biblioteca estándar: ``servidor`` (WSGI + SSE + estáticos), ``seguridad``, ``archivos`` (resolvedor
confinado y lectores tolerantes), ``vigia``, ``acciones`` (consola de lista blanca), ``pulido``, ``api_*`` (lectores de
``/api``) y ``api`` (servicio para Workers y ``engine.orq``). El frontend vive en ``dashboard/web/``. Contrato: ``CONTRATO.md``.
"""
