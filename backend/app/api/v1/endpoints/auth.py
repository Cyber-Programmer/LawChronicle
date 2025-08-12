from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from ....core.auth import authenticate_user, create_access_token, get_current_user, verify_password, get_password_hash
from ....core.config import settings
from shared.types.common import BaseResponse

router = APIRouter()

# For demo purposes - in production, this would be stored in database
# Using environment variables for better security
import os
DEMO_USER = {
    "username": os.getenv("DEMO_USERNAME", "admin"),
    "password": os.getenv("DEMO_USER_PASSWORD", "admin123")  # We'll hash this at runtime
}

@router.post("/login", response_model=BaseResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login endpoint for authentication"""
    # Simple authentication check
    if (form_data.username == DEMO_USER["username"] and 
        form_data.password == DEMO_USER["password"]):
        user = True
    else:
        user = False
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    
    return BaseResponse(
        success=True,
        message="Login successful",
        data={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60
        }
    )

@router.get("/me", response_model=BaseResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return BaseResponse(
        success=True,
        message="User information retrieved",
        data=current_user
    )

@router.post("/logout", response_model=BaseResponse)
async def logout():
    """Logout endpoint (client should discard token)"""
    return BaseResponse(
        success=True,
        message="Logout successful - please discard your token"
    )

@router.get("/test-auth")
async def test_auth():
    """Test authentication debugging"""
    test_password = "admin123"
    stored_hash = DEMO_USER["hashed_password"]
    
    verification_result = verify_password(test_password, stored_hash)
    
    return {
        "test_password": test_password,
        "stored_hash": stored_hash,
        "verification_result": verification_result,
        "demo_user": DEMO_USER
    }
