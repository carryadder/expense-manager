# 💸 Splitly — Expense Splitter

A mobile-friendly Django web app for tracking expenses and splitting them among members, with a rich animated UI.

## What it does

- **Groups** — Organise expenses under user-created buckets like `FLAT`, `TRIP`, or `OFFICE`. Each expense lives inside a group.
- **Expenses** — Add a title, amount, and an optional note, split across the members you pick:
  - **Equal split** — divided evenly, with any rounding remainder absorbed so shares always sum to the exact total.
  - **Custom split** — type each member's share by hand. A live indicator shows how much is left to assign (or by how much you're over), and the server rejects any split whose shares don't sum to the total.
- **Shared groups & invitations** — Invite friends to a group so you all see the same expenses and balances:
  - **Shareable link** — the admin copies a `/join/<code>` link; anyone logged in who opens it can join.
  - **Add by username** — the admin adds an existing user directly.
  - **Guests** — the admin can also add name-only splitters who don't have an account.
  - **Permissions** — only the group **creator (admin)** can invite, remove members, or delete the group. Every member can add expenses and view balances.
- **Flexible split scope** — when adding an expense you pick which members it splits across (default: everyone, or just the ones involved — e.g. "I paid 1000 for food, split among only the 5 who ate").
- **Members (splitters)** — The **Splitters** page manages your own name-only people for reuse; real users join per-group via invites.
- **Settings** — Per-user preferences at `/settings/`: display name, **currency** (symbol applied to every amount), and **date format** (relative / DD-MM-YYYY / MM-DD-YYYY / ISO).
- **Icons** — The whole UI uses inline SVG icons (no emoji, no icon-font file). Groups pick an icon from a built-in grid instead of an emoji.
- **Remembered preference** — Each group remembers the last set of splitters you used. The next expense you add there pre-selects them, so you don't re-pick members every time.
- **Balances** — Every group shows a "Who owes what" breakdown per member.
- **Live split preview** — As you type an amount and toggle splitters, the per-person share updates instantly.

Everything is scoped per user account — you only see your own groups and members.

## Run it

```bash
python -m venv venv
venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source venv/bin/activate && pip install -r requirements.txt  # macOS/Linux

python manage.py migrate
python manage.py createsuperuser      # or sign up in the app at /signup/
python manage.py runserver
```

Then open http://127.0.0.1:8000/ and sign up (or log in).

## Stack

- Django 6.1 · SQLite · server-rendered templates
- Vanilla CSS (dark gradient theme, CSS animations, `:has()` chip selection) and a small vanilla-JS enhancer — no build step, no external assets.

## Structure

```
config/          project settings & root URLs
expenses/        the app
  models.py      UserSettings, Group, GroupMembership, GroupInvite,
                 Member, Expense, ExpenseSplit
  views.py       group / expense / member / settings flows
  forms.py       sign-up, group, member, expense, settings forms
  icons.py       inline SVG icon set + group-icon choices
  context_processors.py   exposes `app_settings` to every template
  templatetags/
    expense_extras.py     {% icon %} tag, money/userdate filters
  templates/     base + page templates
static/          css/app.css, js/app.js
```
