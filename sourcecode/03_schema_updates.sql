-- Run with: psql esl_lessons -f 03_schema_updates.sql

-- Verbs: distinguish an explicitly labeled "Verb Focus" section from a verb
-- inferred by spotting multi-tense treatment inside an undifferentiated
-- vocabulary list (common in the earlier, less-structured weeks).
ALTER TABLE verbs ADD COLUMN IF NOT EXISTS is_explicit BOOLEAN DEFAULT TRUE;

-- Documents: track the two-register Spanish rule (Cuban dialect for
-- narrative/idiom, professional medical/scientific Spanish for clinic
-- content) as free-text observations, not a pass/fail flag -- the students'
-- own Spanish is drifting for real sociolinguistic reasons, so "not Cuban"
-- isn't an error, just a data point.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS spanish_register_narrative TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS spanish_register_clinical TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS register_notes TEXT;

-- extraction_log needs a natural key independent of documents.id, since a
-- unit's log row is created BEFORE the document row exists (log tracks
-- attempts; documents row only gets written on success). Rebuilding it
-- cleanly since it's unused so far.
DROP TABLE IF EXISTS extraction_log;
CREATE TABLE extraction_log (
    unit_key        TEXT PRIMARY KEY,   -- e.g. "Week 9.pdf::day3" or "Week 4 Day 5.pdf"
    document_id     INTEGER REFERENCES documents(id),
    status          TEXT,               -- pending / success / failed
    attempt_count   INTEGER DEFAULT 0,
    error_message   TEXT,
    last_attempted  TIMESTAMP
);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO esl_extractor;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO esl_extractor;
