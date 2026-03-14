from __future__ import annotations

from bachbot.registry.manifests import DatasetManifest


def manifest_completeness(manifest: DatasetManifest) -> float:
    required = {
        "dataset_id": bool(manifest.dataset_id),
        "type": bool(manifest.type),
        "source_url": bool(manifest.source_url),
        "retrieved_at": bool(manifest.retrieved_at),
        "license": bool(manifest.license.data or manifest.license.site_content or manifest.license.files),
        "checksum_policy": bool(manifest.checksum_policy),
    }
    return round(sum(1 for present in required.values() if present) / len(required), 2)
