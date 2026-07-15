import os
import logging
import requests
import jwt
from typing import Optional
from fastapi import Request, HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

JWKS_URL = os.getenv("CLERK_JWKS_URL") or "https://api.clerk.com/v1/jwks"
CLERK_SECRET_KEY = os.getenv("CLERK_SECRET_KEY")

_jwks_cache = None

def get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        try:
            resp = requests.get(JWKS_URL, timeout=5)
            if resp.status_code == 200:
                _jwks_cache = resp.json()
                logger.info("Successfully fetched and cached Clerk JWKS")
            else:
                logger.error(f"Failed to fetch JWKS from Clerk: status={resp.status_code}")
        except Exception as e:
            logger.error(f"Error fetching JWKS from Clerk: {e}")
    return _jwks_cache

async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> str:
    """
    FastAPI dependency to get the current user (owner_id).
    If Clerk auth is not configured or no token is provided, returns 'anonymous'.
    If token is invalid or expired, raises 401.
    """
    if not credentials:
        return "anonymous"

    token = credentials.credentials
    try:
        # Decode without verification first to get kid from header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        jwks = get_jwks()
        if not jwks:
            logger.warning("Clerk JWKS is unavailable, falling back to 'anonymous' or rejecting")
            if CLERK_SECRET_KEY:
                raise HTTPException(status_code=500, detail="Authentication server unavailable")
            return "anonymous"

        # Find the correct public key
        public_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                break

        if not public_key:
            raise HTTPException(status_code=401, detail="Invalid token signing key")

        # Verify JWT (audience validation is off by default for generic Clerk keys, but signature & exp are verified)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False}
        )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing subject claim")
        return user_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Authentication token has expired")
    except Exception as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid authentication token: {str(e)}")

async def require_user(user_id: str = Depends(get_current_user)) -> str:
    """
    FastAPI dependency that enforces strict authentication if Clerk is configured.
    """
    if user_id == "anonymous" and CLERK_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Authentication required for this operation")
    return user_id
