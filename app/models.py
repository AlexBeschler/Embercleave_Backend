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
