from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Convocatoria(Base):
    __tablename__ = 'convocatorias'

    id = Column(String, primary_key=True)  # Hash of the content or stable ID
    fuente = Column(String, nullable=False) # e.g. "diputacion", "boe", "dogv", "benidorm"
    titulo = Column(String, nullable=False) # Plaza o Titulo
    entidad = Column(String) # Ayuntamiento, etc.
    enlace = Column(String) # Link to PDF or base
    hash_contenido = Column(String, nullable=False) # SHA256 of the relevant content
    fecha_publicacion = Column(DateTime, default=datetime.utcnow)
    fecha_inicio = Column(String, nullable=True)
    fecha_fin = Column(String, nullable=True)
    observaciones = Column(Text) # The "Obs" field for dipu
    estado = Column(String, default="nuevo") # "nuevo", "actualizado"
    
    # Metadata as JSON string if needed, or simple columns
    vacantes = Column(String)

    # Tipo de publicacion detectado heuristicamente (ver core/classifier.py):
    # "convocatoria" | "listas" | "nombramiento" | "otros". Para filtrar en
    # la interfaz.
    tipo = Column(String, nullable=False, default="convocatoria")

    # Si el usuario ha marcado esta convocatoria para seguimiento manual:
    # cualquier ACTUALIZACION futura (el hash_contenido cambia) dispara
    # notificacion SIEMPRE, coincida o no con algun perfil de alertas.yaml.
    seguimiento = Column(Boolean, nullable=False, default=False)

class Notificacion(Base):
    __tablename__ = 'notificaciones'

    id = Column(Integer, primary_key=True, autoincrement=True)
    convocatoria_id = Column(String, ForeignKey('convocatorias.id'))
    hash_enviado = Column(String) # To know WHICH version of the convocatoria we sent
    fecha_envio = Column(DateTime, default=datetime.utcnow)
    canal = Column(String) # "telegram", "whatsapp", "email"


class MunicipioFavorito(Base):
    """Municipio marcado como favorito por el usuario: cualquier oferta
    NUEVA o ACTUALIZADA de ese municipio dispara notificacion por los
    canales activos, coincida o no con los perfiles de alertas.yaml.
    ``nombre`` es el canonico de core/geo.py (ver MUNICIPIOS_CANONICOS)."""
    __tablename__ = 'municipios_favoritos'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String, nullable=False, unique=True)
    creado_at = Column(DateTime, default=datetime.utcnow)


class Vigilancia(Base):
    """Plaza objetivo que el usuario vigila de forma fija (ver
    config/vigilancias.py). Se sincroniza desde la configuracion al arrancar.
    ``estado`` es 'vigilando' hasta que aparece una convocatoria que encaja,
    momento en que pasa a 'detectada' (guardando el id de esa convocatoria) y
    se dispara el aviso prioritario. Las REGLAS de deteccion viven en la
    config; esta tabla guarda solo el estado."""
    __tablename__ = 'vigilancias'

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String, nullable=False, unique=True)
    titulo = Column(String, nullable=False)
    entidad = Column(String)
    municipio = Column(String)
    enlace = Column(String)          # referencia (p.ej. PDF de la RPT)
    notas = Column(Text)
    estado = Column(String, nullable=False, default="vigilando")  # 'vigilando' | 'detectada'
    convocatoria_id = Column(String, nullable=True)  # convocatoria real detectada
    detectada_at = Column(DateTime, nullable=True)
    creado_at = Column(DateTime, default=datetime.utcnow)


class AvisoPlazo(Base):
    """Registro de los avisos de PLAZO ya enviados para una convocatoria, para
    no repetirlos. tipo_aviso es 'apertura', 'cierre_5d', 'cierre_1d'... (ver
    core/plazos.py). El UniqueConstraint garantiza que cada aviso se envie una
    sola vez por convocatoria, aunque el cron corra varias veces."""
    __tablename__ = 'avisos_plazo'
    __table_args__ = (UniqueConstraint('convocatoria_id', 'tipo_aviso', name='uq_aviso_plazo'),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    convocatoria_id = Column(String, ForeignKey('convocatorias.id'), nullable=False)
    tipo_aviso = Column(String, nullable=False)
    enviado_at = Column(DateTime, default=datetime.utcnow)
