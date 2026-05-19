"""
Capture Layer — Fake signal generator for demo/development.

Generates hundreds of realistic signals by combining company-specific data
with signal type templates. In production, each source (LinkedIn, RSS,
Crunchbase, job boards) would be a separate module.
"""

import json
import random
from datetime import datetime, timedelta

# ─── Company knowledge base ──────────────────────────────────────────────────
# Each company has people, products, partners, events, etc. to make signals realistic.

COMPANY_DATA = {
    "Databricks": {
        "sector": "Data & AI Infrastructure",
        "people": [
            ("Sophie Marchand", "Country Manager France", "Snowflake"),
            ("Jean-Baptiste Léon", "VP Engineering EMEA", "Google Cloud"),
            ("Amira Benali", "Head of AI Research", "Meta"),
            ("Thomas Girard", "Chief Revenue Officer", "Confluent"),
            ("Nadia Rousseau", "VP Customer Success EMEA", "Salesforce"),
        ],
        "products": [
            ("Mosaic AI Gateway", "GenAI / MLOps", "orchestration multi-LLM pour l'entreprise"),
            ("Unity Catalog 2.0", "Data Governance", "gouvernance unifiée données + modèles IA"),
            ("Delta Lake 4.0", "Data Engineering", "stockage lakehouse nouvelle génération avec support temps réel"),
            ("Databricks Assistant Pro", "GenAI", "copilote IA pour data engineers et analystes"),
            ("LakeFlow Connect", "Data Integration", "ingestion de données en temps réel sans code"),
        ],
        "partners": ["Microsoft Azure", "AWS", "Google Cloud", "dbt Labs", "Fivetran", "Confluent"],
        "events": ["Snowflake Summit", "VivaTech", "Google Cloud Next", "AWS re:Invent"],
        "locations": ["Paris", "Amsterdam", "Londres", "Berlin"],
        "hiring_roles": ["Solutions Architect", "Field Engineer", "Account Executive", "Data Engineer", "ML Engineer"],
        "media_topics": [
            "investit 500M$ dans l'IA générative open source",
            "dépasse les 2Md$ de revenus annuels récurrents",
            "ouvre un centre R&D à Paris avec 200 ingénieurs",
            "classé leader du Magic Quadrant Data & Analytics",
        ],
        "funding_info": [
            ("500M$", "Série I", "43Md$", ["a16z", "T. Rowe Price"]),
        ],
    },
    "Mistral AI": {
        "sector": "IA Générative",
        "people": [
            ("Arthur Mensch", "CEO", "DeepMind"),
            ("Guillaume Lample", "Chief Scientist", "Meta FAIR"),
            ("Timothée Lacroix", "CTO", "Meta FAIR"),
            ("Marie Pellat", "VP Business Development", "Google DeepMind"),
            ("Éric Moulines", "Head of Safety & Alignment", "CNRS / ENS"),
            ("Sophia Chen", "VP Engineering", "OpenAI"),
            ("Laurent Dupont", "Country Director France", "Anthropic"),
        ],
        "products": [
            ("Mistral Large 3", "LLM", "modèle flagship multimodal avec raisonnement avancé"),
            ("Le Chat Enterprise", "ChatBot B2B", "assistant IA pour entreprises avec déploiement souverain"),
            ("Mistral Codestral 2.0", "Code Generation", "modèle de génération de code surpassant GPT-4 sur les benchmarks"),
            ("Mistral Embed v2", "Embeddings", "modèle d'embeddings multilingue optimisé pour le RAG"),
            ("Mistral Guard", "AI Safety", "garde-fou IA pour filtrage de contenu et conformité"),
            ("La Plateforme 2.0", "API Platform", "plateforme API avec fine-tuning et RAG intégrés"),
        ],
        "partners": ["OVHcloud", "Scaleway", "Microsoft Azure", "Orange Business", "Thales", "BNP Paribas"],
        "events": ["VivaTech", "AI Paris", "Web Summit", "Station F Demo Day", "NeurIPS"],
        "locations": ["Paris", "Londres", "San Francisco"],
        "hiring_roles": ["Research Scientist", "ML Engineer", "Solutions Engineer", "Account Executive", "Go-to-market"],
        "media_topics": [
            "valorisée à 6Md€ après sa dernière levée",
            "signe un contrat cadre avec l'État français pour l'IA souveraine",
            "atteint 1 million d'utilisateurs sur Le Chat",
            "surpasse GPT-4 sur les benchmarks MMLU et HumanEval",
            "ouvre son premier bureau à Tokyo pour l'expansion Asie",
        ],
        "funding_info": [
            ("600M€", "Série B", "6Md€", ["a16z", "Lightspeed"]),
            ("400M€", "Série B extension", "6.5Md€", ["Samsung", "NVIDIA"]),
        ],
    },
    "Snowflake": {
        "sector": "Cloud Data Platform",
        "people": [
            ("Sridhar Ramaswamy", "CEO", "Google"),
            ("Marc Dupont", "Country Manager France", "Oracle"),
            ("Claire Fontaine", "VP Solutions Engineering EMEA", "Teradata"),
            ("Benoit Dageville", "Co-founder & President of Products", "Oracle"),
            ("Isabelle Martin", "Head of AI/ML", "Amazon"),
        ],
        "products": [
            ("Cortex Agents", "Agentic AI", "agents IA autonomes intégrés au Data Cloud"),
            ("Snowpark Container Services", "ML Platform", "déploiement de modèles ML dans Snowflake"),
            ("Arctic Embed 2.0", "Embeddings", "modèle d'embeddings open source pour la recherche sémantique"),
            ("Iceberg Tables GA", "Data Engineering", "tables Apache Iceberg natives dans Snowflake"),
            ("Horizon Governance Suite", "Data Governance", "suite complète de gouvernance et catalogage"),
            ("Dynamic Tables v2", "Data Engineering", "pipelines de données déclaratifs temps réel"),
        ],
        "partners": ["Salesforce", "ServiceNow", "Informatica", "Tableau", "Power BI", "Alation"],
        "events": ["Snowflake Summit", "AWS re:Invent", "Google Cloud Next", "Gartner Data & Analytics"],
        "locations": ["San Francisco", "Paris", "Londres", "Berlin", "Sydney"],
        "hiring_roles": ["Solutions Architect", "Sales Engineer", "Account Executive", "Data Cloud Advocate", "Product Manager"],
        "media_topics": [
            "annonce 15 000 participants pour le Snowflake Summit 2026",
            "acquiert une startup française de data observability pour 200M$",
            "dépasse les 3Md$ de product revenue",
            "lance un programme de certification IA gratuit avec 50 000 inscrits",
        ],
        "funding_info": [],
    },
    "Dataiku": {
        "sector": "MLOps & Data Science",
        "people": [
            ("Florian Douetteau", "CEO & Co-founder", "Exalead"),
            ("Clément Fournier", "VP EMEA Sales", "Palantir"),
            ("Clément Stenac", "CTO & Co-founder", "VideoLAN"),
            ("Julie Hervé", "VP Marketing", "Talend"),
            ("Karim Beguir", "Chief AI Officer", "InstaDeep"),
        ],
        "products": [
            ("LLM Mesh", "LLM Governance", "orchestration et gouvernance de multiples LLMs"),
            ("Dataiku 13", "Platform", "plateforme unifiée avec agents IA intégrés"),
            ("Govern 2.0", "AI Governance", "registre IA pour conformité EU AI Act"),
            ("Dataiku Answers", "GenAI", "Q&A augmenté par RAG pour utilisateurs métier"),
            ("Visual ML Pipelines 3.0", "AutoML", "création visuelle de pipelines ML sans code"),
        ],
        "partners": ["Snowflake", "Databricks", "AWS", "Google Cloud", "Palantir", "Informatica"],
        "events": ["VivaTech", "Gartner Data & Analytics", "AI Paris", "Strata Data Conference"],
        "locations": ["Paris", "New York", "Londres", "Singapour"],
        "hiring_roles": ["Solutions Engineer", "Data Scientist", "Account Executive", "Customer Success Manager", "Field CTO"],
        "media_topics": [
            "classé leader du Gartner Magic Quadrant ML & Data Science",
            "atteint 1000 clients enterprise dans le monde",
            "annonce un programme gratuit pour les universités françaises",
            "lève le voile sur sa stratégie d'IA agentique pour 2027",
        ],
        "funding_info": [
            ("200M$", "Série F", "3.7Md$", ["Wellington", "Tiger Global"]),
        ],
    },
    "Accenture": {
        "sector": "Conseil & Intégration",
        "people": [
            ("Julie Sweet", "CEO", "Accenture (interne)"),
            ("Philippe Vidal", "Managing Director France Data & AI", "McKinsey"),
            ("Laura Chen", "Global AI Lead", "Google"),
            ("Marc Lefèvre", "Lead Technology France", "Capgemini"),
            ("Sandrine Moreau", "Head of Industry X France", "Siemens"),
        ],
        "products": [
            ("Accenture AI Refinery", "GenAI Platform", "plateforme d'industrialisation GenAI pour grandes entreprises"),
            ("SynOps AI", "Intelligent Operations", "opérations intelligentes augmentées par l'IA"),
            ("myNav AI Estimator", "AI Assessment", "outil d'estimation de valeur des projets IA"),
            ("Data Mesh Accelerator", "Data Architecture", "accélérateur de déploiement Data Mesh"),
        ],
        "partners": ["Google Cloud", "Microsoft", "AWS", "Salesforce", "SAP", "ServiceNow", "Palantir"],
        "events": ["VivaTech", "Web Summit", "Davos", "CES", "Mobile World Congress"],
        "locations": ["Paris", "Nantes", "Lyon", "Toulouse", "Sophia Antipolis"],
        "hiring_roles": ["Data Engineer", "Data Scientist", "AI Consultant", "Cloud Architect", "Technology Strategist"],
        "media_topics": [
            "investit 3Md$ dans l'IA générative sur 3 ans",
            "double ses effectifs GenAI à 80 000 personnes mondial",
            "ouvre un AI Center of Excellence à Paris-La Défense",
            "annonce 1000 projets GenAI délivrés en entreprise",
            "forme 500 000 employés à l'IA générative",
        ],
        "funding_info": [],
    },
    "OVHcloud": {
        "sector": "Cloud souverain",
        "people": [
            ("Michel Paulin", "CEO", "SFR"),
            ("Thierry Souche", "CTO", "Criteo"),
            ("Yaniv Fdida", "Chief Product & Technology Officer", "Orange"),
            ("Béatrice Biron", "VP Sales France", "IBM"),
            ("Octave Klaba", "Chairman & Founder", "OVH"),
        ],
        "products": [
            ("AI Endpoints", "Managed AI APIs", "API managées pour modèles Mistral, Llama, Stable Diffusion"),
            ("AI Notebooks 2.0", "ML Development", "notebooks Jupyter managés avec GPU A100/H100"),
            ("Sovereign Shield", "Compliance", "offre SecNumCloud pour données sensibles"),
            ("Managed Kubernetes GPU", "Infrastructure", "clusters Kubernetes optimisés pour charges IA"),
            ("Data Platform S3-HA", "Storage", "stockage objet souverain haute disponibilité"),
        ],
        "partners": ["Mistral AI", "Scaleway", "Thales", "Atos", "Orange Business", "Sopra Steria"],
        "events": ["Cloud Expo Europe", "VivaTech", "FIC (Forum InCyber)", "Paris Open Source Summit"],
        "locations": ["Roubaix", "Paris", "Strasbourg", "Francfort"],
        "hiring_roles": ["Cloud Architect", "DevOps Engineer", "Solutions Architect", "Security Engineer", "AI Engineer"],
        "media_topics": [
            "obtient la qualification SecNumCloud pour ses services IA",
            "annonce un chiffre d'affaires cloud en hausse de 20%",
            "signe un partenariat majeur avec la DGFiP pour le cloud souverain",
            "lance un programme d'accélération pour startups IA françaises",
        ],
        "funding_info": [],
    },
    "Capgemini": {
        "sector": "Conseil & Intégration",
        "people": [
            ("Aiman Ezzat", "CEO", "Capgemini (interne)"),
            ("Pascal Brier", "Chief Innovation Officer", "Capgemini (interne)"),
            ("Zhiwei Jiang", "Global Head of AI & Analytics", "IBM"),
            ("Carole Ferrand", "CFO", "Worldline"),
            ("Jérôme Siméon", "Head of Insights & Data France", "Accenture"),
        ],
        "products": [
            ("Capgemini.ai", "AI Platform", "plateforme d'industrialisation IA end-to-end"),
            ("AI Garage", "Innovation Lab", "laboratoire d'expérimentation IA rapide"),
            ("Generative AI Lab", "GenAI", "accélérateur de projets GenAI pour entreprises"),
            ("Intelligent Automation Hub", "RPA + AI", "hub d'automatisation intelligente"),
        ],
        "partners": ["Google Cloud", "Microsoft", "AWS", "SAP", "Salesforce", "NVIDIA"],
        "events": ["VivaTech", "Google Cloud Next", "Microsoft Ignite", "SAP Sapphire"],
        "locations": ["Paris-La Défense", "Mumbai", "Londres", "Berlin", "Toulouse"],
        "hiring_roles": ["AI Engineer", "Data Architect", "Cloud Consultant", "Digital Transformation Lead", "UX Designer"],
        "media_topics": [
            "crée un Centre d'Excellence GenAI à Paris-La Défense",
            "annonce 5Md€ de revenus liés au cloud et données",
            "forme 150 000 collaborateurs à l'IA générative en 6 mois",
            "remporte le contrat de transformation data de la SNCF",
        ],
        "funding_info": [],
    },
    "Contentsquare": {
        "sector": "Analytics & IA",
        "people": [
            ("Jonathan Cherki", "CEO & Founder", "Contentsquare"),
            ("Laure Nègre", "Chief AI Officer", "Criteo"),
            ("Kat Borlongan", "Chief Impact Officer", "La French Tech"),
            ("Brendan Witcher", "VP Product Strategy", "Forrester"),
            ("Naomi Rosen", "VP Engineering", "Google"),
        ],
        "products": [
            ("AI Insights 3.0", "Analytics AI", "insights automatiques par IA sur l'expérience digitale"),
            ("Voice of Customer AI", "NLP", "analyse NLP des feedbacks clients en temps réel"),
            ("Digital Accessibility Checker", "Accessibility", "audit d'accessibilité web par IA"),
            ("Merchandising Optimizer", "E-commerce AI", "optimisation des parcours e-commerce par IA"),
        ],
        "partners": ["Adobe", "Salesforce", "Shopify", "Google Analytics", "Optimizely"],
        "events": ["VivaTech", "Shoptalk", "NRF", "Web Summit", "SXSW"],
        "locations": ["Paris", "New York", "Londres", "Tel Aviv", "Munich"],
        "hiring_roles": ["ML Engineer", "Data Scientist", "Product Manager AI", "Solutions Consultant", "Frontend Engineer"],
        "media_topics": [
            "annonce 800 clients enterprise dont 30% du CAC 40",
            "lève 600M$ en Série F, valorisée à 6Md$",
            "acquiert Heap Analytics pour 500M$ et consolide la digital analytics",
            "lance un programme certifiant gratuit 'DX Academy'",
        ],
        "funding_info": [
            ("600M$", "Série F", "6Md$", ["SoftBank", "BlackRock"]),
        ],
    },
    "Hugging Face": {
        "sector": "IA Open Source",
        "people": [
            ("Clément Delangue", "CEO & Co-founder", "Hugging Face"),
            ("Julien Chaumond", "CTO & Co-founder", "Hugging Face"),
            ("Thomas Wolf", "Chief Science Officer", "Hugging Face"),
            ("Lysandre Debut", "VP Open Source", "Hugging Face"),
            ("Margaret Mitchell", "Chief Ethics Scientist", "Google"),
        ],
        "products": [
            ("Transformers v5", "ML Framework", "framework de référence avec support natif des agents IA"),
            ("Inference Endpoints Pro", "MLOps", "déploiement de modèles en 1 clic avec auto-scaling"),
            ("Hugging Chat 2.0", "ChatBot", "chatbot open source basé sur les meilleurs modèles communautaires"),
            ("Spaces Enterprise", "ML Apps", "hébergement d'applications ML avec GPU dédiés"),
            ("SafeTensors 2.0", "ML Security", "format de sérialisation sécurisé pour modèles IA"),
        ],
        "partners": ["AWS", "Google Cloud", "Microsoft", "NVIDIA", "Intel", "AMD"],
        "events": ["VivaTech", "NeurIPS", "ICML", "Open Source Summit", "PyTorch Conference"],
        "locations": ["Paris", "New York", "San Francisco"],
        "hiring_roles": ["Research Engineer", "ML Engineer", "Developer Advocate", "Solutions Architect", "Community Manager"],
        "media_topics": [
            "héberge désormais 1 million de modèles sur sa plateforme",
            "annonce un partenariat stratégique avec l'Union Européenne pour l'IA ouverte",
            "lance un programme de grants de 10M$ pour la recherche IA en Europe",
            "classé startup IA la plus influente par Forbes",
        ],
        "funding_info": [
            ("235M$", "Série D", "4.5Md$", ["Salesforce Ventures", "Google", "Samsung"]),
            ("100M$", "Série D extension", "5Md$", ["NVIDIA", "AMD"]),
        ],
    },
    "Algolia": {
        "sector": "Search & AI",
        "people": [
            ("Bernadette Nixon", "CEO", "Alfresco"),
            ("Nicolas Dessaigne", "Co-founder & Board Member", "Algolia"),
            ("Julien Lemoine", "Co-founder & CTO", "Algolia"),
            ("Michelle Adams", "Chief Revenue Officer", "Twilio"),
            ("Pierre Chapuis", "VP AI Research", "Naver Labs"),
        ],
        "products": [
            ("NeuralSearch 2.0", "Search + RAG", "recherche vectorielle + RAG intégrés"),
            ("Algolia Recommend AI", "Recommendations", "recommandations personnalisées par IA en temps réel"),
            ("Algolia Answers", "GenAI Search", "réponses génératives basées sur le catalogue produit"),
            ("Search Analytics Pro", "Analytics", "analytics avancées avec insights IA sur les recherches"),
        ],
        "partners": ["Shopify", "Salesforce Commerce Cloud", "Adobe Commerce", "BigCommerce", "Contentful"],
        "events": ["Shoptalk", "VivaTech", "Web Summit", "Big Data & AI Paris"],
        "locations": ["Paris", "San Francisco", "New York", "Londres"],
        "hiring_roles": ["Search Engineer", "ML Engineer", "Solutions Architect", "Account Executive", "Developer Relations"],
        "media_topics": [
            "traite désormais 100 milliards de requêtes par an",
            "annonce 17 000 clients dont Decathlon, Lacoste et LVMH",
            "classé leader du Forrester Wave Search & Product Discovery",
            "ouvre un lab IA dédié à la recherche sémantique à Paris",
        ],
        "funding_info": [
            ("150M$", "Série D", "2.25Md$", ["Lone Pine Capital", "Fidelity"]),
        ],
    },
    # ─── Extra companies for MAPIC ─────────────────────────────────────────────
    "Unibail-Rodamco-Westfield": {
        "sector": "Immobilier commercial",
        "people": [
            ("Jean-Marie Tritant", "CEO", "URW (interne)"),
            ("Fabrice Mouchel", "CFO", "Klépierre"),
            ("Léa Thomassin", "Chief Digital Officer", "Carrefour Property"),
            ("Vincent Bryant", "Head of Sustainability", "BNP Paribas RE"),
            ("Astrid Panosyan-Bouvet", "VP Public Affairs", "Gouvernement"),
        ],
        "products": [
            ("Westfield Rise 2.0", "Retail Media", "plateforme de retail media pour annonceurs dans les centres commerciaux"),
            ("URW Digital Experience", "Digital Twin", "jumeau numérique des centres commerciaux avec analytics IA"),
            ("Footfall AI", "Analytics", "analyse de fréquentation par IA et caméras anonymisées"),
            ("Tenant Connect Platform", "Leasing", "plateforme digitale de gestion locative et relation enseignes"),
        ],
        "partners": ["JCDecaux", "Clear Channel", "Deliveroo", "Uber Eats", "Google"],
        "events": ["MAPIC", "MIPIM", "NRF", "ICSC"],
        "locations": ["Paris-La Défense", "Amsterdam", "Los Angeles", "Londres"],
        "hiring_roles": ["Digital Marketing Manager", "Data Analyst", "Leasing Director", "Sustainability Manager", "Asset Manager"],
        "media_topics": [
            "investit 500M€ dans la rénovation de 10 flagship assets en Europe",
            "annonce un taux d'occupation record de 96% sur ses centres premium",
            "lance un programme 'Better Places 2030' pour la neutralité carbone",
            "signe Primark et Nike pour de nouveaux flagship stores",
        ],
        "funding_info": [],
    },
    "Klépierre": {
        "sector": "Immobilier commercial",
        "people": [
            ("Jean-Marc Jestin", "CEO", "Klépierre (interne)"),
            ("Béatrice Berthoud", "Chief Operating Officer", "Unibail-Rodamco"),
            ("Hugo Sallé de Chou", "Head of Innovation", "LVMH"),
            ("Claire Vernier", "Director of Sustainability", "Danone"),
        ],
        "products": [
            ("Klépierre Brand Ventures", "Retail Media", "offre retail media et pop-up digitaux"),
            ("Act4Good", "Sustainability", "programme RSE certifié SBTi avec suivi IA"),
            ("Clubstore Analytics", "Data Platform", "plateforme data pour enseignes et centres"),
        ],
        "partners": ["BNP Paribas RE", "Cushman & Wakefield", "JLL", "AccorHotels"],
        "events": ["MAPIC", "MIPIM", "ICSC", "RetailDetail Congress"],
        "locations": ["Paris", "Milan", "Madrid", "Oslo"],
        "hiring_roles": ["Leasing Manager", "ESG Analyst", "Center Director", "Marketing Manager", "Data Analyst"],
        "media_topics": [
            "annonce un chiffre d'affaires locatif net en hausse de 8%",
            "classé leader ESG dans l'immobilier commercial par GRESB",
            "inaugure 3 nouveaux centres mixed-use en Europe du Sud",
            "lance un fonds de 100M€ pour la transformation des centres commerciaux",
        ],
        "funding_info": [],
    },
    "Hammerson": {
        "sector": "Immobilier commercial",
        "people": [
            ("Rita-Rose Gagné", "CEO", "Ivanhoé Cambridge"),
            ("James Ainsworth", "CFO", "British Land"),
            ("Sophie Bourdet", "Head of France", "CBRE"),
        ],
        "products": [
            ("Hammerson+", "Loyalty & Data", "programme fidélité cross-centres avec insights IA"),
            ("Net Zero Pathway", "Sustainability", "roadmap carbone zéro 2030 avec tracking temps réel"),
        ],
        "partners": ["Value Retail", "Nuveen", "APG", "Allianz"],
        "events": ["MAPIC", "MIPIM", "ULI Europe Conference"],
        "locations": ["Londres", "Paris", "Birmingham", "Dublin"],
        "hiring_roles": ["Asset Manager", "Sustainability Director", "Leasing Executive", "Finance Analyst"],
        "media_topics": [
            "cède son portefeuille retail parks pour 400M£ et se recentre sur le premium",
            "atteint les objectifs Net Zero en avance sur le calendrier",
            "annonce le repositionnement de Bullring Birmingham en mixed-use",
        ],
        "funding_info": [],
    },
    "IKEA Centres": {
        "sector": "Retail & Mixed-Use",
        "people": [
            ("Gérard Groener", "Managing Director", "Ingka Centres"),
            ("Anna Kihlström", "Head of Sustainability", "IKEA Group"),
            ("Pedro Fernandes", "VP Development EMEA", "Hammerson"),
        ],
        "products": [
            ("Meeting Places 3.0", "Concept", "nouveau concept de lieux de vie mixtes (retail, coworking, loisirs)"),
            ("Green Index", "Sustainability", "indicateur de durabilité pour chaque centre avec IA prédictive"),
        ],
        "partners": ["IKEA Retail", "Sonae Sierra", "Apsys", "McDonald's", "H&M"],
        "events": ["MAPIC", "MIPIM", "NRF", "World Retail Congress"],
        "locations": ["Malmö", "Moscou", "Shanghai", "Paris"],
        "hiring_roles": ["Development Manager", "Sustainability Coordinator", "Tenant Relations Manager", "Experience Designer"],
        "media_topics": [
            "ouvre 5 nouveaux 'meeting places' en Europe avec un investissement de 800M€",
            "intègre des espaces de coworking et des fermes urbaines dans ses centres",
            "atteint 100% d'énergie renouvelable dans ses centres européens",
        ],
        "funding_info": [],
    },
    "Primark": {
        "sector": "Retail Fashion",
        "people": [
            ("Paul Marchant", "CEO", "Primark (ABF)"),
            ("Lynne Walker", "Finance Director", "ABF"),
            ("Florence Rolland", "Expansion Director France", "H&M"),
        ],
        "products": [
            ("Primark Edit", "Premium Range", "ligne premium avec matériaux durables certifiés"),
            ("Click & Collect Pilot", "Omnichannel", "test de click & collect dans 25 magasins UK"),
        ],
        "partners": ["COS", "Zara", "H&M", "Uniqlo"],
        "events": ["MAPIC", "NRF", "Paris Retail Week", "Fashion Retail Congress"],
        "locations": ["Dublin", "Londres", "Madrid", "Paris", "Rome"],
        "hiring_roles": ["Store Manager", "Expansion Manager", "Visual Merchandiser", "Sustainability Manager", "Supply Chain Analyst"],
        "media_topics": [
            "atteint 430 magasins dans le monde avec 30 ouvertures prévues en 2026",
            "annonce l'objectif de 100% coton durable d'ici 2027",
            "ouvre son plus grand magasin français à Paris (6000m²)",
            "teste un concept de magasin nouvelle génération à Birmingham",
        ],
        "funding_info": [],
    },
}

SOURCES = ["linkedin", "techcrunch", "lesechos", "usine_digitale", "maddyness", "crunchbase",
           "lemondeinformatique", "alliancy", "linkedin_jobs", "bfm_business", "journaldunet",
           "frenchweb", "challenges", "latribune"]


# ─── Signal templates ─────────────────────────────────────────────────────────

def _gen_nomination(company, data, idx):
    signals = []
    for person, role, prev in data["people"]:
        signals.append({
            "source": random.choice(["linkedin", "maddyness", "lesechos"]),
            "company": company,
            "signal_type": "nomination",
            "title": f"{company} nomme {person} au poste de {role}",
            "summary": f"{person}, ex-{prev}, rejoint {company} en tant que {role}. Un recrutement stratégique qui signale les ambitions de l'entreprise sur le marché européen.",
            "url": f"https://linkedin.com/posts/{company.lower().replace(' ', '-')}-{person.lower().replace(' ', '-')}",
            "date_offset_days": random.randint(-30, -1),
            "raw_entities": {"person": person, "role": role, "previous": prev},
        })
    return signals


def _gen_funding(company, data, idx):
    signals = []
    for amount, round_name, valuation, investors in data.get("funding_info", []):
        signals.append({
            "source": random.choice(["lesechos", "techcrunch", "crunchbase", "frenchweb"]),
            "company": company,
            "signal_type": "funding",
            "title": f"{company} boucle un tour de table de {amount} en {round_name}",
            "summary": f"{company} annonce une levée de {amount} en {round_name} menée par {' et '.join(investors)}, valorisant l'entreprise à {valuation}. Les fonds serviront à accélérer la croissance en Europe.",
            "url": f"https://lesechos.fr/{company.lower().replace(' ', '-')}-{round_name.lower().replace(' ', '-')}",
            "date_offset_days": random.randint(-25, -1),
            "raw_entities": {"amount": amount, "round": round_name, "valuation": valuation, "lead_investors": investors},
        })
    return signals


def _gen_product_launch(company, data, idx):
    signals = []
    for product, category, desc in data["products"]:
        signals.append({
            "source": random.choice(["techcrunch", "usine_digitale", "lemondeinformatique", "alliancy"]),
            "company": company,
            "signal_type": "product_launch",
            "title": f"{company} lance '{product}' — {desc}",
            "summary": f"{company} annonce {product}, un nouveau produit dans la catégorie {category}. {desc.capitalize()}. Disponibilité prévue dans les prochains mois.",
            "url": f"https://usine-digitale.fr/{company.lower().replace(' ', '-')}-{product.lower().replace(' ', '-')}",
            "date_offset_days": random.randint(-28, -1),
            "raw_entities": {"product": product, "category": category},
        })
    return signals


def _gen_hiring_surge(company, data, idx):
    signals = []
    num_roles = random.randint(15, 200)
    location_sample = random.sample(data["locations"], min(3, len(data["locations"])))
    roles_sample = random.sample(data["hiring_roles"], min(3, len(data["hiring_roles"])))
    signals.append({
        "source": "linkedin_jobs",
        "company": company,
        "signal_type": "hiring_surge",
        "title": f"{company} recrute massivement : {num_roles} postes ouverts en {data['sector']}",
        "summary": f"{num_roles} postes ouverts sur LinkedIn pour {company} : {', '.join(roles_sample)}. Bureaux de {', '.join(location_sample)} concernés. Signal fort d'investissement.",
        "url": f"https://linkedin.com/jobs/{company.lower().replace(' ', '-')}",
        "date_offset_days": random.randint(-14, -1),
        "raw_entities": {"open_roles": num_roles, "key_roles": roles_sample, "locations": location_sample},
    })
    # Second wave
    num_roles2 = random.randint(10, 80)
    signals.append({
        "source": "linkedin_jobs",
        "company": company,
        "signal_type": "hiring_surge",
        "title": f"{company} ouvre {num_roles2} postes supplémentaires en France",
        "summary": f"Nouvelle vague de recrutement chez {company} : {num_roles2} postes en France, focalisés sur {', '.join(random.sample(data['hiring_roles'], min(2, len(data['hiring_roles']))))}.",
        "url": f"https://linkedin.com/jobs/{company.lower().replace(' ', '-')}-france",
        "date_offset_days": random.randint(-20, -1),
        "raw_entities": {"open_roles": num_roles2, "locations": ["France"]},
    })
    return signals


def _gen_competing_event(company, data, idx):
    signals = []
    for event in data["events"]:
        role_at_event = random.choice(["Keynote speaker", "Sponsor Gold", "Exposant", "Panéliste", "Workshop leader"])
        person = data["people"][0][0] if data["people"] else "un dirigeant"
        signals.append({
            "source": random.choice(["linkedin", "bfm_business", "lesechos"]),
            "company": company,
            "signal_type": "competing_event",
            "title": f"{company} confirmé comme {role_at_event} à {event}",
            "summary": f"{person} ({company}) sera {role_at_event} à {event}. L'entreprise sera présente avec un stand et des démonstrations produit.",
            "url": f"https://linkedin.com/posts/{event.lower().replace(' ', '-')}-{company.lower().replace(' ', '-')}",
            "date_offset_days": random.randint(-20, -1),
            "raw_entities": {"event": event, "person": person, "role_at_event": role_at_event},
        })
    return signals


def _gen_media_mention(company, data, idx):
    signals = []
    for topic in data["media_topics"]:
        signals.append({
            "source": random.choice(["lesechos", "usine_digitale", "bfm_business", "challenges", "latribune", "journaldunet"]),
            "company": company,
            "signal_type": "media_mention",
            "title": f"{company} {topic}",
            "summary": f"{company} {topic}. Un signal fort de l'activité et des ambitions de l'entreprise sur le marché.",
            "url": f"https://lesechos.fr/{company.lower().replace(' ', '-')}-{idx}",
            "date_offset_days": random.randint(-30, -1),
            "raw_entities": {"topic": topic},
        })
    return signals


def _gen_partnership(company, data, idx):
    signals = []
    for partner in data["partners"]:
        focus = random.choice(["IA", "Cloud", "Data", "Transformation digitale", "Innovation", "Durabilité"])
        signals.append({
            "source": random.choice(["usine_digitale", "lemondeinformatique", "alliancy", "frenchweb"]),
            "company": company,
            "signal_type": "partnership",
            "title": f"{company} et {partner} annoncent un partenariat stratégique sur {focus}",
            "summary": f"{company} et {partner} signent un partenariat pour accélérer sur le segment {focus}. L'alliance combinera les forces des deux entreprises sur le marché européen.",
            "url": f"https://usine-digitale.fr/{company.lower().replace(' ', '-')}-{partner.lower().replace(' ', '-')}",
            "date_offset_days": random.randint(-25, -1),
            "raw_entities": {"partner": partner, "focus": focus},
        })
    return signals


def _gen_store_opening(company, data, idx):
    """For retail/real-estate companies."""
    signals = []
    for loc in data["locations"]:
        size = random.choice(["3000m²", "5000m²", "8000m²", "12000m²", "20000m²"])
        signals.append({
            "source": random.choice(["lesechos", "challenges", "latribune"]),
            "company": company,
            "signal_type": "store_opening",
            "title": f"{company} ouvre un nouvel espace de {size} à {loc}",
            "summary": f"{company} annonce l'ouverture d'un nouvel espace de {size} à {loc}. Un investissement qui confirme la stratégie d'expansion de l'entreprise.",
            "url": f"https://lesechos.fr/{company.lower().replace(' ', '-')}-{loc.lower()}",
            "date_offset_days": random.randint(-20, -1),
            "raw_entities": {"location": loc, "size": size},
        })
    return signals


GENERATORS = {
    "nomination": _gen_nomination,
    "funding": _gen_funding,
    "product_launch": _gen_product_launch,
    "hiring_surge": _gen_hiring_surge,
    "competing_event": _gen_competing_event,
    "media_mention": _gen_media_mention,
    "partnership": _gen_partnership,
    "store_opening": _gen_store_opening,
}


def generate_signals(config: dict) -> list[dict]:
    """
    Generate hundreds of realistic fake signals based on config targets.
    Each target company × signal type combination produces multiple signals.
    """
    random.seed(42)  # Reproducible for demo
    now = datetime.now()
    valid_signal_types = {s["id"] for s in config.get("signal_types", [])}

    all_signals = []
    for company, data in COMPANY_DATA.items():
        for signal_type_id in valid_signal_types:
            gen = GENERATORS.get(signal_type_id)
            if not gen:
                continue
            raw_batch = gen(company, data, len(all_signals))
            all_signals.extend(raw_batch)

    # Assign IDs and resolve dates
    signals = []
    for i, raw in enumerate(all_signals):
        signal = {
            "id": f"SIG-{i+1:04d}",
            "source": raw["source"],
            "company": raw["company"],
            "signal_type": raw["signal_type"],
            "title": raw["title"],
            "summary": raw["summary"],
            "url": raw["url"],
            "detected_at": (now + timedelta(days=raw["date_offset_days"])).isoformat(),
            "raw_entities": raw["raw_entities"],
        }
        signals.append(signal)

    return signals


if __name__ == "__main__":
    import yaml
    with open("config/bdaip_2026.yaml") as f:
        cfg = yaml.safe_load(f)
    sigs = generate_signals(cfg)
    print(f"Generated {len(sigs)} signals for {cfg['salon']['name']}")
    # Show distribution
    from collections import Counter
    by_company = Counter(s["company"] for s in sigs)
    by_type = Counter(s["signal_type"] for s in sigs)
    print(f"\nBy company: {dict(by_company)}")
    print(f"By type: {dict(by_type)}")
