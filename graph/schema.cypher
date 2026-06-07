// Persona knowledge-graph schema: uniqueness constraints + vector index.
// Idempotent — safe to re-run. Apply with apply_schema() in build_graph.py
// or: cypher-shell -u neo4j -p personagraph -f schema.cypher

CREATE CONSTRAINT persona_id IF NOT EXISTS
  FOR (p:Persona) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT state_name IF NOT EXISTS
  FOR (n:State) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT region_name IF NOT EXISTS
  FOR (n:Region) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT language_name IF NOT EXISTS
  FOR (n:Language) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT dialect_name IF NOT EXISTS
  FOR (n:Dialect) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT religion_name IF NOT EXISTS
  FOR (n:Religion) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT community_name IF NOT EXISTS
  FOR (n:Community) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT occupation_name IF NOT EXISTS
  FOR (n:Occupation) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT tier_name IF NOT EXISTS
  FOR (n:OccupationTier) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT education_name IF NOT EXISTS
  FOR (n:EducationLevel) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT nccs_name IF NOT EXISTS
  FOR (n:NccsClass) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT income_name IF NOT EXISTS
  FOR (n:IncomeBand) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT value_name IF NOT EXISTS
  FOR (n:Value) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT trait_name IF NOT EXISTS
  FOR (n:Trait) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT gatekeeper_name IF NOT EXISTS
  FOR (n:Gatekeeper) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT horizon_name IF NOT EXISTS
  FOR (n:TemporalHorizon) REQUIRE n.name IS UNIQUE;

// Behavioral similarity vector index (cosine). Dimensions must match
// config.BEHAVIORAL_DIM (currently 11).
CREATE VECTOR INDEX persona_behavioral IF NOT EXISTS
  FOR (p:Persona) ON p.embedding_behavioral
  OPTIONS {indexConfig: {
    `vector.dimensions`: 11,
    `vector.similarity_function`: 'cosine'
  }};
