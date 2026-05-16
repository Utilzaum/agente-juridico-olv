from datetime import datetime, timedelta

def calcular_prazo(data_publicacao: str, dias: int, tipo: str = "corrido"):
    if not dias:
        return None

    data = datetime.strptime(data_publicacao, "%Y-%m-%d")

    if tipo == "corrido":
        return (data + timedelta(days=dias)).date()

    # dias úteis (simples, sem feriados)
    contador = 0
    while contador < dias:
        data += timedelta(days=1)
        if data.weekday() < 5:  # 0-4 = seg-sex
            contador += 1

    return data.date()
