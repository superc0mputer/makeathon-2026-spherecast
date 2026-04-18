# makeathon-2026-spherecast

# 🔄 Smart Ingredient Substitution Pipeline & UI
> **Built for the Spherecast Challenge at the TUM.ai Makeathon 2026 🚀**
---

## 🏆 Hackathon Submission Details

### 1. General Approach
We architected a 4-phase generative pipeline that bridges **deterministic feature clustering** with **AI-powered contextual reasoning**. Recognizing that strict biochemical matching requires math, while recipe viability requires human-like intuition, we split the problem:
*   **Discovery:** We query PubChem (for pure chemicals) and USDA FDC (for food mixtures) to build N-dimensional vectors. We compare these using Cosine Similarity alongside historical BOM dataset co-occurrences.
*   **Validation:** We pass the mathematical matches into Google Gemini (via Vertex AI) tightly constrained by Pydantic schemas to ensure no chemical cross-reactions or flavor clashes occur inside the final recipe constraint.
*   **Logistics Routing:** We deterministically map real-world suppliers directly to coordinates via OpenStreetMap (Nominatim) and retrieve known prices.
*   **Decision Engine:** A final LLM pass evaluates the "Supply Chain Manager" priorities (e.g., heavily weighting price savings vs. minimizing transit distance) to select the ultimate Top 3 recommendations.

### 2. What Worked Well
*   **Hybrid Feature-Clustering:** Combining chemical properties, macronutrient profiles, and BOM usage successfully circumvented the severe "cold start" data sparsity problem for generic products (like "B Vitamins").
*   **Strict JSON Pydantic Routing:** Demanding strictly enforced JSON schemas from Gemini eliminated pipeline crash events due to hallucinated formatting.
*   **Read-Through SQLite Caching:** Implementing `cache_service.py` to transparently capture all PubChem, FDC, and OpenStreetMap calls fundamentally bypassed the severe API throttling and rate-limiting we initially encountered.

### 3. What Did Not Work
*   **LLM Geocoding Over-reliance:** Initially, we actively prompted the LLM to process and resolve supplier locations. This generated massive payload token costs and immediately exhausted free-tier API quotas. We fully removed LLM geocoding and reverted to pure deterministic OpenStreetMap API lookups, which proved infinitely more stable.
*   **Insufficient BOM Context:** The initial context for the Bill of Materials (BOM) was too small, which resulted in invalid and poor clustering. We resolved this by enriching the context using additional API resources.

### 4. How We Would Improve Our Submission
*   **Enterprise Vector Database:** Replace local in-memory cosine similarity logic with an embedded Vector Database (e.g., Milvus or Pinecone) to allow for instant, massively scalable nearest-neighbor clustering.
*   **Live SaaS Pricing Integration:** Replace our currently mocked Local API environment with live, authenticated calls to Mintec or another live commodities index.

**Overview**
This pipeline automates the process of finding viable, cost-effective, and low-risk substitute ingredients for a manufacturing process of a company. It leverages chemical databases, supplier logistics, and LLM-driven analysis to recommend the best alternatives.

* **Inputs:** BOM-Ingredient (Target for substitution), Company Location, Customer Preferences (Weights for LLM, specified in UI).
* **Ultimate Goal:** Identify the best chemical/ingredient substitutes and the optimal suppliers to source them from.
* **Final Output:** A strict JSON output representing the **Top 3** recommended substitutes and their respective suppliers, to be rendered by a clean UI Dashboard.

---

### Phase 1: Discovery & Hybrid Feature-Based Clustering
*The goal here is to dynamically map the target ingredient to viable substitutes using a multi-dimensional similarity model.*

* **Step 1: BOM Co-occurrence Analysis**
    Build a matrix of historical usage from the BOM dataset. This overcomes the "cold start" sparsity problem by finding statistical correlations between ingredients.
* **Step 2: API Feature Extraction (FDC & PubChem)**
    Extract numerical vectors from two distinct APIs:
    * **USDA FoodData Central (FDC):** Grabs nutritional macronutrients (Energy, Protein, Fat, Carbs) to handle complex food mixtures (e.g., "MCT oil", "gelatin") that lack pure molecular formulas.
    * **PubChem REST API:** Grabs pure chemical properties (Molecular Weight, XLogP, Charge, Salts) for precise molecular matching. 
* **Step 3: Read-Through API Caching**
    All API calls route through a local SQLite cache (`db/cache.sqlite`) to prevent rate-limiting, mitigate timeouts, and enable fast batch processing. Includes regex fallbacks to dynamically trim lengthy food-grade names if PubChem returns a 404.
* **Step 4: Hybrid Cosine Similarity Scoring**
    Normalize features via `MinMaxScaler` and calculate a weighted similarity matrix.
    * **Weighting Distribution:** `(BOM * 0.20) + (PubChem * 0.25) + (FDC * 0.35) + (Text * 0.20)`.
    * **Absence Penalty:** Zeroes out chemical or nutritional similarity if either the target or candidate completely lacks vector data, preventing "Similarity by Absence" (where two empty profiles mathematically matched as 1.0).
    * **Linguistic Rescue (Text Similarity):** Leverages `difflib.SequenceMatcher` to safely map generic ingredient classes (e.g., "B Vitamins" to other "B Vitamins" variants) when raw biochemical data is unavailable.
    Output a shortlist of statistically viable substitutes.

### Phase 2: Feasibility & Initial Filtering
*The goal here is to use AI to ensure the mathematically similar ingredients actually work in our specific recipe. Driven entirely by the `BiochemicalContext` Pydantic model.*

* **Step 3: LLM Contextual Validation (`BiochemicalContext`)**
    Send the chemical components to an LLM. Ask: *"Can these components actually act as a substitute in this specific context?"* 
    * **Prompt Context Provided:** The clustered similar products AND strictly typed profiles of all other current ingredients in our product's BOM. This ensures no negative chemical cross-reactions, precipitation, or flavor clashes.
* **Step 4: Shortlisting**
    The LLM outputs a curated list of possible substitutions, each tagged with a **Confidence Score** (e.g., 0-100%).

### Phase 3: Logistics & Sourcing Enrichment
*The goal here is to attach real-world business data (price, supplier, distance) to our shortlisted substitutes.*

* **Step 5: Pricing Integration**
    Attach pricing data to the shortlisted substitutes. 
    * *Hackathon State:* Mocked via a static list/JSON based on a local API.
    * *Production State:* Integration with the **Mintec API**.
* **Step 6: Supplier Matching**
    Query our internal database (`db/db.sqlite`) to find all known suppliers that carry these shortlisted substitutes. Also retrieves `stocked_ingredients` to see what else each supplier carries.
* **Step 7: Geolocation Routing**
    Ping the **OpenStreetMap** (Nominatim) to get the exact coordinates/locations of these suppliers to calculate shipping distances from the manufacturer.

### Phase 4: The Logistics & Decision Engine
*The final LLM evaluation that acts as a supply chain manager. Strictly typed via the `LogisticsContext` Pydantic model and evaluating arrays of `SourcedMaterial`. This phase completely decouples biochemical checks (handled in Phase 2) from supply chain logistics.*

* **Step 8: Multi-Criteria Recommendation (`LogisticsContext`)**
    The engine receives purely logistical data (Shortlist + Confidence Scores, Prices, Suppliers, Locations, Full BOM list). The Phase 4 prompt focuses entirely on supply-chain viability matching End-User priority weights (`price_per_kg`, `distance_km`).
    * **Supplier Distance:** Evaluating the geolocation routing from Phase 3 to minimize risks and carbon footprint.
    * **Cost Analysis:** Weighing `price_per_kg` against user-defined prioritization.
    * **Supplier Consolidation:** Analyzing `bom_ingredients` vs `stocked_ingredients` to prioritize suppliers who can fulfill multiple parts of our BOM, drastically reducing shipping complexity.
    * **Confidence & Availability:** Leveraging the earlier chemical validation score without re-processing BOM chemistry.

---

## 🐳 Setup & Running with Docker

We have containerized the entire pipeline and dashboard so you can run it effortlessly without installing any local Python or Node.js dependencies.

### 1. Requirements
* Docker Desktop installed and running on your system.

### 2. Configure Environment (`.env`)
First, create an environment variable file (`.env`) in the root directory. You must supply valid API keys for the Gemini LLM and USDA FoodData Central databases to function properly.

Copy the example template to create your `.env` file:
```bash
cp .env.example .env
```

Then, open `.env` and add your keys. You can choose one of two options for Gemini:
```env
# Option A: Standard Google Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Option B: Google Cloud Vertex AI (Make sure to run `gcloud auth` locally!)
# VERTEX_PROJECT_ID=your_gcp_project_id_here
# VERTEX_LOCATION=us-central1

# USDA FoodData Central API Key (Optional)
FDC_API_KEY=your_fdc_api_key_here
```

### 3. Start the Full Stack Pipeline
Run the provided helper bash script. This will automatically build the Docker image containing both the Python backend and Next.js UI. It will also map your `.env` file and local SQLite databases.

```bash
./run_docker.sh
```

Once the Docker container finishes building and starts, navigate to `http://localhost:3000` in your web browser to interact with the pipeline via the dashboard!
