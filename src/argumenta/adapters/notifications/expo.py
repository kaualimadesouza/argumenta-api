from collections.abc import Sequence

import httpx
from pydantic import BaseModel, ConfigDict


class ExpoPushReceiptDetails(BaseModel):
    error: str | None = None
    model_config = ConfigDict(extra="ignore")


class ExpoPushReceipt(BaseModel):
    status: str
    message: str | None = None
    details: ExpoPushReceiptDetails | None = None
    model_config = ConfigDict(extra="ignore")


class ExpoPushResponse(BaseModel):
    data: list[ExpoPushReceipt]
    model_config = ConfigDict(extra="ignore")


class HttpExpoPushGateway:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(timeout=10.0)
        self._url = "https://exp.host/--/api/v2/push/send"

    def send_streak_reminders(self, tokens: Sequence[str]) -> Sequence[str]:
        if not tokens:
            return []

        unregistered = []
        from itertools import batched

        for chunk in batched(tokens, 100):
            payload = [
                {
                    "to": token,
                    "title": "Seu streak está em risco!",
                    "body": "Você ainda não escreveu hoje. Mantenha seu ritmo!",
                }
                for token in chunk
            ]

            response = self._client.post(self._url, json=payload)
            response.raise_for_status()

            parsed = ExpoPushResponse.model_validate(response.json())

            for token, receipt in zip(chunk, parsed.data, strict=False):
                if (
                    receipt.status == "error"
                    and receipt.details
                    and receipt.details.error == "DeviceNotRegistered"
                ):
                    unregistered.append(token)

        return unregistered
