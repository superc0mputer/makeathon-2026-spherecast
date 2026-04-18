# makeathon-2026-spherecast

# 🔄 Smart Ingredient Substitution Pipeline

**Overview**
This pipeline automates the process of finding viable, cost-effective, and low-risk substitute ingredients for our manufacturing process. It leverages chemical databases, supplier logistics, and LLM-driven analysis to recommend the best alternatives.

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
    All API calls route through a local SQLite cache (`cache.sqlite`) to prevent rate-limiting, mitigate timeouts, and enable fast batch processing. Includes regex fallbacks to dynamically trim lengthy food-grade names if PubChem returns a 404.
* **Step 4: Hybrid Cosine Similarity Scoring**
    Normalize features via `MinMaxScaler` and calculate a weighted similarity matrix.
    * **Weighting Distribution:** `(BOM * 0.30) + (PubChem * 0.25) + (FDC * 0.25) + (Text * 0.20)`.
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

    ![alt text](image-1.png)

### Phase 3: Logistics & Sourcing Enrichment
*The goal here is to attach real-world business data (price, supplier, distance) to our shortlisted substitutes.*

* **Step 5: Pricing Integration**
    Attach pricing data to the shortlisted substitutes. 
    * *Hackathon State:* Mocked via a static list/JSON based on a local API.
    * *Production State:* Integration with the **Mintec API**.
* **Step 6: Supplier Matching**
    Query our internal database (`db.sqlite`) to find all known suppliers that carry these shortlisted substitutes. Also retrieves `stocked_ingredients` to see what else each supplier carries.
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

### 💻 Final Output / Deliverable
The backend will serve exactly 3 objects following the `FinalDecisionResponse` Pydantic schema to the frontend, which will render a **Clean UI Dashboard**. 

The UI must highlight the **Top 3 Choices**, displaying:
1.  The recommended substitute ingredient.
2.  The optimal supplier (along with price and transit distance).
3.  A brief LLM-generated summary of *why* it was chosen (highlighting exact supply chain metrics, supplier consolidation, cost, distance, and chemical confidence score).
