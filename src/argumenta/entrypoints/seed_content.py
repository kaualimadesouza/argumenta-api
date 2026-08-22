"""CLI: python -m argumenta.entrypoints.seed_content (or `make seed`).
Idempotent per story, so it runs on every deploy: a story already there is left
untouched and reported as present."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from argumenta.adapters.db.seed.enem_care import seed_enem_care
from argumenta.adapters.db.seed.tutorial import seed_tutorial
from argumenta.adapters.db.session import session_scope

SEEDS: tuple[tuple[str, Callable[[Session], bool]], ...] = (
    ("tutorial", seed_tutorial),
    ("cuidado-invisivel", seed_enem_care),
)


def main() -> None:
    with session_scope() as session:
        created = {name: seed(session) for name, seed in SEEDS}
    for name, was_created in created.items():
        print(f"seed: {name} {'created' if was_created else 'already present'}")


if __name__ == "__main__":
    main()
