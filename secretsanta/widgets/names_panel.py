from typing import List, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, QLineEdit, QScrollArea, QLabel, QGridLayout
)


class NamesPanel(QWidget):
    """
    Scrollable area with inputs per person:
      - name (QLineEdit)
      - email (QLineEdit)
    Couples are shown as two person-rows inside a "Koppels" group.
    Singles are shown inside "Aparte personen".
    Exposes:
      - couple_rows: List[List[Tuple[name_edit, email_edit]]]  (each inner list length=2)
      - single_rows: List[Tuple[name_edit, email_edit]]
    """
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignTop)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        self.couple_rows: List[List[Tuple[QLineEdit, QLineEdit]]] = []
        self.single_rows: List[Tuple[QLineEdit, QLineEdit]] = []

    def clear(self):
        for i in reversed(range(self.container_layout.count())):
            w = self.container_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.couple_rows.clear()
        self.single_rows.clear()

    def _make_person_row(self, name_ph: str) -> Tuple[QLineEdit, QLineEdit, QWidget]:
        wrap = QWidget()
        g = QGridLayout(wrap)
        g.setContentsMargins(0, 0, 0, 0)
        name = QLineEdit()
        name.setPlaceholderText(name_ph)
        email = QLineEdit()
        email.setPlaceholderText("email@adres.be")
        g.addWidget(QLabel("Naam"), 0, 0)
        g.addWidget(name, 0, 1)
        g.addWidget(QLabel("E-mail"), 1, 0)
        g.addWidget(email, 1, 1)
        return name, email, wrap

    def rebuild(self, couples: int, singles: int):
        self.clear()

        couples_group = QGroupBox("Koppels")
        couples_layout = QVBoxLayout(couples_group)
        for i in range(1, couples + 1):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            a_name, a_email, a_widget = self._make_person_row(f"Couple {i} – Persoon A")
            b_name, b_email, b_widget = self._make_person_row(f"Couple {i} – Persoon B")
            row_layout.addWidget(a_widget)
            row_layout.addWidget(b_widget)
            couples_layout.addWidget(row)
            self.couple_rows.append([(a_name, a_email), (b_name, b_email)])

        singles_group = QGroupBox("Aparte personen")
        singles_layout = QVBoxLayout(singles_group)
        for i in range(1, singles + 1):
            s_name, s_email, s_widget = self._make_person_row(f"Single {i}")
            singles_layout.addWidget(s_widget)
            self.single_rows.append((s_name, s_email))

        self.container_layout.addWidget(couples_group)
        self.container_layout.addWidget(singles_group)
