## ADDED Requirements

### Requirement: ObjectStoreAdapter protocol delete_object is implemented
The concrete object store adapter SHALL implement `delete_object(object_key: str) -> None` to remove a raw source file from the object store. The protocol declaration already exists; this requirement covers the concrete implementation.

#### Scenario: delete_object removes file from bucket
- **WHEN** `delete_object` is called with an existing key
- **THEN** the file is deleted from the configured bucket

#### Scenario: delete_object is non-fatal on missing key
- **WHEN** `delete_object` is called with a key that does not exist in the bucket
- **THEN** a warning is logged and the method returns without raising
