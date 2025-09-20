# Secret Santa (Couples-aware) – PySide6

A small PySide6 app that builds a list of participants (couples + singles) and
computes a Secret Santa assignment where:
- nobody gets themselves, and
- people in the same couple cannot draw each other.

## Run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python main.py
```

# Sending emails

`cp .env.example .env` and fill in your SMTP details (use an App Password if your provider requires it).

Run the app, enter names and emails, draw the pairs via "It’s our little secret", then click "Send emails".

Each giver receives one email:

Subject: Secret Santa

Body: includes the name of their assigned recipient.

Fancy to customize the email content? Edit the 'body' variable in `secretsanta/services/emailer.py`.