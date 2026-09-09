from __future__ import annotations
from typing import Optional
from .._http import HttpClient
from ..models import (
    BalancePackage,
    BalanceTransaction,
    CheckoutResponse,
    PaginatedResponse,
    ReferralHistory,
    ReferralStats,
    TransactionType,
)


class BalanceResource:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def list_packages(self) -> list[BalancePackage]:
        """Lista los paquetes de recarga activos. No requiere autenticación."""
        data = self._http.request("GET", "/balance/packages")
        return [BalancePackage.from_dict(p) for p in data]

    def checkout(
        self, package_id: str, success_url: Optional[str] = None
    ) -> CheckoutResponse:
        """Inicia el checkout de un paquete y devuelve la URL de pago.

        Args:
            package_id: ID del paquete a comprar.
            success_url: Adónde volver tras pagar. Si se omite, la API usa su
                página de saldo por defecto.
        """
        d = self._http.request(
            "POST",
            "/balance/checkout",
            json={"package_id": package_id},
            params={"success_url": success_url},
        )
        return CheckoutResponse.from_dict(d)

    def list_transactions(
        self,
        page: int = 1,
        limit: int = 20,
        type: Optional[TransactionType] = None,
    ) -> PaginatedResponse[BalanceTransaction]:
        """Historial de movimientos de saldo del usuario autenticado.

        Args:
            page: Página a devolver, desde 1.
            limit: Movimientos por página. La API topa en 100.
            type: Filtra por tipo: 'purchase', 'consumption', 'adjustment',
                'earned_public_voice' o 'welcome_bonus'.
        """
        d = self._http.request(
            "GET",
            "/balance/transactions",
            params={"page": page, "limit": limit, "type": type},
        )
        return PaginatedResponse(
            items=[BalanceTransaction.from_dict(t) for t in d["items"]],
            total=d["total"],
            page=d["page"],
            limit=d["limit"],
        )

    def referrals(self) -> ReferralStats:
        """Panel de referidos: quién ha traído el usuario, cuánto ha generado
        cada uno y qué porcentaje de comisión se aplica."""
        return ReferralStats.from_dict(self._http.request("GET", "/balance/referrals"))

    def referral_history(self, referee_id: str) -> ReferralHistory:
        """Movimientos de comisión de un referido concreto."""
        return ReferralHistory.from_dict(
            self._http.request("GET", f"/balance/referrals/{referee_id}")
        )
