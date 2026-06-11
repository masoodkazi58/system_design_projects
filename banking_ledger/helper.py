from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select,func,update,or_,and_,text
from tables import (
    Transaction,JournalEntry,
    TransactionType, TransferStatus,Account
)

# get_balance — no lock, used for read-only responses
def get_balance(db: Session, account_number: int) -> Decimal:
    result = db.execute(
        select(func.sum(JournalEntry.amount))
        .where(JournalEntry.account_number == account_number)
    ).scalar()
    return result or Decimal("0")


# ── DEPOSIT ───────────────────────────────────────────────
def deposit(
    db:             Session,
    account_number: int,
    amount:         Decimal,
    idempotency_key :str,
    description:    str | None = None,
) -> Transaction:
    existing = db.execute(select(Transaction).where(Transaction.idempotency_key == idempotency_key)).scalar_one_or_none()
    if existing:
        return existing
    txn = Transaction(
        type=TransactionType.DEPOSIT,
        idempotency_key = idempotency_key,
        status = TransferStatus.COMPLETED,
        description = description
    )
    db.add(txn)
    db.flush()
    journal_entry = JournalEntry(
        account_number = account_number,
        transaction_id = txn.id,
        amount = (amount),
        entry_type = TransactionType.DEPOSIT
    )
    db.add(journal_entry)
    db.commit()
    return txn

# ── WITHDRAW ──────────────────────────────────────────────
def withdraw(
    db:             Session,
    account_number: int,
    amount:         Decimal,
    idempotency_key : str,
    description:    str | None = None,
) -> Decimal:
    
    existing = db.execute(select(Transaction).where(Transaction.idempotency_key == idempotency_key)).scalar_one_or_none()
    if existing:
        return existing
    MAX_RETRIES = 5
    for attempt in range(MAX_RETRIES):
        account = db.get(Account,account_number)
        current_version = account.version
        balance = get_balance(db,account_number)
        if amount > balance:
            raise ValueError(f"insufficient funds: has {balance}")
        rows_updated = db.execute(
            update(Account)
            .where(Account.account_number == account_number)
            .where(Account.version == current_version)
            .values(version = current_version+1)
        ).rowcount
        if rows_updated == 1:
            txn = Transaction(
                type=TransactionType.WITHDRAW,
                idempotency_key = idempotency_key,
                status = TransferStatus.COMPLETED,
                description = description
            )
            db.add(txn)
            db.flush()
            negative_amount = -abs(amount)
            journal_entry = JournalEntry(
                account_number = account_number,
                transaction_id = txn.id,
                amount = negative_amount,
                entry_type = TransactionType.WITHDRAW
            )
            db.add(journal_entry)
            db.commit()
            return txn
        db.rollback()
        db.expire_all()
    raise ValueError("transaction failed after max retries, please try again")


# ── TRANSFER ──────────────────────────────────────────────
def transfer(
    db:           Session,
    from_account: int,
    to_account:   int,
    amount:       Decimal,
    idempotency_key: str,
    description:  str | None = None,
) -> dict:
    existing = db.execute(select(Transaction).where(Transaction.idempotency_key==idempotency_key)).scalar_one_or_none()
    if existing:
        return existing
    MAX_RETRIES = 5
    for attempts in range(MAX_RETRIES):
        db.expire_all()
        sender_account = db.get(Account,from_account)
        reciever_account = db.get(Account,to_account)
        sender_version = sender_account.version
        receiver_version = reciever_account.version

        balance = get_balance(db,account_number=from_account)
        if amount > balance:
            raise ValueError(f"insufficient funds: has {balance}")
        
        first, second = sorted([from_account, to_account])
        first_version  = sender_version   if first  == from_account else receiver_version
        second_version = receiver_version if second == to_account   else sender_version

        # 5. Execute Atomic Multi-Row Update
        rows_updated = db.execute(
            update(Account)
            .where(
                or_(
                    and_(Account.account_number == first,  Account.version == first_version),
                    and_(Account.account_number == second, Account.version == second_version)
                )
            )
            .values(version=Account.version + 1)
        ).rowcount
        
        if rows_updated == 2:
            negative_amount = -abs(amount)
            txn = Transaction(
                type=TransactionType.TRANSFER,
                idempotency_key = idempotency_key,
                status = TransferStatus.COMPLETED,
                description = description
            )
            db.add(txn)
            db.flush()
            journal_entry_sender = JournalEntry(
                account_number = from_account,
                transaction_id = txn.id,
                amount = negative_amount,
                entry_type = TransactionType.TRANSFER_OUT
            )
            journal_entry_reciever = JournalEntry(
                account_number = to_account,
                transaction_id = txn.id,
                amount = amount,
                entry_type = TransactionType.TRANSFER_IN
            )
            db.add(journal_entry_reciever)
            db.add(journal_entry_sender)
            db.commit()
            return txn
        db.rollback()
        
    raise ValueError("transfer failed after max retries, please try again")
    
def bank_audit(
        db : Session,
        account_number: int
):
    query = text("""
        SELECT je.created_at::text AS timestamp,t.id AS transaction_id,t.type AS transaction_type,je.entry_type AS ledger_action,je.amount AS movement,
            SUM(je.amount) OVER (PARTITION BY je.account_number ORDER BY je.created_at ASC, je.id ASC) AS running_balance,t.description
        FROM journal_entries je JOIN transactions t ON je.transaction_id = t.id WHERE je.account_number = :acc
        ORDER BY je.created_at DESC, je.id DESC;
    """)
    
    result = db.execute(query, {"acc": account_number}).mappings().all()
    return result

def bank_audit(db : Session,account_number: int):
    stmt = (
        select(JournalEntry, Transaction)
        .join(Transaction, JournalEntry.transaction_id == Transaction.id)
        .where(JournalEntry.account_number == account_number)
        .order_by(JournalEntry.created_at.desc(), JournalEntry.id.desc())
        .limit(20)
    )
    
    # Executes the query and returns a list of tuples: (JournalEntry, Transaction)
    return db.execute(stmt).all()