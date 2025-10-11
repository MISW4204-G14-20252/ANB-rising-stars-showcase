# Importación de funciones y clases necesarias desde SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
# URL de la base de datos SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./db.db"
# Creación de un motor de base de datos usando la URL proporcionada
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True, # Imprimir las operaciones SQL realizadas (útil para debugging)
)

# Instancia SessionLocal para obtener una sesión de base de datos
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Instancia que se destinará a la creación de los modelos ORM
Base = declarative_base()

# Función para obtener una instancia de la base de datos
def get_db():
    # Crea una nueva sesión de base de datos
    db = SessionLocal()
    try:
        # Retorna la sesión para ser utilizada en la operación actual
        yield db
    finally:
        # Cierra la sesión de base de datos después de su uso
        db.close()