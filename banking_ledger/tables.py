from sqlalchemy import String, Numeric, DateTime, Integer, ForeignKey, Text,Enum,Sequence
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional
import enum
from database import Base, engine


# ── Enums ─────────────────────────────────────────────────
class TransactionType(str, enum.Enum):
    DEPOSIT      = "deposit"
    WITHDRAW     = "withdraw"
    TRANSFER     = "transfer" 
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN  = "transfer_in"

class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"

class TransferStatus(str, enum.Enum):
    PENDING   = "pending"
    COMPLETED = "completed"
    FAILED    = "failed"
    REVERSED  = "reversed"



# ── Account ───────────────────────────────────────────────
class Account(Base):
    __tablename__ = "accounts"

    
    account_number: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
        )
    password_hash       : Mapped[str]              = mapped_column(String(255),  nullable=False)
    account_holder_name : Mapped[str]              = mapped_column(String(100),  nullable=False)
    email               : Mapped[str]              = mapped_column(String(100),  nullable=False, unique=True, index=True)
    status              : Mapped[AccountStatus]    = mapped_column(Enum(AccountStatus), default=AccountStatus.ACTIVE)
    version             : Mapped[int]             = mapped_column(Integer,default=int(0))
    created_at          : Mapped[datetime]         = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    


# ── Transaction ───────────────────────────────────────────
class Transaction(Base):
    __tablename__ = "transactions"

    id                : Mapped[int]             = mapped_column(Integer,     primary_key=True, autoincrement=True)
    type              : Mapped[TransactionType] = mapped_column(Enum(TransactionType),nullable=False)
    description       : Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key   : Mapped[str]             = mapped_column(String(255), unique=True, nullable=False)
    status            : Mapped[TransferStatus]  = mapped_column(Enum(TransferStatus), default=AccountStatus.ACTIVE)
    created_at        : Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


# ── Transfer ──────────────────────────────────────────────
class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id             : Mapped[int]            = mapped_column(Integer,     primary_key=True, autoincrement=True)
    account_number : Mapped[int]            = mapped_column(Integer, 
                                              ForeignKey("accounts.account_number"), nullable=False, index=True)
    transaction_id : Mapped[int]            = mapped_column(Integer,ForeignKey("transactions.id"),nullable=False,index=True)
    amount         : Mapped[Decimal]        = mapped_column(Numeric(20, 2), nullable=False)
    entry_type     : Mapped[TransactionType]= mapped_column(Enum(TransactionType),nullable=False)
    created_at    : Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    

    


Base.metadata.create_all(bind=engine)
