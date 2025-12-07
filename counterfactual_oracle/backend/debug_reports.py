from app.core.database import SessionLocal
from app.models.report import Report
import json

db = SessionLocal()
reports = db.query(Report).order_by(Report.created_at.desc()).all()

print(f"Found {len(reports)} reports:")
if reports:
    r = reports[0] # Latest because of order_by desc
    print(f"LATEST REPORT: ID: {r.id}")
    print(f"Name: {r.company_name} | FY: {r.fiscal_year}")
    if r.report_data:
        print("Income Statement:", json.dumps(r.report_data.get('income_statement'), indent=2))
        print("Balance Sheet Keys:", list(r.report_data.get('balance_sheet', {}).keys()))
    else:
        print("NO DATA")

db.close()
