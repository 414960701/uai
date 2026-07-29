"""Static validation for mounted-agent graphs."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .models import GraphIssue, GraphValidationResult
from .ports import RepositoryPort


class AgentGraphValidator:
    def __init__(self, repository: RepositoryPort) -> None:
        self.repository = repository

    async def validate(
        self,
        tenant_id: str,
        root_agent_id: str,
        root_revision: Optional[int] = None,
    ) -> GraphValidationResult:
        issues: List[GraphIssue] = []
        nodes: Set[str] = set()
        edges: List[Dict[str, str]] = []
        visited: Set[Tuple[str, int]] = set()
        active: List[Tuple[str, int]] = []

        async def walk(agent_id: str, revision: Optional[int] = None) -> None:
            spec = await self.repository.get_agent(tenant_id, agent_id, revision)
            active_ids = [active_agent_id for active_agent_id, _ in active]
            if spec is None:
                if revision is None:
                    code = "missing_agent"
                    message = f"mounted agent does not exist: {agent_id}"
                else:
                    code = "missing_revision"
                    message = f"{agent_id} revision {revision} does not exist"
                issues.append(
                    GraphIssue(
                        code=code,
                        message=message,
                        path=active_ids + [agent_id],
                    )
                )
                return

            if agent_id in active_ids:
                cycle_start = active_ids.index(agent_id)
                cycle = active_ids[cycle_start:] + [agent_id]
                issues.append(
                    GraphIssue(
                        code="mount_cycle",
                        message=f"mounted-agent cycle detected: {' -> '.join(cycle)}",
                        path=cycle,
                    )
                )
                return

            key = (agent_id, spec.revision)
            if key in visited:
                return
            nodes.add(agent_id)
            if not spec.enabled:
                issues.append(
                    GraphIssue(
                        code="disabled_agent",
                        message=f"agent is disabled: {agent_id}",
                        path=active_ids + [agent_id],
                    )
                )
            active.append(key)
            for mount in spec.children:
                edges.append(
                    {
                        "from": agent_id,
                        "to": mount.agent_id,
                        "alias": mount.alias,
                    }
                )
                await walk(mount.agent_id, mount.revision)
            active.pop()
            visited.add(key)

        await walk(root_agent_id, root_revision)
        return GraphValidationResult(
            valid=not issues,
            nodes=sorted(nodes),
            edges=edges,
            issues=issues,
        )
