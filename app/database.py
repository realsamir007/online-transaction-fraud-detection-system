from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from supabase import Client, create_client


class DatabaseError(RuntimeError):
    """Raised when an insert operation to Supabase fails."""


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    service_role_key: str
    table_name: str = "transactions"

    @classmethod
    def from_env(cls) -> "SupabaseConfig":
        url = os.getenv("SUPABASE_URL", "").strip()
        service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        table_name = os.getenv("SUPABASE_TABLE", "transactions").strip() or "transactions"

        if not url or not service_role_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required environment variables.")

        return cls(url=url, service_role_key=service_role_key, table_name=table_name)


class SupabaseTransactionRepository:
    def __init__(self, config: SupabaseConfig) -> None:
        self.table_name = config.table_name
        self.client: Client = create_client(config.url, config.service_role_key)

    @staticmethod
    def _normalize_payload_keys(payload: dict[str, Any]) -> dict[str, Any]:
        # PostgreSQL folds unquoted identifiers to lowercase. This keeps inserts
        # resilient when the table was created without quoted mixed-case columns.
        return {key.lower(): value for key, value in payload.items()}

    def insert_transaction(self, payload: dict[str, Any]) -> None:
        try:
            self.client.table(self.table_name).insert(payload).execute()
            return
        except Exception as primary_exc:
            normalized_payload = self._normalize_payload_keys(payload)
            if normalized_payload != payload:
                try:
                    self.client.table(self.table_name).insert(normalized_payload).execute()
                    return
                except Exception as fallback_exc:
                    raise DatabaseError(
                        f"Failed to insert into Supabase table '{self.table_name}'. "
                        f"Primary insert error: {primary_exc}. "
                        f"Lowercase-key fallback error: {fallback_exc}."
                    ) from fallback_exc

            raise DatabaseError(
                f"Failed to insert into Supabase table '{self.table_name}'. "
                f"Error: {primary_exc}."
            ) from primary_exc
