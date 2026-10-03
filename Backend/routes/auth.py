import random
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from models.database import get_db
from models.entities import User
from auth.hash import hash_password, verify_password
from auth.jwt import create_access_token, get_current_user
from core.config import settings
from core.email_service import send_verification_email
from core.limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

class SignupRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class VerifyRequest(BaseModel):
    email: Optional[str] = None
    code: Optional[str] = None
    token: Optional[str] = None

class ResendRequest(BaseModel):
    email: str

class AuthResponse(BaseModel):
    token: str
    username: str
    email: str

class SettingsUpdateRequest(BaseModel):
    api_key: Optional[str] = None

def mask_api_key(key: Optional[str]) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:6]}...{key[-4:]}"

@router.post("/signup")
@limiter.limit(settings.SIGNUP_RATE_LIMIT)
def signup(request: Request, req: SignupRequest, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    username_clean = req.username.strip()

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this email address is already registered."
            )
        else:
            # User started signup earlier but hasn't verified yet; refresh credentials and resend code
            existing_user.username = username_clean
            existing_user.hashed_password = hash_password(req.password)
            code = f"{random.randint(100000, 999999)}"
            token = secrets.token_urlsafe(32)
            existing_user.verification_code = code
            existing_user.verification_token = token
            existing_user.verification_expires_at = datetime.utcnow() + timedelta(hours=24)
            db.commit()

            send_verification_email(existing_user.email, existing_user.username, code, token)
            return {
                "status": "pending_verification",
                "email": existing_user.email,
                "message": "Verification email resent. Please enter the 6-digit code sent to your inbox."
            }

    # Check username collision
    if db.query(User).filter(User.username == username_clean).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken. Please choose another username."
        )

    # Generate 6-digit verification code and token
    code = f"{random.randint(100000, 999999)}"
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)

    hashed = hash_password(req.password)
    new_user = User(
        username=username_clean,
        email=email_clean,
        hashed_password=hashed,
        is_verified=False,
        verification_code=code,
        verification_token=token,
        verification_expires_at=expires_at
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Send verification email via SMTP (or console fallback)
    send_verification_email(new_user.email, new_user.username, code, token)

    return {
        "status": "pending_verification",
        "email": new_user.email,
        "message": "Account created! Please check your email for your 6-digit verification code."
    }

@router.post("/login", response_model=AuthResponse)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
def login(request: Request, req: LoginRequest, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    
    # 1. Account not found
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No account found with this email address."
        )

    # 2. Password mismatch
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please try again."
        )

    # 3. Account not verified
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your email has not been verified yet. Please check your inbox for the verification code.",
            headers={"X-Unverified": "true"}
        )

    token = create_access_token(data={"sub": user.id})
    return AuthResponse(token=token, username=user.username, email=user.email)

@router.post("/verify")
def verify_account(req: VerifyRequest, db: Session = Depends(get_db)):
    user = None

    # Verify by token (link click)
    if req.token:
        user = db.query(User).filter(User.verification_token == req.token).first()
    # Verify by 6-digit code + email
    elif req.code and req.email:
        code_clean = req.code.strip()
        email_clean = req.email.strip().lower()
        user = db.query(User).filter(User.email == email_clean, User.verification_code == code_clean).first()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid verification code or token."
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code or link. Please check your code and try again."
        )

    if user.verification_expires_at and datetime.utcnow() > user.verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new one."
        )

    # Mark user as verified
    user.is_verified = True
    user.verification_code = None
    user.verification_token = None
    user.verification_expires_at = None
    db.commit()

    # Automatically issue JWT so user is immediately logged in
    token = create_access_token(data={"sub": user.id})
    return {
        "status": "success",
        "message": "Account verified successfully!",
        "token": token,
        "username": user.username,
        "email": user.email
    }

@router.get("/verify")
def verify_link_redirect(token: str, db: Session = Depends(get_db)):
    """Direct URL verification handler when user clicks link in their email."""
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/verify?error=invalid_token")

    if user.verification_expires_at and datetime.utcnow() > user.verification_expires_at:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/verify?error=expired_token&email={user.email}")

    user.is_verified = True
    user.verification_code = None
    user.verification_token = None
    user.verification_expires_at = None
    db.commit()

    # Issue token and redirect to frontend with token
    auth_token = create_access_token(data={"sub": user.id})
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/verify?verified=true&token={auth_token}&user={user.username}")

@router.post("/resend-verification")
@limiter.limit(settings.RESEND_RATE_LIMIT)
def resend_verification(request: Request, req: ResendRequest, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email address."
        )

    if user.is_verified:
        return {
            "status": "already_verified",
            "message": "This account is already verified. You can log in directly."
        }

    # Generate fresh code and token
    code = f"{random.randint(100000, 999999)}"
    token = secrets.token_urlsafe(32)
    user.verification_code = code
    user.verification_token = token
    user.verification_expires_at = datetime.utcnow() + timedelta(hours=24)
    db.commit()

    send_verification_email(user.email, user.username, code, token)
    return {
        "status": "success",
        "message": "A new verification code has been sent to your email."
    }

@router.put("/settings")
def update_settings(req: SettingsUpdateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.api_key is not None:
        new_key = req.api_key.strip()
        if "..." in new_key or "***" in new_key:
            # Masked key received, don't overwrite
            pass
        elif new_key == "":
            current_user.api_key = None
        else:
            current_user.api_key = new_key
    db.commit()
    return {"status": "success", "message": "Settings updated successfully"}

@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_verified": current_user.is_verified,
        "api_key": mask_api_key(current_user.api_key)
    }
