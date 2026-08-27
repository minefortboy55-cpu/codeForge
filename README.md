# CodeForge

A full Flask starter website for a tiered coding-tool service.

## Features

- Home page
- Bronze / Silver / Platinum pricing
- Signup and login
- Password hashing
- SQLite database
- Session-based authentication
- Plan selection
- Plan-gated tools
- Code editor
- Basic code formatter
- Responsive CSS

## Run it

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run:

   `python -m venv .venv`

4. Activate the environment.

   Windows PowerShell:
   `.venv\Scripts\Activate.ps1`

   macOS/Linux:
   `source .venv/bin/activate`

5. Install dependencies:

   `pip install -r requirements.txt`

6. Start the server:

   `python app.py`

7. Open `http://127.0.0.1:5000`

## Important

The plan buttons currently simulate subscription selection. They do NOT charge a card.

For a real paid website, connect a payment provider such as Stripe Checkout and verify payment/subscription webhooks on the server before changing a user's plan. Also replace `app.secret_key` with a strong environment variable before deployment.
