"""Faker-based seed data for employees, historical projects, and approved technologies."""

from faker import Faker
from sqlalchemy.orm import Session

from app.config import settings
from app.models.employee import Employee, EmployeeSkill, Skill
from app.models.reference import ApprovedTechnology, HistoricalProject

_SENIORITY_LEVELS = ["Junior", "Mid", "Senior", "Lead", "Principal"]
_DOMAINS = ["fintech", "healthtech", "edtech", "ecommerce", "logistics", "saas", "iot"]

_SEED_SKILLS = [
    # Programming languages
    ("Python", "programming"), ("JavaScript", "programming"), ("TypeScript", "programming"),
    ("Go", "programming"), ("Rust", "programming"), ("Java", "programming"),
    ("Ruby", "programming"), ("PHP", "programming"), ("C#", "programming"),
    ("Kotlin", "programming"), ("Elixir", "programming"),
    # Frontend frameworks & tools
    ("React", "frontend"), ("Next.js", "frontend"), ("Vue.js", "frontend"),
    ("Nuxt.js", "frontend"), ("Svelte", "frontend"), ("SvelteKit", "frontend"),
    ("SolidJS", "frontend"), ("Astro", "frontend"), ("Remix", "frontend"),
    ("TanStack Query", "frontend"), ("Zustand", "frontend"), ("Redux Toolkit", "frontend"),
    ("Shadcn UI", "frontend"), ("Tailwind CSS", "frontend"), ("Framer Motion", "frontend"),
    ("Vite", "frontend"), ("Turbopack", "frontend"), ("Playwright", "frontend"),
    ("Vitest", "frontend"), ("Storybook", "frontend"), ("htmx", "frontend"),
    ("Radix UI", "frontend"), ("Three.js", "frontend"),
    # Backend frameworks & tools
    ("FastAPI", "framework"), ("Django", "framework"), ("Node.js", "framework"),
    ("Express.js", "framework"), ("NestJS", "framework"), ("Spring Boot", "framework"),
    ("Ruby on Rails", "framework"), ("Laravel", "framework"), ("Flask", "framework"),
    ("Phoenix", "framework"), ("Fiber", "framework"), ("Actix Web", "framework"),
    ("Axum", "framework"), ("Bun", "framework"), ("Deno", "framework"),
    ("Apollo Server", "framework"), ("gRPC", "framework"), ("tRPC", "framework"),
    ("AdonisJS", "framework"), ("Hono", "framework"), ("Gin", "framework"),
    ("ASP.NET Core", "framework"), ("Ktor", "framework"),
    # Databases & ORMs
    ("PostgreSQL", "database"), ("SQLite", "database"), ("MongoDB", "database"),
    ("Redis", "database"), ("MySQL", "database"), ("Elasticsearch", "database"),
    ("Supabase", "database"), ("Prisma", "database"), ("Drizzle ORM", "database"),
    ("DynamoDB", "database"), ("Cassandra", "database"), ("ClickHouse", "database"),
    ("Neo4j", "database"), ("SurrealDB", "database"), ("Turso", "database"),
    ("Firestore", "database"), ("PlanetScale", "database"), ("CockroachDB", "database"),
    ("Meilisearch", "database"), ("InfluxDB", "database"), ("ScyllaDB", "database"),
    ("DuckDB", "database"), ("TimescaleDB", "database"), ("KeyDB", "database"),
    ("SQL", "database"),
    # DevOps & Infra
    ("Docker", "devops"), ("Kubernetes", "devops"), ("Terraform", "devops"),
    ("AWS", "devops"), ("AWS Lambda", "devops"), ("Railway", "devops"),
    ("Vercel", "devops"), ("Netlify", "devops"), ("GitHub Actions", "devops"),
    ("Ansible", "devops"), ("Pulumi", "devops"), ("Helm", "devops"),
    ("ArgoCD", "devops"), ("Prometheus", "devops"), ("Grafana", "devops"),
    ("Nginx", "devops"), ("Cloudflare Workers", "devops"), ("Podman", "devops"),
    ("Traefik", "devops"), ("OpenTelemetry", "devops"), ("LocalStack", "devops"),
    ("Fly.io", "devops"), ("CircleCI", "devops"), ("MinIO", "devops"),
    ("Envoy Proxy", "devops"),
    # AI / ML
    ("LangChain", "ai"), ("ChromaDB", "ai"), ("LlamaIndex", "ai"),
    ("Pinecone", "ai"), ("Milvus", "ai"), ("Qdrant", "ai"),
    ("Hugging Face", "ai"), ("Ollama", "ai"), ("vLLM", "ai"),
    ("CrewAI", "ai"), ("AutoGen", "ai"), ("LangGraph", "ai"),
    ("OpenAI API", "ai"), ("Anthropic SDK", "ai"), ("Groq", "ai"),
    ("Weaviate", "ai"), ("LangSmith", "ai"), ("LiteLLM", "ai"),
    ("Instructor", "ai"), ("DSPy", "ai"), ("Semantic Kernel", "ai"),
    ("Phidata", "ai"),
    # Design & other
    ("Figma", "design"), ("SQL", "database"),
]

_APPROVED_TECHS = [
    # (name, category, tags)
    # ── Frontend ──────────────────────────────────────────────────────────────
    ("Next.js",         "frontend", "SPA,SSR,TypeScript-first,prototyping,production"),
    ("React",           "frontend", "SPA,component-library,flexible,prototyping,production"),
    ("Vue.js",          "frontend", "SPA,lightweight,progressive,prototyping"),
    ("TypeScript",      "frontend", "typed,compile-time-safety,large-team"),
    ("Tailwind CSS",    "frontend", "utility-CSS,rapid-prototyping,design-system"),
    ("Nuxt.js",         "frontend", "SSR,Vue-based,meta-framework,prototyping,production"),
    ("Svelte",          "frontend", "SPA,compiler-based,lightweight,prototyping"),
    ("SvelteKit",       "frontend", "SSR,Svelte,meta-framework,prototyping,production"),
    ("SolidJS",         "frontend", "SPA,reactive,high-performance,prototyping"),
    ("Astro",           "frontend", "SSG,multi-framework,content-driven,production"),
    ("Remix",           "frontend", "SSR,React,data-focused,production"),
    ("TanStack Query",  "frontend", "async-state,data-fetching,React,TypeScript"),
    ("Zustand",         "frontend", "state-management,minimalist,React"),
    ("Redux Toolkit",   "frontend", "state-management,Redux,React,large-team"),
    ("Shadcn UI",       "frontend", "component-library,Tailwind,accessible,design-system"),
    ("Framer Motion",   "frontend", "animation,React,production"),
    ("Vite",            "frontend", "bundler,fast,tooling,prototyping,production"),
    ("Turbopack",       "frontend", "bundler,incremental,Webpack,large-team"),
    ("Playwright",      "frontend", "E2E-testing,automation,cross-browser"),
    ("Vitest",          "frontend", "unit-testing,fast,Vite-native"),
    ("Storybook",       "frontend", "component-dev,documentation,design-system"),
    ("htmx",            "frontend", "AJAX,hypermedia,lightweight,prototyping"),
    ("Radix UI",        "frontend", "accessible,unstyled,component-primitives"),
    ("Three.js",        "frontend", "3D,WebGL,graphics,visualization"),
    ("Pnpm",            "frontend", "package-manager,fast,disk-efficient"),
    # ── Backend ───────────────────────────────────────────────────────────────
    ("FastAPI",         "backend",  "REST,async,Python,ML-friendly,prototyping,production"),
    ("Django",          "backend",  "REST,batteries-included,ORM,Python,high-scale"),
    ("Node.js",         "backend",  "REST,event-driven,JavaScript,high-scale"),
    ("Go",              "backend",  "REST,high-performance,compiled,high-scale"),
    ("Rust",            "backend",  "systems,high-performance,compiled,high-scale"),
    ("Express.js",      "backend",  "REST,Node.js,minimalist,prototyping,production"),
    ("NestJS",          "backend",  "REST,Node.js,TypeScript,enterprise,production"),
    ("Spring Boot",     "backend",  "REST,Java,enterprise,high-scale,production"),
    ("Ruby on Rails",   "backend",  "REST,Ruby,MVC,convention-over-configuration,production"),
    ("Laravel",         "backend",  "REST,PHP,MVC,full-stack,production"),
    ("Flask",           "backend",  "REST,Python,lightweight,prototyping"),
    ("Phoenix",         "backend",  "REST,Elixir,functional,high-concurrency,real-time,production"),
    ("Fiber",           "backend",  "REST,Go,high-performance,prototyping,production"),
    ("Actix Web",       "backend",  "REST,Rust,high-performance,production"),
    ("Axum",            "backend",  "REST,Rust,modular,production"),
    ("Bun",             "backend",  "JavaScript,TypeScript,runtime,all-in-one,fast"),
    ("Deno",            "backend",  "JavaScript,TypeScript,secure,runtime"),
    ("Apollo Server",   "backend",  "GraphQL,Node.js,API,production"),
    ("gRPC",            "backend",  "RPC,high-performance,microservices,production"),
    ("tRPC",            "backend",  "TypeScript,end-to-end-typesafe,Node.js,prototyping"),
    ("AdonisJS",        "backend",  "REST,TypeScript,Node.js,full-stack,production"),
    ("Hono",            "backend",  "REST,edge,lightweight,fast,TypeScript"),
    ("Gin",             "backend",  "REST,Go,high-performance,prototyping,production"),
    ("ASP.NET Core",    "backend",  "REST,C#,Microsoft,cross-platform,enterprise,production"),
    ("Ktor",            "backend",  "REST,Kotlin,async,JVM,production"),
    # ── Database ──────────────────────────────────────────────────────────────
    ("PostgreSQL",      "database", "relational,ACID,production,high-scale"),
    ("SQLite",          "database", "relational,embedded,prototyping,low-scale"),
    ("MongoDB",         "database", "NoSQL,flexible-schema,document-store,high-scale"),
    ("Redis",           "database", "cache,pub-sub,session-store,high-scale"),
    ("Elasticsearch",   "database", "search,full-text,analytics,high-scale"),
    ("MySQL",           "database", "relational,ACID,production,high-scale"),
    ("Supabase",        "database", "relational,BaaS,real-time,prototyping,production"),
    ("Prisma",          "database", "ORM,TypeScript,Node.js,relational"),
    ("Drizzle ORM",     "database", "ORM,TypeScript,lightweight,performance"),
    ("DynamoDB",        "database", "NoSQL,AWS,managed,high-scale,serverless"),
    ("Cassandra",       "database", "NoSQL,distributed,high-scale,write-heavy"),
    ("ClickHouse",      "database", "OLAP,analytics,columnar,high-scale"),
    ("Neo4j",           "database", "graph,native,analytics,production"),
    ("SurrealDB",       "database", "multi-model,cloud-native,flexible,prototyping"),
    ("Turso",           "database", "SQLite,edge,distributed,low-latency"),
    ("Firestore",       "database", "NoSQL,BaaS,real-time,prototyping,Google"),
    ("PlanetScale",     "database", "MySQL,serverless,branching,production"),
    ("CockroachDB",     "database", "distributed-SQL,ACID,cloud-native,high-scale"),
    ("Meilisearch",     "database", "search,full-text,lightweight,prototyping,production"),
    ("InfluxDB",        "database", "time-series,metrics,analytics,production"),
    ("ScyllaDB",        "database", "NoSQL,high-performance,low-latency,high-scale"),
    ("DuckDB",          "database", "OLAP,analytical,in-process,embedded"),
    ("TimescaleDB",     "database", "time-series,PostgreSQL,SQL,production"),
    ("KeyDB",           "database", "cache,Redis-compatible,multithreaded,high-performance"),
    ("TigerGraph",      "database", "graph,analytics,enterprise,high-scale"),
    # ── Infra ─────────────────────────────────────────────────────────────────
    ("Docker",                  "infra", "containerization,local-dev,portable"),
    ("Kubernetes",              "infra", "orchestration,high-scale,complex-ops,production"),
    ("Railway",                 "infra", "PaaS,simple-deploy,low-ops,prototyping"),
    ("AWS Lambda",              "infra", "serverless,event-driven,high-scale,pay-per-use"),
    ("Terraform",               "infra", "IaC,cloud-provisioning,production"),
    ("Vercel",                  "infra", "PaaS,frontend,serverless,CDN,production"),
    ("Netlify",                 "infra", "PaaS,frontend,JAMstack,CDN,prototyping"),
    ("GitHub Actions",          "infra", "CI/CD,automation,workflows,DevOps"),
    ("Ansible",                 "infra", "configuration-management,automation,IaC"),
    ("Pulumi",                  "infra", "IaC,multi-language,cloud-provisioning,production"),
    ("Helm",                    "infra", "Kubernetes,package-manager,templating,production"),
    ("ArgoCD",                  "infra", "GitOps,Kubernetes,CD,production"),
    ("Prometheus",              "infra", "monitoring,alerting,metrics,production"),
    ("Grafana",                 "infra", "visualization,dashboards,observability,production"),
    ("Nginx",                   "infra", "web-server,reverse-proxy,load-balancer,production"),
    ("Cloudflare Workers",      "infra", "edge,serverless,CDN,low-latency,production"),
    ("Podman",                  "infra", "containers,daemonless,OCI,local-dev"),
    ("Traefik",                 "infra", "reverse-proxy,load-balancer,cloud-native,production"),
    ("OpenTelemetry",           "infra", "observability,tracing,metrics,cloud-native"),
    ("LocalStack",              "infra", "AWS,local-dev,testing,simulation"),
    ("Supabase Self-Hosted",    "infra", "BaaS,open-source,self-hosted,prototyping"),
    ("Fly.io",                  "infra", "PaaS,edge-deploy,low-latency,production"),
    ("CircleCI",                "infra", "CI/CD,managed,automation,DevOps"),
    ("MinIO",                   "infra", "object-storage,S3-compatible,self-hosted,production"),
    ("Envoy Proxy",             "infra", "service-proxy,edge,load-balancer,microservices,production"),
    # ── AI ────────────────────────────────────────────────────────────────────
    ("LangChain",           "ai", "LLM-orchestration,RAG,agents,Python"),
    ("ChromaDB",            "ai", "vector-store,embeddings,RAG,local-dev"),
    ("LlamaIndex",          "ai", "RAG,LLM,data-framework,Python,production"),
    ("Pinecone",            "ai", "vector-store,managed,cloud,high-scale"),
    ("Milvus",              "ai", "vector-store,open-source,high-scale,enterprise"),
    ("Qdrant",              "ai", "vector-store,Rust,high-performance,production"),
    ("Hugging Face",        "ai", "ML-models,NLP,fine-tuning,research,production"),
    ("Ollama",              "ai", "local-LLM,open-source,inference,prototyping"),
    ("vLLM",                "ai", "LLM-serving,high-throughput,production"),
    ("CrewAI",              "ai", "multi-agent,orchestration,Python,production"),
    ("AutoGen",             "ai", "multi-agent,Microsoft,conversation,research"),
    ("LangGraph",           "ai", "LLM-orchestration,stateful,agents,Python"),
    ("OpenAI API",          "ai", "LLM,GPT,API,production"),
    ("Anthropic SDK",       "ai", "LLM,Claude,API,production"),
    ("Groq",                "ai", "inference,LPU,ultra-fast,production"),
    ("Weaviate",            "ai", "vector-store,open-source,semantic-search,production"),
    ("LangSmith",           "ai", "LLM-observability,debugging,testing,production"),
    ("LiteLLM",             "ai", "LLM-proxy,multi-provider,OpenAI-compatible,production"),
    ("Instructor",          "ai", "structured-output,Pydantic,LLM,Python"),
    ("DSPy",                "ai", "LLM-programming,optimization,Stanford,research"),
    ("Semantic Kernel",     "ai", "LLM-SDK,Microsoft,multi-language,production"),
    ("Phidata",             "ai", "AI-assistants,memory,knowledge,tools,Python"),
]


def _ensure_skills(db: Session, fake: Faker) -> list[Skill]:
    existing = {s.name: s for s in db.query(Skill).all()}
    for name, cat in _SEED_SKILLS:
        if name not in existing:
            skill = Skill(name=name, category=cat)
            db.add(skill)
            existing[name] = skill
    db.flush()
    return list(existing.values())


def seed_employees(db: Session, count: int | None = None) -> int:
    if count is None:
        count = settings.seed_employee_count
    fake = Faker()
    fake.seed_instance(settings.faker_seed)
    skills = _ensure_skills(db, fake)
    existing_emails = {e.email for e in db.query(Employee.email).all()}
    seeded = 0
    for _ in range(count):
        name = fake.name()
        email = fake.unique.email()
        seniority = fake.random_element(_SENIORITY_LEVELS)
        availability_pct = fake.random_element([50, 75, 100])
        joined_at = fake.date_time_between(start_date="-3y", end_date="now")
        status = fake.random_element(["active"] * 17 + ["inactive"] * 3)
        num = fake.random_int(min=2, max=5)
        chosen = fake.random_elements(skills, length=min(num, len(skills)), unique=True)
        if email in existing_emails:
            continue
        emp = Employee(
            name=name, email=email, seniority=seniority,
            availability_pct=availability_pct, joined_at=joined_at, status=status,
        )
        db.add(emp)
        db.flush()
        for skill in chosen:
            db.add(EmployeeSkill(employee_id=emp.id, skill_id=skill.id))
        seeded += 1
    db.commit()
    return seeded


def seed_projects(db: Session, count: int | None = None) -> int:
    if count is None:
        count = settings.seed_project_count
    fake = Faker()
    fake.seed_instance(settings.faker_seed)
    seeded = 0
    for _ in range(count):
        db.add(HistoricalProject(
            name=fake.bs().title(),
            domain=fake.random_element(_DOMAINS),
            estimated_points=fake.random_int(min=20, max=150),
            actual_points=fake.random_int(min=20, max=200),
            duration_weeks=round(fake.pyfloat(min_value=2.0, max_value=24.0, right_digits=1), 1),
            team_size=fake.random_int(min=2, max=10),
        ))
        seeded += 1
    db.commit()
    return seeded


def seed_technologies(db: Session, count: int | None = None) -> int:
    seeded = 0
    techs = _APPROVED_TECHS if count is None else _APPROVED_TECHS[:count]
    for name, category, tags in techs:
        existing = db.query(ApprovedTechnology).filter(ApprovedTechnology.name == name).first()
        if existing:
            existing.tags = tags
        else:
            db.add(ApprovedTechnology(name=name, category=category, tags=tags))
        seeded += 1
    db.commit()
    return seeded
