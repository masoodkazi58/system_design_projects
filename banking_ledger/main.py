from fastapi import FastAPI, Request,HTTPException, Depends, status
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Annotated

from database import get_db
from auth import hash_password, verify_password
from schemas import (
    CreateAccount,
    UserResponse,
    BalanceAccount,
    BalanceResponse,
    DepositRequest,
    DepositResponse,
    WithdrawRequest,
    withdrawResponse,
    TransferRequest,
    TransferResponse,
    StatementResponse
)
from tables import Account,AccountStatus

# from ledger import deposit_task, withdraw_task, transfer_task
from helper import deposit,get_balance,withdraw,transfer,bank_audit

DBSession = Annotated[Session, Depends(get_db)]

app = FastAPI(title="Banking ledger")

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
templates = Jinja2Templates(directory="templates")

@app.get("/",name="HOME")
def home_page(request : Request):
    return templates.TemplateResponse(request=request,name="banking.html")


@app.post("/create_account", response_model=UserResponse)
def create_account(user_data: CreateAccount, db: DBSession):
    existing_email = (
        db.execute(select(Account).where(Account.email == user_data.email))
        .scalars()
        .first()
    )
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="user already exists"
        )
    new_user = Account(
        password_hash=hash_password(user_data.password),
        account_holder_name=user_data.account_holder_name,
        email=user_data.email,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserResponse(
        account_number      = new_user.account_number,
        account_holder_name = new_user.account_holder_name,
        email               = new_user.email,
        status              = new_user.status,
        balance             = get_balance(db, new_user.account_number),  # will be 0.00
    )


@app.post("/user_balance", response_model=BalanceResponse)
def user_balance(user_credentials: BalanceAccount, db: DBSession):
    account = db.get(Account, user_credentials.account_number)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="account not found"
        )
    if not verify_password(user_credentials.password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )
    try:
        result = get_balance(db,user_credentials.account_number)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return BalanceResponse(
        balance=result,
        account_holder_name=account.account_holder_name,
        account_number=user_credentials.account_number
    )


@app.post("/deposit",response_model=DepositResponse)
def deposit_route(deposit_data: DepositRequest, db: DBSession):
    account = db.get(Account, deposit_data.account_number)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="account not found"
        )
    if not verify_password(deposit_data.password, account.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        )
    if account.status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"account is {account.status.value}")
    try:
        result = deposit(db,deposit_data.account_number,deposit_data.amount,deposit_data.idempotency_key,deposit_data.description)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    return DepositResponse(
    message         = "deposited successfully",
    account_number  = deposit_data.account_number,
    new_balance     = get_balance(db, deposit_data.account_number),  # SUM query
    )


@app.post("/withdraw",response_model=withdrawResponse)
def withdraw_route(withdraw_data:WithdrawRequest,db:DBSession):
    account = db.get(Account, withdraw_data.account_number)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    if not verify_password(withdraw_data.password, account.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if account.status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"account is {account.status.value}")
    
    try:
        result = withdraw(db,withdraw_data.account_number,withdraw_data.amount,withdraw_data.idempotency_key,withdraw_data.description)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return withdrawResponse(
            message         = "withdraw successfully",
            account_number  = withdraw_data.account_number,
            new_balance     = get_balance(db, withdraw_data.account_number),  # SUM query
    )

@app.post("/transfer",response_model=TransferResponse)
def transfer_route(transfer_data:TransferRequest,db:DBSession):
    sender = db.get(Account,transfer_data.sender_account_no)
    if not sender:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sender account not found")
    if transfer_data.sender_account_no == transfer_data.receiver_account_no:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="sender and receiver cannot be the same account")
    if not verify_password(transfer_data.sender_password, sender.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if sender.status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"sender account is {sender.status.value}")
    
    receiver = db.get(Account,transfer_data.receiver_account_no)
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="receiver account not found")
    if receiver.status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"receiver account is {receiver.status.value}")

    
    try:
        result = transfer(db,from_account=transfer_data.sender_account_no,
                            to_account=transfer_data.receiver_account_no,
                            amount=transfer_data.amount,idempotency_key=transfer_data.idempotency_key)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    return TransferResponse(
        message     = f"transferred {transfer_data.amount} to account no.:{transfer_data.receiver_account_no} successfully",
        sender_balance = get_balance(db,transfer_data.sender_account_no)
    )
    
@app.post("/statement")
def bank_statment(user:BalanceAccount,db:DBSession):
    account = db.get(Account,user.account_number)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")
    if not verify_password(user.password, account.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    
    try:
        audit = bank_audit(db,account_number=user.account_number)
        result = [
                {
                    "timestamp": entry.created_at,
                    "transaction_id": txn.id,
                    "type": txn.type.value,           # e.g., 'deposit', 'withdraw', 'transfer'
                    "action": entry.entry_type.value, # e.g., 'transfer_out', 'transfer_in'
                    "amount": entry.amount,           # This will automatically show negative or positive values
                    "description": txn.description or "No description"
                }
                for entry, txn in audit
            ]
        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
