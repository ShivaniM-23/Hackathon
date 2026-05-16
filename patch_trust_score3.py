import re

with open("backend/trust_score.py", "r", encoding="utf-8") as f:
    content = f.read()

old_risk = '''    risk_level = (
        "LOW" if final_score >= 70
        else "MEDIUM" if final_score >= 40
        else "HIGH"
    )'''

new_risk = '''    risk_level = (
        "LOW RISK" if final_score >= 75
        else "LOW-MEDIUM" if final_score >= 55
        else "MEDIUM RISK" if final_score >= 30
        else "HIGH RISK"
    )'''

content = content.replace(old_risk, new_risk)

with open("backend/trust_score.py", "w", encoding="utf-8") as f:
    f.write(content)
