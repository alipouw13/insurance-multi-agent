export interface DemoScenario {
  id: string
  title: string
  description: string
  category: 'auto' | 'home' | 'health' | 'life'
  complexity: 'simple' | 'moderate' | 'complex'
  data: {
    claim_description: string
    policy_number: string
    incident_date: string
    claim_type: string
    estimated_amount: number
    additional_info?: string
    customer_info?: {
      name: string
      email: string
      phone: string
    }
  }
}

// Demo scenarios with IDs matching the Fabric Lakehouse data
// claims_history: claim_id CLM-2026-NNNNNN, claimant_id CLM-NNNN
// policy_claims_summary: policy_number POL-YYYY-NNN
export const demoScenarios: DemoScenario[] = [
  {
    id: 'auto-fender-bender',
    title: 'Minor Auto Accident',
    description: 'Simple fender bender with clear liability - Mary White (CLM-470)',
    category: 'auto',
    complexity: 'simple',
    data: {
      claim_description: 'Rear-ended at traffic light. Minor damage to bumper and taillight. Other driver admitted fault.',
      policy_number: 'POL-2021-672',
      incident_date: '2025-11-13',
      claim_type: 'Auto Accident',
      estimated_amount: 7907.52,
      additional_info: 'Police report filed. Photos available. Claimant ID: CLM-470',
      customer_info: {
        name: 'Mary White',
        email: 'mary.white@email.com',
        phone: '+1-555-0123'
      }
    }
  },
  {
    id: 'auto-total-loss',
    title: 'Major Collision - Total Loss',
    description: 'High-value claim requiring detailed investigation - Linda Ramirez (CLM-1310)',
    category: 'auto',
    complexity: 'complex',
    data: {
      claim_description: 'Vehicle totaled in highway collision. Airbags deployed. Significant damage to front end and engine compartment.',
      policy_number: 'POL-2025-914',
      incident_date: '2025-05-22',
      claim_type: 'Major Collision',
      estimated_amount: 28392.64,
      additional_info: 'Emergency services responded. Vehicle towed to certified facility. Claimant ID: CLM-1310',
      customer_info: {
        name: 'Linda Ramirez',
        email: 'linda.ramirez@email.com',
        phone: '+1-555-0456'
      }
    }
  },
  {
    id: 'home-water-damage',
    title: 'Property Damage Claim',
    description: 'Property damage requiring assessment - William Gonzalez (CLM-1099)',
    category: 'home',
    complexity: 'moderate',
    data: {
      claim_description: 'Significant property damage from storm. Multiple areas affected requiring professional restoration.',
      policy_number: 'POL-2021-722',
      incident_date: '2025-05-09',
      claim_type: 'Property Damage',
      estimated_amount: 41982.02,
      additional_info: 'Photos and damage assessment documented. Claimant ID: CLM-1099',
      customer_info: {
        name: 'William Gonzalez',
        email: 'william.gonzalez@email.com',
        phone: '+1-555-0789'
      }
    }
  },
  {
    id: 'home-fire',
    title: 'Fire Damage Claim',
    description: 'Kitchen fire with significant damage - Betty Thompson (CLM-1569)',
    category: 'home',
    complexity: 'complex',
    data: {
      claim_description: 'Kitchen fire caused significant damage. Fire started from electrical fault in kitchen appliances. Fire department responded.',
      policy_number: 'POL-2023-988',
      incident_date: '2025-04-25',
      claim_type: 'Fire Damage',
      estimated_amount: 41374.12,
      additional_info: 'Fire report filed. Electrical inspection report available. Claimant ID: CLM-1569',
      customer_info: {
        name: 'Betty Thompson',
        email: 'betty.thompson@email.com',
        phone: '+1-555-0321'
      }
    }
  },
  {
    id: 'auto-liability',
    title: 'Liability Claim',
    description: 'Liability incident requiring investigation - Michael Lewis (CLM-1477)',
    category: 'auto',
    complexity: 'moderate',
    data: {
      claim_description: 'Multi-party accident with disputed liability. Multiple witness statements collected.',
      policy_number: 'POL-2020-977',
      incident_date: '2025-05-26',
      claim_type: 'Liability',
      estimated_amount: 65891.37,
      additional_info: 'Police report and witness statements provided. Claimant ID: CLM-1477',
      customer_info: {
        name: 'Michael Lewis',
        email: 'michael.lewis@email.com',
        phone: '+1-555-0654'
      }
    }
  },
  {
    id: 'auto-theft',
    title: 'Auto Theft Claim',
    description: 'Vehicle theft requiring fraud investigation - Jessica Thomas (CLM-819)',
    category: 'auto',
    complexity: 'complex',
    data: {
      claim_description: 'Vehicle stolen from parking garage. Security footage being reviewed by authorities.',
      policy_number: 'POL-2023-354',
      incident_date: '2024-02-27',
      claim_type: 'Auto Theft',
      estimated_amount: 25195.69,
      additional_info: 'Police report filed. Security footage available. Claimant ID: CLM-819',
      customer_info: {
        name: 'Jessica Thomas',
        email: 'jessica.thomas@email.com',
        phone: '+1-555-0987'
      }
    }
  }
]

export const communicationScenarios = [
  {
    id: 'claim-acknowledgment',
    title: 'Claim Acknowledgment',
    description: 'Initial response confirming claim receipt',
    type: 'email',
    languages: ['en', 'es', 'fr'],
    context: {
      claim_id: 'CLM-2026-000001',
      customer_name: 'Linda Ramirez',
      policy_number: 'POL-2025-914'
    }
  },
  {
    id: 'document-request',
    title: 'Document Request',
    description: 'Request for additional documentation',
    type: 'email',
    languages: ['en', 'es'],
    context: {
      claim_id: 'CLM-2026-000002',
      customer_name: 'William Gonzalez',
      required_docs: ['Police report', 'Repair estimates', 'Photos']
    }
  },
  {
    id: 'claim-approval',
    title: 'Claim Approval Notice',
    description: 'Notification of claim approval and next steps',
    type: 'email',
    languages: ['en', 'fr'],
    context: {
      claim_id: 'CLM-2026-000003',
      customer_name: 'Mary White',
      settlement_amount: 7907.52
    }
  },
  {
    id: 'status-update',
    title: 'Status Update SMS',
    description: 'Brief status update via text message',
    type: 'sms',
    languages: ['en', 'es'],
    context: {
      claim_id: 'CLM-2026-000005',
      customer_name: 'Betty Thompson',
      current_status: 'Under review'
    }
  }
]

export const workflowScenarios = [
  {
    id: 'standard-auto-claim',
    title: 'Standard Auto Claim Processing',
    description: 'Typical auto claim workflow with assessment and communication',
    type: 'auto_claim_standard',
    priority: 'medium',
    steps: ['intake', 'assessment', 'communication', 'settlement']
  },
  {
    id: 'complex-investigation',
    title: 'Complex Claim Investigation',
    description: 'High-value claim requiring detailed investigation and multiple agent coordination',
    type: 'complex_investigation',
    priority: 'high',
    steps: ['intake', 'preliminary_assessment', 'investigation', 'expert_review', 'communication', 'settlement']
  },
  {
    id: 'expedited-processing',
    title: 'Expedited Claim Processing',
    description: 'Fast-track processing for simple, clear-cut claims',
    type: 'expedited',
    priority: 'high',
    steps: ['intake', 'quick_assessment', 'auto_approval', 'communication']
  },
  {
    id: 'multi-party-coordination',
    title: 'Multi-Party Coordination',
    description: 'Complex scenario involving multiple parties and agents',
    type: 'multi_party',
    priority: 'high',
    steps: ['intake', 'party_identification', 'parallel_assessment', 'coordination', 'communication', 'settlement']
  }
]

export function getScenarioById(id: string): DemoScenario | undefined {
  return demoScenarios.find(scenario => scenario.id === id)
}

export function getScenariosByCategory(category: DemoScenario['category']): DemoScenario[] {
  return demoScenarios.filter(scenario => scenario.category === category)
}

export function getScenariosByComplexity(complexity: DemoScenario['complexity']): DemoScenario[] {
  return demoScenarios.filter(scenario => scenario.complexity === complexity)
} 