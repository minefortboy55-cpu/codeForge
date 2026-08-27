from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = "change-this-secret-key-in-production"
DB = "coding_plans.db"

PLANS = {
    "Bronze": {
        "price": 5,
        "description": "A simple starting point for learning and building.",
        "tools": ["Code Editor", "Code Formatter", "Basic Projects"],
    },
    "Silver": {
        "price": 12,
        "description": "More tools for serious coding projects.",
        "tools": ["Everything in Bronze", "AI Coding Helper", "Advanced Formatter", "10 Projects"],
    },
    "Platinum": {
        "price": 25,
        "description": "The complete toolkit for power users.",
        "tools": ["Everything in Silver", "Unlimited Projects", "Code Analyzer", "Priority Features"],
    },
}

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        plan TEXT NOT NULL DEFAULT 'Bronze'
    )""")
    conn.commit()
    conn.close()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

def current_user():
    if "user_id" not in session:
        return None
    conn = db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return user

@app.context_processor
def inject_user():
    return {"current_user": current_user(), "plans": PLANS}

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/pricing")
def pricing():
    return render_template("pricing.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        if not username or len(password) < 6:
            flash("Username is required and password must be at least 6 characters.")
            return render_template("signup.html")
        conn = db()
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )
            conn.commit()
            session["user_id"] = cur.lastrowid
            flash("Account created!")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("That username is already taken.")
        finally:
            conn.close()
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        conn = db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    return render_template("dashboard.html", user=user)

@app.route("/choose-plan/<plan>", methods=["POST"])
@login_required
def choose_plan(plan):
    if plan not in PLANS:
        flash("Invalid plan.")
        return redirect(url_for("pricing"))

    # Demo subscription selection. Replace this with Stripe checkout
    # and server-side payment verification before accepting real payments.
    conn = db()
    conn.execute("UPDATE users SET plan=? WHERE id=?", (plan, session["user_id"]))
    conn.commit()
    conn.close()
    flash(f"{plan} plan selected. This demo does not process real payments.")
    return redirect(url_for("dashboard"))

@app.route("/tools")
@login_required
def tools():
    user = current_user()
    plan_order = {"Bronze": 1, "Silver": 2, "Platinum": 3}
    level = plan_order[user["plan"]]
    all_tools = [
        ("Code Editor", 1, "Write and save code snippets."),
        ("Code Formatter", 1, "Clean up and format your code."),
        ("Basic Projects", 1, "Organize your first projects."),
        ("AI Coding Helper", 2, "Get coding explanations and suggestions."),
        ("Advanced Formatter", 2, "Use advanced formatting options."),
        ("10 Projects", 2, "Create up to ten projects."),
        ("Unlimited Projects", 3, "Create as many projects as you need."),
        ("Code Analyzer", 3, "Inspect code for common issues."),
        ("Priority Features", 3, "Access premium features first."),
    ]
    return render_template("tools.html", user=user, tools=all_tools, level=level)

@app.route("/editor")
@login_required
def editor():
    return render_template("editor.html")

@app.route("/formatter", methods=["GET", "POST"])
@login_required
def formatter():
    code = request.form.get("code", "")
    # Simple whitespace formatter demo; replace/extend for your target language.
    formatted = "\n".join(line.rstrip() for line in code.splitlines())
    return render_template("formatter.html", code=formatted)

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
