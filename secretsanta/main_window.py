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
from .models.participants import collect_participants_or_raise, EMAIL_RE  # added EMAIL_RE
from .services.draw import find_secret_santa_assignment
from .services.emailer import load_smtp_settings_from_env, send_secret_santa_emails, SMTPSettings
from dotenv import load_dotenv

def _is_super_secret_mode() -> bool:
    load_dotenv()
    print("Checking for super secret mode...")
    result = os.getenv("SuperSecret", "").lower() in {"true", "1", "yes"}
    print("Super secret mode is active." if result else "Super secret mode is not active.")
    return result

# Update history utilities to store emails and load latest entry
HISTORY_DIR = Path(__file__).resolve().parent.parent / "output"
HISTORY_DIR.mkdir(exist_ok=True)
HISTORY_INDEX_FILE = HISTORY_DIR / "history_index.json"

# Added: function to gather all historical forbidden pairs (giver->receiver)
def _load_history_pairs() -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    if HISTORY_INDEX_FILE.exists():
        try:
            data = json.loads(HISTORY_INDEX_FILE.read_text(encoding="utf-8"))
            for rec in data.get("assignments", []):
                for giver, receiver in rec.get("pairs", []):
                    pairs.add((giver, receiver))
        except Exception as e:
            print(f"Failed to parse history index for pairs: {e}")
    return pairs

def _append_history(assignment: dict[str, str], emails: dict[str, str] | None):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    detail_path = HISTORY_DIR / f"{timestamp}.secret"
    lines = ["# Secret Santa assignment", f"# Generated: {timestamp}", ""]
    for giver, receiver in assignment.items():
        lines.append(f"{giver} -> {receiver}")
    detail_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    index = {"assignments": []}
    if HISTORY_INDEX_FILE.exists():
        try:
            index = json.loads(HISTORY_INDEX_FILE.read_text(encoding="utf-8")) or index
        except Exception as e:
            print(f"Failed to read existing index: {e}")
    index.setdefault("assignments", []).append({
        "timestamp": timestamp,
        "pairs": list(assignment.items()),
        "emails": emails or {}
    })
    HISTORY_INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_latest_entry() -> tuple[dict[str, str], dict[str, str]] | None:
    if not HISTORY_INDEX_FILE.exists():
        return None
    try:
        data = json.loads(HISTORY_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to parse history index: {e}")
        return None
    assignments = data.get("assignments", [])
    if not assignments:
        return None
    last = assignments[-1]  # appended chronologically
    pairs = dict(last.get("pairs", []))
    emails = last.get("emails", {}) or {}
    return pairs, emails


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
        # New: load last drawing button
        self.load_last_btn = QPushButton("Load last draw")
        self.load_last_btn.setEnabled(True)
        self.load_last_btn.clicked.connect(self._on_load_last)

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
        actions_l.addWidget(self.load_last_btn)
        actions_l.addStretch(1)

        root.addWidget(actions)
        root.addWidget(self.results_table, stretch=2)
        self.setCentralWidget(central)

        # State
        self._last_assignment = None  # type: dict[str, str] | None
        self._last_emails = None      # type: dict[str, str] | None
        self._history_pairs = _load_history_pairs()
        self._reuse_mode = False  # indicates if a historical assignment is loaded
        self._email_change_connected = False  # track if email signals connected

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
        self._email_change_connected = False  # reset so we can reconnect for new edits

    # Helper to attach change listeners to all email fields once
    def _attach_email_change_listeners(self):
        if self._email_change_connected:
            return
        for pair in self.names_panel.couple_rows:
            for _, email_edit in pair:
                email_edit.textChanged.connect(self._on_email_field_changed)
        for _, email_edit in self.names_panel.single_rows:
            email_edit.textChanged.connect(self._on_email_field_changed)
        self._email_change_connected = True

    def _on_email_field_changed(self):
        # Dynamically enable send button in secret mode when at least one valid email is present
        if not self._last_assignment:
            return
        if not _is_super_secret_mode():
            return  # non secret mode already enabled
        # Gather any valid email
        any_valid = False
        for pair in self.names_panel.couple_rows:
            for _, email_edit in pair:
                txt = email_edit.text().strip()
                if txt and EMAIL_RE.match(txt):
                    any_valid = True
                    break
            if any_valid:
                break
        if not any_valid:
            for _, email_edit in self.names_panel.single_rows:
                txt = email_edit.text().strip()
                if txt and EMAIL_RE.match(txt):
                    any_valid = True
                    break
        self.send_btn.setEnabled(any_valid)
        # Update cached emails progressively (optional)
        if any_valid:
            try:
                people, partner_of, emails = collect_participants_or_raise(
                    couple_rows=self.names_panel.couple_rows,
                    single_rows=self.names_panel.single_rows
                )
                self._last_emails = emails
            except Exception:
                pass

    def _on_secret(self):
        # If we were in reuse mode and user clicks secret, exit reuse mode
        self._reuse_mode = False
        self.results_table.setRowCount(0)
        try:
            people, partner_of, emails = collect_participants_or_raise(
                couple_rows=self.names_panel.couple_rows,
                single_rows=self.names_panel.single_rows
            )
        except ValueError as e:
            QMessageBox.warning(self, "Ongeldige invoer", str(e))
            return
        emails_enabled = len(emails) > 0
        secret_mode = _is_super_secret_mode()
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
        # Always store (possibly empty) emails so we can later re-send after user fills them
        self._last_emails = emails
        _append_history(assignment, self._last_emails if self._last_emails else None)
        for pair in assignment.items():
            self._history_pairs.add(pair)
        if secret_mode:
            # Attach listeners so adding emails later enables sending
            self._attach_email_change_listeners()
            msg = "De verdeling is gemaakt en opgeslagen. Vul e-mails in en klik 'Send emails' wanneer klaar." if not emails_enabled else "De verdeling is gemaakt en opgeslagen. Klik 'Send emails' om de e-mails te versturen."
            QMessageBox.information(self, "Super secret mode", msg)
            self.results_table.setRowCount(0)
            self.send_btn.setEnabled(emails_enabled)
        else:
            self.results_table.setRowCount(len(assignment))
            for row, giver in enumerate(people):
                self.results_table.setItem(row, 0, QTableWidgetItem(giver))
                self.results_table.setItem(row, 1, QTableWidgetItem(assignment[giver]))
            self.results_table.resizeColumnsToContents()
            self.results_table.horizontalHeader().setStretchLastSection(True)
            self.send_btn.setEnabled(True)

    def _on_load_last(self):
        latest = _load_latest_entry()
        if not latest:
            QMessageBox.information(self, "Geen historiek", "Er is nog geen eerdere trekking opgeslagen.")
            return
        assignment, emails = latest
        people = list(assignment.keys())
        self.names_panel.rebuild(couples=0, singles=len(people))
        for (name_edit, email_edit), person in zip(self.names_panel.single_rows, people):
            name_edit.setText(person)
            name_edit.setReadOnly(True)
            email_edit.setText(emails.get(person, ""))
        self._last_assignment = assignment
        self._last_emails = emails  # may be empty
        self._reuse_mode = True
        secret_mode = _is_super_secret_mode()
        if secret_mode:
            self._attach_email_change_listeners()
            # Do not show assignment
            if not self.results_table.isHidden():
                self.results_table.hide()
            msg = "Laatste trekking geladen. Vul e-mails aan (geen e-mails bekend)." if len(emails) == 0 else "Laatste trekking geladen. Klik 'Send emails' om opnieuw te versturen of pas e-mails aan."
            QMessageBox.information(self, "Super secret mode", msg)
            self.send_btn.setEnabled(len(emails) > 0)
        else:
            if self.results_table.isHidden():
                self.results_table.show()
            self.results_table.setRowCount(len(assignment))
            for row, giver in enumerate(people):
                self.results_table.setItem(row, 0, QTableWidgetItem(giver))
                self.results_table.setItem(row, 1, QTableWidgetItem(assignment[giver]))
            self.results_table.resizeColumnsToContents()
            self.results_table.horizontalHeader().setStretchLastSection(True)
            self.send_btn.setEnabled(True)
        self.secret_btn.setEnabled(True)

    def _on_send_emails(self):
        # If in reuse mode, refresh emails from fields (allow edits)
        if self._reuse_mode:
            try:
                people, partner_of, emails = collect_participants_or_raise(
                    couple_rows=self.names_panel.couple_rows,
                    single_rows=self.names_panel.single_rows
                )
            except ValueError as e:
                QMessageBox.warning(self, "Ongeldige invoer", str(e))
                return
            if len(emails) == 0:
                QMessageBox.information(self, "Geen e-mails", "Vul minstens één e-mailadres in om iets te kunnen verzenden.")
                return
            if set(people) != set(self._last_assignment.keys()):
                QMessageBox.critical(self, "Namen gewijzigd", "Je kunt de namen niet wijzigen bij hergebruik van een trekking.")
                return
            self._last_emails = emails
        if not self._last_assignment:
            QMessageBox.information(self, "Geen verdeling", "Maak of laad eerst een verdeling.")
            return
        if not self._last_emails or len(self._last_emails) == 0:
            QMessageBox.information(self, "Geen e-mails", "Voeg e-mailadressen toe bij de deelnemers die je wil mailen.")
            return
        # Send only to those with email (handled by emailer)
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
            f"E-mails verzonden naar {len(sent)} deelnemers met een ingevuld e-mailadres."
        )


def run_app():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
