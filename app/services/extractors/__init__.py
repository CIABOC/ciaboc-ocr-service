from app.services.extractors.base_extractor import BaseExtractor
from app.services.extractors.nic_extractor import NICExtractor
from app.services.extractors.passport_extractor import PassportExtractor
from app.services.extractors.driving_licence_extractor import DrivingLicenceExtractor

__all__ = [
    "BaseExtractor",
    "NICExtractor",
    "PassportExtractor",
    "DrivingLicenceExtractor",
]
