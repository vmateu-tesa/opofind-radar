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
