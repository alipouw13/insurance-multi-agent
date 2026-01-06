Insurance claims data for the multi-agent application. Contains 5 tables:

- **claims_history**: Individual claim records with amounts, dates, statuses, vehicle info, fraud flags
- **claimant_profiles**: Customer demographics, risk scores, claim history
- **fraud_indicators**: Detected fraud patterns and investigation status
- **regional_statistics**: Geographic benchmarks for claims and fraud rates
- **policy_claims_summary**: Aggregated policy-level claims with trends

Use for questions about: claim amounts, policy lookups, fraud patterns, regional comparisons, customer risk profiles, and claim trends.

Key fields: estimated_damage (USD), amount_paid (USD), risk_score (0-100), fraud_flag (boolean).
