# Auto OMOP Mapper 🗺️

An automated system for mapping source medical concepts to OMOP standard concepts using vector similarity search and LLM-based reranking.

## 2025 OHDSI Europe Symposium

[Abstract link](https://drive.google.com/file/d/1m-jeBvWbRCNxFuffR210nhSAK-BNqUWF/view?usp=drive_link)
[Poster link](https://drive.google.com/file/d/19kEdJ-7Z5XAA33nVR58EvH2oJnZD5ZNY/view?usp=drive_link)

## Prerequisites

- Docker and Docker Compose installed
- OpenAI API key
- OMOP vocabulary files (CONCEPT.csv, CONCEPT_RELATIONSHIP.csv, CONCEPT_ANCESTOR.csv)

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd auto-omop-mapper
```

### 2. Create Environment Configuration

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# Database Configuration (PostgreSQL)
POSTGRES_USER=omop_user
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=omop_mapper
POSTGRES_HOST=postgres-db
POSTGRES_PORT=5432

# Vector Database
QDRANT_URL=http://qdrant:6333

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Start the Services

```bash
docker-compose up -d
```

This will start:

- PostgreSQL database (port 5432)
- Qdrant vector database (ports 6333, 6334)
- Auto OMOP Mapper web application (port 8501)

### 4. Access the Application

Open your browser and go to: <http://localhost:8501>

## Workflow

### 1. Import OMOP Vocabulary Tables

1. Place your OMOP vocabulary files in the `vocabulary/` directory:
   - **CONCEPT.csv**: Main OMOP concept table
   - **CONCEPT_RELATIONSHIP.csv**: Relationships between concepts
   - **CONCEPT_ANCESTOR.csv**: Hierarchical relationships
2. Go to "Import Data" → "OMOP Vocabulary Tables"
3. Import the vocabulary files

### 2. Process ATC7 Codes

1. Go to "Import Data" → "ATC7 Processing"
2. Click "Process ATC7 Codes" to find and store ATC7 codes for drug concepts

### 3. Import Source Concepts

1. Go to "Import Data" → "Source Concepts"
2. Upload your CSV file with source concepts that need mapping
3. Required columns: `source_value`, `source_concept_name`

### 4. Embed Concepts

1. Go to "Import Data" → "Embedding Management"
2. Click "Embed Standard Concepts" to create vector embeddings
3. Only standard concepts will be embedded, with ATC7 metadata for drugs
4. You can see how many concepts are embedded on [this](http://localhost:6333/dashboard#/collections) page.
**The UI will not update when the embedding is running but the Qdrant dashboard will**

### 5. Configure Models

1. Go to "Configuration" page to change:
   - LLM Model for reranking (gpt-4o, gpt-4o-mini, etc.)
   - Embedding Model (text-embedding-3-small, text-embedding-3-large, etc.)
   - When changing embedding settings, a new vector collection will be created

### 6. Search and Map

1. **Search**: Use the "Search" page to test similarity search
2. **Map**: Use the "Map Concepts" page for interactive mapping
3. **Commit**: Review and export mappings on the "Check and Commit" page

## Architecture

The system uses PostgreSQL for data storage, Qdrant for vector search and OpenAI API for LLM calls.

## Affiliation

This repository contains work developed as part of my role at the Croatian Institute of Public Health.
