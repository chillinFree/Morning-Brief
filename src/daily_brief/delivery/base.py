from __future__ import annotations

from abc import ABC, abstractmethod

from daily_brief.models.digest import Digest


class EmailSender(ABC):
    @abstractmethod
    def send(self, digest: Digest) -> str:
        raise NotImplementedError

    def preview(self, digest: Digest) -> str | None:
        return None
