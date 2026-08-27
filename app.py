import os, sqlite3, stripe
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app=Flask(__name__)
app.secret_key=os.environ.get("FLASK_SECRET_KEY","change-me-in-production")
stripe.api_key=os.environ.get("STRIPE_SECRET_KEY")
DB="coding_plans.db"

PLANS={
 "Bronze":{"price":5,"price_id":os.environ.get("STRIPE_BRONZE_PRICE_ID","price_1U950I4nlKzBxMiGFlxAryfe"),"tools":["Code Editor","Code Formatter","Basic Projects"]},
 "Silver":{"price":10,"price_id":os.environ.get("STRIPE_SILVER_PRICE_ID","price_1U954Z4nlKzBxMiG66rIdDvo"),"tools":["Everything in Bronze","AI Coding Helper","Advanced Formatter","10 Projects"]},
 "Platinum":{"price":25,"price_id":os.environ.get("STRIPE_PLATINUM_PRICE_ID","price_1U95BM4nlKzBxMiG9dNrteQB"),"tools":["Everything in Silver","Unlimited Projects","Code Analyzer","Priority Features"]}
}
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init_db():
 c=db(); c.execute("""CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
 plan TEXT NOT NULL DEFAULT 'Bronze', stripe_customer_id TEXT, stripe_subscription_id TEXT)"""); c.commit(); c.close()
def user():
 if "user_id" not in session:return None
 c=db(); u=c.execute("SELECT * FROM users WHERE id=?",(session["user_id"],)).fetchone(); c.close(); return u
def login_required(f):
 @wraps(f)
 def w(*a,**k):
  if not user(): return redirect(url_for("login"))
  return f(*a,**k)
 return w
@app.context_processor
def inject(): return {"current_user":user(),"plans":PLANS}
@app.route("/")
def home(): return render_template("home.html")
@app.route("/pricing")
def pricing(): return render_template("pricing.html")
@app.route("/signup",methods=["GET","POST"])
def signup():
 if request.method=="POST":
  name=request.form["username"].strip(); pw=request.form["password"]
  if not name or len(pw)<6: flash("Username is required and password must be at least 6 characters."); return render_template("signup.html")
  c=db()
  try:
   cur=c.execute("INSERT INTO users(username,password) VALUES(?,?)",(name,generate_password_hash(pw))); c.commit()
   session["user_id"]=cur.lastrowid; return redirect(url_for("pricing"))
  except sqlite3.IntegrityError: flash("That username is already taken.")
  finally:c.close()
 return render_template("signup.html")
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  c=db(); u=c.execute("SELECT * FROM users WHERE username=?",(request.form["username"].strip(),)).fetchone(); c.close()
  if u and check_password_hash(u["password"],request.form["password"]): session["user_id"]=u["id"]; return redirect(url_for("dashboard"))
  flash("Invalid username or password.")
 return render_template("login.html")
@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("home"))
@app.route("/dashboard")
@login_required
def dashboard(): return render_template("dashboard.html",user=user())
@app.route("/create-checkout-session/<plan>",methods=["POST"])
@login_required
def checkout(plan):
 if plan not in PLANS or not stripe.api_key: flash("Stripe is not configured on the server."); return redirect(url_for("pricing"))
 u=user()
 try:
  cid=u["stripe_customer_id"]
  if not cid:
   customer=stripe.Customer.create(name=u["username"],metadata={"codeforge_user_id":str(u["id"])})
   cid=customer.id; c=db(); c.execute("UPDATE users SET stripe_customer_id=? WHERE id=?",(cid,u["id"])); c.commit(); c.close()
  s=stripe.checkout.Session.create(mode="subscription",customer=cid,line_items=[{"price":PLANS[plan]["price_id"],"quantity":1}],success_url=url_for("success",_external=True),cancel_url=url_for("pricing",_external=True),metadata={"codeforge_user_id":str(u["id"]),"plan":plan},subscription_data={"metadata":{"codeforge_user_id":str(u["id"]),"plan":plan}})
  return redirect(s.url,303)
 except Exception:
  app.logger.exception("Stripe error"); flash("Could not start Stripe checkout."); return redirect(url_for("pricing"))
@app.route("/success")
@login_required
def success(): return render_template("success.html")
@app.route("/stripe-webhook",methods=["POST"])
def webhook():
 secret=os.environ.get("STRIPE_WEBHOOK_SECRET")
 if not secret:return "Webhook not configured",500
 try:event=stripe.Webhook.construct_event(request.data,request.headers.get("Stripe-Signature"),secret)
 except Exception:return "Invalid webhook",400
 obj=event["data"]["object"]; typ=event["type"]; meta=obj.get("metadata",{}); uid=meta.get("codeforge_user_id"); plan=meta.get("plan")
 if uid and typ in ("checkout.session.completed","customer.subscription.updated") and plan in PLANS:
  c=db(); c.execute("UPDATE users SET plan=?,stripe_subscription_id=? WHERE id=?",(plan,obj.get("subscription") or obj.get("id"),uid)); c.commit(); c.close()
 elif uid and typ=="customer.subscription.deleted":
  c=db(); c.execute("UPDATE users SET plan='Bronze',stripe_subscription_id=NULL WHERE id=?",(uid,)); c.commit(); c.close()
 return "ok"
@app.route("/tools")
@login_required
def tools():
 u=user(); level={"Bronze":1,"Silver":2,"Platinum":3}[u["plan"]]
 items=[("Code Editor",1,"Write code in your browser."),("Code Formatter",1,"Clean up your code."),("Basic Projects",1,"Organize projects."),("AI Coding Helper",2,"Premium coding help."),("Advanced Formatter",2,"Advanced formatting."),("10 Projects",2,"Create up to ten projects."),("Unlimited Projects",3,"Create unlimited projects."),("Code Analyzer",3,"Analyze your code."),("Priority Features",3,"Premium features.")]
 return render_template("tools.html",user=u,tools=items,level=level)
@app.route("/editor")
@login_required
def editor(): return render_template("editor.html")
@app.route("/formatter",methods=["GET","POST"])
@login_required
def formatter():
 code=request.form.get("code",""); return render_template("formatter.html",code="\n".join(x.rstrip() for x in code.splitlines()))
if __name__=="__main__": init_db(); app.run(debug=True)
