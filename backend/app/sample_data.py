#!/usr/bin/env python3
"""
Sample Insurance Claim Data

This module contains sample claim data for testing the multi-agent insurance claim processing system.
The claim IDs, policy numbers, and claimant IDs are aligned with the Fabric Lakehouse data:
- claims_history: claim_id format CLM-2026-NNNNNN, claimant_id format CLM-NNNN
- claimant_profiles: claimant_id format CLM-NNN
- policy_claims_summary: policy_number format POL-YYYY-NNN
"""

# Sample insurance claim data with Lakehouse-compatible IDs
# Using real claimant from claimant_profiles (CLM-001 = Christopher Brown, CA)
sample_claim = {
    "claim_id": "CLM-2026-000001",  # Matches claims_history format
    "policy_number": "POL-2025-914",  # Matches policy_claims_summary
    "claimant_id": "CLM-1310",  # Matches claims_history claimant_id format
    "claimant_name": "Linda Ramirez",  # From claims_history row 1
    "incident_date": "2025-05-22",
    "claim_type": "Major Collision",  # Matches claims_history claim_type
    "description": "Rear-end collision at intersection. Vehicle sustained damage to rear bumper, trunk, and tail lights. No injuries reported.",
    "estimated_damage": 28392.64,  # From claims_history
    "location": "Los Angeles, CA",
    "police_report": True,
    "photos_provided": True,
    "witness_statements": "0",
    "state": "CA",
    "vehicle_info": {
        "vin": "1HGBH41JXMN109186",
        "make": "Honda",
        "model": "Civic",
        "year": 2021,
        "license_plate": "ABC123"
    },
    "supporting_images": [
        "workflow/data/claims/invoice.png",
        "workflow/data/claims/crash2.jpg"
    ]
}

# High-value claim - using claimant CLM-1099 (William Gonzalez) from claims_history
high_value_claim = {
    "claim_id": "CLM-2026-000002",
    "policy_number": "POL-2021-722",  # Matches policy_claims_summary
    "claimant_id": "CLM-1099",
    "claimant_name": "William Gonzalez",
    "incident_date": "2025-05-09",
    "claim_type": "Property Damage",
    "description": "Multi-vehicle accident on highway during rush hour. Extensive front-end damage, airbag deployment.",
    "estimated_damage": 41982.02,
    "location": "LA City, LA",
    "police_report": True,
    "photos_provided": True,
    "witness_statements": "2",
    "state": "LA",
    "vehicle_info": {
        "vin": "1HGBH41JXMN109186",
        "make": "Honda",
        "model": "Civic",
        "year": 2021,
        "license_plate": "ABC123"
    }
}

# Auto accident claim - using claimant CLM-470 (Mary White) from claims_history
auto_accident_claim = {
    "claim_id": "CLM-2026-000003",
    "policy_number": "POL-2021-672",
    "claimant_id": "CLM-470",
    "claimant_name": "Mary White",
    "incident_date": "2025-11-13",
    "claim_type": "Auto Accident",
    "description": "Aanrijding met een andere auto tijdens het uitparkeren. Vehicle collision in parking lot with moderate damage.",
    "estimated_damage": 7907.52,
    "location": "Tampa, FL",
    "police_report": True,
    "photos_provided": True,
    "witness_statements": "3",
    "state": "FL",
    "vehicle_info": {
        "vin": "WVWZZZ1JZXW123456",
        "make": "Volkswagen",
        "model": "Golf",
        "year": 2022,
        "license_plate": "12-ABC-3"
    }
}

# Fire damage claim - using claimant CLM-1569 (Betty Thompson) from claims_history
fire_damage_claim = {
    "claim_id": "CLM-2026-000005",
    "policy_number": "POL-2023-988",
    "claimant_id": "CLM-1569",
    "claimant_name": "Betty Thompson",
    "incident_date": "2025-04-25",
    "claim_type": "Fire Damage",
    "description": "Kitchen fire caused significant damage. Fire started from electrical fault in kitchen appliances.",
    "estimated_damage": 41374.12,
    "location": "Cincinnati, OH",
    "police_report": False,
    "photos_provided": True,
    "witness_statements": "1",
    "state": "OH",
    "vehicle_info": None
}

# List of all sample claims for easy access
ALL_SAMPLE_CLAIMS = [sample_claim, high_value_claim, auto_accident_claim, fire_damage_claim]
