@description('The name of the Microsoft Fabric capacity (lowercase letters and numbers only)')
param name string

@description('The location for the Fabric capacity')
param location string

@description('Fabric capacity SKU. F2 is the minimum SKU that supports Fabric data agents.')
@allowed([
  'F2'
  'F4'
  'F8'
  'F16'
  'F32'
  'F64'
])
param skuName string = 'F2'

@description('User principal names or service principal object IDs that administer the capacity')
param adminMembers array

@description('Tags to apply to the capacity')
param tags object = {}

resource fabricCapacity 'Microsoft.Fabric/capacities@2023-11-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: 'Fabric'
  }
  properties: {
    administration: {
      members: adminMembers
    }
  }
}

output capacityId string = fabricCapacity.id
output capacityName string = fabricCapacity.name
output capacitySku string = fabricCapacity.sku.name
