from functools import lru_cache

import plaid
from plaid.api import plaid_api
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.jwk_public_key import JWKPublicKey
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.webhook_verification_key_get_request import WebhookVerificationKeyGetRequest

from app.config import get_settings
from app.secrets import get_secret

_ENVIRONMENT_HOSTS = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}


@lru_cache
def get_plaid_client() -> plaid_api.PlaidApi:
    settings = get_settings()
    configuration = plaid.Configuration(
        host=_ENVIRONMENT_HOSTS[settings.plaid_env],
        api_key={
            "clientId": get_secret(settings.plaid_client_id_secret_id),
            "secret": get_secret(settings.plaid_secret_secret_id),
        },
    )
    return plaid_api.PlaidApi(plaid.ApiClient(configuration))


def create_link_token(uid: str, webhook_url: str) -> str:
    """architecture.md §3.2: mints a short-lived, single-use link_token
    used to launch Plaid Link in the mobile app."""
    request = LinkTokenCreateRequest(
        client_name="Embercleave",
        language="en",
        country_codes=[CountryCode("US")],
        user=LinkTokenCreateRequestUser(client_user_id=uid),
        products=[Products("transactions")],
        webhook=webhook_url,
    )
    response = get_plaid_client().link_token_create(request)
    return response.link_token


def exchange_public_token(public_token: str) -> tuple[str, str]:
    """Returns (access_token, item_id)."""
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = get_plaid_client().item_public_token_exchange(request)
    return response.access_token, response.item_id


def get_accounts(access_token: str) -> list:
    request = AccountsGetRequest(access_token=access_token)
    response = get_plaid_client().accounts_get(request)
    return response.accounts


def sync_transactions_page(access_token: str, cursor: str | None):
    request = TransactionsSyncRequest(access_token=access_token, cursor=cursor)
    return get_plaid_client().transactions_sync(request)


def remove_item(access_token: str) -> None:
    get_plaid_client().item_remove(ItemRemoveRequest(access_token=access_token))


@lru_cache
def get_webhook_verification_key(key_id: str) -> JWKPublicKey:
    """Fetched once per kid and cached for the process lifetime — Plaid's
    keys rotate rarely (architecture.md §3.3.1)."""
    request = WebhookVerificationKeyGetRequest(key_id=key_id)
    response = get_plaid_client().webhook_verification_key_get(request)
    return response.key
