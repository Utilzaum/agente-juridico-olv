# core/ui/progress.py

def get_progress_bar(step: int, total: int) -> str:
    """Gera uma barra de progresso de 10 blocos baseada na proporção step/total."""
    step = min(step, total)
    filled = int((step / total) * 10)
    empty = 10 - filled
    return "█" * filled + "░" * empty

def format_progress(step: int, total: int, text: str) -> str:
    bar = get_progress_bar(step, total)
    return (
        "━━━━━━━━━━━━━━━━━━\n"
        "⚖️ <b>ESTAGIÁRIO OLV</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>ETAPA {step}/{total}</b>\n\n"
        f"<code>{bar}</code>\n\n"
        f"📄 {text}"
    )
