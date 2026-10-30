import os,sqlite3
from datetime import datetime
DB=os.path.join(os.path.dirname(__file__),"data","health_records.db")
os.makedirs(os.path.dirname(DB),exist_ok=True)
def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init_db():
 with conn() as c:
  c.execute("""CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY AUTOINCREMENT,full_name TEXT NOT NULL,dob TEXT NOT NULL,email TEXT NOT NULL UNIQUE COLLATE NOCASE,glucose REAL NOT NULL,haemoglobin REAL NOT NULL,cholesterol REAL NOT NULL,remarks TEXT DEFAULT '',created_at TEXT NOT NULL)""")
  c.execute("""CREATE TABLE IF NOT EXISTS import_issues(id INTEGER PRIMARY KEY AUTOINCREMENT,test_number INTEGER,full_name TEXT,dob TEXT,email TEXT,reason TEXT,logged_at TEXT)""")
def create_patient(d,remarks=""):
 try:
  with conn() as c: c.execute("INSERT INTO patients(full_name,dob,email,glucose,haemoglobin,cholesterol,remarks,created_at) VALUES(?,?,?,?,?,?,?,?,?)".replace("?,?,?,?,?,?,?,?,?","?,?,?,?,?,?,?,?"),(d["full_name"].strip(),d["dob"],d["email"].strip().lower(),float(d["glucose"]),float(d["haemoglobin"]),float(d["cholesterol"]),remarks,datetime.now().isoformat(timespec="seconds")))
 except sqlite3.IntegrityError: raise ValueError("Duplicate record: this email address already exists.")
def list_patients():
 with conn() as c: return [dict(x) for x in c.execute("SELECT * FROM patients ORDER BY id")]
def get_patient(i):
 with conn() as c:
  r=c.execute("SELECT * FROM patients WHERE id=?",(i,)).fetchone(); return dict(r) if r else None
def update_patient(i,d,remarks=None):
 old=get_patient(i)
 if not old: raise ValueError("Patient not found.")
 try:
  with conn() as c: c.execute("UPDATE patients SET full_name=?,dob=?,email=?,glucose=?,haemoglobin=?,cholesterol=?,remarks=? WHERE id=?",(d["full_name"].strip(),d["dob"],d["email"].strip().lower(),float(d["glucose"]),float(d["haemoglobin"]),float(d["cholesterol"]),old["remarks"] if remarks is None else remarks,i))
 except sqlite3.IntegrityError: raise ValueError("That email is already used by another patient.")
def delete_patient(i):
 with conn() as c: c.execute("DELETE FROM patients WHERE id=?",(i,))
def log_issue(i,d,reason):
 with conn() as c: c.execute("INSERT INTO import_issues(test_number,full_name,dob,email,reason,logged_at) VALUES(?,?,?,?,?,?)",(i,d["full_name"],d["dob"],d["email"],reason,datetime.now().isoformat(timespec="seconds")))
def list_issues():
 with conn() as c: return [dict(x) for x in c.execute("SELECT * FROM import_issues ORDER BY test_number,id")]
def clear_issues():
 with conn() as c: c.execute("DELETE FROM import_issues")
