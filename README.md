# AgentForge

> **Build once. Validate once. Reuse your business AI agent anywhere.**

AgentForge is a full-stack platform for creating **database-trained AI agents** that understand a company's data and can answer business questions through natural language.

Instead of building a chatbot from scratch for every use case, AgentForge allows organizations to create an agent that is already configured around their database, business knowledge, and rules — then validate it and reuse it in conversational experiences.

**Connect → Understand → Configure → Validate → Chat → Share**

---

## What is AgentForge?

Business data is often locked inside relational databases and requires SQL knowledge to access.

AgentForge bridges that gap by allowing users to build an AI agent that understands:

- The database schema
- Tables and relationships
- Business documentation
- Organization-specific business rules
- Validation requirements

Once configured and validated, the agent can answer natural-language questions against the connected database.

For example:

> **"Which department has the highest average salary?"**

The agent understands the question, generates the appropriate SQL, executes it against the business database, and returns a clear business answer.

The underlying SQL and data remain available for users who need deeper visibility.

---

# Core Workflow

```text
┌─────────────────┐
│  Create Agent   │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Connect Database│
└────────┬────────┘
         ↓
┌─────────────────┐
│    Knowledge    │
│ Schema + Docs   │
│ Business Rules  │
└────────┬────────┘
         ↓
┌─────────────────┐
│    Validate     │
│ Questions + SQL │
│ Answers + Judge │
└────────┬────────┘
         ↓
┌─────────────────┐
│      Ready      │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Share / Reuse   │
└────────┬────────┘
         ↓
┌─────────────────┐
│      Chat       │
│  Business Q&A   │
└─────────────────┘
