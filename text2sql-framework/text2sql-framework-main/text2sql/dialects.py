"""Per-dialect guidance for the LLM on where schema metadata lives."""

from __future__ import annotations

# Each dialect returns instructions the LLM gets in its system prompt.
# The LLM uses execute_sql to query these catalog tables itself.

DIALECT_GUIDES = {
    "postgresql": """
## Schema Metadata (PostgreSQL)

To find tables:
  SELECT table_schema, table_name FROM information_schema.tables
  WHERE table_schema NOT IN ('pg_catalog', 'information_schema')

To find columns (with descriptions):
  SELECT c.table_schema, c.table_name, c.column_name, c.data_type, c.is_nullable,
         pgd.description AS column_description
  FROM information_schema.columns c
  LEFT JOIN pg_catalog.pg_statio_all_tables st ON c.table_schema = st.schemaname AND c.table_name = st.relname
  LEFT JOIN pg_catalog.pg_description pgd ON pgd.objoid = st.relid AND pgd.objsubid = c.ordinal_position
  WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema')

To find foreign keys / relationships:
  SELECT
    tc.table_name, kcu.column_name,
    ccu.table_name AS foreign_table, ccu.column_name AS foreign_column
  FROM information_schema.table_constraints tc
  JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
  JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
  WHERE tc.constraint_type = 'FOREIGN KEY'

You can filter any of these with ILIKE to search by keyword, e.g.:
  WHERE c.column_name ILIKE '%revenue%'
""",

    "mysql": """
## Schema Metadata (MySQL)

To find tables:
  SELECT table_schema, table_name, table_comment
  FROM information_schema.tables
  WHERE table_schema = DATABASE()

To find columns (with descriptions):
  SELECT table_name, column_name, data_type, column_type, is_nullable, column_comment
  FROM information_schema.columns
  WHERE table_schema = DATABASE()

To find foreign keys:
  SELECT table_name, column_name, referenced_table_name, referenced_column_name
  FROM information_schema.key_column_usage
  WHERE table_schema = DATABASE() AND referenced_table_name IS NOT NULL

Filter with LIKE to search by keyword, e.g.:
  WHERE column_name LIKE '%revenue%'
""",

    "sqlite": """
## Schema Metadata (SQLite)

To find tables:
  SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'

To see a table's columns and types:
  PRAGMA table_info('table_name')

To see a table's full DDL:
  SELECT sql FROM sqlite_master WHERE type='table' AND name='table_name'

To find foreign keys for a table:
  PRAGMA foreign_key_list('table_name')

SQLite does not have column descriptions/comments. You must infer meaning from column names.
""",

    "mssql": """
## Schema Metadata (SQL Server)

To find tables:
  SELECT s.name AS schema_name, t.name AS table_name
  FROM sys.tables t JOIN sys.schemas s ON t.schema_id = s.schema_id

To find columns (with descriptions):
  SELECT t.name AS table_name, c.name AS column_name, ty.name AS data_type,
         ep.value AS column_description
  FROM sys.columns c
  JOIN sys.tables t ON c.object_id = t.object_id
  JOIN sys.types ty ON c.user_type_id = ty.user_type_id
  LEFT JOIN sys.extended_properties ep ON ep.major_id = c.object_id AND ep.minor_id = c.column_id

To find foreign keys:
  SELECT
    tp.name AS parent_table, cp.name AS parent_column,
    tr.name AS referenced_table, cr.name AS referenced_column
  FROM sys.foreign_key_columns fkc
  JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
  JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id AND fkc.parent_column_id = cp.column_id
  JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
  JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id AND fkc.referenced_column_id = cr.column_id

Filter with LIKE to search by keyword.
""",

    "snowflake": """
## Schema Metadata (Snowflake)

To find tables:
  SELECT table_schema, table_name, comment AS table_description
  FROM information_schema.tables
  WHERE table_schema NOT IN ('INFORMATION_SCHEMA')

To find columns (with descriptions):
  SELECT table_name, column_name, data_type, is_nullable, comment AS column_description
  FROM information_schema.columns
  WHERE table_schema NOT IN ('INFORMATION_SCHEMA')

To find foreign keys:
  SHOW IMPORTED KEYS IN SCHEMA

Filter with ILIKE to search by keyword, e.g.:
  WHERE column_name ILIKE '%revenue%'
""",

    "oracle": """
## Schema Metadata (Oracle)

Oracle stores schema metadata in data-dictionary views. The connection is scoped
to one schema, so use the USER_* views (the current user's own objects).

To find tables:
  SELECT table_name FROM user_tables

To find columns (name, type, nullability):
  SELECT table_name, column_name, data_type, nullable
  FROM user_tab_columns

To find foreign keys / relationships (child column -> parent table/column):
  SELECT ac.constraint_name, acc.table_name AS child_table, acc.column_name AS child_column,
         rcc.table_name AS parent_table, rcc.column_name AS parent_column
  FROM user_constraints ac
  JOIN user_cons_columns acc  ON acc.constraint_name = ac.constraint_name
  JOIN user_cons_columns rcc  ON rcc.constraint_name = ac.r_constraint_name
                              AND rcc.position = acc.position
  WHERE ac.constraint_type = 'R'

IMPORTANT Oracle rules:
- Identifiers are stored UPPERCASE. When searching by keyword, uppercase the
  pattern, e.g.  WHERE UPPER(column_name) LIKE '%REVENUE%'
- Oracle has NO LIMIT keyword. Cap rows with  FETCH FIRST 100 ROWS ONLY  (12c+)
  or  WHERE ROWNUM <= 100 .
- Do NOT terminate statements with a trailing semicolon.
- Use Oracle date functions (TO_DATE, TRUNC, SYSDATE, ADD_MONTHS), not MySQL/Postgres ones.
""",

    "bigquery": """
## Schema Metadata (BigQuery)

To find tables:
  SELECT table_schema, table_name
  FROM INFORMATION_SCHEMA.TABLES

To find columns (with descriptions):
  SELECT table_name, column_name, data_type, description
  FROM INFORMATION_SCHEMA.COLUMN_FIELD_PATHS

To find foreign keys:
  SELECT * FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
  WHERE constraint_type = 'FOREIGN KEY'

Filter with LIKE to search by keyword.
""",
}


def get_dialect_guide(dialect_name):
    # type: (str) -> str
    """Get schema metadata guidance for a given SQL dialect."""
    # Normalize dialect name
    name = dialect_name.lower()
    # Handle aliases
    if name in ("postgres", "psycopg2", "pg8000"):
        name = "postgresql"
    elif name in ("mysql+pymysql", "mysql+mysqlconnector", "mariadb"):
        name = "mysql"
    elif name in ("mssql+pyodbc", "mssql+pymssql"):
        name = "mssql"

    if name in DIALECT_GUIDES:
        return DIALECT_GUIDES[name]

    # Fallback: generic information_schema (works for most SQL databases)
    return """
## Schema Metadata ({dialect})

Try querying information_schema (most SQL databases support this):
  SELECT table_name FROM information_schema.tables
  SELECT table_name, column_name, data_type FROM information_schema.columns

If that doesn't work, try SHOW TABLES or DESCRIBE <table_name>.
""".format(dialect=dialect_name)
