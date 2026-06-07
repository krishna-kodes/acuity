from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    main_llm_provider: str = "google"
    main_llm_model: str = "gemini-1.5-pro"
    fast_llm_provider: str = "google"
    fast_llm_model: str = "gemini-1.5-flash"
    temperature: float = 0.2
    openai_api_key: str = ""
    google_api_key: str = ""
    anthropic_api_key: str = ""
    github_token: str = ""
    github_owner: str = ""
    github_repo: str = ""
    github_use_projects_v2: bool = False
    sync_provider: str = "github"
    jira_url: str = ""
    jira_username: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""
    embedding_dimensions: int = 1536
    chroma_persist_path: str = "./chroma_db"
    pii_encryption_key: str = ""
    pii_detection_enabled: bool = True
    pii_regex_enabled: bool = True
    pii_ner_enabled: bool = True
    pii_review_gate: bool = True
    chunk_size_max_tokens: int = 800
    chunk_size_min_tokens: int = 50
    top_k_retrieval: int = 20
    top_n_rerank: int = 4
    query_rewrite_count: int = 3
    groundedness_check_enabled: bool = True
    groundedness_threshold: float = 0.7
    max_cost_per_workflow_usd: float = 0.50
    observability_provider: str = "langsmith"
    langsmith_api_key: str = ""
    faker_seed: int = 42
    seed_employee_count: int = 20
    seed_project_count: int = 15
    seed_technology_count: int = 22
    metrics_enabled: bool = True

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


settings = Settings()
