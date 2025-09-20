import random
from typing import Dict, List, Optional, Set, Tuple


def find_secret_santa_assignment(
    people: List[str],
    partner_of: Dict[str, Optional[str]],
    max_tries: int = 200,
    forbidden_pairs: Optional[Set[Tuple[str, str]]] = None,
) -> Optional[Dict[str, str]]:
    """
    Backtracking with light randomization.
    Constraints:
      - No self-assignments.
      - No giving to your partner (if any).
      - No (giver, receiver) in forbidden_pairs (historical assignments) if provided.
    Returns mapping giver -> receiver, or None if impossible.

    Quick impossibility: exactly two people who are a couple.
    """
    n = len(people)
    if n == 2:
        a, b = people
        if partner_of.get(a) == b and partner_of.get(b) == a:
            return None

    base_candidates: Dict[str, List[str]] = {}
    for g in people:
        forbidden = {g}
        if partner_of.get(g):
            forbidden.add(partner_of[g])
        base_candidates[g] = [p for p in people if p not in forbidden]

    for _ in range(max_tries):
        receivers_available = set(people)
        assignment: Dict[str, str] = {}

        # Heuristic: sort by fewest options first, then lightly shuffle head
        order = sorted(people, key=lambda x: len(base_candidates[x]))
        random.shuffle(order[:max(1, len(order)//3)])

        def backtrack(i: int) -> bool:
            if i == len(order):
                return True
            giver = order[i]
            candidates = [r for r in base_candidates[giver] if r in receivers_available]
            random.shuffle(candidates)
            for r in candidates:
                if forbidden_pairs and (giver, r) in forbidden_pairs:
                    continue
                assignment[giver] = r
                receivers_available.remove(r)
                if backtrack(i + 1):
                    return True
                receivers_available.add(r)
                del assignment[giver]
            return False

        if backtrack(0):
            return assignment

    return None
