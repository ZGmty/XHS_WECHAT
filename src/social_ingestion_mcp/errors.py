class SocialIngestionError(Exception):
    code = "social_ingestion_error"


class ConfigError(SocialIngestionError):
    code = "config_error"


class DependencyNotAvailableError(SocialIngestionError):
    code = "dependency_not_available"


class NetworkTimeoutError(SocialIngestionError):
    code = "network_timeout"


class AntiScrapingBlockedError(SocialIngestionError):
    code = "anti_scraping_blocked"


class RpaFocusLostError(SocialIngestionError):
    code = "rpa_focus_lost"


class UpstreamServiceError(SocialIngestionError):
    code = "upstream_service_error"


class JobNotFoundError(SocialIngestionError):
    code = "job_not_found"