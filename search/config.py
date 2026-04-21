import os
from pathlib import Path
from attr import dataclass
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

# from .logger_setup import logger
import logging
logger = logging.getLogger(__name__)
from dotenv import load_dotenv

# Project root directory
BASE_DIR = Path(__file__).resolve().parent.parent
shared_config = SettingsConfigDict(
    env_file=BASE_DIR / ".env", 
    env_file_encoding="utf-8",
    extra="ignore"
)
load_dotenv(BASE_DIR / ".env")

# class DatabaseConfig(BaseModel):
#     """Defines the database configuration settings."""
#     dbname: str = Field(alias='DB_NAME',default='news_rag')
#     user: str = Field(alias='DB_USER', default='postgres')
#     password: str = Field(alias='DB_PASSWORD', default='newsrag')
#     host: str = Field(alias='DB_HOST',default='localhost')
#     port: int = Field(alias='DB_PORT', default=5432)
    
#     @property
#     def dbs_url(self) -> str:
#         """Constructs the database URL from the configuration."""
#         return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"

class ModelConfig(BaseSettings):
    """Defines the model configuration settings."""
    model_config = shared_config
    embedding: str = Field(alias='EMBEDDING_MODEL', default='BAAI/bge-m3')
    reranking: str = Field(alias='RERANKING_MODEL', default='BAAI/bge-reranker-v2-m3')
    sparse :str = Field(alias='SPARSE_MODEL', default='prithivida/Splade_PP_en_v1')
    embedding_size: int = Field(alias='EMBEDDING_SIZE', default=1024)

    top_k: int = Field(alias='TOP_K', default=50)
    top_k_rerank: int = Field(alias='TOP_K_RERANK', default=5)

class LLMInstanceConfig(BaseModel):
    """Defines the configuration for a specific LLM instance."""
    provider: str
    model_id: str
    name: str
    temperature: float = 0.0
    max_tokens: int
    api_key: str = None
    base_url: str = None

class LLMConfig(BaseSettings):
    """Defines the LLM configuration settings."""
    model_config = shared_config
    default_temperature: float = Field(alias='LLM_TEMPERATURE', default=0.1)
    max_tokens: int = Field(alias='LLM_MAX_TOKENS', default=2048)
    num_models: int = Field(alias='NUM_MODEL_SUPPORT', default=1)
    instances: list[LLMInstanceConfig] = []

    @model_validator(mode='after')
    def populate_instances(self) -> 'LLMConfig':
        """
        Dynamically populates the list of LLM instances based on the number specified in the environment variables.
        It reads the configuration for each instance (up to num_instances) and creates LLMInstance
        """
        temp_instances = []
        for i in range(1, self.num_models + 1):
            # Đọc dữ liệu động dựa trên số thứ tự i
            name = os.getenv(f'MODEL_{i}_NAME')
            provider = os.getenv(f'MODEL_{i}_PROVIDER').strip()
            model_id = os.getenv(f'MODEL_{i}_MODEL_ID').strip()
            api_key = os.getenv(f'MODEL_{i}_API_KEY').strip() or None
            base_url = os.getenv(f'MODEL_{i}_BASE_URL', None) or None

            # Lấy temperature riêng, nếu không có thì dùng default_temperature
            raw_temp = os.getenv(f'MODEL_{i}_TEMPERATURE')
            temp = float(raw_temp) if raw_temp else self.default_temperature

            max_tokens = int(os.getenv(f'MODEL_{i}_MAX_TOKENS', self.max_tokens))
            base_url = os.getenv(f'MODEL_{i}_BASE_URL', '')

            # Chỉ nạp nếu có đủ thông tin cốt lõi
            if name and provider and model_id:
                instance = LLMInstanceConfig(
                    name=name,
                    provider=provider.lower(),
                    model_id=model_id,
                    api_key=api_key,
                    base_url=base_url,
                    temperature=temp,
                    max_tokens=max_tokens
                )
                temp_instances.append(instance)
            else:
                # Log cảnh báo nếu config trong .env bị thiếu
                logger.warning(f"MODEL_{i} configuration is incomplete. Skipping this instance. Required fields: NAME, PROVIDER, MODEL_ID.")

        self.instances = temp_instances
        return self

class SearchConfig(BaseSettings):
    """Defines the search configuration settings."""
    model_config = shared_config
    host: str = Field(alias='QDRANT_HOST', default='localhost')
    port: int = Field(alias='QDRANT_PORT', default=6333)
    api_key: str = Field(alias='QDRANT_API_KEY', default='')
    grpc_port: int = Field(alias='QDRANT_GRPC_PORT', default=6334)
    collection_name: str = Field(alias='QDRANT_COLLECTION_NAME', default='news_chunks')

    @property
    def qdrant_url(self) -> str:
        """Constructs the Qdrant URL from the host and port."""
        protocol = "https" if ".cloud.qdrant.io" in self.host else "http"
        return f"{protocol}://{self.host}"

class Settings(BaseSettings):
    """Defines the main settings for the search configuration."""

    model_config=shared_config
    # database: DatabaseConfig = DatabaseConfig()
    search: SearchConfig = SearchConfig()
    model: ModelConfig = ModelConfig()
    llm: LLMConfig = LLMConfig()

# Singleton instance of the settings
settings = Settings()