"use client"

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { AlertCircle, CheckCircle, Info } from "lucide-react"
import { EvaluationResult } from "@/lib/api"

interface EvaluationDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  evaluation: EvaluationResult | null
  loading?: boolean
}

export function EvaluationDialog({ open, onOpenChange, evaluation, loading }: EvaluationDialogProps) {
  const getScoreColor = (score: number) => {
    if (score >= 4.5) return "text-green-600"
    if (score >= 3.5) return "text-blue-600"
    if (score >= 2.5) return "text-yellow-600"
    return "text-red-600"
  }

  const getScoreBadge = (score: number) => {
    if (score >= 4.5) return "default"
    if (score >= 3.5) return "secondary"
    if (score >= 2.5) return "outline"
    return "destructive"
  }

  const getScoreIcon = (score: number) => {
    if (score >= 4.0) return <CheckCircle className="h-4 w-4 text-green-600" />
    if (score >= 3.0) return <Info className="h-4 w-4 text-blue-600" />
    return <AlertCircle className="h-4 w-4 text-yellow-600" />
  }

  const formatScore = (score?: number) => {
    return score ? score.toFixed(2) : "N/A"
  }

  const scoreToPercentage = (score?: number) => {
    return score ? (score / 5) * 100 : 0
  }

  if (loading) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Evaluating Performance...</DialogTitle>
            <DialogDescription>
              Running Azure AI Foundry evaluation metrics
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  if (!evaluation) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>No Evaluation Available</DialogTitle>
            <DialogDescription>
              No evaluation data could be loaded.
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            Agent Performance Evaluation
            {getScoreIcon(evaluation.overall_score)}
          </DialogTitle>
          <DialogDescription>
            Azure AI Foundry Evaluation • {evaluation.agent_type} • {new Date(evaluation.evaluation_timestamp).toLocaleString()}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 mt-4">
          {/* Overall Score */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center justify-between">
                Overall Score
                <Badge variant={getScoreBadge(evaluation.overall_score)}>
                  {formatScore(evaluation.overall_score)} / 5.0
                </Badge>
              </CardTitle>
              <CardDescription>
                Aggregate performance across all metrics
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Progress value={scoreToPercentage(evaluation.overall_score)} className="h-3" />
            </CardContent>
          </Card>

          {/* Individual Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Groundedness */}
            {evaluation.groundedness_score !== undefined && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Groundedness</CardTitle>
                  <CardDescription className="text-xs">
                    How well the answer is supported by context
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-2xl font-bold ${getScoreColor(evaluation.groundedness_score)}`}>
                      {formatScore(evaluation.groundedness_score)}
                    </span>
                    <span className="text-sm text-muted-foreground">/ 5.0</span>
                  </div>
                  <Progress value={scoreToPercentage(evaluation.groundedness_score)} className="h-2" />
                </CardContent>
              </Card>
            )}

            {/* Relevance */}
            {evaluation.relevance_score !== undefined && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Relevance</CardTitle>
                  <CardDescription className="text-xs">
                    How well the answer addresses the question
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-2xl font-bold ${getScoreColor(evaluation.relevance_score)}`}>
                      {formatScore(evaluation.relevance_score)}
                    </span>
                    <span className="text-sm text-muted-foreground">/ 5.0</span>
                  </div>
                  <Progress value={scoreToPercentage(evaluation.relevance_score)} className="h-2" />
                </CardContent>
              </Card>
            )}

            {/* Coherence */}
            {evaluation.coherence_score !== undefined && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Coherence</CardTitle>
                  <CardDescription className="text-xs">
                    Logical consistency of the response
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-2xl font-bold ${getScoreColor(evaluation.coherence_score)}`}>
                      {formatScore(evaluation.coherence_score)}
                    </span>
                    <span className="text-sm text-muted-foreground">/ 5.0</span>
                  </div>
                  <Progress value={scoreToPercentage(evaluation.coherence_score)} className="h-2" />
                </CardContent>
              </Card>
            )}

            {/* Fluency */}
            {evaluation.fluency_score !== undefined && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">Fluency</CardTitle>
                  <CardDescription className="text-xs">
                    Language quality and readability
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-2xl font-bold ${getScoreColor(evaluation.fluency_score)}`}>
                      {formatScore(evaluation.fluency_score)}
                    </span>
                    <span className="text-sm text-muted-foreground">/ 5.0</span>
                  </div>
                  <Progress value={scoreToPercentage(evaluation.fluency_score)} className="h-2" />
                </CardContent>
              </Card>
            )}
          </div>

          {/* Reasoning */}
          {evaluation.reasoning && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Evaluation Reasoning</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {evaluation.reasoning}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Feedback */}
          {evaluation.feedback && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Feedback</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {evaluation.feedback}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Recommendations */}
          {evaluation.recommendations && evaluation.recommendations.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Recommendations</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                  {evaluation.recommendations.map((rec, index) => (
                    <li key={index}>{rec}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Metadata */}
          <Card className="bg-muted/50">
            <CardHeader>
              <CardTitle className="text-sm font-medium">Evaluation Metadata</CardTitle>
            </CardHeader>
            <CardContent className="text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Evaluation ID:</span>
                <span className="font-mono">{evaluation.evaluation_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Execution ID:</span>
                <span className="font-mono">{evaluation.execution_id}</span>
              </div>
              {evaluation.claim_id && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Claim ID:</span>
                  <span className="font-mono">{evaluation.claim_id}</span>
                </div>
              )}
              {evaluation.evaluation_duration && (
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Duration:</span>
                  <span>{evaluation.evaluation_duration.toFixed(2)}s</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-muted-foreground">Evaluator:</span>
                <span className="capitalize">{evaluation.evaluator_type}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </DialogContent>
    </Dialog>
  )
}
