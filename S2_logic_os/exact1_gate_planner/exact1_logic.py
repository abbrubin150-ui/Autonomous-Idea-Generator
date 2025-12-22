"""S2: EXACT1 gate planner."""\n\nfrom typing import Iterable\n\n\ndef exact1(bits: Iterable[bool]) -> bool:\n    bits = list(bits)\n    return sum(1 for b in bits if b) == 1\n
