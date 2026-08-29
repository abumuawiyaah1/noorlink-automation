-- Support ticket language tag for multilingual inbox (next wave #16)

ALTER TABLE support_tickets
  ADD COLUMN IF NOT EXISTS language VARCHAR(8) NOT NULL DEFAULT 'en';

CREATE INDEX IF NOT EXISTS idx_support_tickets_language
  ON support_tickets (language);

COMMENT ON COLUMN support_tickets.language IS 'ISO-style short code: en, ar, etc.';
