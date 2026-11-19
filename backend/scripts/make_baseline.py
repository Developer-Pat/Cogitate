"""Generate the single baseline revision from Base.metadata.

Runs alembic's autogenerate against a THROWAWAY EMPTY database, so the revision
it writes is the whole schema as `create_table` calls instead of a diff against
the developer's populated database. The generated revision's `down_revision` is
then cleared, which makes it the root — the one revision the chain keeps.

Usage: python scripts/make_baseline.py
"""

import os
import tempfile

from alembic import command
from alembic.config import Config

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    tmp_dir = tempfile.mkdtemp()
    url = f"sqlite:///{os.path.join(tmp_dir, 'empty.db')}"

    cfg = Config(os.path.join(HERE, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(HERE, "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)

    # Autogenerate refuses a database that is not at the current head, and this
    # one is empty. Stamping it at head writes no DDL — it only lets the
    # comparison run against zero tables, which is what makes the revision a
    # full create_table script rather than a diff.
    command.stamp(cfg, "head")

    command.revision(cfg, message="baseline", rev_id="0001", autogenerate=True)
    print("generated rev 0001 against", url)


if __name__ == "__main__":
    main()
