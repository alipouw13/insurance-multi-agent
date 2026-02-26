<#
Purview Unified Catalog - Data Quality Rules (Public Preview API)
API version: 2025-09-01-preview

Features:
- Imports asset GUIDs from purview-guids.xlsx (run discover-guids.ps1 first)
- Multi-select assets to apply rules in bulk
- List / Create / Update / Delete rules

Docs:
GET   .../rules?api-version=2025-09-01-preview
PUT   .../rules/{ruleId}?api-version=2025-09-01-preview
PATCH .../rules/{ruleId}?api-version=2025-09-01-preview
DELETE.../rules/{ruleId}?api-version=2025-09-01-preview
#>

# prereqs
az login --use-device-code | Out-Null

# ImportExcel module (for reading the xlsx)
if (-not (Get-Module -ListAvailable -Name ImportExcel)) {
    Write-Host "Installing ImportExcel module..." -ForegroundColor Yellow
    Install-Module ImportExcel -Scope CurrentUser -Force -ErrorAction Stop
}
Import-Module ImportExcel -ErrorAction Stop

# helper fxns
function Get-TenantId {
    return (az account show --query tenantId -o tsv).Trim()
}

function Get-PurviewToken {
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

# main
$apiVersion = "2025-09-01-preview"

$tenantId = Get-TenantId
Write-Host "Tenant ID: $tenantId"

$endpoint = "https://$tenantId-api.purview-service.microsoft.com"
Write-Host "Purview Endpoint: $endpoint"

# load assets excel or manual
$excelPath = Join-Path $PSScriptRoot "purview-guids.xlsx"
$assets = @()

if (Test-Path $excelPath) {
    Write-Host "`nLoading assets from: $excelPath" -ForegroundColor Cyan
    $assets = @(Import-Excel -Path $excelPath -WorksheetName "DataAssets")
    Write-Host "Found $($assets.Count) assets in Excel.`n"
} else {
    Write-Host "`nExcel file not found at $excelPath" -ForegroundColor Yellow
    Write-Host "Run discover-guids.ps1 first, or enter GUIDs manually.`n"
}

# Let user choose: pick from Excel or enter manually
if ($assets.Count -gt 0) {
    $source = Read-Host -Prompt "(E)xcel asset list or (M)anual GUID entry? [E]"
    if ([string]::IsNullOrWhiteSpace($source)) { $source = "E" }
} else {
    $source = "M"
}

$selectedAssets = @()

if ($source.ToUpper() -eq "E") {
    # Display numbered list
    Write-Host "`n  #  AssetName                          AssetId                              DomainId                             ProductId" -ForegroundColor White
    Write-Host "  -- --------------------------------- ------------------------------------ ------------------------------------ ------------------------------------" -ForegroundColor DarkGray
    for ($i = 0; $i -lt $assets.Count; $i++) {
        $a = $assets[$i]
        $num = ($i + 1).ToString().PadLeft(3)
        $name = if ($a.AssetName.Length -gt 33) { $a.AssetName.Substring(0,30) + "..." } else { $a.AssetName.PadRight(33) }
        Write-Host ("  {0}  {1}  {2}  {3}  {4}" -f $num, $name, $a.AssetId, $a.DomainId, $a.ProductId)
    }

    Write-Host "`nEnter asset numbers (comma-separated), a range (1-5), or 'all':" -ForegroundColor Cyan
    $selection = Read-Host -Prompt "Selection"

    if ($selection.Trim().ToLower() -eq "all") {
        $selectedAssets = $assets
    } else {
        $indices = @()
        foreach ($part in ($selection -split ",")) {
            $part = $part.Trim()
            if ($part -match '^(\d+)-(\d+)$') {
                $start = [int]$Matches[1]; $end = [int]$Matches[2]
                $indices += ($start..$end)
            } elseif ($part -match '^\d+$') {
                $indices += [int]$part
            }
        }
        foreach ($idx in ($indices | Sort-Object -Unique)) {
            if ($idx -ge 1 -and $idx -le $assets.Count) {
                $selectedAssets += $assets[$idx - 1]
            }
        }
    }

    if ($selectedAssets.Count -eq 0) {
        Write-Host "No valid assets selected. Exiting." -ForegroundColor Red
        return
    }
    Write-Host "`nSelected $($selectedAssets.Count) asset(s)." -ForegroundColor Green

} else {
    # manual single-asset entry (original behavior)
    $businessDomainId = Read-Host -Prompt "Enter Business Domain ID (GUID)"
    $dataProductId    = Read-Host -Prompt "Enter Data Product ID (GUID)"
    $dataAssetId      = Read-Host -Prompt "Enter Data Asset ID (GUID)"
    $selectedAssets += [PSCustomObject]@{
        AssetId   = $dataAssetId
        AssetName = "(manual)"
        DomainId  = $businessDomainId
        ProductId = $dataProductId
    }
}

# list existing rules for ALL selected assets
foreach ($asset in $selectedAssets) {
    $rulesUrl = Build-BaseRulesUrl -Endpoint $endpoint -BusinessDomainId $asset.DomainId -DataProductId $asset.ProductId -DataAssetId $asset.AssetId -ApiVersion $apiVersion
    Write-Host "`n--- Existing rules for: $($asset.AssetName) ($($asset.AssetId)) ---" -ForegroundColor Cyan
    $existingRules = Invoke-PurviewRequest -Method "GET" -Url $rulesUrl
    if ($existingRules) {
        $existingRules | Select-Object id, name, type, status, typeProperties | ConvertTo-Json -Depth 10
    } else {
        Write-Host "  (no rules)" -ForegroundColor Yellow
    }
}

# Menu
$action = Read-Host -Prompt "`nChoose action: (C)reate, (U)pdate, (D)elete, (L)ist all, (Q)uit"

switch ($action.ToUpper()) {

    # CREATE (PUT) — applied to ALL selected assets

    "C" {
        $allowedTypes = @("Timeliness","Duplicate","NotNull","Unique","TypeMatch","Regex","CustomTruth")
        $type = Read-Host -Prompt ("Enter rule type (" + ($allowedTypes -join ", ") + ")")
        if ($type -notin $allowedTypes) { throw "Invalid type. Allowed: $($allowedTypes -join ', ')" }

        $baseName = Read-Host -Prompt "Enter rule name (or press Enter for default)"
        $description = Read-Host -Prompt "Enter rule description (optional)"
        $status = "Active"

        # Column-based types: ask whether to use same or different columns per asset
        $columnTypes = @("Duplicate","NotNull","Unique","TypeMatch","Regex")
        $perAssetColumns = $false
        $sharedTypeProps  = $null
        $sharedPattern    = $null     # only for Regex

        if ($type -in $columnTypes -and $selectedAssets.Count -gt 1) {
            $colMode = Read-Host -Prompt "Use (S)ame column(s) for all assets, or (D)ifferent per asset? [S]"
            if ([string]::IsNullOrWhiteSpace($colMode)) { $colMode = "S" }
            $perAssetColumns = ($colMode.ToUpper() -eq "D")
        }

        # If same columns (or only 1 asset), collect type properties once up front
        if (-not $perAssetColumns) {
            switch ($type) {
                "Timeliness" {
                    $ms = Read-Host -Prompt "Enter time difference in milliseconds (e.g., 2592000000 for 30 days)"
                    if (-not $baseName) { $baseName = "Freshness" }
                    $sharedTypeProps = @{ timeDifference = [long]$ms }
                }
                "Duplicate" {
                    $cols = Read-Host -Prompt "Enter logical column names (comma-separated) used to detect duplicates"
                    $colList = $cols -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
                    if ($colList.Count -lt 1) { throw "Duplicate rule requires at least one column." }
                    if (-not $baseName) { $baseName = "Duplicate_rows_" + ($colList -join "_") }
                    $sharedTypeProps = @{ columns = @() }
                    foreach ($c in $colList) { $sharedTypeProps.columns += @{ type = "Column"; value = $c } }
                }
                "NotNull" {
                    $col = Read-Host -Prompt "Enter logical column name that must not be empty"
                    if (-not $baseName) { $baseName = "Empty/blank_fields_$col" }
                    $sharedTypeProps = @{ column = @{ type = "Column"; value = $col } }
                }
                "Unique" {
                    $col = Read-Host -Prompt "Enter logical column name that must be unique"
                    if (-not $baseName) { $baseName = "Unique_values_$col" }
                    $sharedTypeProps = @{ column = @{ type = "Column"; value = $col } }
                }
                "TypeMatch" {
                    $col = Read-Host -Prompt "Enter logical column name for type validation"
                    if (-not $baseName) { $baseName = "Data_type_match_$col" }
                    $sharedTypeProps = @{ column = @{ type = "Column"; value = $col } }
                }
                "Regex" {
                    $col = Read-Host -Prompt "Enter logical column name to validate with regex"
                    $sharedPattern = Read-Host -Prompt "Enter regex pattern"
                    if (-not $baseName) { $baseName = "String_format_match_$col" }
                    $sharedTypeProps = @{ column = @{ type = "Column"; value = $col }; pattern = $sharedPattern }
                }
                "CustomTruth" {
                    $condition = Read-Host -Prompt "Enter condition (row expression), e.g. (Amount > 0 AND Country IS NOT NULL)"
                    $filter    = Read-Host -Prompt "Enter filterCriteria (optional), e.g. (Status = 'Active')"
                    $empty     = Read-Host -Prompt "Enter emptyCriteria (optional), e.g. (Amount IS NULL)"
                    if (-not $baseName) { $baseName = "Custom_rule" }
                    $sharedTypeProps = @{ condition = $condition }
                    if (-not [string]::IsNullOrWhiteSpace($filter)) { $sharedTypeProps.filterCriteria = $filter }
                    if (-not [string]::IsNullOrWhiteSpace($empty))  { $sharedTypeProps.emptyCriteria  = $empty }
                }
            }
        } else {
            # Per-asset mode: collect a regex pattern once (shared) if Regex type
            if ($type -eq "Regex") {
                $sharedPattern = Read-Host -Prompt "Enter regex pattern (shared across all assets)"
            }
        }

        # Loop over each selected asset
        Write-Host "`nCreating rule on $($selectedAssets.Count) asset(s)..." -ForegroundColor Cyan
        $successCount = 0
        $failCount    = 0

        foreach ($asset in $selectedAssets) {
            Write-Host "`n  Asset: $($asset.AssetName) ($($asset.AssetId))" -ForegroundColor White

            # Per-asset rule name when in per-asset mode
            $ruleName = $baseName
            if ($perAssetColumns) {
                $assetRuleName = Read-Host -Prompt "    Rule name for $($asset.AssetName) (Enter for '$baseName')"
                if (-not [string]::IsNullOrWhiteSpace($assetRuleName)) { $ruleName = $assetRuleName }
            }

            # Build per-asset typeProperties if needed
            if ($perAssetColumns) {
                $typeProps = @{}
                switch ($type) {
                    "Duplicate" {
                        $cols = Read-Host -Prompt "    Column(s) for $($asset.AssetName) (comma-separated)"
                        $colList = $cols -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
                        if ($colList.Count -lt 1) { Write-Host "    Skipped (no columns)." -ForegroundColor Yellow; $failCount++; continue }
                        $typeProps = @{ columns = @() }
                        foreach ($c in $colList) { $typeProps.columns += @{ type = "Column"; value = $c } }
                        if (-not $baseName) { $baseName = "Duplicate_rows_" + ($colList -join "_") }
                    }
                    "NotNull" {
                        $col = Read-Host -Prompt "    Column for $($asset.AssetName)"
                        if ([string]::IsNullOrWhiteSpace($col)) { Write-Host "    Skipped (no column)." -ForegroundColor Yellow; $failCount++; continue }
                        $typeProps = @{ column = @{ type = "Column"; value = $col } }
                        if (-not $baseName) { $baseName = "Empty/blank_fields_$col" }
                    }
                    "Unique" {
                        $col = Read-Host -Prompt "    Column for $($asset.AssetName)"
                        if ([string]::IsNullOrWhiteSpace($col)) { Write-Host "    Skipped (no column)." -ForegroundColor Yellow; $failCount++; continue }
                        $typeProps = @{ column = @{ type = "Column"; value = $col } }
                        if (-not $baseName) { $baseName = "Unique_values_$col" }
                    }
                    "TypeMatch" {
                        $col = Read-Host -Prompt "    Column for $($asset.AssetName)"
                        if ([string]::IsNullOrWhiteSpace($col)) { Write-Host "    Skipped (no column)." -ForegroundColor Yellow; $failCount++; continue }
                        $typeProps = @{ column = @{ type = "Column"; value = $col } }
                        if (-not $baseName) { $baseName = "Data_type_match_$col" }
                    }
                    "Regex" {
                        $col = Read-Host -Prompt "    Column for $($asset.AssetName)"
                        if ([string]::IsNullOrWhiteSpace($col)) { Write-Host "    Skipped (no column)." -ForegroundColor Yellow; $failCount++; continue }
                        $typeProps = @{ column = @{ type = "Column"; value = $col }; pattern = $sharedPattern }
                        if (-not $baseName) { $baseName = "String_format_match_$col" }
                    }
                }
            } else {
                $typeProps = $sharedTypeProps
            }

            $ruleId  = [guid]::NewGuid().ToString()
            $ruleUrl = Build-RuleUrl -Endpoint $endpoint -BusinessDomainId $asset.DomainId -DataProductId $asset.ProductId -DataAssetId $asset.AssetId -RuleId $ruleId -ApiVersion $apiVersion

            $body = @{
                id             = $ruleId
                name           = $ruleName
                description    = $description
                type           = $type
                status         = $status
                typeProperties = $typeProps
                businessDomain = @{ referenceId = $asset.DomainId;  type = "BusinessDomainReference" }
                dataProduct    = @{ referenceId = $asset.ProductId; type = "DataProductReference" }
                dataAsset      = @{ referenceId = $asset.AssetId;   type = "DataAssetReference" }
            }

            try {
                $resp = Invoke-PurviewRequest -Method "PUT" -Url $ruleUrl -Body $body
                Write-Host "  Created rule: $($resp.id) - $($resp.name)" -ForegroundColor Green
                $successCount++
            } catch {
                Write-Host "  FAILED to create rule on $($asset.AssetName)" -ForegroundColor Red
                $failCount++
            }
        }

        Write-Host "`nBulk create complete: $successCount succeeded, $failCount failed." -ForegroundColor Cyan
    }

    #  show rules for every selected asset

    "L" {
        foreach ($asset in $selectedAssets) {
            $url = Build-BaseRulesUrl -Endpoint $endpoint -BusinessDomainId $asset.DomainId -DataProductId $asset.ProductId -DataAssetId $asset.AssetId -ApiVersion $apiVersion
            Write-Host "`n--- $($asset.AssetName) ($($asset.AssetId)) ---" -ForegroundColor Cyan
            $rules = Invoke-PurviewRequest -Method "GET" -Url $url
            if ($rules) {
                $rules | Select-Object id, name, type, status | ConvertTo-Json -Depth 10
            } else {
                Write-Host "  (no rules or error)" -ForegroundColor Yellow
            }
        }
    }

    # UPDATE (PATCH) — single asset

    "U" {
        $asset = $selectedAssets[0]
        Write-Host "Updating rule on: $($asset.AssetName) ($($asset.AssetId))" -ForegroundColor White

        $ruleId = Read-Host -Prompt "Enter ruleId (GUID) to update"
        $ruleUrl = Build-RuleUrl -Endpoint $endpoint -BusinessDomainId $asset.DomainId -DataProductId $asset.ProductId -DataAssetId $asset.AssetId -RuleId $ruleId -ApiVersion $apiVersion

        $newName = Read-Host -Prompt "Enter new name (optional)"
        $newDesc = Read-Host -Prompt "Enter new description (optional)"
        $newStatus = Read-Host -Prompt "Enter new status (optional, e.g., Active/Inactive)"
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

    # DELETE — across all selected assets

    "D" {
        $ruleId = Read-Host -Prompt "Enter ruleId (GUID) to delete (applied to all selected assets)"
        $confirm = Read-Host -Prompt "Type DELETE to confirm"
        if ($confirm -ne "DELETE") { Write-Host "Cancelled."; break }

        $successCount = 0
        $failCount    = 0

        foreach ($asset in $selectedAssets) {
            $ruleUrl = Build-RuleUrl -Endpoint $endpoint -BusinessDomainId $asset.DomainId -DataProductId $asset.ProductId -DataAssetId $asset.AssetId -RuleId $ruleId -ApiVersion $apiVersion
            $listUrl = Build-BaseRulesUrl -Endpoint $endpoint -BusinessDomainId $asset.DomainId -DataProductId $asset.ProductId -DataAssetId $asset.AssetId -ApiVersion $apiVersion

            Write-Host "`n  Asset: $($asset.AssetName) ($($asset.AssetId))" -ForegroundColor White
            try {
                Invoke-PurviewRequest -Method "DELETE" -Url $ruleUrl | Out-Null
                Write-Host "  Delete request sent." -ForegroundColor Green
                $successCount++
            } catch {
                Write-Host "  Delete FAILED." -ForegroundColor Red
                $failCount++
                continue
            }

            # Verify
            $postRules = Invoke-PurviewRequest -Method "GET" -Url $listUrl
            $remaining = @($postRules) | Where-Object { $_.id -eq $ruleId }
            if ($remaining.Count -eq 0) {
                Write-Host "  Confirmed deleted." -ForegroundColor Green
            } else {
                Write-Host "  WARNING: rule still exists after delete!" -ForegroundColor Yellow
            }
        }

        Write-Host "`nBulk delete complete: $successCount succeeded, $failCount failed." -ForegroundColor Cyan
    }

    "Q" { Write-Host "Bye." }

    default { Write-Host "Unknown action." }
}