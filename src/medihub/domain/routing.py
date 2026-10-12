"""Durable, non-clinical routing decisions."""

from .base import DomainModel, NonEmptyText
from .delivery import SafeErrorCode


class BlockedRoute(DomainModel):
    """A route held by policy, represented only by a destination and safe code."""

    destination_id: NonEmptyText
    reason_code: SafeErrorCode
