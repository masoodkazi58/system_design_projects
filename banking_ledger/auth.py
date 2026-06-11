from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

def hash_password(password:str) -> str:
    return password_hash.hash(password=password)

def verify_password(plain_password:str,hashed_password:str) -> bool:
    return password_hash.verify(plain_password,hashed_password)

# # auth.py
# from fastapi import HTTPException, Depends, Header
# from sqlalchemy.orm import Session
# from datetime import datetime, timedelta
# import jwt
# from database import  get_db

# # JWT Configuration
# SECRET_KEY = "your-super-secret-key-change-this-in-production"  # Use environment variable!
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour

# def create_access_token(account_number: str) -> str:
#     """Create JWT token for authenticated account"""
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     payload = {
#         "sub": account_number,
#         "exp": expire,
#         "iat": datetime.utcnow()
#     }
#     token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
#     return token

# def verify_token(token: str) -> str:
#     """Verify JWT token and return account number"""
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         account_number = payload.get("sub")
#         if account_number is None:
#             raise HTTPException(status_code=401, detail="Invalid token")
#         return account_number
#     except jwt.ExpiredSignatureError:
#         raise HTTPException(status_code=401, detail="Token has expired")
#     except jwt.InvalidTokenError:
#         raise HTTPException(status_code=401, detail="Invalid token")

# async def get_current_account(
#     authorization: str = Header(..., alias="Authorization"),
#     db: Session = Depends(get_db)
# ) -> Account:
#     """Dependency to get current authenticated account from JWT token"""
#     # Extract token from "Bearer <token>"
#     if not authorization.startswith("Bearer "):
#         raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
#     token = authorization.replace("Bearer ", "")
#     account_number = verify_token(token)
    
#     # Get account from database
#     account = db.query(Account).filter(Account.account_number == account_number).first()
#     if not account:
#         raise HTTPException(status_code=401, detail="Account not found")
    
#     if account.status != "active":
#         raise HTTPException(status_code=403, detail=f"Account is {account.status}")
    
#     return account