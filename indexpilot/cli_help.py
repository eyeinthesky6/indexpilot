DOCTOR_HELP = {"fix": "Apply safe automatic fixes", "json": "Machine-readable diagnostics", "strict": "Warnings as errors"}
AUDIT_HELP = {"path": "Root or config to audit", "format": "text|json|markdown", "fail-on": "Min severity for non-zero exit"}
COMPARE_HELP = {"left": "Baseline report", "right": "Candidate report", "output": "Comparison output path"}
def help_for(command: str, option: str) -> str:
    return {"doctor": DOCTOR_HELP, "audit": AUDIT_HELP, "compare": COMPARE_HELP}.get(command, {}).get(option, "")
