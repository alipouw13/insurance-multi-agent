"use client"

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle, CheckCircle, Info } from "lucide-react"
import { EvaluationResult } from "@/lib/api"

interface EvaluationDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  evaluation: EvaluationResult | null
  loading?: boolean
}

export function EvaluationDialog({ open, onOpenChange, evaluation, loading }: EvaluationDialogProps) {
  const getScoreColor = (score?: number) => {
    if (score === undefined || score === null) return "text-muted-foreground"
    if (score >= 4.5) return "text-green-600"
    if (score >= 3.5) return "text-blue-600"
    if (score >= 2.5) return "text-yellow-600"
    return "text-red-600"
  }

  const getScoreBadge = (score?: number) => {
    if (score === undefined || score === null) return "outline"
    if (score >= 4.5) return "default"
    if (score >= 3.5) return "secondary"
    if (score >= 2.5) return "outline"
    return "destructive"
  }

  const getScoreIcon = (score?: number) => {
    if (score === undefined || score === null) return <AlertCircle className="h-4 w-4 text-muted-foreground" />
    if (score >= 4.0) return <CheckCircle className="h-4 w-4 text-green-600" />
    if (score >= 3.0) return <Info className="h-4 w-4 text-blue-600" />
    return <AlertCircle className="h-4 w-4 text-yellow-600" />
  }

  const formatScore = (score?: number) => {
    return score !== undefined && score !== null ? score.toFixed(2) : "N/A"
  }

  const scoreToPercentage = (score?: number) => {
    return score ? (score / 5) * 100 : 0
  }

  // Content-harm severity is 0-7 where LOWER is better, the opposite direction
  // to the 1-5 quality scores.
  const severityLabel = (score: number) => {
    if (score <= 1) return "Very low"
    if (score <= 3) return "Low"
    if (score <= 5) return "Medium"
    return "High"
  }

  const severityColor = (score: number) => {
    if (score <= 1) return "text-green-600"
    if (score <= 3) return "text-blue-600"
    if (score <= 5) return "text-yellow-600"
    return "text-red-600"
  }

  const safetyMetrics: Array<{ key: string; label: string; score?: number }> = [
    { key: "violence", label: "Violence", score: evaluation?.violence_score },
    { key: "sexual", label: "Sexual", score: evaluation?.sexual_score },
    { key: "self_harm", label: "Self-harm", score: evaluation?.self_harm_score },
    { key: "hate_unfairness", label: "Hate / unfairness", score: evaluation?.hate_unfairness_score },
  ]

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
                Overall Quality Score
                <Badge variant={getScoreBadge(evaluation.overall_score)}>
                  {formatScore(evaluation.overall_score)} / 5.0
                </Badge>
              </CardTitle>
              <CardDescription>
                Average of the quality metrics, scored 1&ndash;5 where higher is better
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Progress value={scoreToPercentage(evaluation.overall_score)} className="h-3" />
              {evaluation.status && evaluation.status !== "completed" && (
                <p className="mt-3 text-xs text-yellow-700 dark:text-yellow-400">
                  Evaluation status: <strong>{evaluation.status}</strong>
                  {evaluation.error_message ? ` — ${evaluation.error_message}` : null}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Foundry portal link */}
          {evaluation.studio_url && (
            <Alert>
              <Info className="h-4 w-4" />
              <AlertDescription className="text-sm">
                This run was uploaded to the Microsoft Foundry portal.{" "}
                <a
                  href={evaluation.studio_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium underline underline-offset-4"
                >
                  Open in the Evaluations pane
                </a>
                {evaluation.evaluation_run_name ? (
                  <span className="block text-xs text-muted-foreground mt-1 font-mono">
                    {evaluation.evaluation_run_name}
                  </span>
                ) : null}
              </AlertDescription>
            </Alert>
          )}
          {!evaluation.studio_url && evaluation.uploaded_to_portal === false && (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="text-xs">
                Results were computed locally and not uploaded to the Foundry portal.
                Check that the project is configured and the identity has access.
              </AlertDescription>
            </Alert>
          )}

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

          {/* Risk & Safety */}
          {(safetyMetrics.some((m) => m.score !== undefined && m.score !== null) ||
            evaluation.indirect_attack_detected !== undefined ||
            evaluation.protected_material_detected !== undefined) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center justify-between">
                  Risk &amp; Safety
                  {evaluation.safety_passed !== undefined && (
                    <Badge variant={evaluation.safety_passed ? "default" : "destructive"}>
                      {evaluation.safety_passed ? "Passed" : "Attention needed"}
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  Azure AI Content Safety severity, scored 0&ndash;7 where{" "}
                  <strong>lower is better</strong>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {safetyMetrics
                    .filter((m) => m.score !== undefined && m.score !== null)
                    .map((m) => (
                      <div
                        key={m.key}
                        className="flex items-center justify-between p-3 border rounded-lg"
                      >
                        <span className="text-sm font-medium">{m.label}</span>
                        <div className="text-right">
                          <div className={`text-lg font-bold ${severityColor(m.score as number)}`}>
                            {(m.score as number).toFixed(1)}{" "}
                            <span className="text-xs font-normal text-muted-foreground">/ 7</span>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {severityLabel(m.score as number)}
                          </div>
                        </div>
                      </div>
                    ))}
                </div>

                {(evaluation.indirect_attack_detected !== undefined ||
                  evaluation.protected_material_detected !== undefined) && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {evaluation.indirect_attack_detected !== undefined && (
                      <div className="flex items-center justify-between p-3 border rounded-lg">
                        <span className="text-sm font-medium">Indirect attack (XPIA)</span>
                        <Badge
                          variant={evaluation.indirect_attack_detected ? "destructive" : "default"}
                        >
                          {evaluation.indirect_attack_detected ? "Detected" : "Not detected"}
                        </Badge>
                      </div>
                    )}
                    {evaluation.protected_material_detected !== undefined && (
                      <div className="flex items-center justify-between p-3 border rounded-lg">
                        <span className="text-sm font-medium">Protected material</span>
                        <Badge
                          variant={
                            evaluation.protected_material_detected ? "destructive" : "default"
                          }
                        >
                          {evaluation.protected_material_detected ? "Detected" : "Not detected"}
                        </Badge>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

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
