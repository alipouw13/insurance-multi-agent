# Insurance Claims Lakehouse - Data Source Description

This Lakehouse contains comprehensive insurance claims data for the insurance multi-agent application. Use this data source for any questions about:

## What This Data Contains
- **Claims Records**: Individual insurance claim details including amounts, dates, statuses, vehicle information, and fraud flags
- **Customer Profiles**: Claimant demographics, contact information, risk scores, and claim history summaries
- **Fraud Indicators**: Detected fraud patterns, investigation status, and severity levels
- **Regional Statistics**: Geographic benchmarks for claim amounts, fraud rates, and seasonal patterns
- **Policy Summaries**: Aggregated claims data per policy with trend analysis

## Types of Questions This Can Answer
- What is the average claim amount for auto collision claims?
- Show me all claims for a specific policy number
- Find high-risk claimants with risk scores above a threshold
- What is the fraud rate in California?
- How does a specific claim amount compare to regional averages?
- Which policies have increasing claim trends?
- What fraud patterns have been detected for a specific claim?
- Show customers with poor driving records and high claim frequency

## Business Context
- **estimated_damage**: Initial damage estimate (USD), used for claim assessment
- **amount_paid**: Final approved amount (USD), for settled claims only
- **risk_score**: 0-100 scale where higher values indicate greater risk
- **fraud_flag**: Boolean indicator for potentially fraudulent claims
- Claims span auto, property, theft, weather, injury, liability, and medical categories
