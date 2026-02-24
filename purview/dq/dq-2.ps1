<#
Purview Unified Catalog - Data Quality Rules (Public Preview API)
API version: 2025-09-01-preview

Operations:
- List rules (GET)
- Create rule (PUT)
- Update rule (PATCH)
- Delete rule (DELETE)

Docs:
GET  .../rules?api-version=2025-09-01-preview
PUT  .../rules/{ruleId}?api-version=2025-09-01-preview
PATCH.../rules/{ruleId}?api-version=2025-09-01-preview
#>

# -----------------------------
# Prereqs
# -----------------------------
# Sign in once per session (device-code is VS Code friendly)
az login --use-device-code | Out-Null

# -----------------------------
# Helpers
# -----------------------------
function Get-TenantId {
    return (az account show --query tenantId -o tsv).Trim()
}

function Get-PurviewToken {
    # Token scope/resource for Purview data plane
    return (az account get-access-token --resource "https://purview.azure.net" --query accessToken -o tsv).Trim()
}

function Invoke-PurviewRequest {
    param(
        [Parameter(Mandatory=$true)][ValidateSet("GET","PUT","PATCH","DELETE")] [string]$Method,
        [Parameter(Mandatory=$true)][string]$Url,
        [Parameter(Mandatory=$false)][object]$Body = $null
    )

    $token = Get-PurviewToken
    $headers = @{
        Authorization = "Bearer $token"
        "Content-Type" = "application/json"
    }

    Write-Host "  -> $Method $Url" -ForegroundColor DarkGray

    try {
        if ($null -ne $Body) {
            $json = $Body | ConvertTo-Json -Depth 10
            return Invoke-RestMethod -UseBasicParsing -Method $Method -Uri $Url -Headers $headers -Body $json
        } else {
            return Invoke-RestMethod -UseBasicParsing -Method $Method -Uri $Url -Headers $headers
        }
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        $errorBody  = $_.ErrorDetails.Message
        Write-Host "  !! HTTP $statusCode" -ForegroundColor Red
        if ($errorBody) { Write-Host "  !! $errorBody" -ForegroundColor Red }
        throw
    }
}

function Build-BaseRulesUrl {
    param(
        [Parameter(Mandatory=$true)][string]$Endpoint,
        [Parameter(Mandatory=$true)][string]$BusinessDomainId,
        [Parameter(Mandatory=$true)][string]$DataProductId,
        [Parameter(Mandatory=$true)][string]$DataAssetId,
        [Parameter(Mandatory=$true)][string]$ApiVersion
    )

    return ('{0}/datagovernance/quality/business-domains/{1}/data-products/{2}/data-assets/{3}/rules?api-version={4}' -f $Endpoint, $BusinessDomainId, $DataProductId, $DataAssetId, $ApiVersion)
}

function Build-RuleUrl {
    param(
        [Parameter(Mandatory=$true)][string]$Endpoint,
        [Parameter(Mandatory=$true)][string]$BusinessDomainId,
        [Parameter(Mandatory=$true)][string]$DataProductId,
        [Parameter(Mandatory=$true)][string]$DataAssetId,
        [Parameter(Mandatory=$true)][string]$RuleId,
        [Parameter(Mandatory=$true)][string]$ApiVersion
    )

    return ('{0}/datagovernance/quality/business-domains/{1}/data-products/{2}/data-assets/{3}/rules/{4}?api-version={5}' -f $Endpoint, $BusinessDomainId, $DataProductId, $DataAssetId, $RuleId, $ApiVersion)
}

# -----------------------------
# Main
# -----------------------------
$apiVersion = "2025-09-01-preview"

$tenantId = Get-TenantId
Write-Host "Tenant ID: $tenantId"

# Keep your existing endpoint style; adjust if your org uses a different base endpoint.
$endpoint = "https://$tenantId-api.purview-service.microsoft.com"
Write-Host "Purview Endpoint: $endpoint"

$businessDomainId  = Read-Host -Prompt "Enter Business Domain ID (GUID)"
$dataProductId     = Read-Host -Prompt "Enter Data Product ID (GUID)"
$dataAssetId       = Read-Host -Prompt "Enter Data Asset ID (GUID)"

# 1) List existing rules (GET)
$rulesUrl = Build-BaseRulesUrl -Endpoint $endpoint -BusinessDomainId $businessDomainId -DataProductId $dataProductId -DataAssetId $dataAssetId -ApiVersion $apiVersion
Write-Host "`nListing existing rules..."
$existingRules = Invoke-PurviewRequest -Method "GET" -Url $rulesUrl
$existingRules | Select-Object id, name, type, status, typeProperties | ConvertTo-Json -Depth 10

# Menu
$action = Read-Host -Prompt "`nChoose action: (C)reate, (U)pdate, (D)elete, (Q)uit"

switch ($action.ToUpper()) {

    # -----------------------------
    # CREATE (PUT)
    # -----------------------------
    "C" {
        $allowedTypes = @("Timeliness","Duplicate","NotNull","Unique","TypeMatch","Regex","CustomTruth")
        $type = Read-Host -Prompt ("Enter rule type (" + ($allowedTypes -join ", ") + ")")
        if ($type -notin $allowedTypes) { throw "Invalid type. Allowed: $($allowedTypes -join ', ')" }

        $ruleId = [guid]::NewGuid().ToString()

        $name = Read-Host -Prompt "Enter rule name (or press Enter for default)"
        $description = Read-Host -Prompt "Enter rule description (optional)"
        $status = "Active"

        $typeProps = @{}

        switch ($type) {
            "Timeliness" {
                $ms = Read-Host -Prompt "Enter time difference in milliseconds (e.g., 2592000000 for 30 days)"
                if (-not $name) { $name = "Freshness" }
                $typeProps = @{ timeDifference = [long]$ms }
            }

            "Duplicate" {
                $cols = Read-Host -Prompt "Enter logical column names (comma-separated) used to detect duplicates"
                $colList = $cols -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }

                if ($colList.Count -lt 1) { throw "Duplicate rule requires at least one column." }

                if (-not $name) { $name = "Duplicate_rows_" + ($colList -join "_") }

                $typeProps = @{ columns = @() }
                foreach ($c in $colList) {
                    $typeProps.columns += @{ type = "Column"; value = $c }
                }
            }

            "NotNull" {
                $col = Read-Host -Prompt "Enter logical column name that must not be empty"
                if (-not $name) { $name = "Empty/blank_fields_$col" }
                $typeProps = @{ column = @{ type = "Column"; value = $col } }
            }

            "Unique" {
                $col = Read-Host -Prompt "Enter logical column name that must be unique"
                if (-not $name) { $name = "Unique_values_$col" }
                $typeProps = @{ column = @{ type = "Column"; value = $col } }
            }

            "TypeMatch" {
                $col = Read-Host -Prompt "Enter logical column name for type validation"
                if (-not $name) { $name = "Data_type_match_$col" }
                # API examples show just the column reference for TypeMatch
                $typeProps = @{ column = @{ type = "Column"; value = $col } }
            }

            "Regex" {
                $col = Read-Host -Prompt "Enter logical column name to validate with regex"
                $pattern = Read-Host -Prompt "Enter regex pattern"
                if (-not $name) { $name = "String_format_match_$col" }
                $typeProps = @{
                    column  = @{ type = "Column"; value = $col }
                    pattern = $pattern
                }
            }

            "CustomTruth" {
                # Custom rule expressions (GUI-like): condition / filterCriteria / emptyCriteria
                # condition = row expression
                # filterCriteria = optional filter expression
                # emptyCriteria = optional null/empty expression
                $condition = Read-Host -Prompt "Enter condition (row expression), e.g. (Amount > 0 AND Country IS NOT NULL)"
                $filter    = Read-Host -Prompt "Enter filterCriteria (optional), e.g. (Status = 'Active')"
                $empty     = Read-Host -Prompt "Enter emptyCriteria (optional), e.g. (Amount IS NULL)"

                if (-not $name) { $name = "Custom_rule_$ruleId" }

                $typeProps = @{ condition = $condition }
                if (-not [string]::IsNullOrWhiteSpace($filter)) { $typeProps.filterCriteria = $filter }
                if (-not [string]::IsNullOrWhiteSpace($empty))  { $typeProps.emptyCriteria  = $empty }
            }
        }

        $ruleUrl = Build-RuleUrl -Endpoint $endpoint -BusinessDomainId $businessDomainId -DataProductId $dataProductId -DataAssetId $dataAssetId -RuleId $ruleId -ApiVersion $apiVersion

        $body = @{
            id = $ruleId
            name = $name
            description = $description
            type = $type
            status = $status
            typeProperties = $typeProps
            businessDomain = @{ referenceId = $businessDomainId; type = "BusinessDomainReference" }
            dataProduct    = @{ referenceId = $dataProductId;    type = "DataProductReference" }
            dataAsset      = @{ referenceId = $dataAssetId;      type = "DataAssetReference" }
        }

        Write-Host "`nCreating rule via PUT..."
        $resp = Invoke-PurviewRequest -Method "PUT" -Url $ruleUrl -Body $body
        $resp | ConvertTo-Json -Depth 10
    }

    # -----------------------------
    # UPDATE (PATCH)
    # -----------------------------
    "U" {
        $ruleId = Read-Host -Prompt "Enter ruleId (GUID) to update"
        $ruleUrl = Build-RuleUrl -Endpoint $endpoint -BusinessDomainId $businessDomainId -DataProductId $dataProductId -DataAssetId $dataAssetId -RuleId $ruleId -ApiVersion $apiVersion

        $newName = Read-Host -Prompt "Enter new name (optional)"
        $newDesc = Read-Host -Prompt "Enter new description (optional)"
        $newStatus = Read-Host -Prompt "Enter new status (optional, e.g., Active/Inactive)"

        # If you need to update expressions/properties, paste JSON for typeProperties
        $typePropsJson = Read-Host -Prompt "Enter typeProperties as JSON (optional; press Enter to skip)"
        $patchBody = @{}

        if (-not [string]::IsNullOrWhiteSpace($newName))   { $patchBody.name = $newName }
        if (-not [string]::IsNullOrWhiteSpace($newDesc))   { $patchBody.description = $newDesc }
        if (-not [string]::IsNullOrWhiteSpace($newStatus)) { $patchBody.status = $newStatus }

        if (-not [string]::IsNullOrWhiteSpace($typePropsJson)) {
            $patchBody.typeProperties = ($typePropsJson | ConvertFrom-Json)
        }

        if ($patchBody.Keys.Count -eq 0) { throw "Nothing to update. Provide at least one field." }

        Write-Host "`nUpdating rule via PATCH..."
        $resp = Invoke-PurviewRequest -Method "PATCH" -Url $ruleUrl -Body $patchBody
        $resp | ConvertTo-Json -Depth 10
    }

    # -----------------------------
    # DELETE (DELETE)
    # -----------------------------
    "D" {
        $ruleId = Read-Host -Prompt "Enter ruleId (GUID) to delete"
        $ruleUrl = Build-RuleUrl -Endpoint $endpoint -BusinessDomainId $businessDomainId -DataProductId $dataProductId -DataAssetId $dataAssetId -RuleId $ruleId -ApiVersion $apiVersion

        $confirm = Read-Host -Prompt "Type DELETE to confirm"
        if ($confirm -ne "DELETE") { Write-Host "Cancelled."; break }

        Write-Host "`nDeleting rule..."
        try {
            Invoke-PurviewRequest -Method "DELETE" -Url $ruleUrl | Out-Null
            Write-Host "Delete request sent for ruleId: $ruleId" -ForegroundColor Green
        } catch {
            Write-Host "Delete FAILED for ruleId: $ruleId" -ForegroundColor Red
            break
        }

        # Verify deletion by re-listing rules
        Write-Host "`nVerifying deletion..."
        $postDeleteRules = Invoke-PurviewRequest -Method "GET" -Url $rulesUrl
        $remaining = @($postDeleteRules) | Where-Object { $_.id -eq $ruleId }
        if ($remaining.Count -eq 0) {
            Write-Host "Confirmed: rule $ruleId no longer exists." -ForegroundColor Green
        } else {
            Write-Host "WARNING: rule $ruleId still exists after delete!" -ForegroundColor Yellow
            Write-Host "The API returned 204 but the rule was not removed. Check the ruleId and try again." -ForegroundColor Yellow
        }

        # Show remaining rules
        Write-Host "`nRemaining rules:"
        $postDeleteRules | Select-Object id, name, type, status | ConvertTo-Json -Depth 10
    }

    "Q" { Write-Host "Bye." }

    default { Write-Host "Unknown action." }
}