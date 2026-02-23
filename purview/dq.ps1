#Use this to create DQ rules programatically using REST API in case you want to automate the creation of DQ rules for multiple data assets or if you want to create more complex rules that are not supported out of the box in Purview portal. You can also use this as a reference to understand how to call Purview REST API to manage DQ rules and then adapt it to your needs.
# Login to Azure CLI (using device code flow for VS Code terminal compatibility)
az login --use-device-code

# Using Azure CLI get the ID of the current tenant
$tenantId = az account show --query tenantId -o tsv
Write-Host "Tenant ID: $tenantId"

# Prompt for required Purview IDs (GUIDs from Purview portal → Unified Catalog → Governance domains)
$businessDomainId = Read-Host -Prompt 'Enter the Business Domain ID (GUID from Purview governance domain)'
$dataProductId = Read-Host -Prompt 'Enter the Data Product ID (GUID from the data product within the domain)'
$createdDataAssetId = Read-Host -Prompt 'Enter the Data Asset ID (GUID from the data asset within the data product)'

# Get a token for Microsoft Purview API
$token = az account get-access-token --resource "https://purview.azure.net" --query accessToken -o tsv

# List the existing Data Quality rule for the considered data product
$dataQualityRulesUrl = "https://$tenantId-api.purview-service.microsoft.com/datagovernance/quality/business-domains/$businessDomainId/data-products/$dataProductId/data-assets/$createdDataAssetId/global-rules"
$dataQualityRulesResponse = Invoke-RestMethod -Uri $dataQualityRulesUrl -Headers @{Authorization = "Bearer $token"}
$dataQualityRulesResponse | Select-Object id, name, type, typeProperties | ConvertTo-Json -Depth 4

# Prompt the user to ask if they want to create a new Data Quality rule
$createNewDataQualityRule = Read-Host -Prompt 'Do you want to create a new Data Quality rule? (Y/N)'

# If the user wants to create a new Data Quality rule
if ($createNewDataQualityRule.ToUpper() -eq "Y") {
    # Prompt the user to select the type of the new Data Quality rule
    $allowedDataQualityRuleTypes = @("Timeliness", "Duplicate", "NotNull", "Unique", "TypeMatch", "Regex")
    $allowedDataQualityRuleTypesString = $allowedDataQualityRuleTypes -join ", "
    $retryCount = 0
    $maxRetries = 3

    do {
        $prompt = "Enter the type of the new Data Quality rule ($allowedDataQualityRuleTypesString)"
        $dataQualityRuleType = Read-Host -Prompt $prompt

        $retryCount++
    } while ($dataQualityRuleType -notin $allowedDataQualityRuleTypes -and $retryCount -lt $maxRetries)

    # Definition of the variables for the configuration of the rule depending on the type using a switch statement
    switch ($dataQualityRuleType) {
        "Timeliness" {
            $timeDifferenceInMilliseconds = Read-Host -Prompt 'Enter the time difference in milliseconds to consider knowing that 1 month = 2592000000 milliseconds'
            $dataQualityRuleName = "Freshness"
            $dataQualityRuleTypeProperties = @{
                timeDifference = [long]$timeDifferenceInMilliseconds
            }
        }
        "Duplicate" {
            $dataQualityRuleColumns = Read-Host -Prompt 'Enter the logical name of the columns separated by a comma to consider for duplicates checking'
            $dataQualityRuleColumnsString = $dataQualityRuleColumns -split "," -join "_"
            $dataQualityRuleName = "Duplicate_rows_$dataQualityRuleColumnsString"
            $dataQualityRuleTypeProperties = @{
                columns = @()
            }
            $dataQualityRuleColumns -split "," | ForEach-Object {
                $dataQualityRuleTypeProperties.columns += @{
                    type = "Column"
                    value = $_
                }
            }
        }
        "NotNull" {
            $dataQualityRuleColumn = Read-Host -Prompt 'Enter the logical name of the column that should not be empty'
            $dataQualityRuleName = "Empty/blank_fields_$dataQualityRuleColumn"
            $dataQualityRuleTypeProperties = @{
                column = @{
                    type = "Column"
                    value = $dataQualityRuleColumn
                }
            }
        }
        "Unique" {
            $dataQualityRuleColumn = Read-Host -Prompt 'Enter the logical name of the column that should contain unique values'
            $dataQualityRuleName = "Unique_values_$dataQualityRuleColumn"
            $dataQualityRuleTypeProperties = @{
                column = @{
                    type = "Column"
                    value = $dataQualityRuleColumn
                }
            }
        }
        "TypeMatch" {
            $dataQualityRuleColumn = Read-Host -Prompt 'Enter the logical name of the column that should match the expected data type'
            $dataQualityRuleName = "Data_type_match_$dataQualityRuleColumn"
            $dataQualityRuleTypeProperties = @{
                column = @{
                    type = "Column"
                    value = $dataQualityRuleColumn
                }
            }
        }
        "Regex" {
            $dataQualityRuleColumn = Read-Host -Prompt 'Enter the logical name of the column that should match the regular expression'
            $dataQualityRuleRegex = Read-Host -Prompt 'Enter the regular expression to match'
            $dataQualityRuleName = "String_format_match_$dataQualityRuleColumn"
            $dataQualityRuleTypeProperties = @{
                column = @{
                    type = "Column"
                    value = $dataQualityRuleColumn
                }
                pattern = $dataQualityRuleRegex
            }
        }
    }

    # Define the URL to create a new Data Quality rule
    $createDataQualityRuleUrl = "https://$tenantId-api.purview-service.microsoft.com/datagovernance/quality/business-domains/$businessDomainId/data-products/$dataProductId/data-assets/$createdDataAssetId/global-rules"

    $body = @{
        id = [guid]::NewGuid().ToString()
        name = $dataQualityRuleName
        description = ""
        type = $dataQualityRuleType
        status = "Active"
        typeProperties = $dataQualityRuleTypeProperties
        businessDomain = @{
            referenceId = $businessDomainId
            type = "BusinessDomainReference"
        }
        dataProduct = @{
            referenceId = $dataProductId
            type = "DataProductReference"
        }
        dataAsset = @{
            referenceId = $createdDataAssetId
            type = "DataAssetReference"
        }
    }

    # Create the new Data Quality rule
    $createDataQualityRuleResponse = Invoke-RestMethod -UseBasicParsing -Uri $createDataQualityRuleUrl -Method "POST" -Headers @{Authorization = "Bearer $token"; "Content-Type" = "application/json"} -Body ($body | ConvertTo-Json -Depth 4)
}