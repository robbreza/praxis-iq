# Clean GitHub Setup Instructions

Repository name: praxis-iq

## Target structure

praxis-iq/
- README.md
- docs/README.md
- database/README.md
- backend/README.md
- frontend/README.md
- python/README.md
- assets/README.md
- tests/README.md

## Critical rule

Before creating any top-level folder, confirm the breadcrumb is:

robbreza / praxis-iq

Do not create a file named `docs/README.md` while already inside `/docs`. That creates `/docs/docs/README.md`.

## Manual folder creation process

1. Start at repository root.
2. Click Add file → Create new file.
3. Enter filename, for example `database/README.md`.
4. Enter content.
5. Commit.
6. Click breadcrumb `praxis-iq` to return to root.
7. Repeat for next top-level folder.
