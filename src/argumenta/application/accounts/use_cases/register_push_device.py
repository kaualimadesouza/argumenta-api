import uuid
from dataclasses import dataclass

from argumenta.application.accounts.ports import PushDeviceRepository
from argumenta.domain.enums import DevicePlatform


@dataclass(frozen=True)
class RegisterPushDevice:
    user_id: uuid.UUID
    platform: DevicePlatform
    token: str


class RegisterPushDeviceUseCase:
    def __init__(self, devices: PushDeviceRepository) -> None:
        self._devices = devices

    def execute(self, command: RegisterPushDevice) -> None:
        self._devices.register(command.user_id, command.platform, command.token)
