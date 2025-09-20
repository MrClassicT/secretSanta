import sys
import os
import json
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QSpinBox, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QSizePolicy
)

from .widgets.names_panel import NamesPanel
from .models.participants import collect_participants_or_raise
from .services.draw import find_secret_santa_assignment
from .services.emailer import load_smtp_settings_from_env, send_secret_santa_emails, SMTPSettings
from dotenv import load_dotenv

def _is_super_secret_mode() -> bool:
    load_dotenv()
    print("Checking for super secret mode...")
    result = os.getenv("SuperSecret", "").lower() in {"true", "1", "yes"}
    print("Super secret mode is active." if result else "Super secret mode is not active.")
    return result

# Persistent history utilities
HISTORY_DIR = Path(__file__).resolve().parent.parent / "output"
HISTORY_DIR.mkdir(exist_ok=True)

HISTORY_INDEX_FILE = HISTORY_DIR / "history_index.json"


def _load_history_pairs() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    if HISTORY_INDEX_FILE.exists():
        try:
            data = json.loads(HISTORY_INDEX_FILE.read_text(encoding="utf-8"))
            for rec in data.get("assignments", []):
                for giver, receiver in rec.get("pairs", []):
                    pairs.add((giver, receiver))
        except Exception as e:
            print(f"Failed to parse history index: {e}")
    return pairs


def _append_history(assignment: dict[str, str]):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Write detailed file
    detail_path = HISTORY_DIR / f"{timestamp}.secret"
    lines = ["# Secret Santa assignment", f"# Generated: {timestamp}", ""]
    for giver, receiver in assignment.items():
        lines.append(f"{giver} -> {receiver}")
    detail_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Update index
    index = {"assignments": []}
    if HISTORY_INDEX_FILE.exists():
        try:
            index = json.loads(HISTORY_INDEX_FILE.read_text(encoding="utf-8")) or index
        except Exception as e:
            print(f"Failed to read existing index: {e}")
    index.setdefault("assignments", []).append({
        "timestamp": timestamp,
        "pairs": list(assignment.items())
    })
    HISTORY_INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secret Santa – Couples Aware")
        self.resize(980, 760)

        # ===== Header =====
        header = QWidget()
        header_layout = QHBoxLayout(header)

        self.singles_spin = QSpinBox()
        self.singles_spin.setRange(0, 999)
        self.singles_spin.setValue(0)
        self.couples_spin = QSpinBox()
        self.couples_spin.setRange(0, 999)
        self.couples_spin.setValue(0)

        header_form = QFormLayout()
        header_form.setLabelAlignment(Qt.AlignRight)
        header_form.addRow(QLabel("Aantal aparte personen:"), self.singles_spin)
        header_form.addRow(QLabel("Aantal koppels:"), self.couples_spin)

        self.build_btn = QPushButton("Build list")
        self.build_btn.clicked.connect(self._on_build_list)

        header_layout.addLayout(header_form, stretch=1)
        header_layout.addWidget(self.build_btn, alignment=Qt.AlignLeft)

        # ===== Names panel =====
        self.names_panel = NamesPanel()

        # ===== Action & results =====
        self.secret_btn = QPushButton("It's our little secret")
        self.secret_btn.setEnabled(False)
        self.secret_btn.clicked.connect(self._on_secret)

        self.send_btn = QPushButton("Send emails")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self._on_send_emails)

        self.results_table = QTableWidget(0, 2)
        self.results_table.setHorizontalHeaderLabels(["Gever", "Ontvanger"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Hide the table entirely in super secret mode
        if _is_super_secret_mode():
            self.results_table.hide()

        # ===== Layout =====
        central = QWidget()
        root = QVBoxLayout(central)
        root.addWidget(header)
        root.addWidget(self.names_panel, stretch=1)

        actions = QWidget()
        actions_l = QHBoxLayout(actions)
        actions_l.addWidget(self.secret_btn)
        actions_l.addWidget(self.send_btn)
        actions_l.addStretch(1)

        root.addWidget(actions)
        root.addWidget(self.results_table, stretch=2)
        self.setCentralWidget(central)

        # State
        self._last_assignment = None  # type: dict[str, str] | None
        self._last_emails = None      # type: dict[str, str] | None
        self._history_pairs = _load_history_pairs()

    # ---- Slots ----
    def _on_build_list(self):
        couples = self.couples_spin.value()
        singles = self.singles_spin.value()
        total = 2 * couples + singles
        if total < 2:
            QMessageBox.warning(self, "Not enough people", "Je hebt minstens 2 personen nodig.")
            self.secret_btn.setEnabled(False)
            self.send_btn.setEnabled(False)
            return
        self.results_table.setRowCount(0)
        self._last_assignment = None
        self._last_emails = None
        self.names_panel.rebuild(couples=couples, singles=singles)
        self.secret_btn.setEnabled(True)
        self.send_btn.setEnabled(False)

    def _on_secret(self):
        self.results_table.setRowCount(0)
        try:
            people, partner_of, emails = collect_participants_or_raise(
                couple_rows=self.names_panel.couple_rows,
                single_rows=self.names_panel.single_rows
            )
        except ValueError as e:
            QMessageBox.warning(self, "Ongeldige invoer", str(e))
            return
        # Try with history constraints
        assignment = find_secret_santa_assignment(people, partner_of, forbidden_pairs=self._history_pairs)
        if assignment is None:
            QMessageBox.critical(
                self,
                "Geen geldige verdeling",
                "Er kon geen geldige Secret Santa-verdeling gevonden worden met de huidige namen (rekening houdend met eerdere jaren).\n\n"
                "Tip: voeg extra personen toe of verander de samenstelling, of wis history als dat acceptabel is."
            )
            self._last_assignment = None
            self.send_btn.setEnabled(False)
            return
        self._last_assignment = assignment
        self._last_emails = emails
        _append_history(assignment)
        # Update in-memory forbidden pairs for subsequent draws this session
        for pair in assignment.items():
            self._history_pairs.add(pair)
        if _is_super_secret_mode():
            QMessageBox.information(
                self,
                "Super secret mode",
                "De verdeling is gemaakt en opgeslagen, maar wordt niet getoond. Klik 'Send emails' om de e-mails te versturen."
            )
            self.results_table.setRowCount(0)
            self.send_btn.setEnabled(True)
        else:
            self.results_table.setRowCount(len(assignment))
            for row, giver in enumerate(people):
                self.results_table.setItem(row, 0, QTableWidgetItem(giver))
                self.results_table.setItem(row, 1, QTableWidgetItem(assignment[giver]))
            self.results_table.resizeColumnsToContents()
            self.results_table.horizontalHeader().setStretchLastSection(True)
            self.send_btn.setEnabled(True)

    def _on_send_emails(self):
        if not self._last_assignment or not self._last_emails:
            QMessageBox.information(self, "Geen verdeling", "Maak eerst een verdeling.")
            return

        try:
            settings: SMTPSettings = load_smtp_settings_from_env()
        except Exception as e:
            QMessageBox.critical(self, "SMTP-configuratiefout", str(e))
            return

        try:
            sent = send_secret_santa_emails(
                assignment=self._last_assignment,
                emails=self._last_emails,
                settings=settings,
                dry_run=False
            )
        except Exception as e:
            QMessageBox.critical(self, "Verzenden mislukt", f"Fout tijdens verzenden: {e}")
            return

        QMessageBox.information(
            self,
            "E-mails verzonden",
            f"E-mails verzonden naar {len(sent)} deelnemers."
        )


def run_app():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
