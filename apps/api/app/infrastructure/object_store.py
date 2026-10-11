"""S3-compatible object-store adapter used by background ingestion stages."""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.settings import Settings

logger = logging.getLogger(__name__)

_NOT_FOUND_CODES = {"404", "NoSuchKey", "NoSuchObject", "NotFound"}


class S3ObjectStoreAdapter:
    """Delete objects from the configured local or S3-compatible store.

    Raw upload keys are persisted as complete object keys, so this adapter does
    not rebuild or broaden them. A missing object is treated as an idempotent
    success, while connectivity and authentication failures are allowed to
    propagate so BullMQ can retry the delete job.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def delete_object(self, object_key: str) -> None:
        """Delete one object, tolerating an object that is already absent."""
        local_root = self._settings.object_store_local_path
        if local_root:
            await self._delete_local_object(Path(local_root), object_key)
            return

        import aioboto3  # type: ignore[import-untyped]

        session = aioboto3.Session()
        try:
            async with session.client(
                "s3",
                endpoint_url=self._settings.object_store_endpoint,
                aws_access_key_id=self._settings.object_store_access_key,
                aws_secret_access_key=self._settings.object_store_secret_key,
                region_name=self._settings.object_store_region,
            ) as s3:
                await s3.delete_object(
                    Bucket=self._settings.object_store_bucket,
                    Key=object_key,
                )
        except Exception as error:
            if _is_not_found_error(error):
                logger.warning("Object already absent during delete: %s", object_key)
                return
            raise

    async def _delete_local_object(self, root: Path, object_key: str) -> None:
        """Delete a development-local object without escaping its root."""
        resolved_root = root.resolve()
        path = (resolved_root / object_key).resolve()
        if resolved_root not in path.parents:
            raise ValueError("Object key resolves outside the configured object-store root")
        try:
            path.unlink()
        except FileNotFoundError:
            logger.warning("Object already absent during delete: %s", object_key)


def _is_not_found_error(error: Exception) -> bool:
    if isinstance(error, FileNotFoundError):
        return True
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return False
    error_data = response.get("Error")
    if not isinstance(error_data, dict):
        return False
    return str(error_data.get("Code", "")) in _NOT_FOUND_CODES
