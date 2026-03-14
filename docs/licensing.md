# Licensing Policy

## Principle

Licensing is architecture, not paperwork. BACHBOT must distinguish clearly between open metadata, open symbolic encodings, restricted editions, local private files, and derived annotations.

## Storage Separation

The repository should keep:

- open metadata and manifests in version control;
- checksums and references to restricted assets in version control;
- restricted score files and rights-sensitive material in local private storage;
- derived annotations and feature tables only when their upstream licenses permit it.

Do not assume that “Bach is public domain” means every modern file is redistributable.

## Dataset Classes

### Authority Metadata

Authority metadata includes catalog, source, and repository records from resources such as Bach Digital and RISM. These records may be open, but their licenses still need to be stored explicitly.

### Open Symbolic Corpora

Some corpora, such as certain DCML datasets, are open enough to redistribute or derive from more freely. Their exact terms still need manifest entries.

### Edition-Sensitive Files

Modern editions, pedagogical editions, engraved files, and some repository exports may carry restrictions even when the underlying music is historically public domain.

### Derived Outputs

Derived analyses, feature tables, and generated artifacts may or may not be redistributable depending on the provenance chain. They should inherit a license snapshot or an explicit local-use flag.

## Manifest Requirements

Every dataset manifest should include:

- dataset id;
- source url or persistent identifier base;
- retrieved date;
- declared license fields;
- checksum policy;
- redistribution notes;
- storage policy;
- attribution requirements when applicable.

## Recommended Policy Defaults

- Default to conservative handling when license status is ambiguous.
- Keep raw restricted files out of the public repo.
- Preserve attribution obligations in exports and reports.
- Store enough manifest detail to rehydrate a local corpus from lawful sources later.

## Generated Artifacts

Generated materials should carry:

- their own artifact class label;
- the corpus bucket they drew from;
- provenance to the generation and validation workflow;
- a display label that makes non-authentic status obvious.

That honesty requirement is separate from copyright but closely related to responsible publication.
