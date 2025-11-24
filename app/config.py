# app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ✅ wszystkie pola mają typy (str)

    # Baza – w katalogu ./data, idealna pod volume Dockera
    DATABASE_URL: str = "sqlite:///./data/pc_manager.db"

    # Hasło do zmiany statusów (Zarządzany/Znaleziony/Wyjątek) – z .env
    ADMIN_TOGGLE_PASSWORD: str

    # Podsieci do skanowania – możesz zmienić na swoją
    NETWORKS: str = "192.168.1.0/24"

    # Dane do WinRM – z .env, bez wartości domyślnych
    WINRM_USER: str
    WINRM_PASSWORD: str

    class Config:
        env_file = ".env"


settings = Settings()
