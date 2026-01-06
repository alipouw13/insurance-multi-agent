# Insurance Claims Lakehouse - Data Source Instructions

## General Knowledge

This Lakehouse contains insurance claims data for the insurance multi-agent application. All monetary amounts are in USD. The schema uses `dbo` as the default schema prefix.

**Key Business Terms:**
- **estimated_damage**: Initial damage estimate submitted with claim
- **amount_paid**: Final approved/settled amount (null for pending/denied claims)
- **risk_score**: 0-100 scale (0-25=low, 26-50=moderate, 51-75=elevated, 76-100=high risk)
- **fraud_flag**: Boolean indicating potential fraud
- **claim_frequency**: very_low, low, moderate, high
- **claims_trend**: INCREASING, STABLE, DECREASING, INSUFFICIENT_DATA

## Table Descriptions

### claims_history
Individual insurance claim records with comprehensive details.

| Column | Type | Description |
|--------|------|-------------|
| claim_id | string | Unique identifier (CLM-XXXXX) |
| policy_number | string | Associated policy |
| claimant_id | string | Customer reference |
| claimant_name | string | Customer name |
| claim_type | string | Auto Collision, Property Damage, Theft, Weather Damage, Personal Injury, Liability, Medical, Comprehensive |
| estimated_damage | decimal | Initial damage estimate (USD) |
| amount_paid | decimal | Final approved amount (USD) |
| claim_date | date | Date filed |
| incident_date | date | Date of incident |
| status | string | PENDING, APPROVED, DENIED, SETTLED, UNDER_REVIEW |
| state | string | US state code |
| police_report | boolean | Police report filed |
| photos_provided | boolean | Photos submitted |
| witness_statements | string | none, one, multiple |
| vehicle_make | string | Vehicle manufacturer |
| vehicle_model | string | Vehicle model |
| vehicle_year | integer | Model year |
| fraud_flag | boolean | Fraud indicator |

### claimant_profiles
Customer profiles with risk assessments.

| Column | Type | Description |
|--------|------|-------------|
| claimant_id | string | Unique identifier (CLM-XXX) |
| name | string | Full name |
| age | integer | Age in years |
| state | string | State of residence |
| city | string | City |
| phone | string | Contact phone |
| email | string | Email |
| customer_since | date | Account creation |
| total_claims_count | integer | Lifetime claims |
| total_claims_amount | decimal | Lifetime value (USD) |
| risk_score | decimal | Risk score 0-100 |
| claim_frequency | string | Filing frequency |
| credit_score | string | excellent, good, fair, poor |
| driving_record | string | clean, minor_violations, major_violations |
| account_status | string | ACTIVE, SUSPENDED, CLOSED |

### fraud_indicators
Fraud detection records linked to claims.

| Column | Type | Description |
|--------|------|-------------|
| indicator_id | string | Unique identifier |
| claim_id | string | Associated claim |
| indicator_type | string | Fraud pattern type |
| severity | string | LOW, MEDIUM, HIGH, CRITICAL |
| detected_date | date | Detection date |
| pattern_description | string | Pattern details |
| investigation_status | string | OPEN, CLOSED, CONFIRMED |

**indicator_type values**: Multiple Claims Short Period, Excessive Claim Amount, Inconsistent Documentation, Staged Accident Pattern, Previous Fraud History, Suspicious Timing, Witness Inconsistency, Medical Bill Padding, Phantom Damage, Policyholder Collusion

### regional_statistics
Geographic claims benchmarks.

| Column | Type | Description |
|--------|------|-------------|
| region | string | Northeast, Southeast, Midwest, Southwest, West |
| state | string | US state code |
| city | string | City name |
| avg_claim_amount | decimal | Average claim (USD) |
| claim_frequency | decimal | Claims per 1,000 policies |
| fraud_rate | decimal | Fraud percentage (0-100) |
| most_common_claim_type | string | Most frequent type |
| seasonal_peak | string | Winter, Spring, Summer, Fall |
| total_claims | integer | Total claims count |
| year | integer | Statistics year |

### policy_claims_summary
Aggregated policy-level claims data.

| Column | Type | Description |
|--------|------|-------------|
| policy_number | string | Policy identifier |
| total_claims | integer | Claims count |
| total_amount_paid | decimal | Total paid (USD) |
| avg_claim_amount | decimal | Average claim (USD) |
| last_claim_date | date | Most recent claim |
| first_claim_date | date | First claim |
| claims_trend | string | INCREASING, DECREASING, STABLE, INSUFFICIENT_DATA |
| policy_type | string | AUTO, HOME, COMMERCIAL, LIFE |
| fraud_claims_count | integer | Fraud-flagged claims |

## When Asked About

**Individual claims**: Use `claims_history` for claim lookups by claim_id, policy_number, claimant_name, claim_type, status, or date range.

**Customer information or risk**: Use `claimant_profiles` for customer details, risk scores, driving records, claim frequency.

**Fraud patterns or investigations**: Use `fraud_indicators` for fraud pattern analysis, investigation status, or linking fraud indicators to specific claims.

**Regional comparisons or benchmarks**: Use `regional_statistics` for average claim amounts by location, fraud rates by geography, or seasonal patterns.

**Policy-level analysis**: Use `policy_claims_summary` for aggregated policy data, claim trends, or identifying high-claim policies.

**Comparing claim amounts**: Join `claims_history` with `regional_statistics` on state/city to compare individual claims against regional averages.

**High-risk customers with fraud history**: Join `claimant_profiles` with `claims_history` on claimant_id, then with `fraud_indicators` on claim_id.

**Best-selling/highest should be determined by count** unless the user specifically mentions amount or value.

Always include relevant identifiers (claim_id, policy_number, claimant_id) in query results.
