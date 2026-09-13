"""Files bounded context: storing files across diverse storage classes.

A root module beside `shipment` and `customs_clearance`, not a shared utility:
it owns the `files` schema, an aggregate with its own invariants, and an HTTP
contract of its own, which is what it would need to leave the monolith and run
as a separate service.

Nothing about the storage class leaks across its boundary. A caller names a
disk and receives a `file_uuid`; whether the bytes live on a local volume, in a
GCS or S3 bucket, or on an SFTP server is this module's business alone. It
imports no other business module.
"""
