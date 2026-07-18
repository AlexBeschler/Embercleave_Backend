from datetime import datetime

from pydantic import BaseModel


class BootstrapResponse(BaseModel):
    uid: str
    email: str | None
    connectionStatus: str
    activePeriodId: str


class LinkTokenResponse(BaseModel):
    linkToken: str


class BankConnectionRequest(BaseModel):
    publicToken: str


class ConnectionStatusResponse(BaseModel):
    connectionStatus: str


class BudgetResponse(BaseModel):
    id: str
    name: str
    amount: float
    order: int


class CreateBudgetRequest(BaseModel):
    name: str
    amount: float


class PatchBudgetRequest(BaseModel):
    name: str | None = None
    amount: float | None = None


class ReorderBudgetsRequest(BaseModel):
    orderedIds: list[str]


class TransactionResponse(BaseModel):
    id: str
    accountId: str
    accountType: str
    description: str
    amount: float
    postedDate: datetime | None
    transactedAt: datetime | None
    pending: bool
    status: str
    budgetId: str | None
    periodId: str


class AcceptTransactionRequest(BaseModel):
    budgetId: str


class BudgetSummaryResponse(BaseModel):
    id: str
    name: str
    amount: float
    order: int
    spent: float
    left: float


class DashboardResponse(BaseModel):
    cashBalance: float
    budgets: list[BudgetSummaryResponse]
    recentTransactions: list[TransactionResponse]


class ClearMonthResponse(BaseModel):
    activePeriodId: str
