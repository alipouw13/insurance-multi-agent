'use client'

import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { 
  IconDatabase,
  IconRefresh,
  IconCircleCheck,
  IconAlertCircle,
  IconClock,
  IconUser,
  IconRobot,
  IconTool,
  IconBook,
  IconChartBar,
  IconSearch
} from '@tabler/icons-react'
import { StarIcon } from 'lucide-react'
import { toast } from 'sonner'
import { getApiUrl } from '@/lib/config'
import { AgentWorkflowVisualization } from '@/components/agent-workflow-visualization'
import { EvaluationDialog } from '@/components/evaluation-dialog'
import { evaluateExecution, EvaluationResult } from '@/lib/api'

// Sample claims from API
interface SampleClaim {
  claim_id: string
  claimant_name: string
  claim_type: string
  estimated_damage: number
  description: string
}

interface AnalysisResult {
  success: boolean
  agent_name: string
  claim_body: Record<string, unknown>
  conversation_chronological: Array<{
    role: string
    content: string
  }>
  execution_id?: string
}

export default function ClaimsDataAnalystDemo() {
  const [sampleClaims, setSampleClaims] = useState<SampleClaim[]>([])
  const [processingClaimId, setProcessingClaimId] = useState<string | null>(null)
  const [isLoadingSamples, setIsLoadingSamples] = useState(true)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [customQuery, setCustomQuery] = useState<string>('')
  const [evaluationDialogOpen, setEvaluationDialogOpen] = useState(false)
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null)
  const [evaluatingExecution, setEvaluatingExecution] = useState(false)

  // Fetch sample claims on component mount
  useEffect(() => {
    const fetchSampleClaims = async () => {
      try {
        const apiUrl = await getApiUrl()
        const response = await fetch(`${apiUrl}/api/v1/workflow/sample-claims`)
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        
        const data = await response.json()
        setSampleClaims(data.available_claims)
      } catch (err) {
        console.error('Failed to fetch sample claims:', err)
        toast.error('Failed to load sample claims')
      } finally {
        setIsLoadingSamples(false)
      }
    }

    fetchSampleClaims()
  }, [])

  const runAnalysis = async (claim: SampleClaim) => {
    setProcessingClaimId(claim.claim_id)
    setError(null)
    
    try {
      const apiUrl = await getApiUrl()

      // Build request body with optional custom query
      const requestBody: Record<string, unknown> = { claim_id: claim.claim_id }
      if (customQuery.trim()) {
        requestBody.custom_query = customQuery.trim()
      }

      const response = await fetch(`${apiUrl}/api/v1/agent/claims_data_analyst/run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
      }

      const data: AnalysisResult = await response.json()
      setResult(data)
      toast.success('Data analysis completed successfully!')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      setError(errorMessage)
      toast.error('Analysis failed: ' + errorMessage)
    } finally {
      setProcessingClaimId(null)
    }
  }

  const resetDemo = () => {
    setResult(null)
    setError(null)
    setCustomQuery('')
    setEvaluation(null)
  }

  const handleEvaluate = async () => {
    if (!result || !result.execution_id) {
      toast.error('No execution ID available for evaluation')
      return
    }

    setEvaluatingExecution(true)
    setEvaluationDialogOpen(true)

    try {
      // Extract question and answer from conversation
      const conversation = result.conversation_chronological || []
      const firstUserMessage = conversation.find(step => step.role === 'human')
      const lastAssistantMessage = conversation
        .filter(step => step.role === 'ai' && !step.content.startsWith('TOOL_CALL:'))
        .pop()

      const question = firstUserMessage?.content || `Analyze data for claim ${result.claim_body.claim_id}`
      const answer = lastAssistantMessage?.content || 'No response available'

      // Extract context from claim body
      const context = [
        `Claim ID: ${result.claim_body.claim_id || 'N/A'}`,
        `Claimant: ${result.claim_body.claimant_name || 'N/A'}`,
        `Claim Type: ${result.claim_body.claim_type || 'N/A'}`,
        `Description: ${result.claim_body.description || 'N/A'}`,
        `Estimated Damage: $${result.claim_body.estimated_damage || 'N/A'}`,
      ]

      const evaluationResponse = await evaluateExecution({
        execution_id: result.execution_id,
        claim_id: String(result.claim_body.claim_id),
        agent_type: 'claims_data_analyst',
        question,
        answer,
        context,
        metrics: ['groundedness', 'relevance', 'coherence', 'fluency'],
      })

      if (evaluationResponse.success && evaluationResponse.data) {
        setEvaluation(evaluationResponse.data)
        toast.success('Evaluation completed successfully!')
      } else {
        throw new Error(evaluationResponse.error || 'Evaluation failed')
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      toast.error('Evaluation failed: ' + errorMessage)
      setEvaluationDialogOpen(false)
    } finally {
      setEvaluatingExecution(false)
    }
  }

  const formatConversationStep = (step: { role: string; content: string }, index: number, isLast: boolean) => {
    const isUser = step.role === 'human'
    const isAssistant = step.role === 'ai'

    // Skip tool calls in the display
    if (step.content.startsWith('TOOL_CALL:')) {
      return null
    }

    return (
      <div key={index} className="relative">
        <div className="flex gap-4">
          {/* Timeline connector */}
          <div className="flex flex-col items-center">
            <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center border-2 ${
              isUser ? 'bg-blue-100 dark:bg-blue-900/30 border-blue-200 dark:border-blue-800' :
              isAssistant ? 'bg-cyan-100 dark:bg-cyan-900/30 border-cyan-200 dark:border-cyan-800' :
              'bg-orange-100 dark:bg-orange-900/30 border-orange-200 dark:border-orange-800'
            }`}>
              {isUser ? (
                <IconUser className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              ) : isAssistant ? (
                <IconRobot className="h-5 w-5 text-cyan-600 dark:text-cyan-400" />
              ) : (
                <IconTool className="h-5 w-5 text-orange-600 dark:text-orange-400" />
              )}
            </div>
            {/* Connecting line */}
            {!isLast && (
              <div className="w-0.5 h-8 bg-border mt-2"></div>
            )}
          </div>
          
          {/* Content */}
          <div className="flex-1 pb-8">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant={isUser ? 'secondary' : isAssistant ? 'default' : 'outline'}>
                {isUser ? 'User' : isAssistant ? 'Claims Data Analyst' : 'Tool Response'}
              </Badge>
              <span className="text-xs text-muted-foreground">
                Step {index + 1}
              </span>
            </div>
            
            <div className={`rounded-lg p-4 shadow-sm ${
              isUser ? 'bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800' :
              isAssistant ? 'bg-cyan-50 dark:bg-cyan-950/30 border border-cyan-200 dark:border-cyan-800' :
              'bg-orange-50 dark:bg-orange-950/30 border border-orange-200 dark:border-orange-800'
            }`}>
              <div className="text-sm whitespace-pre-wrap leading-relaxed">
                {step.content}
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Agent Overview Card */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-3">
            <div className="p-2 bg-cyan-100 dark:bg-cyan-900/30 rounded-lg">
              <IconDatabase className="h-6 w-6 text-cyan-600 dark:text-cyan-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Claims Data Analyst Agent</h1>
              <p className="text-sm text-muted-foreground font-normal">
                Specialized in enterprise data analysis using Microsoft Fabric
              </p>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <IconTool className="h-4 w-4" />
                Data Sources (Fabric Lakehouse)
              </h3>
              <div className="space-y-3">
                <div className="bg-muted/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <IconChartBar className="h-4 w-4 text-cyan-600" />
                    <span className="font-medium text-sm">Claims History</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Historical claims data with outcomes and patterns
                  </p>
                </div>
                
                <div className="bg-muted/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <IconUser className="h-4 w-4 text-cyan-600" />
                    <span className="font-medium text-sm">Claimant Profiles</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Customer risk scores and claim frequency
                  </p>
                </div>

                <div className="bg-muted/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <IconSearch className="h-4 w-4 text-cyan-600" />
                    <span className="font-medium text-sm">Fraud Indicators</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Detected fraud patterns and investigation status
                  </p>
                </div>
              </div>
            </div>
            
            <div>
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <IconCircleCheck className="h-4 w-4" />
                Analysis Capabilities
              </h3>
              <div className="bg-cyan-50 dark:bg-cyan-950/30 rounded-lg border border-cyan-200 dark:border-cyan-800 p-4">
                <div className="flex flex-wrap gap-2">
                  <Badge variant="default" className="text-xs bg-cyan-600">Historical Claims</Badge>
                  <Badge variant="secondary" className="text-xs">Fraud Patterns</Badge>
                  <Badge variant="outline" className="text-xs">Regional Stats</Badge>
                  <Badge variant="outline" className="text-xs">Benchmarking</Badge>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Queries enterprise data to provide statistical context and risk insights
                </p>
              </div>

              <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-950/30 rounded-lg border border-amber-200 dark:border-amber-800">
                <p className="text-xs text-amber-700 dark:text-amber-400">
                  <strong>Note:</strong> This agent requires Microsoft Fabric integration to be enabled. 
                  If Fabric is not configured, the agent will return limited results.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Sample Claims Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <IconDatabase className="h-5 w-5" />
            Query Enterprise Data
          </CardTitle>
          <CardDescription>
            Select a sample claim to analyze historical data, or provide a custom data query
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          
          {/* Custom Query Section */}
          <div className="space-y-3">
            <Label className="text-sm font-medium">Custom Data Query (Optional)</Label>
            <Textarea
              placeholder="Enter a custom query, e.g., 'What are the average claim amounts for auto collision claims in California?' or 'Show me claimants with risk scores above 70'"
              value={customQuery}
              onChange={(e) => setCustomQuery(e.target.value)}
              className="min-h-[80px]"
            />
            <p className="text-xs text-muted-foreground">
              Leave empty to run standard historical analysis for the selected claim
            </p>
          </div>

          {isLoadingSamples ? (
            <div className="flex items-center justify-center py-8">
              <IconClock className="h-6 w-6 animate-spin mr-2" />
              <span>Loading sample claims...</span>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-3">
              {sampleClaims.map((claim) => (
                <Card
                  key={claim.claim_id}
                  className="cursor-pointer hover:shadow-md transition-shadow"
                >
                  <CardContent className="p-4 h-full">
                    <div className="flex flex-col h-full">
                      <div className="flex items-center justify-between mb-3">
                        <Badge variant="secondary" className="text-xs">
                          {claim.claim_id}
                        </Badge>
                        <span className="text-lg font-semibold text-cyan-600">
                          ${claim.estimated_damage.toLocaleString()}
                        </span>
                      </div>
                      
                      <div className="mb-3">
                        <h3 className="font-medium text-base mb-1">
                          {claim.claim_type}
                        </h3>
                        <p className="text-sm text-muted-foreground">
                          Claimant: {claim.claimant_name}
                        </p>
                      </div>
                      
                      <div className="text-xs text-muted-foreground leading-relaxed flex-grow mb-4">
                        {claim.description}
                      </div>
                      
                      <Button 
                        variant="outline" 
                        size="sm" 
                        disabled={processingClaimId !== null}
                        className="w-full mt-auto"
                        onClick={() => runAnalysis(claim)}
                      >
                        {processingClaimId === claim.claim_id ? 'Querying Data...' : 'Analyze Data'}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {result && (
            <div className="pt-4 space-y-2">
              <Button 
                variant="default" 
                onClick={handleEvaluate} 
                className="w-full"
                disabled={evaluatingExecution || !result.execution_id}
              >
                <StarIcon className="mr-2 h-4 w-4" />
                {evaluatingExecution ? 'Evaluating...' : 'View Evaluation'}
              </Button>
              <Button variant="outline" onClick={resetDemo} className="w-full">
                <IconRefresh className="mr-2 h-4 w-4" />
                Reset Demo
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <IconCircleCheck className="h-5 w-5" />
            Data Analysis Results
          </CardTitle>
          <CardDescription>
            Enterprise data insights from Microsoft Fabric
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert className="mb-4">
              <IconAlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {processingClaimId !== null && (
            <div className="flex items-center justify-center py-8">
              <IconClock className="h-6 w-6 animate-spin mr-2" />
              <span>Querying enterprise data...</span>
            </div>
          )}

          {result && (
            <div className="space-y-6">
              {/* Claim Data */}
              <div>
                <h4 className="font-medium mb-3 flex items-center gap-2">
                  <IconDatabase className="h-4 w-4" />
                  Query Context
                </h4>
                <div className="bg-muted/30 rounded-lg p-4">
                  <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {Object.entries(result.claim_body).map(([key, value]) => (
                      <div key={key} className="space-y-1">
                        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                          {key.replace(/_/g, ' ')}
                        </div>
                        <div className="text-sm">
                          {typeof value === 'boolean' ? (
                            <Badge variant={value ? 'default' : 'secondary'}>
                              {value ? 'Yes' : 'No'}
                            </Badge>
                          ) : typeof value === 'number' ? (
                            <span className="font-medium">
                              {key.includes('damage') || key.includes('amount') ? 
                                `$${value.toLocaleString()}` : 
                                value.toLocaleString()
                              }
                            </span>
                          ) : (
                            <span className="break-words">
                              {String(value) || 'N/A'}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <Separator />

              {/* Conversation Timeline */}
              <div>
                <h4 className="font-medium mb-3 flex items-center gap-2">
                  <IconBook className="h-4 w-4" />
                  Analysis Timeline
                </h4>
                <ScrollArea className="h-[calc(100vh-28rem)] min-h-[500px] max-h-[700px]">
                  <div className="py-4">
                    {result.conversation_chronological
                      .map((step, index, array) => formatConversationStep(step, index, index === array.length - 1))
                      .filter(Boolean)}
                  </div>
                </ScrollArea>
              </div>
            </div>
          )}

          {!result && processingClaimId === null && !error && (
            <div className="text-center py-8 text-muted-foreground">
              <IconDatabase className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>Select a sample claim to query enterprise data</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Workflow Visualization */}
      <AgentWorkflowVisualization currentAgent="claims-data-analyst" />

      {/* Evaluation Dialog */}
      <EvaluationDialog
        open={evaluationDialogOpen}
        onOpenChange={setEvaluationDialogOpen}
        evaluation={evaluation}
        loading={evaluatingExecution}
      />
    </div>
  )
}
