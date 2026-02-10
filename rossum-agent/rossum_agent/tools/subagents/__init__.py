"""Sub-agents for the Rossum Agent.

Opus-powered sub-agents for complex iterative tasks:
- Knowledge base search with AI analysis
- Elis documentation search with AI analysis
- Schema patching with programmatic bulk updates
"""

from __future__ import annotations

from rossum_agent.bedrock_client import OPUS_MODEL_ID
from rossum_agent.tools.subagents.base import SubAgent, SubAgentConfig, SubAgentResult
from rossum_agent.tools.subagents.elis_docs import search_elis_docs
from rossum_agent.tools.subagents.knowledge_base import search_knowledge_base
from rossum_agent.tools.subagents.mcp_helpers import call_mcp_tool
from rossum_agent.tools.subagents.schema_creation import SchemaCreationSubAgent, create_schema_with_subagent
from rossum_agent.tools.subagents.schema_patching import SchemaPatchingSubAgent, patch_schema_with_subagent

__all__ = [
    "OPUS_MODEL_ID",
    "SchemaCreationSubAgent",
    "SchemaPatchingSubAgent",
    "SubAgent",
    "SubAgentConfig",
    "SubAgentResult",
    "call_mcp_tool",
    "create_schema_with_subagent",
    "patch_schema_with_subagent",
    "search_elis_docs",
    "search_knowledge_base",
]
