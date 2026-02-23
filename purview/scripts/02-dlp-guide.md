# DLP Policy Guide for Fabric Workspaces

This guide covers creating and configuring **Data Loss Prevention (DLP) policies** for
Microsoft Fabric workspaces using both the Purview portal and PowerShell automation.

> **Context**: This is part of the Contoso Insurance data governance pipeline. Our
> custom classifications (`CONTOSO.INSURANCE.*`) have been applied to Fabric lakehouse
> columns via the Purview Atlas API. DLP policies protect Fabric items by detecting
> sensitivity labels and sensitive info types, then restricting access.

---

## Prerequisites

1. **Sensitivity labels created** in Information Protection → Labels:
   - **Highly Confidential** — PII, fraud data, risk scores
   - **Confidential** — financial amounts, identifiers
   - **General** — metadata, evidence flags
2. **Label scope**: Each label must have **"Files & other data assets"** enabled
3. **Licensing** — admin account must have one of:
   - Microsoft 365 E5
   - Microsoft 365 E5 Compliance
   - Microsoft 365 E5 Information Protection & Governance
4. **Fabric capacity** — DLP only works on workspaces hosted in Fabric or Premium capacity
5. **Admin role** — Compliance administrator, Security administrator, or Information
   Protection Admin

---

## Recommended DLP Policies

### Policy 1: Protect Highly Confidential Insurance Data

| Setting | Value |
|---------|-------|
| **Policy name** | `DLP - Highly Confidential Insurance Data` |
| **Template** | Custom policy |
| **Location** | Fabric and Power BI workspaces (all or specific) |
| **Condition** | Content contains → **Sensitivity labels** → Any of: |
| | `Highly Confidential` |
| **Action** | Restrict access — Block everyone except owner |
| **User notification** | Policy tip to data owner |
| **Severity** | High |

### Policy 2: Protect Confidential Insurance Data

| Setting | Value |
|---------|-------|
| **Policy name** | `DLP - Confidential Insurance Data` |
| **Template** | Custom policy |
| **Location** | Fabric and Power BI workspaces (all or specific) |
| **Condition** | Content contains → **Sensitivity labels** → Any of: |
| | `Confidential` |
| **Action** | Restrict access — Block people outside your organization |
| **User notification** | Policy tip to data owner |
| **Severity** | Medium |

### Policy 3: Detect Sensitive Info Types (alternative approach)

Match on **sensitive info types** directly (credit cards, SSNs found in lakehouse data):

| Setting | Value |
|---------|-------|
| **Policy name** | `DLP - PII Detection in Fabric` |
| **Template** | Custom policy |
| **Location** | Fabric and Power BI workspaces |
| **Condition** | Content contains → **Sensitive info types** → Any of: |
| | Credit Card Number (≥1 instance) |
| | U.S. Social Security Number (≥1 instance) |
| **Action** | Restrict access — Block everyone except owner |
| **User notification** | Policy tip + email to compliance admin |
| **Severity** | High |

---

## Step-by-Step: Create a DLP Policy (Portal)

1. Open **[Microsoft Purview portal](https://purview.microsoft.com)** →
   **Data Loss Prevention** → **Policies** → **+ Create policy**
2. Choose **Custom** category → **Custom policy** template → **Next**
3. Name the policy (e.g., `DLP - Highly Confidential Insurance Data`) → **Next**
4. Skip **Admin units** (not supported for Fabric DLP) → **Next**
5. **Location**: Select **Fabric and Power BI workspaces**
   - All other locations are automatically disabled
   - Optionally click **Edit** to include/exclude specific workspaces
   - Click **Next**
6. Choose **Create or customize advanced DLP rules** → **Next**
7. Click **Create rule**:
   - **Name**: `Detect Highly Confidential labels`
   - **Conditions**: Add condition → Content contains → Add → **Sensitivity labels**
     → Select `Highly Confidential`
   - **Actions**: Enable **Restrict access or encrypt the content** →
     Select "Block everyone" or "Block people outside your organization"
   - **User notifications**: Toggle ON → Enable **Policy tips**
   - **Incident reports**: Set severity to **High**, enable admin email alerts
   - Save the rule
8. Click **Next** → Review → **Submit**

---

## Automate DLP Policies via PowerShell

All three DLP policies can be created programmatically using Security & Compliance
PowerShell (`New-DlpCompliancePolicy` + `New-DlpComplianceRule`).

### Connect to Security & Compliance PowerShell

```powershell
# Install the Exchange Online Management module (includes SCC cmdlets)
Install-Module -Name ExchangeOnlineManagement -Scope CurrentUser

# Connect to Security & Compliance PowerShell
Connect-IPPSSession
```

### Step 1: Get Your Sensitivity Label GUIDs

```powershell
# List all labels with their GUIDs
Get-Label | Format-Table DisplayName, Name, Guid, Priority

# Store the GUIDs (replace with your actual values)
$highlyConfidentialGuid = "<your-highly-confidential-label-guid>"
$confidentialGuid       = "<your-confidential-label-guid>"
```

### Step 2: Create the DLP Policies

```powershell
# ── Policy 1: Highly Confidential Insurance Data ──────────────────────
New-DlpCompliancePolicy `
    -Name "DLP - Highly Confidential Insurance Data" `
    -Comment "Detects Highly Confidential sensitivity labels on Fabric items" `
    -PowerBIDlpLocation "All" `
    -Mode Enable

# Create the rule with sensitivity label condition
$advancedRule1 = @{
    Version   = "1.0"
    Condition = @{
        Operator      = "And"
        SubConditions = @(
            @{
                ConditionName = "ContentContainsSensitiveInformation"
                Value         = @(
                    @{
                        groups = @(
                            @{
                                Operator = "Or"
                                name     = "Default"
                                labels   = @(
                                    @{ name = $highlyConfidentialGuid; type = "Sensitivity" }
                                )
                            }
                        )
                    }
                )
            }
        )
    }
} | ConvertTo-Json -Depth 20

New-DlpComplianceRule `
    -Name "Detect Highly Confidential Labels" `
    -Policy "DLP - Highly Confidential Insurance Data" `
    -AdvancedRule $advancedRule1 `
    -RestrictAccess @(@{setting="ExcludeContentProcessing"; value="Block"}) `
    -NotifyUser @("SiteAdmin") `
    -GenerateAlert @("SiteAdmin") `
    -ReportSeverityLevel "High"


# ── Policy 2: Confidential Insurance Data ─────────────────────────────
New-DlpCompliancePolicy `
    -Name "DLP - Confidential Insurance Data" `
    -Comment "Detects Confidential sensitivity labels on Fabric items" `
    -PowerBIDlpLocation "All" `
    -Mode Enable

$advancedRule2 = @{
    Version   = "1.0"
    Condition = @{
        Operator      = "And"
        SubConditions = @(
            @{
                ConditionName = "ContentContainsSensitiveInformation"
                Value         = @(
                    @{
                        groups = @(
                            @{
                                Operator = "Or"
                                name     = "Default"
                                labels   = @(
                                    @{ name = $confidentialGuid; type = "Sensitivity" }
                                )
                            }
                        )
                    }
                )
            }
        )
    }
} | ConvertTo-Json -Depth 20

New-DlpComplianceRule `
    -Name "Detect Confidential Labels" `
    -Policy "DLP - Confidential Insurance Data" `
    -AdvancedRule $advancedRule2 `
    -RestrictAccess @(@{setting="ExcludeContentProcessing"; value="BlockExternalAccess"}) `
    -NotifyUser @("SiteAdmin") `
    -GenerateAlert @("SiteAdmin") `
    -ReportSeverityLevel "Medium"


# ── Policy 3: PII Detection (sensitive info types) ────────────────────
New-DlpCompliancePolicy `
    -Name "DLP - PII Detection in Fabric" `
    -Comment "Detects PII like credit cards and SSNs in Fabric items" `
    -PowerBIDlpLocation "All" `
    -Mode Enable

New-DlpComplianceRule `
    -Name "Detect PII in Fabric" `
    -Policy "DLP - PII Detection in Fabric" `
    -ContentContainsSensitiveInformation @(
        @{Name = "Credit Card Number"},
        @{Name = "U.S. Social Security Number (SSN)"}
    ) `
    -RestrictAccess @(@{setting="ExcludeContentProcessing"; value="Block"}) `
    -NotifyUser @("SiteAdmin") `
    -GenerateAlert @("SiteAdmin") `
    -ReportSeverityLevel "High"
```

### Step 3: Exclude Specific Workspaces (optional)

```powershell
# Create a policy that excludes dev/test workspaces
New-DlpCompliancePolicy `
    -Name "DLP - Prod Only" `
    -PowerBIDlpLocation "All" `
    -PowerBIDlpLocationException "workspace-guid-1","workspace-guid-2" `
    -Mode Enable
```

### Step 4: Verify Policies

```powershell
# List all DLP policies targeting Fabric
Get-DlpCompliancePolicy | Where-Object { $_.PowerBIDlpLocation } |
    Format-Table Name, Mode, Enabled

# List rules for a specific policy
Get-DlpComplianceRule -Policy "DLP - Highly Confidential Insurance Data" |
    Format-List Name, ContentContainsSensitiveInformation, RestrictAccess
```

---

## Classification-to-Label-to-DLP Mapping

| Classification | Sensitivity Label | DLP Policy |
|---|---|---|
| `CONTOSO.INSURANCE.CLAIMANT_NAME` | Highly Confidential | DLP - Highly Confidential |
| `CONTOSO.INSURANCE.LICENSE_PLATE` | Highly Confidential | DLP - Highly Confidential |
| `CONTOSO.INSURANCE.VEHICLE_INFO` | Highly Confidential | DLP - Highly Confidential |
| `CONTOSO.INSURANCE.RISK_SCORE` | Highly Confidential | DLP - Highly Confidential |
| `CONTOSO.INSURANCE.FRAUD_INDICATOR` | Highly Confidential | DLP - Highly Confidential |
| `CONTOSO.INSURANCE.FRAUD_SEVERITY` | Confidential | DLP - Confidential |
| `CONTOSO.INSURANCE.FINANCIAL_AMOUNT` | Confidential | DLP - Confidential |
| `CONTOSO.INSURANCE.CLAIM_ID` | Confidential | DLP - Confidential |
| `CONTOSO.INSURANCE.CLAIMANT_ID` | Confidential | DLP - Confidential |
| `CONTOSO.INSURANCE.POLICY_NUMBER` | Confidential | DLP - Confidential |
| `CONTOSO.INSURANCE.CLAIM_METADATA` | General | (no DLP restriction) |
| `CONTOSO.INSURANCE.EVIDENCE_FLAGS` | General | (no DLP restriction) |

---

## Important Notes

- Fabric DLP policies only support the **Custom** template (no predefined templates)
- DLP conditions can match on **sensitivity labels** or **built-in sensitive info types**
- Custom classifications (`CONTOSO.INSURANCE.*`) cannot be used as DLP conditions directly
- DLP actions only work for workspaces on **Fabric or Premium capacity**
- DLP evaluates lakehouses when data changes (new data, table updates, etc.)
- DLP evaluates semantic models on publish, republish, and refresh
- **User overrides**: Owners can override DLP restrictions with a business justification
- DLP policies for Fabric apply only to data in **Delta-format** tables
- Unsupported Delta types: binary, timestamp_ntz, struct, array, list, map, json

## References

- [Configure DLP policies for Fabric](https://learn.microsoft.com/en-us/fabric/governance/data-loss-prevention-configure)
- [DLP for Power BI — Get started](https://learn.microsoft.com/en-us/purview/dlp-powerbi-get-started)
- [New-DlpCompliancePolicy](https://learn.microsoft.com/en-us/powershell/module/exchange/new-dlpcompliancepolicy)
- [New-DlpComplianceRule](https://learn.microsoft.com/en-us/powershell/module/exchange/new-dlpcompliancerule)
- [Information protection in Microsoft Fabric](https://learn.microsoft.com/en-us/fabric/governance/information-protection)
