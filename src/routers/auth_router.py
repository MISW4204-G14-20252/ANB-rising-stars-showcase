from fastapi import APIRouter, Depends, HTTPException, status

from src.db.database import get_db
from src.models.db_models import Usuario
from src.schemas.pydantic_schemas import UsuarioCreateSchema, UsuarioLoginSchema, UsuarioSchema, TokenData

from sqlalchemy.orm import Session

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone

# from worker.tasks import registrar_log

SECRET_KEY = "secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

auth_router = APIRouter(tags=['Auth'])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login')

@auth_router.post('/signup', response_model = UsuarioSchema)
async def create_user(user: UsuarioCreateSchema, db: Session = Depends(get_db)):
    db_user_username = db.query(Usuario).filter(Usuario.nombre == user.nombre).first()
    if db_user_username:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = 'El nombre ya se encuentra registrado.',
        )
    db_user = Usuario(
        nombre = user.nombre,
        contrasena = user.contrasena,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@auth_router.post('/login', response_model = TokenData)
async def login_for_access_token(user: UsuarioLoginSchema, db: Session = Depends(get_db)):
    user_db = db.query(Usuario).filter(Usuario.nombre == user.nombre).first()
    if not user_db:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST, detail = 'El usuario no es correcto.')

    if not user.contrasena == user_db.contrasena:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail = 'La contraseña no es correcta.')

    # registrar_log.delay(user.nombre, datetime.now(timezone.utc))
    expires_delta = timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token_data={'sub': user_db.nombre,
                       'exp': datetime.now(timezone.utc) + expires_delta}
    return {'access_token': jwt.encode(access_token_data, SECRET_KEY, algorithm = ALGORITHM), 'token_type': 'bearer'}

# use this function as a dependency in routes that require authentication
# auth: HTTPAuthorizationCredentials = Depends(bearer) as parameter
# and the username = verify_token(auth.credentials)
async def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        if username is None:
            raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = 'Credenciales de autenticación inválidas.',
            headers = {'WWW-Authenticate': 'Bearer'})
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail = 'Credenciales de autenticación inválidas.',
            headers = {'WWW-Authenticate': 'Bearer'})
