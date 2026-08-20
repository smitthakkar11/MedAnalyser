"""Data-access layer.

Repositories own all query construction. Services depend on repositories, never
on the ORM session directly, so that persistence details stay replaceable and
ownership filters live in exactly one place.
"""
