-- Weekly goals use Monday 00:00 through Sunday 23:59:59 in Singapore time.
ALTER TABLE user_stats
    ALTER COLUMN weekly_score_week
    SET DEFAULT date_trunc(
        'week',
        timezone('Asia/Singapore', CURRENT_TIMESTAMP)
    )::date;
