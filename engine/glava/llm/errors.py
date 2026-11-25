"""Ошибки слоя моделей."""


class ProviderUnavailable(RuntimeError):
    """cost_usd — сколько стоил отвергнутый ответ: поставщик его уже посчитал."""

    def __init__(self, message: str, cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.cost_usd = cost_usd
