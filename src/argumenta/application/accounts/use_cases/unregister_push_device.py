import uuid
from dataclasses import dataclass

from argumenta.application.accounts.ports import PushDeviceRepository


@dataclass(frozen=True)
class UnregisterPushDevice:
    user_id: uuid.UUID
    token: str


class UnregisterPushDeviceUseCase:
    def __init__(self, devices: PushDeviceRepository) -> None:
        self._devices = devices

    def execute(self, command: UnregisterPushDevice) -> None:
        self._devices.unregister(command.user_id, command.token)
