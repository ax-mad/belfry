import os
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

TOKEN = os.environ["REMINDER_API_TOKEN"]
bearer = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Security(bearer)):
    if credentials.credentials != TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
