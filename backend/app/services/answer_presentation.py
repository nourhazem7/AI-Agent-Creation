"""Deterministic Chat answer presentation — no LLM call, no network I/O, pure function of the
already-executed SQL result (`result.data`, the same rows persisted as `Message.result_data`).

This replaced an earlier design that ran a second LLM call to rewrite the agent's raw
commentary into business prose. Live testing showed that call ran on nearly every message
(the agent's raw commentary is essentially never clean prose on its own), so the latency/cost
problem was structural, not something worth patching around — the fix is to stop depending on
a second model call at all and build the primary answer directly from the real, structured
result instead. `result.commentary` is still preserved as `Message.raw_answer` for debugging,
but it is never read by this module — the executed SQL result is the sole source of truth.

Presentation style: a single value (or a single row) is one short sentence — "Total
employees: 420." reads fine as prose and isn't "multiple pieces of information" in the sense
that needs a list. Anything with more than one row (a ranking, a grouped breakdown, a plain
listing) is rendered as an intro line followed by one bullet per item — dense multi-row
paragraphs are exactly what employees found hard to scan, so those never get concatenated
into a single sentence anymore.

The row shapes this is built around were inspected directly against the real Sales Analytics
and HR Analytics demo databases (schema + live chat output captured during development), not
assumed — see the module's test file for the exact real shapes covered.
"""

from __future__ import annotations

_ID_COLUMN = "id"
_ID_SUFFIX = "_id"
_DATE_SUFFIXES = ("_date", "_month")
_BULLET = "•"

# Keyword membership on the column name (case-insensitive substring match) decides currency
# vs. plain number formatting. Deliberately excludes bare "total" — true of both
# total_revenue (currency) and total_orders (a count) — the more specific token does the work.
_CURRENCY_KEYWORDS = (
    "amount", "revenue", "price", "cost", "salary", "budget", "spend", "spent", "pay", "fee",
    "target", "net", "gross", "payment", "earning", "income", "sales",
)

_MAX_RANKED_ITEMS = 5
_MAX_LISTED_ITEMS = 8


def _is_id_column(name: str) -> bool:
    lower = name.lower()
    return lower == _ID_COLUMN or lower.endswith(_ID_SUFFIX)


def _is_date_column(name: str) -> bool:
    lower = name.lower()
    return lower == "date" or lower.endswith(_DATE_SUFFIXES)


def _is_currency_column(name: str) -> bool:
    lower = name.lower()
    return any(keyword in lower for keyword in _CURRENCY_KEYWORDS)


def _classify_columns(row: dict) -> tuple[list[str], list[str], list[str]]:
    """Returns (label_cols, metric_cols, date_cols) in original column order, excluding id
    columns entirely — they're never business-meaningful to show on their own. Value type is
    checked before any name-based keyword matching, which is what keeps a column like
    target_month (contains "target", a currency keyword, but holds a date string) safely out
    of the metric bucket — it never reaches keyword matching because it isn't numeric."""
    labels: list[str] = []
    metrics: list[str] = []
    dates: list[str] = []
    for col, value in row.items():
        if _is_id_column(col):
            continue
        if isinstance(value, bool):
            labels.append(col)
        elif isinstance(value, (int, float)):
            metrics.append(col)
        elif _is_date_column(col):
            dates.append(col)
        else:
            labels.append(col)
    return labels, metrics, dates


def _humanize(name: str) -> str:
    words = name.replace("_", " ").strip().lower()
    return words[:1].upper() + words[1:] if words else name


def _humanize_lower(name: str) -> str:
    return name.replace("_", " ").strip().lower()


def _capitalize_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _format_number(value: float) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return f"{int(value):,}"
    return f"{round(value, 2):,}"


def _format_currency(value: float) -> str:
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        return f"{sign}${magnitude / 1_000_000:.2f}M"
    if isinstance(value, int) or float(magnitude).is_integer():
        return f"{sign}${int(magnitude):,}"
    return f"{sign}${magnitude:,.2f}"


def _format_value(column: str, value) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return _format_currency(value) if _is_currency_column(column) else _format_number(value)
    return str(value) if value is not None else "—"


def _format_pair(column: str, value) -> str:
    return f"{_humanize(column)}: {_format_value(column, value)}"


def _pluralize(word: str) -> str:
    lower = word.lower()
    if lower.endswith(("s", "x", "z")) or lower.endswith(("sh", "ch")):
        return word + "es"
    if len(lower) > 1 and lower[-1] == "y" and lower[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word if lower.endswith("s") else word + "s"


def _entity_label_from_column(column: str) -> str:
    base = column
    for suffix in ("_name", "name"):
        if base.lower().endswith(suffix):
            base = base[: -len(suffix)]
            break
    base = base.replace("_", " ").strip()
    return _pluralize(base) if base else "results"


def _identity(row: dict, label_cols: list[str]) -> str:
    """Builds a short display identity for one row from its label columns — merging an
    adjacent first_name/last_name pair into a full name (the single most common case seen in
    both real demo databases), and otherwise using just the first label column so bullets stay
    short; every label column is still visible in View data regardless."""
    lower_cols = [c.lower() for c in label_cols]
    if "first_name" in lower_cols and "last_name" in lower_cols:
        first = row[label_cols[lower_cols.index("first_name")]]
        last = row[label_cols[lower_cols.index("last_name")]]
        return f"{first} {last}".strip()
    if label_cols:
        return str(row[label_cols[0]])
    return "This result"


_MAX_EXTRA_LABEL_COLUMNS = 1


def _has_ambiguous_identity(label_cols: list[str]) -> bool:
    """True when there are too many independent label dimensions to safely collapse into one
    short per-row identity — e.g. first_name/last_name/job_title/project_name/role (5 columns,
    real shape from the 131-row employee-project-assignment case): naming just the employee
    while silently dropping which project and role would misrepresent what the row is
    actually about. One extra label beyond the core identity (e.g. a sales rep's region) is a
    reasonable simplification for concision; several is a sign this isn't a single-dimension
    ranking at all."""
    lower_cols = [c.lower() for c in label_cols]
    core_used = 2 if ("first_name" in lower_cols and "last_name" in lower_cols) else 1
    return max(0, len(label_cols) - core_used) > _MAX_EXTRA_LABEL_COLUMNS


def _is_sorted_desc(rows: list[dict], metric_col: str) -> bool:
    values = [row[metric_col] for row in rows]
    return all(values[i] >= values[i + 1] for i in range(len(values) - 1))


def _bullet_metric_phrase(row: dict, metric_cols: list[str]) -> str:
    """A single metric is shown as a bare value (the bullet's intro line already names it); two
    or more are each labeled so it stays unambiguous which number is which."""
    if len(metric_cols) == 1:
        col = metric_cols[0]
        return _format_value(col, row[col])
    return " · ".join(_format_pair(m, row[m]) for m in metric_cols)


def _join_with_and(items: list[str]) -> str:
    if len(items) <= 1:
        return items[0] if items else ""
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _split_constant_metrics(rows: list[dict], metric_cols: list[str]) -> tuple[list[str], list[str]]:
    """A metric that holds the exact same value on every row (e.g. unit_price when every row
    is a purchase of the same single product) isn't something worth repeating per item, or
    worth computing a "ranging from X to X" range over — it's one shared fact about the whole
    result, stated once, not a per-row metric. Splits into (constant, varying); only the
    varying ones drive ranking/bullet/range math."""
    constant, varying = [], []
    for col in metric_cols:
        values = {row[col] for row in rows}
        (constant if len(values) == 1 else varying).append(col)
    return constant, varying


def _compose(intro: str, bullets: list[str], tail: str | None) -> str:
    body = intro + "\n\n" + "\n".join(bullets)
    if tail:
        body += "\n\n" + tail
    return body


def _ranked_bullets(rows: list[dict], label_cols: list[str], metric_cols: list[str]) -> str:
    constant_metrics, varying_metrics = _split_constant_metrics(rows, metric_cols)
    # If every metric happens to be constant (unusual), fall back to using them all rather
    # than being left with nothing to rank by.
    active_metrics = varying_metrics or metric_cols
    metric_col = active_metrics[0]
    sorted_desc = _is_sorted_desc(rows, metric_col)
    shown = rows[: min(len(rows), _MAX_RANKED_ITEMS)]

    metric_phrase_lower = _join_with_and([_humanize_lower(m) for m in active_metrics])
    if sorted_desc:
        # Real ranking language is only used when the data itself demonstrates it — checked
        # above, never assumed from row position alone.
        intro = f"Highest {metric_phrase_lower}:"
    else:
        label_phrase = _humanize_lower(label_cols[0])
        intro = f"{_capitalize_first(metric_phrase_lower)} by {label_phrase}:"

    bullets = [
        f"{_BULLET} {_identity(r, label_cols)} — {_bullet_metric_phrase(r, active_metrics)}" for r in shown
    ]

    tail = None
    if len(rows) > _MAX_RANKED_ITEMS:
        values = [row[metric_col] for row in rows]
        tail = (
            f"{len(rows)} results total, ranging from {_format_value(metric_col, min(values))} to "
            f"{_format_value(metric_col, max(values))} — View data for the full breakdown."
        )

    body = _compose(intro, bullets, tail)
    if constant_metrics and varying_metrics:
        # State the shared fact once, up front, rather than repeating it on every bullet.
        shared = ", ".join(_format_pair(m, rows[0][m]) for m in constant_metrics)
        body = f"{shared}.\n\n{body}"
    return body


def _listed_identity(row: dict, label_cols: list[str]) -> str:
    """Unlike _identity (used for rankings, where a merged first/last name genuinely *is* the
    natural identity), a pure listing's entity is whatever the first label column represents —
    e.g. department_name, not the manager's name that happens to share the row. That first
    column decides what "N <entity> found" refers to, so it must stay primary; any name pair
    among the remaining columns becomes supporting detail in parentheses instead of displacing
    it (real shape: department_name, company_name, first_name, last_name — the department is
    the thing being listed, the manager is detail about it)."""
    primary = str(row[label_cols[0]])
    remaining = label_cols[1:]
    lower_remaining = [c.lower() for c in remaining]
    if "first_name" in lower_remaining and "last_name" in lower_remaining:
        first = row[remaining[lower_remaining.index("first_name")]]
        last = row[remaining[lower_remaining.index("last_name")]]
        return f"{primary} ({first} {last})"
    if remaining:
        return f"{primary} ({row[remaining[0]]})"
    return primary


def _listed_bullets(rows: list[dict], label_cols: list[str]) -> str:
    entity_label = _entity_label_from_column(label_cols[0]) if label_cols else "results"
    shown = rows[: min(len(rows), _MAX_LISTED_ITEMS)]
    intro = f"{len(rows)} {entity_label} found:"
    bullets = [f"{_BULLET} {_listed_identity(r, label_cols)}" for r in shown]
    tail = None
    if len(rows) > _MAX_LISTED_ITEMS:
        tail = f"{len(rows) - _MAX_LISTED_ITEMS} more not shown — View data for the full breakdown."
    return _compose(intro, bullets, tail)


def format_business_answer(rows: list[dict]) -> str:
    """The sole entry point. Deterministic, no network I/O — a pure function of the real,
    already-executed query result. Never states a number, name, or count that isn't a literal
    value already present in `rows` (or a directly-computed count/min/max over them); falls
    back to an honest count when the shape doesn't fit a recognized pattern rather than forcing
    a summary that could misrepresent the data.

    A single value (or single row) stays one short sentence — that's not "multiple pieces of
    information" needing a list. Anything with more than one row is rendered as an intro line
    plus one bullet per item, never concatenated into a single dense paragraph."""
    if not rows:
        return "No matching results were found."

    if len(rows) == 1:
        row = rows[0]
        pairs = [_format_pair(col, val) for col, val in row.items() if not _is_id_column(col)]
        if not pairs:
            return "Here's what I found."
        return ", ".join(pairs) + "."

    label_cols, metric_cols, _date_cols = _classify_columns(rows[0])

    if metric_cols and label_cols and not _has_ambiguous_identity(label_cols):
        return _ranked_bullets(rows, label_cols, metric_cols)

    if not metric_cols and label_cols:
        return _listed_bullets(rows, label_cols)

    if metric_cols and not label_cols:
        # Pure metrics, no identity to hang them on — nothing safe to put on a bullet, so
        # report the count plainly rather than inventing per-row labels.
        return f"{len(rows)} results found. View data for details."

    # Either no recognizable label/metric column at all, or (metric_cols and label_cols but
    # _has_ambiguous_identity) — a genuinely multi-dimensional result like the 131-row
    # employee/project/role case, where no single short identity can represent a row without
    # dropping context that changes what it means. The required graceful fallback: an honest
    # count rather than a guessed summary or a misleading per-row bullet.
    return f"{len(rows)} results found. View data for the full breakdown."
