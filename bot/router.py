def detect_topic(query: str) -> str:
    """
    Определяет тему запроса для выбора нужного файла законов
    
    Returns:
        "tax" | "koap" | "ved" | "general"
    """
    query_lower = query.lower()
    
    tax_keywords = [
        "налог", "ндс", "налоговая", "ип", "самозанятый", "усн", "осно",
        "вычет", "декларация", "отчет", "6-ндфл", "нк рф", "фнс"
    ]
    
    koap_keywords = [
        "штраф", "административ", "нарушение", "коап", "ответственность",
        "взыскание", "протокол"
    ]
    
    ved_keywords = [
        "вэд", "импорт", "экспорт", "таможня", "внешнеэкономическ",
        "контракт", "валют", "валюта", "валютный"
    ]
    
    for keyword in tax_keywords:
        if keyword in query_lower:
            return "tax"
    
    for keyword in koap_keywords:
        if keyword in query_lower:
            return "koap"
    
    for keyword in ved_keywords:
        if keyword in query_lower:
            return "ved"
    
    return "tax"

