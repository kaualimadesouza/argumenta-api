"""CLI: python -m argumenta.entrypoints.seed_content (or `make seed`)."""

from argumenta.adapters.db.seed.tutorial import seed_tutorial
from argumenta.adapters.db.session import session_scope


def main() -> None:
    with session_scope() as session:
        created = seed_tutorial(session)
    print("seed: tutorial created" if created else "seed: tutorial already present")


if __name__ == "__main__":
    main()
