"""S5: Risk & DIA metrics analyst (stub)."""\n\n\ndef dia_rate(prev: float, cur: float) -> float:\n    if prev == 0:\n        return 0.0\n    return (cur - prev) / prev\n
