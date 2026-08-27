import os
import sqlite3
import ast
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import stripe

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-in-render")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
DB = "coding_plans.db"

PLANS = {
    "Bronze": {"price": 5, "price_id": "price_1U950I4nlKzBxMiGFlxAryfe", "level": 1},
    "Silver": {"price": 10, "price_id": "price_1U954Z4nlKzBxMiG66rIdDvo", "level": 2},
    "Platinum": {"price": 25, "price_id": "price_1U95BM4nlKzBxMiG9dNrteQB", "level": 3},
}

def get_db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = get_db()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        plan TEXT NOT NULL DEFAULT 'Bronze',
        stripe_customer_id TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        code TEXT NOT NULL DEFAULT ''
    )""")
    c.commit()
    c.close()

def current_user():
    if "user_id" not in session:
        return None
    c = get_db()
    u = c.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    c.close()
    return u

def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def user_level(u):
    return PLANS.get(u["plan"], PLANS["Bronze"])["level"]

@app.context_processor
def common():
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
        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return render_template("signup.html")
        c = get_db()
        try:
            cur = c.execute(
                "INSERT INTO users(username,password) VALUES(?,?)",
                (username, generate_password_hash(password))
            )
            c.commit()
            session["user_id"] = cur.lastrowid
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("That username is already taken.")
        finally:
            c.close()
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        c = get_db()
        u = c.execute("SELECT * FROM users WHERE username=?", (request.form["username"].strip(),)).fetchone()
        c.close()
        if u and check_password_hash(u["password"], request.form["password"]):
            session["user_id"] = u["id"]
            return redirect(url_for("dashboard"))
        flash("Wrong username or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
@require_login
def dashboard():
    u = current_user()
    c = get_db()
    projects = c.execute("SELECT * FROM projects WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
    c.close()
    return render_template("dashboard.html", user=u, projects=projects)

@app.route("/tools")
@require_login
def tools():
    u = current_user()
    return render_template("tools.html", user=u, level=user_level(u))

@app.route("/editor", methods=["GET", "POST"])
@require_login
def editor():
    u = current_user()
    if request.method == "POST":
        name = request.form.get("name", "My Project").strip() or "My Project"
        code = request.form.get("code", "")
        c = get_db()
        c.execute("INSERT INTO projects(user_id,name,code) VALUES(?,?,?)", (u["id"], name, code))
        c.commit()
        c.close()
        flash("Project saved.")
    return render_template("editor.html")

@app.route("/formatter", methods=["GET", "POST"])
@require_login
def formatter():
    code = request.form.get("code", "")
    formatted = code
    if request.method == "POST":
        try:
            formatted = ast.unparse(ast.parse(code))
        except SyntaxError as e:
            flash(f"Syntax error on line {e.lineno}: {e.msg}")
    return render_template("formatter.html", code=formatted)

@app.route("/helper", methods=["GET", "POST"])
@require_login
def helper():
    u = current_user()
    if user_level(u) < 2:
        flash("The Coding Helper is a Silver feature.")
        return redirect(url_for("pricing"))
    question = request.form.get("question", "")
    answer = ""
    q = question.lower()
    if "function" in q:
        answer = "A function is reusable code. Example: def greet(name): return f'Hello, {name}!'"
    elif "loop" in q:
        answer = "A for-loop repeats code for each item. Example: for item in items: print(item)"
    elif "list" in q:
        answer = "A list stores multiple values. Example: numbers = [1, 2, 3]"
    elif question:
        answer = "Break the problem into small steps, test each step, and read the last line of any Python error first."
    return render_template("helper.html", question=question, answer=answer)
@app.route("/run-code", methods=["POST"])
@require_login
def run_code():
    code = request.form.get("code", "")

    try:
        tree = ast.parse(code)
        output = []

        for node in tree.body:
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "print"
            ):
                values = [ast.literal_eval(arg) for arg in node.value.args]
                output.append(" ".join(str(value) for value in values))

        result = "\n".join(output) or "Code ran successfully."

    except Exception as e:
        result = f"Error: {e}"

    return render_template("editor.html", output=result)
@app.route("/analyzer", methods=["GET", "POST"])
@require_login
def analyzer():
    u = current_user()
    if user_level(u) < 3:
        flash("The Code Analyzer is a Platinum feature.")
        return redirect(url_for("pricing"))
    code = request.form.get("code", "")
    result = None
    if request.method == "POST":
        try:
            tree = ast.parse(code)
            result = {
                "valid": True,
                "lines": len(code.splitlines()),
                "functions": [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)],
                "classes": [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)],
            }
        except SyntaxError as e:
            result = {"valid": False, "error": f"Line {e.lineno}: {e.msg}"}
    return render_template("analyzer.html", code=code, result=result)

@app.route("/projects")
@require_login
def projects():
    u = current_user()
    c = get_db()
    rows = c.execute("SELECT * FROM projects WHERE user_id=? ORDER BY id DESC", (u["id"],)).fetchall()
    c.close()
    return render_template("projects.html", projects=rows)

@app.route("/create-checkout-session/<plan>", methods=["POST"])
@require_login
def create_checkout(plan):
    if plan not in PLANS or not stripe.api_key:
        flash("Stripe is not configured.")
        return redirect(url_for("pricing"))
    u = current_user()
    try:
        customer_id = u["stripe_customer_id"]
        if not customer_id:
            customer = stripe.Customer.create(name=u["username"])
            customer_id = customer.id
            c = get_db()
            c.execute("UPDATE users SET stripe_customer_id=? WHERE id=?", (customer_id, u["id"]))
            c.commit()
            c.close()
        checkout = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": PLANS[plan]["price_id"], "quantity": 1}],
            success_url=url_for("success", _external=True),
            cancel_url=url_for("pricing", _external=True),
            metadata={"codeforge_user_id": str(u["id"]), "plan": plan},
        )
        return redirect(checkout.url, code=303)
    except Exception:
        app.logger.exception("Stripe checkout error")
        flash("Could not start Stripe Checkout.")
        return redirect(url_for("pricing"))

@app.route("/success")
@require_login
def success():
    return render_template("success.html")

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        return "Webhook not configured", 500
    try:
        event = stripe.Webhook.construct_event(
            request.data, request.headers.get("Stripe-Signature"), secret
        )
    except Exception:
        return "Invalid webhook", 400
    obj = event["data"]["object"]
    meta = obj.get("metadata", {})
    uid = meta.get("codeforge_user_id")
    plan = meta.get("plan")
    if uid and plan in PLANS and event["type"] in ("checkout.session.completed", "customer.subscription.updated"):
        c = get_db()
        c.execute("UPDATE users SET plan=? WHERE id=?", (plan, uid))
        c.commit()
        c.close()
    return "ok"

init_db()

if __name__ == "__main__":
    app.run(debug=True)
