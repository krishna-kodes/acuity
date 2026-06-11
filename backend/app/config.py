import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

# Generated once per server process — unknown to attackers during a session.
# Override with PROMPT_CANARY_TOKEN in .env for persistence across restarts.
_RUNTIME_CANARY = secrets.token_hex(10)


class Settings(BaseSettings):
    main_llm_provider: str = "openai"
    main_llm_model: str = "gpt-5.4-mini"
    fast_llm_provider: str = "openai"
    fast_llm_model: str = "gpt-5.4-nano"
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
    # Branding defaults (overridden by DB row in branding_settings)
    branding_company_name: str = ""
    branding_primary_color: str = "#2E5FA3"
    branding_secondary_color: str = "#1A3A6B"
    branding_prepared_by: str = ""
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

    groundedness_check_enabled: bool = False
    groundedness_threshold: float = 0.7
    
    domain_classifier_enabled: bool = True
    domain_classifier_confidence_threshold: float = 0.85

    prompt_injection_detection_enabled: bool = True
    injection_llm_confidence_threshold: float = 0.80
    prompt_canary_token: str = _RUNTIME_CANARY
    output_monitor_enabled: bool = True
    retrieval_gate_enabled: bool = False
    retrieval_confidence_threshold: float = 0.2
    
    max_cost_per_workflow_usd: float = 0.50
    observability_provider: str = "langsmith"
    langsmith_api_key: str = ""
    faker_seed: int = 42
    seed_employee_count: int = 20
    seed_project_count: int = 15
    seed_technology_count: int = 22
    metrics_enabled: bool = True
    cost_per_1k_input_tokens: float = 0.0015
    cost_per_1k_output_tokens: float = 0.002

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")


settings = Settings()
