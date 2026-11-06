"""Offline operator configuration; never accepted from an application request."""
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .correspondence_block_model import BLOCK_SYSTEM
from .correspondence_model import MODEL
from .correspondence_model_transport import SafePublicClaude
from .public_proposal_jobs import PublicProposalJobs, load_approvals
from .source_config import _protected_path, load_private


class PublicProposalConfig(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra='forbid', hide_input_in_errors=True)
    version: Literal[1]
    executable: str = Field(min_length=1)
    approvals_path: str = Field(min_length=1)
    kinds: list[Literal['vendor', 'correspondence']] = Field(min_length=1, max_length=2)


def open_public_jobs(db_path, config_path):
    config = load_private(config_path, PublicProposalConfig)
    executable = Path(config.executable)
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError('Select the existing absolute Claude Code executable.')
    if len(set(config.kinds)) != len(config.kinds):
        raise ValueError('Configure each proposal kind once.')
    approval_path = _protected_path(config.approvals_path)
    load_approvals(approval_path)
    providers = {}
    for kind in config.kinds:
        if kind == 'vendor':
            from .vendor_model_jobs import build_vendor_provider
            providers[kind] = build_vendor_provider(str(executable))
        else:
            providers[kind] = SafePublicClaude(str(executable), model=MODEL, system=BLOCK_SYSTEM)
    return PublicProposalJobs(db_path, approval_path, providers)
