# Database migrations

Apply the migration from the repository root after PostgreSQL is running:

```powershell
psql -h localhost -p 5432 -U postgres -d fyp_postgres -f backend/migrations/001_conversation_telemetry.sql
```

The SQL is idempotent and can be applied more than once. Set `PGPASSWORD=password` in the shell, or enter the password when prompted.
