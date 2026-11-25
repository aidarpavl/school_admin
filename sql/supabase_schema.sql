-- Supabase → SQL Editor ішінде бір рет іске қосыңыз (бағдарлама кестелерді өзі де құрады).
CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  full_name TEXT, email TEXT, role TEXT DEFAULT 'teacher', position TEXT, subject TEXT, active INTEGER DEFAULT 1, created_at TEXT);
CREATE TABLE IF NOT EXISTS reset_codes (id SERIAL PRIMARY KEY, username TEXT, code TEXT, expires_at TEXT, used INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS tasks (id SERIAL PRIMARY KEY, title TEXT, description TEXT, assignee TEXT, created_by TEXT,
  due_date TEXT, priority TEXT, done INTEGER DEFAULT 0, done_at TEXT, report TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS duties (id SERIAL PRIMARY KEY, duty TEXT, username TEXT, assigned_by TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS documents (id SERIAL PRIMARY KEY, title TEXT, doc_type TEXT, channel TEXT, author TEXT,
  to_role TEXT, to_user TEXT, status TEXT, content TEXT, file_url TEXT, resolution TEXT, due_date TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS doc_history (id SERIAL PRIMARY KEY, doc_id INTEGER, actor TEXT, action TEXT, note TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS feedback (id SERIAL PRIMARY KEY, author TEXT, anonymous INTEGER DEFAULT 0, target_role TEXT,
  source TEXT, category TEXT, text TEXT, sentiment REAL, topics TEXT, status TEXT DEFAULT 'Жаңа', response TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS records (id SERIAL PRIMARY KEY, module TEXT, kind TEXT, author TEXT, data TEXT,
  private INTEGER DEFAULT 0, created_at TEXT);
CREATE INDEX IF NOT EXISTS idx_records_module ON records(module, kind);
CREATE INDEX IF NOT EXISTS idx_tasks_assignee ON tasks(assignee);
-- Бағдарлама серверде тікелей Postgres қосылымы арқылы жұмыс істейді; кестелерге ашық API кірісін жабу:
ALTER TABLE users ENABLE ROW LEVEL SECURITY; ALTER TABLE reset_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY; ALTER TABLE duties ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY; ALTER TABLE doc_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY; ALTER TABLE records ENABLE ROW LEVEL SECURITY;
