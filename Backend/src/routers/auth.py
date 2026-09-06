from fastapi import APIRouter, HTTPException, status
from fastapi import Depends

from src.models.auth import LoginRequest, RegisterRequest, TokenResponse, LogoutRequest
from src.services.auth import get_auth_service
from src.services.database import get_database_service
from src.dependencies import get_current_user
from src.utils.config_loader import get_jwt_settings

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    db = get_database_service()
    auth = get_auth_service()

    # Check email not already taken
    existing = db.get_user_by_email(req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    password_hash = auth.hash_password(req.password)
    user = db.create_user(
        name=req.name,
        email=req.email,
        password_hash=password_hash,
    )

    token = auth.create_access_token(
        user_id=str(user["user_id"]),
        email=user["email"],
    )
    return TokenResponse(
        access_token=token,
        user_id=str(user["user_id"]),
        name=user["name"],
        email=user["email"],
    )



@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    db = get_database_service()
    auth = get_auth_service()

    user = db.get_user_by_email(req.email)
    if not user or not auth.verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Close any sessions that outlived the previous JWT
    cfg = get_jwt_settings()
    db.close_expired_sessions(expiry_minutes=cfg["access_token_expire_minutes"])

    token = auth.create_access_token(
        user_id=str(user["user_id"]),
        email=user["email"],
    )
    return TokenResponse(
        access_token=token,
        user_id=str(user["user_id"]),
        name=user["name"],
        email=user["email"],
    )


@router.post("/logout")
def logout(
    req: LogoutRequest,
    user: dict = Depends(get_current_user)
):
    """Close active session on logout."""
    db = get_database_service()
    if req.session_id:
        db.close_session(req.session_id)
    return {"detail": "Logged out"}