# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # Baza – w katalogu ./data, idealna pod volume Dockera
    DATABASE_URL: str = "sqlite:///./data/pc_manager.db"

    # Hasło do operacji administracyjnych (status + ręczne wyłączanie + skanowanie)
    ADMIN_TOGGLE_PASSWORD: Optional[str] = None

    # Podsieci do skanowania – rozdzielane średnikiem
    # Np: "192.168.1.0/24;192.168.2.0/24"
    NETWORKS: str = "192.168.1.0/24"

    # Konto do WinRM
    WINRM_USER: Optional[str] = None
    WINRM_PASSWORD: Optional[str] = None

    # Żeby nie przeszkadzała zmienna środowiskowa tz / TZ (np. Europe/Warsaw)
    tz: Optional[str] = None
    TZ: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
