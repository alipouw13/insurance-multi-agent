# Insurance Claims Processing - Ontology Bindings Guidance

This document provides guidance for thinking through specific bindings and use cases for your insurance claims processing multi-agent system.

---

## Core Principles for Binding Design

### 1. Start with Questions, Not Data

Before creating bindings, identify the **questions** your users will ask. Bindings should directly answer business questions.

### 2. Consider the Query Chain

Your multi-agent system has specific agents with specific needs:
- **Claim Assessor** → Needs damage assessment, documentation status
- **Policy Checker** → Needs coverage validation, policy limits
- **Risk Analyst** → Needs fraud indicators, risk scores, patterns
- **Claims Data Analyst** → Needs regional statistics, historical trends, portfolio analytics
- **Communication Agent** → Needs customer info, claim status for messaging

### 3. Balance Pre-computation vs. Flexibility

| Pre-computed Bindings | Dynamic Queries |
|----------------------|-----------------|
| Faster query response | More flexible |
| Good for common patterns | Good for ad-hoc analysis |
| Reduces LLM reasoning | Requires more context |

---

## Use Case Analysis

### Use Case 1: Claims Processing Workflow

**Scenario**: A new claim comes in and needs to be assessed.

**Questions the agents will ask:**
1. "What is the estimated damage for this claim?"
2. "Is documentation complete?"
3. "Does this claim match any fraud patterns?"
4. "What is the customer's claims history?"
5. "Is this claim within policy limits?"

**Recommended Bindings:**

#### On `claims_history`

| Binding | Logic | Agent Use |
|---------|-------|-----------|
| `documentation_status` | `CASE WHEN police_report AND photos_provided AND witness_statements > 0 THEN 'Complete' WHEN police_report OR photos_provided THEN 'Partial' ELSE 'Missing' END` | Claim Assessor |
| `claim_age_days` | `DATEDIFF(day, claim_date, GETDATE())` | All agents |
| `is_stale_claim` | `DATEDIFF(day, claim_date, GETDATE()) > 30 AND status = 'PENDING'` | Supervisor |
| `estimated_severity` | `CASE WHEN estimated_damage > 50000 THEN 'Critical' WHEN estimated_damage > 25000 THEN 'High' WHEN estimated_damage > 10000 THEN 'Medium' ELSE 'Low' END` | Claim Assessor |
| `processing_sla_status` | `CASE WHEN status = 'PENDING' AND DATEDIFF(day, claim_date, GETDATE()) > 14 THEN 'SLA Breach' WHEN status = 'PENDING' AND DATEDIFF(day, claim_date, GETDATE()) > 7 THEN 'At Risk' ELSE 'On Track' END` | Supervisor |

---

### Use Case 2: Fraud Detection

**Scenario**: Risk analyst needs to identify potentially fraudulent claims.

**Questions:**
1. "Are there multiple claims from this customer in a short period?"
2. "Does the claim amount seem excessive for the damage type?"
3. "Are there known fraud patterns matching this claim?"
4. "What is the customer's overall risk score?"

**Recommended Bindings:**

#### On `fraud_indicators`

| Binding | Logic | Agent Use |
|---------|-------|-----------|
| `priority_score` | `CASE severity WHEN 'CRITICAL' THEN 4 WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 ELSE 1 END` | Risk Analyst |
| `requires_immediate_action` | `severity IN ('CRITICAL', 'HIGH') AND investigation_status = 'OPEN'` | Risk Analyst, Supervisor |
| `days_since_detection` | `DATEDIFF(day, detected_date, GETDATE())` | Risk Analyst |
| `is_aging_investigation` | `investigation_status = 'OPEN' AND DATEDIFF(day, detected_date, GETDATE()) > 30` | Supervisor |

#### On `claimant_profiles`

| Binding | Logic | Agent Use |
|---------|-------|-----------|
| `fraud_risk_tier` | `CASE WHEN risk_score > 80 THEN 'Extreme' WHEN risk_score > 60 THEN 'High' WHEN risk_score > 40 THEN 'Moderate' ELSE 'Low' END` | Risk Analyst |
| `claims_velocity` | `CASE WHEN total_claims_count > 10 THEN 'Very High' WHEN total_claims_count > 5 THEN 'High' WHEN total_claims_count > 2 THEN 'Moderate' ELSE 'Normal' END` | Risk Analyst |
| `avg_claim_vs_portfolio` | Compare `average_claim_amount` against portfolio average | Risk Analyst |

---

### Use Case 3: Customer Service & Communication

**Scenario**: Communication agent needs context to draft appropriate messages.

**Questions:**
1. "What is the current status of the customer's claim?"
2. "Is this a long-term or new customer?"
3. "Are there any special circumstances?"
4. "What documentation is missing?"

**Recommended Bindings:**

#### On `claimant_profiles`

| Binding | Logic | Agent Use |
|---------|-------|-----------|
| `customer_tier` | `CASE WHEN total_claims_amount > 100000 THEN 'Platinum' WHEN total_claims_amount > 50000 THEN 'Gold' WHEN total_claims_amount > 10000 THEN 'Silver' ELSE 'Standard' END` | Communication Agent |
| `relationship_length` | `DATEDIFF(year, customer_since, GETDATE())` | Communication Agent |
| `is_at_risk_customer` | `account_status = 'ACTIVE' AND risk_score > 60` | Communication Agent |
| `preferred_contact` | Based on available contact info (phone vs email) | Communication Agent |

#### On `claims_history`

| Binding | Logic | Agent Use |
|---------|-------|-----------|
| `missing_documentation_list` | `CONCAT(IIF(NOT police_report, 'Police Report, ', ''), IIF(NOT photos_provided, 'Photos, ', ''), IIF(witness_statements = '0', 'Witness Statement', ''))` | Communication Agent |
| `claim_status_friendly` | `CASE status WHEN 'PENDING' THEN 'Under Review' WHEN 'APPROVED' THEN 'Approved' WHEN 'DENIED' THEN 'Not Approved' WHEN 'SETTLED' THEN 'Completed' ELSE status END` | Communication Agent |
| `next_action_required` | Based on status and documentation | Communication Agent |

---

### Use Case 4: Regional & Portfolio Analysis

**Scenario**: Management needs insights on claims patterns across regions.

**Questions:**
1. "Which regions have the highest fraud rates?"
2. "What's our claims performance by state?"
3. "Are there seasonal patterns we should be aware of?"

**Recommended Bindings:**

#### On `regional_statistics`

| Binding | Logic | Agent Use |
|---------|-------|-----------|
| `fraud_risk_level` | `CASE WHEN fraud_rate > 10 THEN 'High Risk' WHEN fraud_rate > 5 THEN 'Elevated' ELSE 'Normal' END` | Claims Data Analyst |
| `is_high_volume_region` | `total_claims > 100` | Claims Data Analyst |
| `cost_category` | `CASE WHEN avg_claim_amount > 20000 THEN 'High Cost' WHEN avg_claim_amount > 10000 THEN 'Medium Cost' ELSE 'Low Cost' END` | Claims Data Analyst |

---

## Customer-Specific Use Cases

### High-Value Customer Handling

**Objective**: Provide enhanced service for valuable customers.

```
Binding: is_high_value_customer
Logic: total_claims_amount > 75000 
       OR (policy_count >= 3 AND account_status = 'ACTIVE')
       OR relationship_length > 10

Use: Trigger priority processing, personalized communication
```

### At-Risk Customer Identification

**Objective**: Identify customers who might churn or escalate.

```
Binding: customer_satisfaction_risk
Logic: 
  CASE 
    WHEN (pending_claims > 2 OR denied_claims > 0) 
         AND relationship_length > 5 THEN 'High Risk - Long-term Customer Frustrated'
    WHEN processing_time > 30 THEN 'At Risk - Slow Processing'
    WHEN claim_count_this_year > 3 THEN 'At Risk - Frequent Claimant'
    ELSE 'Normal'
  END

Use: Proactive outreach, escalation triggers
```

### Claims Complexity Assessment

**Objective**: Route complex claims appropriately.

```
Binding: claim_complexity
Logic:
  CASE
    WHEN estimated_damage > 50000 THEN 'Complex - High Value'
    WHEN fraud_flag = true THEN 'Complex - Fraud Review Required'
    WHEN claim_type IN ('Personal Injury', 'Liability') THEN 'Complex - Injury/Liability'
    WHEN witness_statements > 2 THEN 'Complex - Multiple Witnesses'
    ELSE 'Standard'
  END

Use: Supervisor routing, SLA assignment
```

---

## Binding Interactions Across Entities

Consider how bindings from different entities work together:

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLAIM PROCESSING DECISION                    │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌──────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ CLAIM BINDINGS   │  │CLAIMANT BINDINGS│  │ FRAUD BINDINGS  │
├──────────────────┤  ├─────────────────┤  ├─────────────────┤
│• claim_complexity│  │• customer_tier  │  │• priority_score │
│• doc_status      │  │• fraud_risk_tier│  │• requires_action│
│• severity        │  │• claims_velocity│  │• days_since_det │
└────────┬─────────┘  └────────┬────────┘  └────────┬────────┘
         │                     │                    │
         └─────────────────────┼────────────────────┘
                              ▼
                   ┌─────────────────────┐
                   │  COMBINED DECISION  │
                   ├─────────────────────┤
                   │ IF:                 │
                   │ • claim_complexity  │
                   │   = 'Complex'       │
                   │ • AND customer_tier │
                   │   = 'Platinum'      │
                   │ • AND priority_score│
                   │   >= 3              │
                   │                     │
                   │ THEN: Escalate to   │
                   │ Senior Adjuster     │
                   └─────────────────────┘
```

---

## Things to Consider

### Data Quality Dependencies

| Binding | Dependent Data | Risk if Missing |
|---------|---------------|-----------------|
| `documentation_status` | police_report, photos_provided, witness_statements | All nulls = "Missing" (may be correct or data issue) |
| `claim_age_days` | claim_date | Nulls break calculation |
| `fraud_risk_tier` | risk_score | Need default for new customers |

### Performance Considerations

| Binding Type | Performance Impact | Recommendation |
|--------------|-------------------|----------------|
| Simple conditionals | Low | Use freely |
| Date calculations | Low | Use freely |
| String operations | Medium | Limit complexity |
| Aggregations | High | Pre-compute if possible |
| Cross-entity lookups | High | Use relationships instead |

### Maintenance Burden

Consider who will maintain these bindings:
- **Business-owned**: Thresholds like "high value = $50K" may change
- **IT-owned**: Complex logic that requires testing
- **Shared**: SLA thresholds, risk scores

---

## Recommended Priority Implementation

### Phase 1: Core Operations (Implement First)
- [ ] `documentation_status` on claims_history
- [ ] `claim_age_days` on claims_history  
- [ ] `estimated_severity` on claims_history
- [ ] `is_high_risk` on claimant_profiles
- [ ] `requires_immediate_action` on fraud_indicators

### Phase 2: Customer Experience
- [ ] `customer_tier` on claimant_profiles
- [ ] `claim_status_friendly` on claims_history
- [ ] `missing_documentation_list` on claims_history
- [ ] `relationship_length` on claimant_profiles

### Phase 3: Advanced Analytics
- [ ] `claim_complexity` on claims_history
- [ ] `fraud_risk_tier` on claimant_profiles
- [ ] `processing_sla_status` on claims_history
- [ ] `claims_velocity` on claimant_profiles
- [ ] `priority_score` on fraud_indicators

### Phase 4: Regional Insights
- [ ] `fraud_risk_level` on regional_statistics
- [ ] `is_high_volume_region` on regional_statistics
- [ ] `cost_category` on regional_statistics

---

## Testing Your Bindings

For each binding, test with these query patterns:

```
1. Direct filter: "Show all [binding_value] claims"
   Example: "Show all high-value claims"

2. Aggregation: "How many claims are [binding_value]?"
   Example: "How many claims have complete documentation?"

3. Combined: "Show [binding_value] claims for [entity condition]"
   Example: "Show critical severity claims for high-risk customers"

4. Temporal: "Show [binding_value] claims from last month"
   Example: "Show stale claims from last month"
```

---

## Binding Template

Use this template when creating new bindings:

```yaml
Binding Name: [snake_case_name]
Entity: [entity_type_name]
Purpose: [One sentence description]
Logic: |
  [SQL/expression logic]
  
Business Owner: [Name/Role]
Used By Agents: [List of agents that use this]
Test Query: "[Sample natural language query]"
Expected Result: [What should return]
Dependencies: [Other bindings or data requirements]
Threshold Review: [Quarterly/Annually/Fixed]
```

---

*Last Updated: January 2026*
