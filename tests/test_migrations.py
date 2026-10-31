"""The Alembic migrations build exactly the tables in server/models.py."""
from alembic import command
from alembic.config import Config

import server.importer


def test_migrations_match_models(tmp_path, monkeypatch):
    monkeypatch.setenv('SPACE_COWBOY_DB', f'sqlite:///{tmp_path}/m.db')
    server.importer.migrate()
    root = server.importer.os.path.dirname(server.importer.os.path.dirname(server.importer.__file__))
    cfg = Config(f'{root}/alembic.ini')
    cfg.set_main_option('script_location', f'{root}/migrations')
    command.check(cfg)              # raises if the models differ from the migrations
