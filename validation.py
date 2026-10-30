import re
from datetime import datetime,date
EMAIL=re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
def validate_patient(d):
 errors=[]
 if not d.get("full_name","").strip(): errors.append("Full name is required.")
 email=d.get("email","").strip()
 if not EMAIL.match(email): errors.append(f"Invalid email address: {email!r}.")
 parsed=None
 for fmt in ("%d/%m/%Y","%d.%m.%Y","%Y-%m-%d"):
  try: parsed=datetime.strptime(str(d.get("dob","")).strip(),fmt).date(); break
  except ValueError: pass
 if parsed is None: errors.append(f"Invalid date of birth {d.get('dob')!r}; enter a real date as DD/MM/YYYY.")
 elif parsed>date.today(): errors.append("Date of birth cannot be in the future.")
 for field in ("glucose","haemoglobin","cholesterol"):
  try:
   if float(d.get(field,""))<0: errors.append(f"{field.title()} must be zero or greater.")
  except (TypeError,ValueError): errors.append(f"{field.title()} must be numeric.")
 return errors
