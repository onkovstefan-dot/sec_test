# Smoke Test Checklist

Run these after every milestone/change.

## Start the app

```bash
python app.py
```

## Browser / curl checks

- [ ] `GET /` — Home page loads
- [ ] `GET /check-cik` — CIK check form loads
- [ ] `POST /check-cik` — CIK redirect works (test with CIK: `0001318605`)
- [ ] `GET /daily-values` — Daily values page renders
- [ ] `GET /daily-values?entity_id=1` — Filters work
- [ ] `GET /admin` — Admin page loads
- [ ] `POST /admin/populate-daily-values` — Job can start
- [ ] `GET /admin/populate-daily-values` — Job status displays
- [ ] `POST /admin/recreate-db` — DB recreate works
- [ ] `GET /db-check` — DB check page loads

## Stop criteria

If any item fails, stop and fix before proceeding to the next milestone.
