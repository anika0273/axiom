Validate the stats module code quality: type checking and formatting.

Run both checks from the project root:

```bash
cd /Users/owner/Desktop/Test_claude && python -m mypy backend/app/stats/ --ignore-missing-imports --strict 2>&1
```

```bash
cd /Users/owner/Desktop/Test_claude && python -m black --check backend/app/stats/ 2>&1
```

Report:
- Any mypy type errors (file, line number, message)
- Any black formatting violations (which files need reformatting)
- Overall pass/fail for each check
- If black reports violations, offer to run `black backend/app/stats/` to fix them automatically
