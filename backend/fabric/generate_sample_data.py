#!/usr/bin/env python3
"""
Generate Sample Insurance Claims Data for Microsoft Fabric Lakehouse.

This script creates synthetic insurance claims data that mimics real-world patterns
for testing the Claims Data Analyst agent with Fabric Data Agent integration.

The generated data includes:
- claims_history: 10,000+ historical claim records
- claimant_profiles: 2,000+ customer profiles
- fraud_indicators: 500+ fraud pattern records
- regional_statistics: 200+ regional data points
- policy_claims_summary: 3,000+ policy summaries

Usage:
    python generate_sample_data.py [--output-dir ./data] [--seed 42]
"""

import argparse
import os
import random
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import numpy as np

# Set random seed for reproducibility
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CLAIM_TYPES = [
    "Auto Collision", "Auto Accident", "Auto Theft", "Major Collision",
    "Property Damage", "Property Theft", "Comprehensive",
    "Water Damage", "Fire Damage", "Hail Damage", "Vandalism",
    "Personal Injury", "Liability", "Medical", "Ruitschade"
]

CLAIM_STATUSES = ["APPROVED", "DENIED", "PENDING", "UNDER_REVIEW", "SETTLED", "CLOSED"]

# Vehicle makes and models for realistic data
VEHICLE_MAKES = {
    "Honda": ["Civic", "Accord", "CR-V", "Pilot", "Odyssey"],
    "Toyota": ["Camry", "Corolla", "RAV4", "Highlander", "Prius"],
    "Ford": ["F-150", "Escape", "Explorer", "Mustang", "Focus"],
    "Chevrolet": ["Silverado", "Equinox", "Malibu", "Tahoe", "Camaro"],
    "Volkswagen": ["Golf", "Jetta", "Passat", "Tiguan", "Atlas"],
    "BMW": ["3 Series", "5 Series", "X3", "X5", "M3"],
    "Mercedes": ["C-Class", "E-Class", "GLE", "GLC", "S-Class"],
    "Nissan": ["Altima", "Sentra", "Rogue", "Pathfinder", "Maxima"],
    "Hyundai": ["Elantra", "Sonata", "Tucson", "Santa Fe", "Kona"],
    "Kia": ["Forte", "Optima", "Sportage", "Sorento", "Telluride"],
}

STATES = [
    "CA", "TX", "FL", "NY", "PA", "IL", "OH", "GA", "NC", "MI",
    "NJ", "VA", "WA", "AZ", "MA", "TN", "IN", "MO", "MD", "WI",
    "CO", "MN", "SC", "AL", "LA", "KY", "OR", "OK", "CT", "UT"
]

CITIES = {
    "CA": ["Los Angeles", "San Francisco", "San Diego", "Sacramento", "San Jose"],
    "TX": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth"],
    "FL": ["Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale"],
    "NY": ["New York", "Buffalo", "Rochester", "Albany", "Syracuse"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading"],
    "IL": ["Chicago", "Aurora", "Naperville", "Joliet", "Rockford"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron"],
    "GA": ["Atlanta", "Augusta", "Savannah", "Columbus", "Macon"],
    "NC": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem"],
    "MI": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor"],
}

REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West", "Northwest"]

FRAUD_INDICATOR_TYPES = [
    "Multiple Claims Short Period", "Excessive Claim Amount",
    "Inconsistent Documentation", "Staged Accident Pattern",
    "Previous Fraud History", "Suspicious Timing",
    "Witness Inconsistency", "Medical Bill Padding",
    "Phantom Damage", "Policyholder Collusion"
]

FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "William", "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
    "Thomas", "Sarah", "Charles", "Karen", "Christopher", "Nancy", "Daniel", "Lisa",
    "Matthew", "Betty", "Anthony", "Margaret", "Mark", "Sandra"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson"
]


# ---------------------------------------------------------------------------
# Data Generation Functions
# ---------------------------------------------------------------------------

def generate_claimant_profiles(n: int = 2000, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Generate synthetic claimant profiles matching the app's claimant data structure."""
    random.seed(seed)
    np.random.seed(seed)
    
    profiles = []
    for i in range(n):
        claimant_id = f"CLM-{i+1:03d}"  # Match app format: CLM-001
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        state = random.choice(STATES)
        city = random.choice(CITIES.get(state, [f"{state} City"]))
        
        # Customer tenure affects risk
        customer_since = datetime.now() - timedelta(days=random.randint(30, 3650))
        tenure_years = (datetime.now() - customer_since).days / 365
        
        # Generate correlated data
        base_claims = random.randint(0, 15)
        total_claims_count = base_claims
        avg_claim = random.uniform(1000, 15000)
        total_claims_amount = round(base_claims * avg_claim, 2) if base_claims > 0 else 0
        
        # Risk factors (matching your app's structure)
        claim_frequency = random.choices(
            ["very_low", "low", "moderate", "high"],
            weights=[0.3, 0.4, 0.2, 0.1]
        )[0]
        credit_score = random.choices(
            ["excellent", "good", "fair", "poor"],
            weights=[0.25, 0.45, 0.20, 0.10]
        )[0]
        driving_record = random.choices(
            ["clean", "minor_violations", "major_violations", "suspended"],
            weights=[0.6, 0.25, 0.12, 0.03]
        )[0]
        
        # Risk score based on multiple factors
        risk_score = min(100, max(0, 
            30 + 
            (total_claims_count * 5) +
            (random.gauss(0, 15)) +
            (-tenure_years * 2) +
            (20 if driving_record == "major_violations" else 0) +
            (10 if credit_score == "poor" else 0)
        ))
        
        # Contact info
        phone = f"555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
        email = f"{first_name.lower()}.{last_name.lower()}@email.com"
        address = f"{random.randint(100, 9999)} {random.choice(['Main', 'Oak', 'Maple', 'Cedar', 'Pine', 'Elm'])} {random.choice(['St', 'Ave', 'Blvd', 'Dr', 'Ln'])}, {city}, {state} {random.randint(10000, 99999)}"
        
        profiles.append({
            "claimant_id": claimant_id,
            "name": f"{first_name} {last_name}",
            "age": random.randint(18, 85),
            "state": state,
            "city": city,
            "address": address,
            "phone": phone,
            "email": email,
            "customer_since": customer_since.strftime("%Y-%m-%d"),
            "total_claims_count": total_claims_count,
            "total_claims_amount": total_claims_amount,
            "average_claim_amount": round(avg_claim, 2) if base_claims > 0 else 0,
            "risk_score": round(risk_score, 2),
            "claim_frequency": claim_frequency,
            "credit_score": credit_score,
            "driving_record": driving_record,
            "policy_count": random.randint(1, 5),
            "account_status": random.choices(
                ["ACTIVE", "SUSPENDED", "CLOSED"],
                weights=[0.85, 0.10, 0.05]
            )[0]
        })
    
    return pd.DataFrame(profiles)


def generate_claims_history(
    claimant_profiles: pd.DataFrame,
    n: int = 10000,
    seed: int = RANDOM_SEED
) -> pd.DataFrame:
    """Generate synthetic claims history based on claimant profiles."""
    random.seed(seed)
    np.random.seed(seed)
    
    claims = []
    claimant_ids = claimant_profiles["claimant_id"].tolist()
    
    for i in range(n):
        claim_id = f"CLM-{datetime.now().year}-{i+1:06d}"
        claimant_id = random.choice(claimant_ids)
        claimant = claimant_profiles[claimant_profiles["claimant_id"] == claimant_id].iloc[0]
        
        # Generate dates
        incident_date = datetime.now() - timedelta(days=random.randint(1, 1095))  # Last 3 years
        claim_date = incident_date + timedelta(days=random.randint(0, 14))
        
        # Status and settlement
        status = random.choices(
            CLAIM_STATUSES,
            weights=[0.40, 0.12, 0.15, 0.08, 0.10, 0.15]
        )[0]
        
        settlement_date = None
        amount_paid = None
        if status in ["APPROVED", "SETTLED", "CLOSED"]:
            settlement_date = claim_date + timedelta(days=random.randint(7, 90))
        
        # Claim amount based on type
        claim_type = random.choice(CLAIM_TYPES)
        base_amounts = {
            "Auto Collision": (2000, 25000),
            "Auto Accident": (2000, 30000),
            "Auto Theft": (5000, 40000),
            "Major Collision": (15000, 75000),
            "Property Damage": (3000, 50000),
            "Property Theft": (1000, 30000),
            "Liability": (5000, 100000),
            "Medical": (500, 75000),
            "Comprehensive": (500, 15000),
            "Personal Injury": (2000, 150000),
            "Water Damage": (2000, 40000),
            "Fire Damage": (10000, 200000),
            "Hail Damage": (1000, 15000),
            "Vandalism": (500, 10000),
            "Ruitschade": (200, 2500),
        }
        min_amt, max_amt = base_amounts.get(claim_type, (1000, 20000))
        estimated_damage = round(random.uniform(min_amt, max_amt), 2)
        
        # Amount paid (if settled/approved) - usually less than estimated
        if status in ["APPROVED", "SETTLED", "CLOSED"]:
            amount_paid = round(estimated_damage * random.uniform(0.7, 1.0), 2)
        
        # Fraud flag - correlated with risk score
        fraud_probability = claimant["risk_score"] / 500  # Higher risk = higher fraud chance
        fraud_flag = random.random() < fraud_probability
        
        # Policy number - match your app's format
        policy_types = ["AUTO", "HOME", "COMM"]
        policy_type = random.choice(policy_types)
        policy_number = f"POL-{random.randint(2020, 2025)}-{random.randint(1, 999):03d}"
        
        # Generate vehicle info for auto claims
        vehicle_make = random.choice(list(VEHICLE_MAKES.keys()))
        vehicle_model = random.choice(VEHICLE_MAKES[vehicle_make])
        vehicle_year = random.randint(2015, 2025)
        vin = ''.join(random.choices('0123456789ABCDEFGHJKLMNPRSTUVWXYZ', k=17))
        license_plate = f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=3))}{random.randint(100, 999)}"
        
        # Documentation flags (matching your app's fields)
        police_report = random.choices([True, False], weights=[0.7, 0.3])[0]
        photos_provided = random.choices([True, False], weights=[0.8, 0.2])[0]
        witness_count = random.choices([0, 1, 2, 3], weights=[0.3, 0.4, 0.2, 0.1])[0]
        
        claims.append({
            "claim_id": claim_id,
            "policy_number": policy_number,
            "claimant_id": claimant_id,
            "claimant_name": claimant["name"],
            "claim_type": claim_type,
            "estimated_damage": estimated_damage,
            "amount_paid": amount_paid,
            "claim_date": claim_date.strftime("%Y-%m-%d"),
            "incident_date": incident_date.strftime("%Y-%m-%d"),
            "settlement_date": settlement_date.strftime("%Y-%m-%d") if settlement_date else None,
            "status": status,
            "location": f"{claimant['city']}, {claimant['state']}",
            "state": claimant["state"],
            "description": f"{claim_type} incident reported at {claimant['city']}. {random.choice(['Minor damage reported.', 'Significant damage to vehicle.', 'Multiple vehicles involved.', 'Single vehicle incident.', 'Weather-related incident.', 'Parking lot incident.'])}",
            "police_report": police_report,
            "photos_provided": photos_provided,
            "witness_statements": str(witness_count) if witness_count > 0 else "0",
            "vehicle_vin": vin if "Auto" in claim_type or "Collision" in claim_type else None,
            "vehicle_make": vehicle_make if "Auto" in claim_type or "Collision" in claim_type else None,
            "vehicle_model": vehicle_model if "Auto" in claim_type or "Collision" in claim_type else None,
            "vehicle_year": vehicle_year if "Auto" in claim_type or "Collision" in claim_type else None,
            "license_plate": license_plate if "Auto" in claim_type or "Collision" in claim_type else None,
            "fraud_flag": fraud_flag
        })
    
    return pd.DataFrame(claims)


def generate_fraud_indicators(
    claims_history: pd.DataFrame,
    seed: int = RANDOM_SEED
) -> pd.DataFrame:
    """Generate fraud indicator records for flagged claims."""
    random.seed(seed)
    
    fraud_claims = claims_history[claims_history["fraud_flag"] == True]
    indicators = []
    
    for idx, claim in fraud_claims.iterrows():
        # Each fraud claim can have multiple indicators
        num_indicators = random.randint(1, 3)
        
        for i in range(num_indicators):
            indicator_id = f"FRD-{len(indicators)+1:06d}"
            indicator_type = random.choice(FRAUD_INDICATOR_TYPES)
            
            descriptions = {
                "Multiple Claims Short Period": f"Claimant filed {random.randint(3, 8)} claims within {random.randint(30, 90)} days",
                "Excessive Claim Amount": f"Claim amount ${claim['estimated_damage']:,.2f} exceeds typical range by {random.randint(50, 200)}%",
                "Inconsistent Documentation": "Documentation shows inconsistencies in dates and damage descriptions",
                "Staged Accident Pattern": "Incident characteristics match known staged accident patterns",
                "Previous Fraud History": f"Claimant has {random.randint(1, 3)} previous fraud flags on record",
                "Suspicious Timing": f"Claim filed {random.randint(1, 5)} days after policy inception/modification",
                "Witness Inconsistency": "Witness statements contain conflicting information",
                "Medical Bill Padding": f"Medical bills inflated by estimated {random.randint(30, 100)}%",
                "Phantom Damage": "Claimed damage not consistent with incident type",
                "Policyholder Collusion": "Evidence suggests coordination between parties",
            }
            
            indicators.append({
                "indicator_id": indicator_id,
                "claim_id": claim["claim_id"],
                "indicator_type": indicator_type,
                "severity": random.choices(
                    ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                    weights=[0.2, 0.35, 0.30, 0.15]
                )[0],
                "detected_date": (
                    datetime.strptime(claim["claim_date"], "%Y-%m-%d") + 
                    timedelta(days=random.randint(1, 30))
                ).strftime("%Y-%m-%d"),
                "pattern_description": descriptions.get(indicator_type, f"{indicator_type} detected"),
                "investigation_status": random.choices(
                    ["OPEN", "CLOSED", "CONFIRMED"],
                    weights=[0.4, 0.35, 0.25]
                )[0]
            })
    
    return pd.DataFrame(indicators)


def generate_regional_statistics(
    claims_history: pd.DataFrame,
    seed: int = RANDOM_SEED
) -> pd.DataFrame:
    """Generate regional statistics aggregated from claims data."""
    random.seed(seed)
    
    stats = []
    
    for state in STATES:
        state_claims = claims_history[claims_history["state"] == state]
        cities = CITIES.get(state, [f"{state} Metro"])
        region = random.choice(REGIONS)
        
        for city in cities:
            city_claims = state_claims[state_claims["location"].str.contains(city, na=False)]
            
            if len(city_claims) > 0:
                avg_amount = city_claims["estimated_damage"].mean()
                fraud_count = city_claims["fraud_flag"].sum()
                fraud_rate = (fraud_count / len(city_claims)) * 100
            else:
                avg_amount = random.uniform(3000, 15000)
                fraud_rate = random.uniform(1, 8)
            
            # Most common claim type
            if len(city_claims) > 0:
                common_type = city_claims["claim_type"].mode()
                most_common = common_type.iloc[0] if len(common_type) > 0 else random.choice(CLAIM_TYPES)
            else:
                most_common = random.choice(CLAIM_TYPES)
            
            stats.append({
                "region": region,
                "state": state,
                "city": city,
                "avg_claim_amount": round(avg_amount, 2),
                "claim_frequency": round(random.uniform(5, 50), 2),  # Claims per 1000 policies
                "fraud_rate": round(fraud_rate, 2),
                "most_common_claim_type": most_common,
                "seasonal_peak": random.choice(["Winter", "Spring", "Summer", "Fall"]),
                "total_claims": len(city_claims) if len(city_claims) > 0 else random.randint(10, 500),
                "year": datetime.now().year
            })
    
    return pd.DataFrame(stats)


def generate_policy_claims_summary(
    claims_history: pd.DataFrame,
    seed: int = RANDOM_SEED
) -> pd.DataFrame:
    """Generate policy-level claims summaries."""
    random.seed(seed)
    
    # Convert claim_date to datetime for proper sorting
    claims_history = claims_history.copy()
    claims_history["claim_date_dt"] = pd.to_datetime(claims_history["claim_date"])
    
    summaries = []
    policies = claims_history["policy_number"].unique()
    
    for policy in policies:
        policy_claims = claims_history[claims_history["policy_number"] == policy]
        approved_claims = policy_claims[policy_claims["status"].isin(["APPROVED", "SETTLED"])]
        
        total_claims = len(policy_claims)
        total_amount_paid = approved_claims["estimated_damage"].sum() if len(approved_claims) > 0 else 0
        avg_claim_amount = policy_claims["estimated_damage"].mean() if total_claims > 0 else 0
        
        # Determine trend using datetime column for sorting
        if total_claims >= 3:
            recent = policy_claims.nlargest(total_claims // 2, "claim_date_dt")["estimated_damage"].mean()
            older = policy_claims.nsmallest(total_claims // 2, "claim_date_dt")["estimated_damage"].mean()
            if recent > older * 1.2:
                trend = "INCREASING"
            elif recent < older * 0.8:
                trend = "DECREASING"
            else:
                trend = "STABLE"
        else:
            trend = "INSUFFICIENT_DATA"
        
        # Extract policy type from policy number
        policy_type = "AUTO"
        if "HOME" in policy:
            policy_type = "HOME"
        elif "COMM" in policy:
            policy_type = "COMMERCIAL"
        elif "LIFE" in policy:
            policy_type = "LIFE"
        
        summaries.append({
            "policy_number": policy,
            "total_claims": total_claims,
            "total_amount_paid": round(total_amount_paid, 2),
            "avg_claim_amount": round(avg_claim_amount, 2),
            "last_claim_date": policy_claims["claim_date"].max(),
            "first_claim_date": policy_claims["claim_date"].min(),
            "claims_trend": trend,
            "policy_type": policy_type,
            "fraud_claims_count": policy_claims["fraud_flag"].sum()
        })
    
    return pd.DataFrame(summaries)


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate sample insurance claims data for Fabric Lakehouse"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./data",
        help="Output directory for generated CSV files"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=RANDOM_SEED,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--num-claimants",
        type=int,
        default=2000,
        help="Number of claimant profiles to generate"
    )
    parser.add_argument(
        "--num-claims",
        type=int,
        default=10000,
        help="Number of claim records to generate"
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 Generating sample insurance claims data...")
    print(f"   Output directory: {output_dir.absolute()}")
    print(f"   Random seed: {args.seed}")
    print()
    
    # Generate data in dependency order
    print("1️⃣  Generating claimant profiles...")
    claimant_profiles = generate_claimant_profiles(n=args.num_claimants, seed=args.seed)
    claimant_profiles.to_csv(output_dir / "claimant_profiles.csv", index=False)
    print(f"   ✅ Generated {len(claimant_profiles)} claimant profiles")
    
    print("2️⃣  Generating claims history...")
    claims_history = generate_claims_history(claimant_profiles, n=args.num_claims, seed=args.seed)
    claims_history.to_csv(output_dir / "claims_history.csv", index=False)
    print(f"   ✅ Generated {len(claims_history)} claim records")
    print(f"      - Fraud flags: {claims_history['fraud_flag'].sum()}")
    
    print("3️⃣  Generating fraud indicators...")
    fraud_indicators = generate_fraud_indicators(claims_history, seed=args.seed)
    fraud_indicators.to_csv(output_dir / "fraud_indicators.csv", index=False)
    print(f"   ✅ Generated {len(fraud_indicators)} fraud indicator records")
    
    print("4️⃣  Generating regional statistics...")
    regional_stats = generate_regional_statistics(claims_history, seed=args.seed)
    regional_stats.to_csv(output_dir / "regional_statistics.csv", index=False)
    print(f"   ✅ Generated {len(regional_stats)} regional statistics records")
    
    print("5️⃣  Generating policy claims summaries...")
    policy_summaries = generate_policy_claims_summary(claims_history, seed=args.seed)
    policy_summaries.to_csv(output_dir / "policy_claims_summary.csv", index=False)
    print(f"   ✅ Generated {len(policy_summaries)} policy summary records")
    
    print()
    print("=" * 60)
    print("✅ Data generation complete!")
    print("=" * 60)
    print()
    print("Generated files:")
    for f in output_dir.glob("*.csv"):
        size_kb = f.stat().st_size / 1024
        print(f"   📄 {f.name} ({size_kb:.1f} KB)")
    print()
    print("Next steps:")
    print("   1. Review the generated CSV files")
    print("   2. Run 'python upload_to_fabric.py' to upload to your Lakehouse")
    print("   3. Create a Fabric Data Agent in your workspace")
    print("   4. Configure the connection in Azure AI Foundry")


if __name__ == "__main__":
    main()
