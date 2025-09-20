# Secret Santa (Couples-aware)

A small app that builds a list of participants (couples + singles) and
computes a Secret Santa assignment where:
- nobody gets themselves
- people in the same couple cannot draw each other
- a history of previous years is taken into account to avoid repeats
- a super secret mode where not even the organizer knows who is assigned to whom

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

`cp .env.example .env` and fill in your SMTP details.

Run the app, enter names and emails, draw the pairs via "It’s our little secret", then click "Send emails".

Each giver receives **one email**:

---
**Subject:** Secret Santa

**Body:** includes the name of their assigned recipient.

---

Fancy to customize the email content? Edit the 'body' variable in `secretsanta/services/emailer.py`. 

> Make sure to keep `{giver}` and `{recipient}` in the body, as they will be replaced with the actual names!!!

# License
This project is licensed for personal use only. You may use and modify the code for your own purposes. Redistribution or commercial use is not permitted without prior written consent from the author. If you wish to share or distribute this project, please contact the repository owner and retain proper attribution.