"""SQLAlchemy models for AgentForge's own persistence layer.

Import every model module here so relationships resolve when Base.metadata
is used (e.g. create_all()), regardless of which router imports which model.
"""

from app.models.company import Company
from app.models.user import User
from app.models.agent import Agent
from app.models.agent_share import AgentShare
from app.models.database_connection import DatabaseConnection
from app.models.knowledge_asset import KnowledgeAsset
from app.models.validation_test import ValidationTest
from app.models.validation_run import ValidationRun
from app.models.conversation import Conversation
from app.models.message import Message

__all__ = [
    "Company",
    "User",
    "Agent",
    "AgentShare",
    "DatabaseConnection",
    "KnowledgeAsset",
    "ValidationTest",
    "ValidationRun",
    "Conversation",
    "Message",
]
