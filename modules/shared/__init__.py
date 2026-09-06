"""Cross-cutting building blocks reused by every business module.

``shared`` must never import from a business module; the dependency direction
is always ``shipment``/``customs_clearance`` -> ``shared``.
"""
