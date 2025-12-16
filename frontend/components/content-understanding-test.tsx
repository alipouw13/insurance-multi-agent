"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { FileUpload } from "@/components/ui/file-upload"
import { getApiUrl } from "@/lib/config"
import { toast } from "sonner"
import {
  IconFileAnalytics,
  IconCheck,
  IconAlertCircle,
  IconTable,
  IconFileText
} from '@tabler/icons-react'

interface AnalysisResult {
  status: string
  filename: string
  extracted_fields: Record<string, unknown>
  confidence_scores: Record<string, number>
  tables: Array<Record<string, unknown>>
  content_preview: string
  field_count: number
  table_count: number
}

type ProcessingStep = 'uploading' | 'analyzing' | 'indexing' | 'complete' | 'error'

export function ContentUnderstandingTest() {
  const [currentStep, setCurrentStep] = useState<ProcessingStep | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [uploadedFilename, setUploadedFilename] = useState<string>('')
  const [isConfigured, setIsConfigured] = useState<boolean | null>(null)

  useEffect(() => {
    const checkConfiguration = async () => {
      try {
        const apiUrl = await getApiUrl()
        const response = await fetch(`${apiUrl}/api/v1/documents/analyzer-status`)
        if (response.ok) {
          const data = await response.json()
          setIsConfigured(data.available)
          if (!data.available) {
            setError('Content Understanding is not configured. Please add Azure Content Understanding credentials to the backend environment variables.')
          }
        }
      } catch (err) {
        console.error('Failed to check analyzer status:', err)
        setIsConfigured(false)
      }
    }
    checkConfiguration()
  }, [])

  const handleFileUpload = async (files: File[]) => {
    if (files.length === 0) return

    const file = files[0]
    setCurrentStep('uploading')
    setError(null)
    setResult(null)
    setUploadedFilename(file.name)

    try {
      // Step 1: Upload and analyze with Content Understanding
      setCurrentStep('analyzing')
      const formData = new FormData()
      formData.append('file', file)
      const apiUrl = await getApiUrl()

      const response = await fetch(`${apiUrl}/api/v1/documents/analyze`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        let errorMessage = 'Analysis failed'
        try {
          const errorData = await response.json()
          errorMessage = errorData.detail || errorMessage
        } catch {
          errorMessage = `Analysis failed with status ${response.status}`
        }
        throw new Error(errorMessage)
      }

      const data: AnalysisResult = await response.json()
      setResult(data)
      toast.success(`Analysis complete! Extracted ${data.field_count} fields`)
      
      // Step 2: Index the document in AI Search
      setCurrentStep('indexing')
      
      const indexResponse = await fetch(`${apiUrl}/api/v1/documents/upload`, {
        method: 'POST',
        body: formData
      })

      if (!indexResponse.ok) {
        const errorData = await indexResponse.json().catch(() => ({ detail: 'Indexing failed' }))
        console.warn('Indexing warning:', errorData.detail)
        toast.warning('Document analyzed but indexing failed: ' + errorData.detail)
      } else {
        toast.success(`Document indexed successfully`)
      }

      setCurrentStep('complete')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred'
      setError(errorMessage)
      setCurrentStep('error')
      toast.error('Processing failed: ' + errorMessage)
    }
  }

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.9) return 'default'
    if (confidence >= 0.7) return 'secondary'
    return 'destructive'
  }

  const getStepStatus = (step: ProcessingStep) => {
    if (!currentStep) return 'pending'
    const steps: ProcessingStep[] = ['uploading', 'analyzing', 'indexing', 'complete']
    const currentIndex = steps.indexOf(currentStep)
    const stepIndex = steps.indexOf(step)
    
    if (currentStep === 'error') return stepIndex <= currentIndex ? 'error' : 'pending'
    if (stepIndex < currentIndex) return 'complete'
    if (stepIndex === currentIndex) return 'active'
    return 'pending'
  }

  const isProcessing = currentStep && !['complete', 'error'].includes(currentStep)

  return (
    <div className="space-y-6 p-6">
      {/* Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <IconFileAnalytics className="h-6 w-6" />
            Content Understanding Test
          </CardTitle>
          <CardDescription>
            Upload a claim document (PDF, PNG, JPG, TIFF) to extract structured data using Azure Content Understanding
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isConfigured === false && (
            <Alert variant="destructive" className="mb-4">
              <IconAlertCircle className="h-4 w-4" />
              <AlertDescription>
                Content Understanding is not configured. Please configure Azure Content Understanding in the backend environment variables.
              </AlertDescription>
            </Alert>
          )}
          <FileUpload
            onFilesChange={handleFileUpload}
            disabled={isProcessing || isConfigured === false}
            accept=".pdf,.png,.jpg,.jpeg,.tiff"
          />
          
          {/* Processing Progress */}
          {isProcessing && (
            <div className="mt-6 space-y-4">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">Processing {uploadedFilename}</span>
                <span className="text-muted-foreground">
                  {currentStep === 'uploading' && 'Uploading...'}
                  {currentStep === 'analyzing' && 'Analyzing...'}
                  {currentStep === 'indexing' && 'Indexing...'}
                </span>
              </div>
              
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${getStepStatus('uploading') === 'complete' ? 'bg-green-500' : getStepStatus('uploading') === 'active' ? 'bg-blue-500 animate-pulse' : 'bg-gray-300'}`} />
                  <span className="text-sm">Upload Document</span>
                  {getStepStatus('uploading') === 'complete' && <IconCheck className="h-4 w-4 text-green-500 ml-auto" />}
                </div>
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${getStepStatus('analyzing') === 'complete' ? 'bg-green-500' : getStepStatus('analyzing') === 'active' ? 'bg-blue-500 animate-pulse' : 'bg-gray-300'}`} />
                  <span className="text-sm">Analyze with Content Understanding</span>
                  {getStepStatus('analyzing') === 'complete' && <IconCheck className="h-4 w-4 text-green-500 ml-auto" />}
                </div>
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${getStepStatus('indexing') === 'complete' ? 'bg-green-500' : getStepStatus('indexing') === 'active' ? 'bg-blue-500 animate-pulse' : 'bg-gray-300'}`} />
                  <span className="text-sm">Index in AI Search</span>
                  {getStepStatus('indexing') === 'complete' && <IconCheck className="h-4 w-4 text-green-500 ml-auto" />}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Success Message */}
      {currentStep === 'complete' && result && (
        <>
          {result.field_count > 0 ? (
            <Alert className="border-green-500 bg-green-50 dark:bg-green-950">
              <IconCheck className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-600 dark:text-green-400">
                Document successfully processed and indexed! Extracted {result.field_count} fields.
              </AlertDescription>
            </Alert>
          ) : (
            <Alert className="border-yellow-500 bg-yellow-50 dark:bg-yellow-950">
              <IconAlertCircle className="h-4 w-4 text-yellow-600" />
              <AlertDescription className="text-yellow-700 dark:text-yellow-400">
                <div className="font-medium mb-2">Analysis completed but no fields were extracted</div>
                <div className="text-sm space-y-1">
                  <p>This usually means the analyzer needs to be trained. Options:</p>
                  <ul className="list-disc ml-4 mt-1">
                    <li>Use a prebuilt analyzer: <code className="text-xs bg-yellow-100 dark:bg-yellow-900 px-1 rounded">prebuilt-document</code>, <code className="text-xs bg-yellow-100 dark:bg-yellow-900 px-1 rounded">prebuilt-invoice</code>, or <code className="text-xs bg-yellow-100 dark:bg-yellow-900 px-1 rounded">prebuilt-receipt</code></li>
                    <li>Train a custom analyzer in Azure AI Studio with sample documents</li>
                  </ul>
                  {(result as any).analyzer_id && (
                    <p className="mt-2 text-xs">Current analyzer: <code className="bg-yellow-100 dark:bg-yellow-900 px-1 rounded">{(result as any).analyzer_id}</code></p>
                  )}
                </div>
              </AlertDescription>
            </Alert>
          )}
        </>
      )}

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <IconAlertCircle className="h-4 w-4" />
          <AlertDescription>
            <div className="font-medium mb-1">Processing Failed</div>
            <div className="text-sm">{error}</div>
          </AlertDescription>
        </Alert>
      )}

      {/* Results Display */}
      {result && (
        <div className="space-y-4">
          {/* Summary Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Analysis Summary</span>
                <Badge variant="outline">{result.filename}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-3xl font-bold">{result.field_count}</div>
                <div className="text-sm text-muted-foreground">Fields Extracted</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">{result.table_count}</div>
                <div className="text-sm text-muted-foreground">Tables Found</div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold">
                  {result.confidence_scores ? 
                    Math.round(Object.values(result.confidence_scores).reduce((a, b) => a + b, 0) / Object.values(result.confidence_scores).length * 100) 
                    : 0}%
                </div>
                <div className="text-sm text-muted-foreground">Avg Confidence</div>
              </div>
            </CardContent>
          </Card>

          {/* Extracted Fields */}
          {result.field_count > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <IconFileText className="h-5 w-5" />
                  Extracted Fields & Confidence Scores
                </CardTitle>
                <CardDescription>
                  Key-value pairs extracted from the document with confidence scores
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(result.extracted_fields).map(([key, value]) => {
                    const confidence = result.confidence_scores[key] || 0
                    return (
                      <div key={key} className="border rounded-lg p-4">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex-1">
                            <div className="font-semibold text-sm text-muted-foreground mb-1">
                              {key}
                            </div>
                            <div className="text-base">
                              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                            </div>
                          </div>
                          <Badge variant={getConfidenceBadge(confidence)} className="ml-4">
                            {Math.round(confidence * 100)}%
                          </Badge>
                        </div>
                        <Progress 
                          value={confidence * 100} 
                          className="h-2"
                        />
                      </div>
                    )
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Tables */}
          {result.table_count > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <IconTable className="h-5 w-5" />
                  Extracted Tables
                </CardTitle>
                <CardDescription>
                  Structured tables found in the document
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {result.tables.map((table, idx) => (
                    <div key={idx} className="border rounded-lg p-4">
                      <div className="text-sm font-medium mb-2">
                        Table {idx + 1}: {table.row_count} rows × {table.column_count} columns
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {table.cells?.length || 0} cells detected
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Content Preview */}
          {result.content_preview && (
            <Card>
              <CardHeader>
                <CardTitle>Content Preview</CardTitle>
                <CardDescription>First 500 characters of extracted text</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="bg-muted p-4 rounded-lg font-mono text-sm whitespace-pre-wrap">
                  {result.content_preview}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
