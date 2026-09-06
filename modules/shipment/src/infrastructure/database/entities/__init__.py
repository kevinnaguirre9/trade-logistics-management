"""Table definitions and imperative mappings of the Shipment module.

Tables are declared against the shared metadata using the module schema, and
domain objects are attached to them with
``mapper_registry.map_imperatively(...)`` inside :func:`start_mappers`.
"""

_mappers_started = False


def start_mappers() -> None:
    """Attach the Shipment domain objects to their tables (idempotent).

    Called once by the application composition root at start-up.
    """
    global _mappers_started
    if _mappers_started:
        return

    # Mappings are registered here as aggregates are implemented, e.g.:
    # mapper_registry.map_imperatively(
    #     Aggregate,
    #     aggregate_table,
    #     properties={"value_object": composite(ValueObject, ...)},
    # )

    _mappers_started = True
