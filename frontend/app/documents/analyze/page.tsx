'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { AppSidebar } from "@/components/app-sidebar"
import { SiteHeader } from "@/components/site-header"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { FileUpload } from '@/components/ui/file-upload'
import { getApiUrl } from '@/lib/config'
import {
  FileText,
  Upload,
  CheckCircle,
  AlertCircle,
  Clock,
  FileCheck,
  TrendingUp,
  Search
} from 'lucide-react'

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

interface AnalyzedDocument {
  id: string
  filename: string
  timestamp: string
  status: 'succeeded' | 'failed' | 'processing'
  field_count: number
  table_count: number
  schema_score?: number
  result?: AnalysisResult
}

export default function DocumentAnalyzePage() {
  const [documents, setDocuments] = useState<AnalyzedDocument[]>([])
  const [selectedDoc, setSelectedDoc] = useState<AnalyzedDocument | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [documentUrl, setDocumentUrl] = useState<string | null>(null)
  
  // Panel widths (percentages)
  const [leftWidth, setLeftWidth] = useState(20)
  const [centerWidth, setCenterWidth] = useState(40)
  const [isResizing, setIsResizing] = useState<'left' | 'right' | null>(null)

  // Load document history from storage on mount
  useEffect(() => {
    loadClaimsFromStorage()
  }, [])

  const loadClaimsFromStorage = async () => {
    try {
      const apiUrl = await getApiUrl()
      const response = await fetch(`${apiUrl}/api/v1/documents?category=claim`)
      
      if (response.ok) {
        const data = await response.json()
        // Transform storage documents to AnalyzedDocument format
        const storageDocs: AnalyzedDocument[] = data.documents.map((doc: any) => ({
          id: doc.id,
          filename: doc.filename,
          timestamp: doc.upload_date,
          status: 'succeeded' as const,
          field_count: 0,
          table_count: 0,
          schema_score: 100
        }))
        setDocuments(storageDocs)
        console.log(`Loaded ${storageDocs.length} claims from storage`)
      } else {
        // Fallback to localStorage if API fails
        const saved = localStorage.getItem('analyzed_documents')
        if (saved) {
          setDocuments(JSON.parse(saved))
        }
      }
    } catch (err) {
      console.error('Failed to load claims from storage:', err)
      // Fallback to localStorage
      const saved = localStorage.getItem('analyzed_documents')
      if (saved) {
        setDocuments(JSON.parse(saved))
      }
    }
  }

  // Save to localStorage whenever documents change
  useEffect(() => {
    if (documents.length > 0) {
      localStorage.setItem('analyzed_documents', JSON.stringify(documents))
    }
  }, [documents])

  // Fetch document preview when selectedDoc changes (only for stored documents)
  useEffect(() => {
    const fetchDocumentPreview = async () => {
      if (!selectedDoc) {
        // Only clear if we don't have a valid blob URL
        if (!documentUrl || !documentUrl.startsWith('blob:')) {
          setDocumentUrl(null)
        }
        return
      }

      // Skip fetching if document is still processing or if we already have a valid preview
      if (selectedDoc.status === 'processing' || (documentUrl && documentUrl.startsWith('blob:'))) {
        return
      }

      try {
        // Try to get document from storage
        const apiUrl = await getApiUrl()
        const response = await fetch(`${apiUrl}/api/v1/documents/${selectedDoc.id}/download`)
        if (response.ok) {
          const blob = await response.blob()
          const url = URL.createObjectURL(blob)
          // Clean up old URL before setting new one
          if (documentUrl && documentUrl.startsWith('blob:')) {
            URL.revokeObjectURL(documentUrl)
          }
          setDocumentUrl(url)
          
          // If document doesn't have analysis results, analyze it now
          if (!selectedDoc.result && !isAnalyzing) {
            analyzeExistingDocument(selectedDoc.id, blob, selectedDoc.filename)
          }
        } else {
          console.warn('Document preview not available from storage:', selectedDoc.filename)
        }
      } catch (error) {
        console.error('Error fetching document preview:', error)
      }
    }

    fetchDocumentPreview()
  }, [selectedDoc?.id, selectedDoc?.status])

  const handleClearCache = () => {
    localStorage.removeItem('analyzed_documents')
    setDocuments([])
    setSelectedDoc(null)
    setDocumentUrl(null)
    toast.success('Document cache cleared')
  }

  // Analyze an existing document from storage that doesn't have results yet
  const analyzeExistingDocument = async (docId: string, blob: Blob, filename: string) => {
    setIsAnalyzing(true)
    toast.info(`Analyzing ${filename}...`)
    
    try {
      const apiUrl = await getApiUrl()
      
      // Create a File from the blob for the analyze endpoint
      const file = new File([blob], filename, { type: blob.type })
      const formData = new FormData()
      formData.append('file', file)
      
      console.log('Analyzing existing document:', filename)
      const response = await fetch(`${apiUrl}/api/v1/documents/analyze`, {
        method: 'POST',
        body: formData
      })
      
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Analysis error:', errorText)
        toast.error(`Analysis failed: ${response.statusText}`)
        return
      }
      
      const result: AnalysisResult = await response.json()
      console.log('Analysis result for existing doc:', result)
      
      // Calculate schema score
      const confidenceValues = Object.values(result.confidence_scores)
      const schemaScore = confidenceValues.length > 0
        ? Math.round((confidenceValues.filter(c => c >= 0.9).length / confidenceValues.length) * 100)
        : 0
      
      // Update the document with analysis results
      setDocuments(prev => prev.map(d => 
        d.id === docId 
          ? {
              ...d,
              field_count: result.field_count,
              table_count: result.table_count,
              schema_score: schemaScore,
              result
            }
          : d
      ))
      
      // Update selectedDoc if it's the one being analyzed
      setSelectedDoc(prev => 
        prev?.id === docId 
          ? {
              ...prev,
              field_count: result.field_count,
              table_count: result.table_count,
              schema_score: schemaScore,
              result
            }
          : prev
      )
      
      toast.success(`Extracted ${result.field_count} fields from ${filename}`)
      
    } catch (err) {
      console.error('Error analyzing existing document:', err)
      toast.error('Failed to analyze document')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleFileUpload = async (files: File[]) => {
    if (files.length === 0) return

    const file = files[0]
    console.log('Starting file upload:', file.name)
    setIsAnalyzing(true)

    // Create document URL for preview
    const url = URL.createObjectURL(file)
    setDocumentUrl(url)

    // Create pending document entry
    const pendingDoc: AnalyzedDocument = {
      id: Date.now().toString(),
      filename: file.name,
      timestamp: new Date().toISOString(),
      status: 'processing',
      field_count: 0,
      table_count: 0
    }

    setDocuments(prev => [pendingDoc, ...prev])
    setSelectedDoc(pendingDoc)

    try {
      const formData = new FormData()
      formData.append('file', file)
      const apiUrl = await getApiUrl()
      console.log('API URL:', apiUrl)

      // Step 1: Upload and analyze with Content Understanding
      console.log('Sending analysis request to:', `${apiUrl}/api/v1/documents/analyze`)
      const response = await fetch(`${apiUrl}/api/v1/documents/analyze`, {
        method: 'POST',
        body: formData
      })

      console.log('Analysis response status:', response.status)
      if (!response.ok) {
        const errorText = await response.text()
        console.error('Analysis error:', errorText)
        throw new Error(`Analysis failed: ${response.statusText}`)
      }

      const result: AnalysisResult = await response.json()
      console.log('Analysis result:', result)

      // Calculate schema score (percentage of fields with high confidence)
      const confidenceValues = Object.values(result.confidence_scores)
      const schemaScore = confidenceValues.length > 0
        ? Math.round((confidenceValues.filter(c => c >= 0.9).length / confidenceValues.length) * 100)
        : 0

      // Update document with results
      const updatedDoc: AnalyzedDocument = {
        ...pendingDoc,
        status: 'succeeded',
        field_count: result.field_count,
        table_count: result.table_count,
        schema_score: schemaScore,
        result
      }

      setDocuments(prev => prev.map(d => d.id === pendingDoc.id ? updatedDoc : d))
      setSelectedDoc(updatedDoc)
      toast.success(`Extracted ${result.field_count} fields from ${file.name}`)

      // Step 2: Upload document to storage (claim category) and index in AI Search
      try {
        const uploadFormData = new FormData()
        uploadFormData.append('files', file)  // Backend expects 'files' (plural)
        
        const indexResponse = await fetch(`${apiUrl}/api/v1/documents/upload?category=claim&auto_index=true`, {
          method: 'POST',
          body: uploadFormData
        })

        if (!indexResponse.ok) {
          const errorText = await indexResponse.text()
          console.error('Upload failed:', indexResponse.status, errorText)
          toast.warning(`Document analyzed but upload failed: ${errorText}`)
          const errorData = { detail: `Upload failed with status ${indexResponse.status}` }
        } else {
          toast.success('Document uploaded and indexed successfully')
        }
      } catch (indexErr) {
        console.warn('Failed to index document:', indexErr)
        toast.warning('Document analyzed but indexing failed')
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      console.error('Upload error:', err)
      
      // Update document as failed
      setDocuments(prev => prev.map(d => 
        d.id === pendingDoc.id 
          ? { ...d, status: 'failed' as const }
          : d
      ))
      
      toast.error(errorMessage)
    } finally {
      setIsAnalyzing(false)
    }
  }

  const filteredDocs = documents.filter(doc =>
    doc.filename.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const getStatusIcon = (status: AnalyzedDocument['status']) => {
    switch (status) {
      case 'succeeded':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'processing':
        return <Clock className="h-4 w-4 text-blue-500 animate-spin" />
    }
  }

  const getStatusBadge = (status: AnalyzedDocument['status']) => {
    const variants = {
      succeeded: 'default',
      failed: 'destructive',
      processing: 'secondary'
    }
    return <Badge variant={variants[status] as any}>{status}</Badge>
  }

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.9) return { variant: 'default' as const, label: 'High', color: 'text-green-600' }
    if (confidence >= 0.7) return { variant: 'secondary' as const, label: 'Medium', color: 'text-yellow-600' }
    return { variant: 'destructive' as const, label: 'Low', color: 'text-red-600' }
  }

  const getFieldType = (value: unknown): string => {
    if (typeof value === 'number') return 'number'
    if (typeof value === 'boolean') return 'boolean'
    if (Array.isArray(value)) return 'array'
    if (typeof value === 'object' && value !== null) return 'object'
    // Check if it's a date string
    if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) return 'date'
    return 'string'
  }

  // Handle resize
  const handleMouseMove = (e: MouseEvent) => {
    if (!isResizing) return
    
    const containerWidth = window.innerWidth - 288 // Subtract sidebar width
    const mouseX = e.clientX - 288 // Adjust for sidebar
    
    if (isResizing === 'left') {
      const newLeftWidth = (mouseX / containerWidth) * 100
      if (newLeftWidth >= 15 && newLeftWidth <= 35) {
        setLeftWidth(newLeftWidth)
      }
    } else if (isResizing === 'right') {
      const newCenterWidth = (mouseX / containerWidth) * 100 - leftWidth
      if (newCenterWidth >= 25 && newCenterWidth <= 60) {
        setCenterWidth(newCenterWidth)
      }
    }
  }

  const handleMouseUp = () => {
    setIsResizing(null)
  }

  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isResizing, leftWidth, centerWidth])

  const rightWidth = 100 - leftWidth - centerWidth

  return (
    <SidebarProvider
      style={{
        "--sidebar-width": "calc(var(--spacing) * 72)",
        "--header-height": "calc(var(--spacing) * 12)",
      } as React.CSSProperties}
    >
      <AppSidebar variant="inset" />
      <SidebarInset>
        <SiteHeader />
        
        <div className="flex h-[calc(100vh-var(--header-height))] overflow-hidden relative">
          {/* Left Panel - Document Queue */}
          <div 
            className="border-r bg-muted/10 flex flex-col overflow-hidden"
            style={{ 
              width: `${leftWidth}%`,
              minWidth: '380px',
              maxWidth: '600px'
            }}
          >
            <div className="p-4 border-b space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">Document Library</h2>
                  <p className="text-sm text-muted-foreground">
                    {documents.length} document{documents.length !== 1 ? 's' : ''} analyzed
                  </p>
                </div>
                {documents.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClearCache}
                    className="h-8 text-xs"
                  >
                    Clear All
                  </Button>
                )}
              </div>
              
              <FileUpload
                onFilesChange={handleFileUpload}
                disabled={isAnalyzing}
                maxFiles={1}
                accept=".pdf,.png,.jpg,.jpeg,.tiff"
              />

              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search documents..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>

            <ScrollArea className="flex-1">
              <div className="p-2 space-y-2">
                {filteredDocs.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <FileText className="h-12 w-12 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">No documents analyzed yet</p>
                  </div>
                ) : (
                  filteredDocs.map(doc => (
                    <Card
                      key={doc.id}
                      className={`cursor-pointer transition-colors hover:bg-accent ${
                        selectedDoc?.id === doc.id ? 'border-primary bg-accent' : ''
                      }`}
                      onClick={() => setSelectedDoc(doc)}
                    >
                      <CardContent className="p-3">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            {getStatusIcon(doc.status)}
                            <span className="text-sm font-medium truncate">
                              {doc.filename}
                            </span>
                          </div>
                          <div className="flex-shrink-0">
                            {getStatusBadge(doc.status)}
                          </div>
                        </div>
                        
                        <div className="space-y-1 text-xs text-muted-foreground">
                          <div className="flex justify-between items-center">
                            <span>Schema Score:</span>
                            <div className="flex items-center gap-1">
                              <span className="font-medium">
                                {doc.schema_score !== undefined && doc.schema_score !== null 
                                  ? `${doc.schema_score}%` 
                                  : 'N/A'}
                              </span>
                              <TrendingUp className="h-3 w-3" />
                            </div>
                          </div>
                          <div className="text-xs">
                            {new Date(doc.timestamp).toLocaleString()}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))
                )}
              </div>
            </ScrollArea>
          </div>

          {/* Resize Handle - Left */}
          <div
            className="w-1 hover:w-2 bg-border hover:bg-primary cursor-col-resize transition-all relative group"
            onMouseDown={() => setIsResizing('left')}
          >
            <div className="absolute inset-y-0 -left-1 -right-1" />
          </div>

          {/* Center Panel - Document Viewer */}
          <div 
            className="flex flex-col bg-muted/5 overflow-hidden"
            style={{ 
              width: `${centerWidth}%`,
              minWidth: '300px'
            }}
          >
            {selectedDoc ? (
              <>
                <div className="border-b p-4 bg-background">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold">{selectedDoc.filename}</h3>
                      <p className="text-sm text-muted-foreground">
                        {new Date(selectedDoc.timestamp).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      {selectedDoc.schema_score !== undefined && (
                        <Badge variant="outline" className="text-lg px-3 py-1">
                          <TrendingUp className="h-4 w-4 mr-1" />
                          {selectedDoc.schema_score}% Schema Score
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex-1 overflow-auto p-4">
                  {documentUrl && (
                    <div className="w-full h-full flex items-center justify-center bg-background rounded-lg border">
                      {selectedDoc.filename.toLowerCase().endsWith('.pdf') ? (
                        <iframe
                          src={documentUrl}
                          className="w-full h-full rounded-lg"
                          title="Document Preview"
                        />
                      ) : (
                        <img
                          src={documentUrl}
                          alt="Document Preview"
                          className="max-w-full max-h-full object-contain"
                        />
                      )}
                    </div>
                  )}
                  {!documentUrl && (
                    <div className="text-center text-muted-foreground py-12">
                      <FileText className="h-16 w-16 mx-auto mb-4 opacity-50" />
                      <p>Document preview not available</p>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <Upload className="h-16 w-16 mx-auto mb-4 opacity-50" />
                  <p className="text-lg font-medium mb-2">No document selected</p>
                  <p className="text-sm">Upload a document to get started</p>
                </div>
              </div>
            )}
          </div>

          {/* Resize Handle - Right */}
          <div
            className="w-1 hover:w-2 bg-border hover:bg-primary cursor-col-resize transition-all relative group"
            onMouseDown={() => setIsResizing('right')}
          >
            <div className="absolute inset-y-0 -left-1 -right-1" />
          </div>

          {/* Right Panel - Extracted Results */}
          <div 
            className="border-l bg-background flex flex-col overflow-hidden"
            style={{ 
              width: `${rightWidth}%`,
              minWidth: '300px'
            }}
          >
            {selectedDoc && selectedDoc.result ? (
              <>
                <div className="border-b p-4">
                  <h3 className="font-semibold mb-2">Extracted Results</h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="space-y-1">
                      <p className="text-muted-foreground">Fields</p>
                      <p className="text-2xl font-bold">{selectedDoc.field_count}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-muted-foreground">Tables</p>
                      <p className="text-2xl font-bold">{selectedDoc.table_count}</p>
                    </div>
                  </div>
                </div>

                <Tabs defaultValue="fields" className="flex-1 flex flex-col overflow-hidden">
                  <TabsList className="w-full rounded-none border-b">
                    <TabsTrigger value="fields" className="flex-1">
                      Fields ({selectedDoc.field_count})
                    </TabsTrigger>
                    <TabsTrigger value="tables" className="flex-1">
                      Tables ({selectedDoc.table_count})
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="fields" className="flex-1 mt-0 overflow-hidden">
                    <ScrollArea className="h-full">
                      <div className="p-4 space-y-3">
                        {Object.entries(selectedDoc.result.extracted_fields).map(([key, value]) => {
                          const confidence = selectedDoc.result!.confidence_scores[key] || 0
                          const confBadge = getConfidenceBadge(confidence)
                          const fieldType = getFieldType(value)

                          return (
                            <Card key={key} className="p-3">
                              <div className="space-y-2">
                                <div className="flex items-start justify-between gap-2">
                                  <div className="space-y-1 min-w-0 flex-1">
                                    <p className="text-sm font-medium text-muted-foreground truncate">
                                      {key.replace(/_/g, ' ')}
                                    </p>
                                    <div className="flex items-center gap-2">
                                      <Badge variant="outline" className="text-xs">
                                        {fieldType}
                                      </Badge>
                                      <Badge variant={confBadge.variant} className="text-xs">
                                        {(confidence * 100).toFixed(0)}%
                                      </Badge>
                                    </div>
                                  </div>
                                  <FileCheck className={`h-4 w-4 ${confBadge.color}`} />
                                </div>
                                
                                <div className="text-sm font-mono bg-muted p-2 rounded break-words">
                                  {fieldType === 'array' || fieldType === 'object' 
                                    ? JSON.stringify(value, null, 2)
                                    : String(value)
                                  }
                                </div>
                              </div>
                            </Card>
                          )
                        })}
                      </div>
                    </ScrollArea>
                  </TabsContent>

                  <TabsContent value="tables" className="flex-1 mt-0 overflow-hidden h-full">
                    <ScrollArea className="h-full">
                      <div className="p-4 space-y-4 pb-8">
                        {selectedDoc.table_count === 0 ? (
                          <div className="text-center text-muted-foreground py-12">
                            <FileText className="h-12 w-12 mx-auto mb-2 opacity-50" />
                            <p>No tables extracted</p>
                          </div>
                        ) : (
                          <>
                            {selectedDoc.result.tables.map((table, idx) => (
                              <Card key={idx} className="p-4">
                                <CardHeader className="p-0 pb-3">
                                  <CardTitle className="text-sm">Table {idx + 1}</CardTitle>
                                  <CardDescription className="text-xs">
                                    {table.row_count} rows × {table.column_count} columns
                                  </CardDescription>
                                </CardHeader>
                                <CardContent className="p-0">
                                  <ScrollArea className="h-[300px] w-full">
                                    <pre className="text-xs bg-muted p-3 rounded">
                                      {JSON.stringify(table, null, 2)}
                                    </pre>
                                  </ScrollArea>
                                </CardContent>
                              </Card>
                            ))}
                          </>
                        )}
                      </div>
                    </ScrollArea>
                  </TabsContent>
                </Tabs>
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-muted-foreground p-8">
                <div className="text-center">
                  {isAnalyzing ? (
                    <>
                      <Clock className="h-12 w-12 mx-auto mb-4 opacity-50 animate-spin" />
                      <p className="text-sm font-medium">Analyzing document...</p>
                      <p className="text-xs mt-2">Extracting fields and tables with Content Understanding</p>
                    </>
                  ) : (
                    <>
                      <FileCheck className="h-12 w-12 mx-auto mb-4 opacity-50" />
                      <p className="text-sm">
                        {selectedDoc?.status === 'processing' 
                          ? 'Processing document...'
                          : 'Select a document to view analysis results'
                        }
                      </p>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  )
}
