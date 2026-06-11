from pydantic import BaseModel,field_validator,EmailStr
from decimal import Decimal
from datetime import datetime
from typing import Optional



class CreateAccount(BaseModel):
    account_holder_name:str
    email : EmailStr
    password: str

class UserResponse(BaseModel):
    account_number:int
    account_holder_name:str
    email:str
    balance : Decimal
    status : str

class BalanceAccount(BaseModel):
    account_number:int
    password:str

class BalanceResponse(BaseModel):
    balance : Decimal
    account_holder_name:str
    account_number:int

    
class DepositRequest(BaseModel):
    account_number: int
    amount:     Decimal
    password:  str
    idempotency_key : str
    description : str | None=None
    @field_validator("amount")
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v
    
class DepositResponse(BaseModel):
    message : str
    account_number: int
    new_balance : Decimal
    
class WithdrawRequest(BaseModel):
    account_number : int
    amount:     Decimal
    idempotency_key : str
    password : str
    description:    str | None = None

    @field_validator("amount")
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v
    
class withdrawResponse(DepositResponse):
    pass
    
class TransferRequest(BaseModel):
    sender_account_no:   int
    sender_password : str
    receiver_account_no: int
    idempotency_key : str
    amount:              Decimal

    @field_validator("amount")
    def must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be greater than zero")
        return v
    
class TransferResponse(BaseModel):
    message : str
    sender_balance : Decimal

class StatementResponse(BaseModel):
    entry_type  : str
    amount      : Decimal
    description : str | None
    created_at  : datetime



