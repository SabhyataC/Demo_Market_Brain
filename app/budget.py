import os
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

MAX_DAILY_BUDGET = float(os.getenv("MAX_DAILY_BUDGET", "500"))


def check_budget(payload: dict):
    amount = payload.get("daily_budget")
    if amount is None:
        raise HTTPException(400, "Ad proposals must include daily_budget")
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise HTTPException(400, "daily_budget must be a positive number")
    if amount > MAX_DAILY_BUDGET:
        raise HTTPException(
            400, f"daily_budget {amount} exceeds cap {MAX_DAILY_BUDGET}"
        )