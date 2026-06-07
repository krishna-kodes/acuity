"""Resolves the correct sync function for a project based on its sync_provider.

Per-project sync_config is deserialized through SyncConfigRequest (Pydantic).
Falls back to settings.sync_provider when project.sync_provider is None.
"""

from typing import Callable

from app.config import settings
from app.models.project import Project
from app.schemas.sync import SyncConfigRequest, SyncProvider


def get_sync_fn(project: Project) -> tuple[SyncProvider, SyncConfigRequest, Callable]:
    """Return (resolved_provider, config, sync_callable) for the given project.

    The callable signature:
      sync_fn(epics: list[dict]) -> dict   (may be a coroutine for Jira)
    """
    provider_str = project.sync_provider or settings.sync_provider
    try:
        provider = SyncProvider(provider_str)
    except ValueError:
        provider = SyncProvider.github

    config = SyncConfigRequest.model_validate(project.sync_config or {})

    if provider == SyncProvider.jira:
        from app.services.jira_sync import sync_epics_to_jira

        async def jira_fn(epics: list[dict]) -> dict:
            return await sync_epics_to_jira(epics, config)

        return provider, config, jira_fn

    from app.services.github_sync import sync_epics_to_github

    def github_fn(epics: list[dict]) -> dict:
        return sync_epics_to_github(epics, config)

    return provider, config, github_fn
