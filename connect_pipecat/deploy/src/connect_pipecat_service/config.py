from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    odoo_url: str = Field(alias='ODOO_URL')
    pipecat_service_token: str = Field(alias='PIPECAT_SERVICE_TOKEN', min_length=24)
    host: str = Field(default='0.0.0.0', alias='HOST')
    port: int = Field(default=7860, alias='PORT')
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')


settings = ServiceSettings()
