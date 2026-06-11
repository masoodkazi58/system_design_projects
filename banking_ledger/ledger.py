import threading
import queue
from decimal import Decimal
from database import Sessionlocal
from helper import deposit,withdraw,transfer

transaction_queue = queue.Queue()

def worker():
    while True:
        task = transaction_queue.get()
        if task is None:
            break

        kind = task["kind"]
        result = task["result"]
        db = Sessionlocal()

        try:
            if kind == "deposit":
                new_balance = deposit(
                    db             = db,
                    account_number = task["account_number"],
                    amount         = task["amount"],
                    description    = task.get("description"),
                )
                result["status"]  = "ok"
                result["balance"] = new_balance

            elif kind == "withdraw":
                new_balance = withdraw(
                    db             = db,
                    account_number = task["account_number"],
                    amount         = task["amount"],
                    description    = task.get("description"),
                )
                result["status"]  = "ok"
                result["balance"] = new_balance

            elif kind == "transfer":
                data = transfer(
                    db           = db,
                    from_account = task["from_account"],
                    to_account   = task["to_account"],
                    amount       = task["amount"],
                    description  = task.get("description"),
                )
                result["status"] = "ok"
                result["data"]   = data
        except ValueError as e:
            db.rollback()
            result["status"] = "error"
            result["error"]  = str(e)

        except Exception as e:
            db.rollback()
            result["status"] = "error"
            result["error"]  = f"unexpected error: {str(e)}"
           
        finally:
            result["event"].set()           # wake up the waiting route
            transaction_queue.task_done()
            db.close()    

worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()

def _make_result() ->dict:
    return {
        "status":None,
        "error" :None,
        "event" :threading.Event(),
    }

def _submit(task:dict) -> dict:
    result = _make_result()
    task["result"] = result
    transaction_queue.put(task)
    fired = result["event"].wait(timeout = 30)
    if not fired:
        result["status"] = "error"
        result["error"]  = "transaction timed out"
    return result

def deposit_task(account_number: int, amount: Decimal, description: str = None) -> dict:
    return _submit({
        "kind":           "deposit",
        "account_number": account_number,
        "amount":         Decimal(str(amount)),
        "description":    description,
    })

def withdraw_task(account_number: int, amount: Decimal, description: str = None) -> dict:
    return _submit({
        "kind":           "withdraw",
        "account_number": account_number,
        "amount":         Decimal(str(amount)),
        "description":    description,
    })

def transfer_task(from_account: int, to_account: int, amount: Decimal, description: str = None) -> dict:
    return _submit({
        "kind":         "transfer",
        "from_account": from_account,
        "to_account":   to_account,
        "amount":       Decimal(str(amount)),
        "description":  description,
    })

def get_queue_size() -> int:
    return transaction_queue.qsize()

def shutdown_worker():
    transaction_queue.put(None)
    worker_thread.join(timeout=5)