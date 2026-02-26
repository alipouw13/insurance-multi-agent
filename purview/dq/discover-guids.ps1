<#
Purview GUID Discovery Script
Bulk-fetches all Business Domains, Data Products, and Data Assets

APIs used:
  Unified Catalog (2025-09-15-preview):
    GET /datagovernance/catalog/businessdomains
    GET /datagovernance/catalog/dataProducts?domainId={domainId}
  Data Quality (2025-09-01-preview):
    GET /datagovernance/quality/bulk-asset-metadata
#>

# auth
az login --use-device-code | Out-Null

$tenantId = (az account show --query tenantId -o tsv).Trim()
Write-Host "Tenant ID : $tenantId"

$endpoint = "https://$tenantId-api.purview-service.microsoft.com"
Write-Host "Endpoint  : $endpoint`n"

function Get-PurviewToken {
    return (az account get-access-token --resource "https://purview.azure.net" --query accessToken -o tsv).Trim()
}

function Invoke-Purview {
    param(
        [Parameter(Mandatory)][string]$Url
    )
    $token = Get-PurviewToken
    $headers = @{
        Authorization  = "Bearer $token"
        "Content-Type" = "application/json"
    }
    Write-Host "  -> GET $Url" -ForegroundColor DarkGray
    try {
        return Invoke-RestMethod -UseBasicParsing -Method GET -Uri $Url -Headers $headers
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        $body = $_.ErrorDetails.Message
        Write-Host "  !! HTTP $code" -ForegroundColor Red
        if ($body) { Write-Host "  !! $body" -ForegroundColor Red }
        return $null
    }
}

# 1. business domains
Write-Host "=== Business Domains ===" -ForegroundColor Cyan
$catalogApiVersion = "2025-09-15-preview"

$domainsUrl = '{0}/datagovernance/catalog/businessdomains?api-version={1}' -f $endpoint, $catalogApiVersion
$domainsResp = Invoke-Purview -Url $domainsUrl

$domains = @()
if ($null -ne $domainsResp) {
    # Response may be { value: [...] } or a bare array
    if ($domainsResp.PSObject.Properties.Name -contains 'value') {
        $domains = $domainsResp.value
    } else {
        $domains = @($domainsResp)
    }
}

if ($domains.Count -eq 0) {
    Write-Host "  No business domains found." -ForegroundColor Yellow
} else {
    $domains | ForEach-Object {
        Write-Host ("  [{0}] {1}" -f $_.id, $_.name) -ForegroundColor Green
    }
}

# 2. Data Products (per domain)
Write-Host "`n=== Data Products (by Domain) ===" -ForegroundColor Cyan

$allProducts = @()
foreach ($domain in $domains) {
    Write-Host "`n  Domain: $($domain.name) ($($domain.id))" -ForegroundColor White

    $productsUrl = '{0}/datagovernance/catalog/dataProducts?api-version={1}&domainId={2}' -f $endpoint, $catalogApiVersion, $domain.id
    $prodResp = Invoke-Purview -Url $productsUrl

    $products = @()
    if ($null -ne $prodResp) {
        if ($prodResp.PSObject.Properties.Name -contains 'value') {
            $products = $prodResp.value
        } else {
            $products = @($prodResp)
        }
    }

    if ($products.Count -eq 0) {
        Write-Host "    (no data products)" -ForegroundColor Yellow
    } else {
        foreach ($p in $products) {
            Write-Host ("    [{0}] {1}" -f $p.id, $p.name) -ForegroundColor Green
            $allProducts += [PSCustomObject]@{
                DomainId    = $domain.id
                DomainName  = $domain.name
                ProductId   = $p.id
                ProductName = $p.name
            }
        }
    }
}

# 3. data assets (bulk dq api)
Write-Host "`n=== Data Assets (from Data Quality bulk metadata) ===" -ForegroundColor Cyan
$dqApiVersion = "2025-09-01-preview"

$allAssets = @()
$continuationToken = $null

do {
    if ($continuationToken) {
        $assetsUrl = '{0}/datagovernance/quality/bulk-asset-metadata?api-version={1}&continuationToken={2}' -f $endpoint, $dqApiVersion, [uri]::EscapeDataString($continuationToken)
    } else {
        $assetsUrl = '{0}/datagovernance/quality/bulk-asset-metadata?api-version={1}' -f $endpoint, $dqApiVersion
    }

    $assetsResp = Invoke-Purview -Url $assetsUrl
    if ($null -eq $assetsResp) { break }

    $page = @()
    if ($assetsResp.PSObject.Properties.Name -contains 'metadata') {
        $page = $assetsResp.metadata
    }

    foreach ($m in $page) {
        $am = $m.assetMetadata
        if ($null -eq $am) { $am = $m }

        $assetName  = if ($am.name) { $am.name } else { "(unnamed)" }
        $assetId    = if ($am.dataAsset.referenceId) { $am.dataAsset.referenceId } elseif ($am.id) { $am.id } else { "?" }
        $prodId     = if ($am.dataProduct.referenceId) { $am.dataProduct.referenceId } else { "?" }
        $domId      = if ($am.businessDomain.referenceId) { $am.businessDomain.referenceId } else { "?" }

        Write-Host ("  [{0}] {1}" -f $assetId, $assetName) -ForegroundColor Green
        Write-Host ("       Domain={0}  Product={1}" -f $domId, $prodId) -ForegroundColor Gray

        $allAssets += [PSCustomObject]@{
            AssetId     = $assetId
            AssetName   = $assetName
            DomainId    = $domId
            ProductId   = $prodId
        }
    }

    $continuationToken = $assetsResp.continuationToken
} while ($continuationToken)

if ($allAssets.Count -eq 0) {
    Write-Host "  No data assets found via bulk metadata." -ForegroundColor Yellow
}

# summary table (console) 
Write-Host "`n=== Summary ===" -ForegroundColor Cyan

Write-Host "`nBusiness Domains ($($domains.Count)):" -ForegroundColor White
$domains | ForEach-Object {
    Write-Host ("  {0}  {1}" -f $_.id, $_.name)
}

Write-Host "`nData Products ($($allProducts.Count)):" -ForegroundColor White
$allProducts | Format-Table -AutoSize | Out-String | Write-Host

Write-Host "Data Assets ($($allAssets.Count)):" -ForegroundColor White
$allAssets | Format-Table -AutoSize | Out-String | Write-Host

# typed objects for excel export
$domainRows = $domains | ForEach-Object {
    [PSCustomObject]@{
        DomainId   = $_.id
        DomainName = $_.name
    }
}

# $allProducts and $allAssets are already PSCustomObjects

# export excel
$excelPath = Join-Path $PSScriptRoot "purview-guids.xlsx"

# Install ImportExcel if missing (current user only, no admin needed)
if (-not (Get-Module -ListAvailable -Name ImportExcel)) {
    Write-Host "`nInstalling ImportExcel module..." -ForegroundColor Yellow
    Install-Module ImportExcel -Scope CurrentUser -Force -ErrorAction Stop
}
Import-Module ImportExcel -ErrorAction Stop

# remove old file so sheets don't accumulate
if (Test-Path $excelPath) { Remove-Item $excelPath -Force }

# write each dataset to its own worksheet
if ($domainRows.Count -gt 0) {
    $domainRows  | Export-Excel -Path $excelPath -WorksheetName "Domains"      -AutoSize -TableName "Domains"      -Append
}
if ($allProducts.Count -gt 0) {
    $allProducts | Export-Excel -Path $excelPath -WorksheetName "DataProducts"  -AutoSize -TableName "DataProducts"  -Append
}
if ($allAssets.Count -gt 0) {
    $allAssets   | Export-Excel -Path $excelPath -WorksheetName "DataAssets"    -AutoSize -TableName "DataAssets"    -Append
}

Write-Host "`nExcel saved to: $excelPath" -ForegroundColor Green
Write-Host "Done." -ForegroundColor Green
