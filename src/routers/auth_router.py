from fastapi import APIRouter, Depends, HTTPException, status

from src.db.database import get_db
from src.models.db_models import Usuario
from src.schemas.pydantic_schemas import UsuarioCreateSchema, UsuarioLoginSchema, UsuarioSchema, TokenData

from sqlalchemy.orm import Session

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext


SECRET_KEY = "secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

auth_router = APIRouter(tags=['Auth'])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login')
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@auth_router.post('/signup', response_model = UsuarioSchema, status_code=status.HTTP_201_CREATED)
async def create_user(user: UsuarioCreateSchema, db: Session = Depends(get_db)):

    #Validate passwords
    if user.password1 != user.password2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Las contraseñas no coinciden.')
    
    #Validate unique email
    db_user_username = db.query(Usuario).filter(Usuario.email == user.email).first()
    if db_user_username:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = 'El correo electrónico ya se encuentra registrado.',
        )
    
    #Hash password
    #hashed_password = pwd_context.hash(user.password1)

    #Create user    
    db_user = Usuario(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        password=user.password1,
        city=user.city,
        country=user.country
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@auth_router.post('/login', response_model = TokenData)
async def login_for_access_token(user: UsuarioLoginSchema, db: Session = Depends(get_db)):
    user_db = db.query(Usuario).filter(Usuario.email == user.email).first()
    if not user_db:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST, detail = 'El usuario no es correcto.')

    if user.password != user_db.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail = 'La contraseña no es correcta.')

    # registrar_log.delay(user.nombre, datetime.now(timezone.utc))
    expires_delta = timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token_data={'sub': user_db.email,
                       'exp': datetime.now(timezone.utc) + expires_delta}
    return {'access_token': jwt.encode(access_token_data, SECRET_KEY, algorithm = ALGORITHM), 'token_type': 'bearer'}

# use this function as a dependency in routes that require authentication
# auth: HTTPAuthorizationCredentials = Depends(bearer) as parameter
# and the username = verify_token(auth.credentials)
def verify_token(token: str = Depends(oauth2_scheme)):
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

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """Decodifica el token JWT y devuelve el usuario autenticado."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(Usuario).filter(Usuario.email == username).first()
    if user is None:
        raise credentials_exception

    return user