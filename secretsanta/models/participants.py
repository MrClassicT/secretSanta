import re
from typing import Dict, List, Optional, Tuple
from PySide6.QtWidgets import QLineEdit

# Simple, pragmatic email pattern (not perfect RFC5322)
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _read_pair(edits: Tuple[QLineEdit, QLineEdit]) -> Tuple[str, str]:
    name = edits[0].text().strip()
    email = edits[1].text().strip()
    return name, email


def collect_participants_or_raise(
    couple_rows: List[List[Tuple[QLineEdit, QLineEdit]]],
    single_rows: List[Tuple[QLineEdit, QLineEdit]]
) -> Tuple[List[str], Dict[str, Optional[str]], Dict[str, str]]:
    """
    Returns:
      people: ordered list of names
      partner_of: name -> partner name (or None for singles)
      emails: name -> email (may be empty if user provided none)
    Raises ValueError for missing/invalid inputs.

    Rule: If the user provides ZERO email addresses (all blank), we allow proceeding
    without email sending capability (emails dict empty). If ANY email is provided,
    then ALL emails must be provided and valid.
    """
    people: List[str] = []
    partner_of: Dict[str, Optional[str]] = {}
    emails: Dict[str, str] = {}

    # First pass: detect if any email was entered at all
    any_email_entered = False
    for pair in couple_rows:
        for name_e, email_e in pair:
            if email_e.text().strip():
                any_email_entered = True
                break
        if any_email_entered:
            break
    if not any_email_entered:
        for s_name_e, s_email_e in single_rows:
            if s_email_e.text().strip():
                any_email_entered = True
                break

    # Couples
    for pair in couple_rows:
        (a_name_e, a_email_e), (b_name_e, b_email_e) = pair
        a_name, a_email = _read_pair((a_name_e, a_email_e))
        b_name, b_email = _read_pair((b_name_e, b_email_e))

        if not a_name or not b_name:
            raise ValueError("Vul alle namen van koppels in (geen lege velden).")
        if a_name == b_name:
            raise ValueError("Namen binnen een koppel moeten verschillend zijn.")

        if any_email_entered:
            if not (a_email and EMAIL_RE.match(a_email)) or not (b_email and EMAIL_RE.match(b_email)):
                raise ValueError("Gebruik geldige e-mailadressen voor elk koppel (of laat alle velden leeg om zonder e-mail verder te gaan).")
            emails[a_name] = a_email
            emails[b_name] = b_email

        people.extend([a_name, b_name])
        partner_of[a_name] = b_name
        partner_of[b_name] = a_name

    # Singles
    for s_name_e, s_email_e in single_rows:
        s_name, s_email = _read_pair((s_name_e, s_email_e))
        if not s_name:
            raise ValueError("Vul alle namen van aparte personen in (geen lege velden).")
        if any_email_entered:
            if not (s_email and EMAIL_RE.match(s_email)):
                raise ValueError(f"Gebruik een geldig e-mailadres voor single “{s_name or '—'}” (of laat alle e-mails leeg).")
            emails[s_name] = s_email
        people.append(s_name)
        partner_of[s_name] = None

    # Duplicates & count
    if len(set(people)) != len(people):
        raise ValueError("Elke naam moet uniek zijn (dubbele namen gevonden).")
    if len(people) < 2:
        raise ValueError("Je hebt minstens 2 personen nodig.")

    return people, partner_of, emails
