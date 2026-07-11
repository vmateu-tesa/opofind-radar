import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from db.models import Base, Convocatoria

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'oporadar.db')

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(f'sqlite:///{DB_PATH}', echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _migrate_missing_columns():
    """Base.metadata.create_all() solo crea tablas NUEVAS: si una columna se
    añade al modelo (p.ej. tipo/seguimiento) despues de que la tabla ya
    exista en produccion, create_all() no la añade y la app rompe con
    "no such column". Como es una BD SQLite pequeña de un solo usuario, se
    hace una migracion minima a mano (ALTER TABLE ADD COLUMN) en vez de
    traer Alembic para esto."""
    inspector = inspect(engine)
    if 'convocatorias' not in inspector.get_table_names():
        return  # tabla nueva: create_all() ya la crea con todas las columnas

    columnas_existentes = {c['name'] for c in inspector.get_columns('convocatorias')}
    for col in Convocatoria.__table__.columns:
        if col.name in columnas_existentes:
            continue
        tipo_sql = col.type.compile(engine.dialect)
        default_sql = ''
        if col.default is not None and col.default.is_scalar:
            valor = col.default.arg
            if isinstance(valor, bool):
                default_sql = f" DEFAULT {1 if valor else 0}"
            elif isinstance(valor, (int, float)):
                default_sql = f" DEFAULT {valor}"
            else:
                default_sql = f" DEFAULT '{valor}'"
        with engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE convocatorias ADD COLUMN {col.name} {tipo_sql}{default_sql}'))


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_missing_columns()

def get_session():
    return SessionLocal()
