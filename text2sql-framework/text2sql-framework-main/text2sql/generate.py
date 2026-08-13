"""SQL generation using the Deep Agents SDK.

The LLM gets pre-loaded tools (execute_sql, lookup_example) and a system prompt
with dialect-specific guidance on where schema metadata lives. Deep Agents handles
the agentic loop, context compaction, and provider abstraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from text2sql.agent import create_deep_agent

from text2sql.connection import Database
from text2sql.dialects import get_dialect_guide
from text2sql.examples import ExampleStore
from text2sql.tools import make_tools
from text2sql.tracing import Tracer


@dataclass
class SQLResult:
    """Result of a text-to-SQL query."""

    question: str
    sql: str
    data: list = field(default_factory=list)
    error: Optional[str] = None
    commentary: str = ""
    tool_calls_made: int = 0
    iterations: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def success(self) -> bool:
        return self.error is None and self.sql != ""

    def __str__(self) -> str:
        if self.error:
            return f"Error: {self.error}\nSQL: {self.sql}"
        return f"SQL: {self.sql}\n({len(self.data)} rows)"


SYSTEM_PROMPT = """You are a SQL expert. Translate natural language questions into SQL queries.

This is a **{dialect}** database.

{dialect_guide}
{custom_metadata}
## Tools

- `execute_sql` — run any read-only SQL (SELECT, WITH, SHOW, DESCRIBE, PRAGMA). Use this to explore the schema metadata and test queries. Use LIMIT to keep result sets under 100 rows when possible.
{example_tool_note}
## Workflow

1. EXPLORE: Query the schema metadata (see above) to find relevant tables and columns
   - Search by keyword: filter table/column names with LIKE or ILIKE
   - Look at column descriptions/comments if available
2. INSPECT: Query full column lists for candidate tables to see exact names and types
3. RELATIONSHIPS: Query foreign keys to find how tables join
4. EXAMPLES: If the question involves a business concept you're unsure about, use `lookup_example` to get guidance{example_list_note}
5. WRITE & EXECUTE: Write your SQL and execute it to verify it works
6. FIX: If it errors, read the error, fix, and re-execute

## Rules
- ALWAYS explore the schema first — never guess table or column names
- Use exact names from the metadata catalog
- Write {dialect} SQL syntax
- You MUST execute your final SQL via `execute_sql` before responding. Never return SQL you haven't run.
- If execution fails, read the error, fix the SQL, and execute again. Repeat until it works.
- Once the query executes successfully, your final response MUST include the SQL inside a ```sql code block. You may include brief commentary outside the code block if helpful. The results are captured automatically and displayed to the user separately.
{instructions}"""


class SQLGenerator:
    """Creates a Deep Agent pre-loaded with text2sql tools."""

    def __init__(
        self,
        db: Database,
        model: str = "anthropic:claude-sonnet-4-6",
        instructions: str | None = None,
        custom_metadata: str | None = None,
        example_store: ExampleStore | None = None,
        tracer: Tracer | None = None,
        base_url: str | None = None,
        verify_ssl: bool = True,
        extra_body: dict | None = None,
        llm_api_key: str | None = None,
    ):
        self.db = db
        self.model = model
        self.instructions = instructions
        self.custom_metadata = custom_metadata
        self.example_store = example_store
        self.tracer = tracer
        self.base_url = base_url
        self.verify_ssl = verify_ssl
        self.extra_body = extra_body
        self.llm_api_key = llm_api_key

        self.tools = make_tools(db, example_store)
        self.system_prompt = self._build_system_prompt()

        self.agent = create_deep_agent(
            model=model,
            tools=self.tools,
            system_prompt=self.system_prompt,
            base_url=base_url,
            verify_ssl=verify_ssl,
            extra_body=extra_body,
            llm_api_key=llm_api_key,
        )

    def _build_system_prompt(self) -> str:
        dialect = self.db.dialect
        dialect_guide = get_dialect_guide(dialect)

        custom = ""
        if self.custom_metadata:
            custom = f"\n## Custom Metadata\n{self.custom_metadata}\n"

        instructions = ""
        if self.instructions:
            instructions = f"\n## Instructions\n{self.instructions}\n"

        example_tool_note = ""
        example_list_note = ""
        if self.example_store:
            example_tool_note = "- `lookup_example` — look up a curated example scenario by keyword (e.g. \"net revenue\", \"customer address\"). Returns guidance on which tables/columns/joins to use.\n"
            scenarios = self.example_store.list_scenarios()
            if scenarios:
                example_list_note = "\n   Available examples: {}".format(", ".join(scenarios))

        return SYSTEM_PROMPT.format(
            dialect=dialect,
            dialect_guide=dialect_guide,
            custom_metadata=custom,
            instructions=instructions,
            example_tool_note=example_tool_note,
            example_list_note=example_list_note,
        )

    def ask(self, question: str, max_rows: int | None = None) -> SQLResult:
        if self.tracer:
            self.tracer.start_query(question)

        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": question}]}
        )

        return self._parse_result(question, result["messages"], max_rows=max_rows)

    def stream_ask(self, question: str, max_rows: int | None = None):
        """Yield ('step'|'step_result', payload) events as the agent works,
        then yield ('result', SQLResult). Additive; ask() is unchanged."""
        accumulated = []
        args_by_id = {}
        last_step_failed = False

        if self.tracer:
            self.tracer.start_query(question)

        try:
            stream_iter = self.agent.stream(
                {"messages": [{"role": "user", "content": question}]},
                stream_mode="updates",
            )
            for chunk in stream_iter:
                for node_state in chunk.values():
                    if not node_state or not hasattr(node_state, "get"):
                        continue
                    for msg in node_state.get("messages", []):
                        accumulated.append(msg)
                        
                        # AIMessage with tool_calls
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tc in msg.tool_calls:
                                tc_id = tc.get("id")
                                tc_name = tc.get("name")
                                args = tc.get("args", {})
                                if tc_id:
                                    args_by_id[tc_id] = args
                                if tc_name == "execute_sql":
                                    sql = args.get("sql", "")
                                    kind = "query"
                                    if any(x in sql.lower() for x in ["user_tables", "user_tab_columns", "user_constraints", "all_tab_cols", "all_tables", "cols", "tabs"]):
                                        kind = "explore"
                                    elif last_step_failed:
                                        kind = "fix"
                                    
                                    label = f"Querying {kind} schema/data"
                                    if kind == "explore":
                                        label = "Exploring database schema"
                                    elif kind == "fix":
                                        label = "Self-correcting SQL query"
                                    else:
                                        label = "Executing database query"
                                    
                                    yield ("step", {"kind": kind, "sql": sql, "label": label, "id": tc_id})

                        # ToolMessage
                        if hasattr(msg, "name") and hasattr(msg, "tool_call_id"):
                            tc_id = getattr(msg, "tool_call_id", None)
                            tc_name = getattr(msg, "name", "")
                            content = msg.content if isinstance(msg.content, str) else str(msg.content)
                            
                            if tc_name == "execute_sql":
                                error_str = None
                                rows_count = None
                                if content.lstrip().startswith(("SQL Error", "Blocked", "Empty")):
                                    error_str = content.strip()
                                    last_step_failed = True
                                else:
                                    last_step_failed = False
                                    match = re.search(r"\((\d+)\s+rows?\)", content)
                                    if match:
                                        rows_count = int(match.group(1))
                                    elif "0 rows returned" in content:
                                        rows_count = 0
                                
                                yield ("step_result", {"id": tc_id, "rows": rows_count, "error": error_str})

            # Finished streaming loop, parse final result
            result = self._parse_result(question, accumulated, max_rows=max_rows)
            yield ("result", result)

        except Exception as e:
            # Fallback if streaming is not supported or raises error
            import os
            import traceback
            try:
                os.makedirs("d:/EPC/TandD/Site_Vision/SiteVision_V2/Backend/logs", exist_ok=True)
                with open("d:/EPC/TandD/Site_Vision/SiteVision_V2/Backend/logs/stream_error.log", "a", encoding="utf-8") as f:
                    f.write(f"\n--- ERROR AT {re.sub(r'[^0-9a-zA-Z]', '_', str(e))} ---\n")
                    traceback.print_exc(file=f)
            except Exception as log_err:
                print(f"[LOG ERROR] {log_err}")
            print(f"[STREAM FALLBACK] Error in streaming agent, falling back to ask(): {e}")
            
            # Emit a synthetic step
            yield ("step", {
                "kind": "query",
                "sql": "-- (Executing via fallback, no live SQL stream available)",
                "label": "Executing database query (fallback)",
                "id": "fallback"
            })
            
            # Get result synchronously
            # Avoid infinite recursion by calling agent.invoke directly or ask
            if self.tracer:
                self.tracer.start_query(question)
            invoke_res = self.agent.invoke(
                {"messages": [{"role": "user", "content": question}]}
            )
            result = self._parse_result(question, invoke_res["messages"], max_rows=max_rows)
            
            yield ("step_result", {
                "id": "fallback",
                "rows": len(result.data) if result.success else None,
                "error": result.error
            })
            yield ("result", result)

    def _parse_result(self, question: str, messages: list, max_rows: int | None = None) -> SQLResult:
        """Extract SQL from the agent's final text response, then execute it.

        The agent is instructed to respond with ONLY the final SQL in its last
        message (no tool calls). We parse that SQL out and execute it ourselves,
        giving the caller control over max_rows.
        """
        tool_calls_made = 0
        last_executed_sql = ""  # fallback if the model forgets the ```sql block
        args_by_id: dict[str, dict] = {}
        last_ai_timestamp = self.tracer._current.start_time if self.tracer and self.tracer._current else 0.0

        for msg in messages:
            resp_meta = getattr(msg, "response_metadata", {}) if hasattr(msg, "response_metadata") else {}
            msg_time = resp_meta.get("timestamp", 0)

            # Accumulate token usage from AIMessages
            usage = resp_meta.get("usage", {})
            if usage and self.tracer:
                self.tracer.record_token_usage(
                    usage.get("input_tokens", 0),
                    usage.get("output_tokens", 0),
                )

            # AIMessage with tool_calls
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                if self.tracer and hasattr(msg, "content"):
                    content = msg.content
                    if isinstance(content, str) and content.strip():
                        self.tracer.record_reasoning(content)
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = block.get("text", "")
                                if text.strip():
                                    self.tracer.record_reasoning(text)

                for tc in msg.tool_calls:
                    tool_calls_made += 1
                    args_by_id[tc["id"]] = tc["args"]

                if msg_time:
                    last_ai_timestamp = msg_time

            # AIMessage without tool_calls — pure reasoning
            elif hasattr(msg, "content") and hasattr(msg, "type") and getattr(msg, "type", None) == "ai":
                if self.tracer:
                    content = msg.content
                    if isinstance(content, str) and content.strip():
                        self.tracer.record_reasoning(content)
                if msg_time:
                    last_ai_timestamp = msg_time

            # ToolMessage — track every successful execute_sql for the fallback
            if hasattr(msg, "name") and hasattr(msg, "tool_call_id"):
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                tc_id = getattr(msg, "tool_call_id", None)

                if getattr(msg, "name", "") == "execute_sql" and not content.lstrip().startswith(
                    ("SQL Error", "Blocked", "Empty")
                ):
                    recovered = args_by_id.get(tc_id, {}).get("sql", "")
                    if recovered:
                        last_executed_sql = recovered

                if self.tracer:
                    if last_ai_timestamp > 0:
                        self.tracer._last_event_time = self.tracer._last_event_time or last_ai_timestamp
                        self.tracer._tool_start_time = last_ai_timestamp

                    args = args_by_id.get(tc_id, {})
                    self.tracer.record_tool_call(msg.name, args, content)

        # Extract SQL from the agent's final message (the one with no tool calls)
        final_sql = ""
        commentary = ""
        error = None
        final_text = ""
        if messages:
            last_msg = messages[-1]
            final_text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
            if isinstance(final_text, list):
                final_text = " ".join(
                    b.get("text", "") for b in final_text if isinstance(b, dict)
                )
            final_text = str(final_text)
            final_sql, commentary = _extract_sql_from_response(final_text)

        if not final_sql and last_executed_sql:
            # Model gave a prose answer without the ```sql block — use the last
            # query it actually ran successfully as the answer.
            final_sql = last_executed_sql

        if not final_sql:
            error = f"No SQL produced. Response: {final_text[:300]}"

        # Execute the SQL the agent specified in its response
        data = []
        if final_sql and not error:
            try:
                rows = self.db.execute(final_sql)
                if max_rows is not None:
                    rows = rows[:max_rows]
                data = rows
            except Exception as e:
                error = f"Final execution failed: {e}"

        if self.tracer:
            self.tracer.end_query(
                sql=final_sql,
                success=error is None and final_sql != "",
                error=error,
                iterations=tool_calls_made,
            )

        # Pull token counts from the trace
        input_tokens = 0
        output_tokens = 0
        if self.tracer and self.tracer.traces:
            last_trace = self.tracer.traces[-1]
            input_tokens = last_trace.input_tokens
            output_tokens = last_trace.output_tokens

        return SQLResult(
            question=question,
            sql=final_sql,
            data=data,
            error=error,
            commentary=commentary,
            tool_calls_made=tool_calls_made,
            iterations=tool_calls_made,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )



    # ── Single-pass SQL generation ────────────────────────────────────────────

    def write_sql(
        self,
        question: str,
        execute: bool = False,
        max_rows: int | None = None,
    ) -> SQLResult:
        """Single-pass SQL generation — no tool loop, no schema exploration.

        Dumps the full schema into the prompt and asks the LLM to produce SQL
        in one call. Faster and cheaper than ask(), but no self-correction and
        accuracy degrades on large schemas.

        Args:
            question:  Natural language question.
            execute:   If True, run the generated SQL and populate result.data.
            max_rows:  Max rows to return (only used when execute=True).
        """
        from text2sql.agent import _get_chat_model
        from langchain_core.messages import HumanMessage

        schema_summary = self.db.get_schema_summary()
        schema_text = _format_schema_for_prompt(schema_summary)
        dialect = self.db.dialect

        instructions_block = ""
        if self.instructions:
            instructions_block = f"\n## Instructions\n{self.instructions}\n"

        prompt = _WRITE_SQL_PROMPT.format(
            dialect=dialect,
            dialect_hint=_get_dialect_syntax_hint(dialect),
            schema=schema_text,
            instructions=instructions_block,
            question=question,
        )

        llm = _get_chat_model(
            self.model,
            base_url=self.base_url,
            verify_ssl=self.verify_ssl,
            extra_body=self.extra_body,
            llm_api_key=self.llm_api_key,
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = (
            response.content if isinstance(response.content, str) else str(response.content)
        )

        final_sql, commentary = _extract_sql_from_response(response_text)

        error = None
        data = []
        if not final_sql:
            error = f"No SQL produced. Response: {response_text[:300]}"
        elif execute:
            try:
                rows = self.db.execute(final_sql)
                if max_rows is not None:
                    rows = rows[:max_rows]
                data = rows
            except Exception as e:
                error = f"Execution failed: {e}"

        return SQLResult(
            question=question,
            sql=final_sql,
            data=data,
            error=error,
            commentary=commentary,
            tool_calls_made=0,
            iterations=0,
        )


_WRITE_SQL_PROMPT = """You are a SQL expert. Given the database schema below, write a single {dialect} SQL query that answers the question.

{dialect_hint}

## Schema

{schema}
{instructions}
## Rules
- Use ONLY table and column names that appear exactly in the schema above.
- Write valid {dialect} SQL syntax.
- Return ONLY the SQL query inside a ```sql code block. No explanation needed.

## Question

{question}"""


def _format_schema_for_prompt(schema: dict) -> str:
    """Render the schema dict from Database.get_schema_summary() as compact text."""
    lines = []
    for table, info in schema.items():
        comment = f"  -- {info['comment']}" if info.get("comment") else ""
        lines.append(f"Table: {table}{comment}")
        for col in info["columns"]:
            nullable = "" if col["nullable"] else " NOT NULL"
            col_comment = f"  -- {col['comment']}" if col.get("comment") else ""
            lines.append(f"  {col['name']}  {col['type']}{nullable}{col_comment}")
        if info.get("primary_keys"):
            lines.append(f"  PK: {', '.join(info['primary_keys'])}")
        for fk in info.get("foreign_keys", []):
            cols = ", ".join(fk["constrained_columns"])
            ref_cols = ", ".join(fk["referred_columns"])
            lines.append(f"  FK: {cols} -> {fk['referred_table']}({ref_cols})")
        lines.append("")
    return "\n".join(lines)


def _get_dialect_syntax_hint(dialect: str) -> str:
    hints = {
        "sqlite":     "Use SQLite syntax. String functions: SUBSTR, INSTR, LENGTH.",
        "postgresql": "Use PostgreSQL syntax. String functions: SUBSTRING, POSITION. Use ILIKE for case-insensitive matching.",
        "mysql":      "Use MySQL syntax. Use LIMIT for row caps. Dates: DATE_SUB, DATE_FORMAT.",
        "mssql":      "Use T-SQL syntax. Use TOP instead of LIMIT. Dates: DATEADD, DATEDIFF.",
    }
    return hints.get(dialect, f"Use {dialect} SQL syntax.")


def _extract_sql_from_response(text: str) -> tuple[str, str]:
    """Extract SQL and commentary from the agent's final text response.

    The agent wraps its final SQL in a ```sql code block. Everything outside
    the code block is commentary.

    Returns:
        (sql, commentary) tuple
    """
    if not text or not text.strip():
        return "", ""

    # Try to extract from ```sql ... ``` code block
    match = re.search(r'```(?:sql)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        sql = match.group(1).strip()
        # Commentary is everything outside the code block
        commentary = re.sub(r'```(?:sql)?\s*\n?.*?\n?```', '', text, flags=re.DOTALL).strip()
        return sql, commentary

    # Fallback: the whole response might be bare SQL — look for SELECT or a proper
    # CTE (WITH <name> AS (...)).  Require the CTE pattern so that prose sentences
    # starting with "with" are not mistaken for SQL.
    stripped = text.strip()
    match = re.search(
        r'(WITH\s+\w+\s+AS\s*\(.*|SELECT\b.*)',
        stripped,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        sql = match.group(1).strip()
        if ';' in sql:
            sql = sql[:sql.rindex(';') + 1]
        return sql, ""

    return "", text.strip()
