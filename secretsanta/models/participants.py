import re
from typing import Dict, List, Optional, Tuple
from PySide6.QtWidgets import QLineEdit

# Simple, pragmatic email pattern (not perfect RFC5322)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def collect_participants_or_raise(
    couple_rows: List[List[Tuple[QLineEdit, QLineEdit]]],
    single_rows: List[Tuple[QLineEdit, QLineEdit]]
) -> Tuple[List[str], Dict[str, Optional[str]], Dict[str, str]]:
    """
    Returns:
      people: ordered list of names
      partner_of: name -> partner name (or None for singles)
      emails: name -> email (may be subset: only those with an email filled)
    Raises ValueError for missing/invalid names.

    New behavior: emails are OPTIONAL per participant. We only validate
    format for those provided. Missing emails simply means no mail will be
    sent for that giver.
    """
    people: List[str] = []
    partner_of: Dict[str, Optional[str]] = {}
    emails: Dict[str, str] = {}

    # Couples
    for pair in couple_rows:
        (a_name_e, a_email_e), (b_name_e, b_email_e) = pair
        a_name = a_name_e.text().strip()
        a_email = a_email_e.text().strip()
        b_name = b_name_e.text().strip()
        b_email = b_email_e.text().strip()
        if not a_name or not b_name:
            raise ValueError("Vul alle namen van koppels in (geen lege velden).")
        if a_name == b_name:
            raise ValueError("Namen binnen een koppel moeten verschillend zijn.")
        if a_email and not EMAIL_RE.match(a_email):
            raise ValueError(f"Ongeldig e-mailadres voor {a_name}.")
        if b_email and not EMAIL_RE.match(b_email):
            raise ValueError(f"Ongeldig e-mailadres voor {b_name}.")
        people.extend([a_name, b_name])
        partner_of[a_name] = b_name
        partner_of[b_name] = a_name
        if a_email:
            emails[a_name] = a_email
        if b_email:
            emails[b_name] = b_email

    # Singles
    for s_name_e, s_email_e in single_rows:
        s_name = s_name_e.text().strip()
        s_email = s_email_e.text().strip()
        if not s_name:
            raise ValueError("Vul alle namen van aparte personen in (geen lege velden).")
        if s_email and not EMAIL_RE.match(s_email):
            raise ValueError(f"Ongeldig e-mailadres voor single “{s_name}”.")
        people.append(s_name)
        partner_of[s_name] = None
        if s_email:
            emails[s_name] = s_email

    if len(set(people)) != len(people):
        raise ValueError("Elke naam moet uniek zijn (dubbele namen gevonden).")
    if len(people) < 2:
        raise ValueError("Je hebt minstens 2 personen nodig.")

    return people, partner_of, emails
