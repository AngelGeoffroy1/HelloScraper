"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { CheckCircle2, Loader2, XCircle, Download } from "lucide-react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface JobStatus {
  job_id: string
  status: "pending" | "running" | "completed" | "failed"
  progress?: string
  result_files?: string[]
  error?: string
  created_at: string
  completed_at?: string
}

interface ScraperStatusProps {
  jobId: string
  onJobComplete?: () => void
}

export default function ScraperStatus({ jobId, onJobComplete }: ScraperStatusProps) {
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch(`${API_URL}/api/status/${jobId}`)
        if (response.ok) {
          const data = await response.json()
          setStatus(data)

          // Appeler onJobComplete si le job est terminé
          if ((data.status === "completed" || data.status === "failed") && onJobComplete) {
            onJobComplete()
          }
        }
      } catch (err) {
        console.error("Erreur lors de la récupération du statut:", err)
      } finally {
        setLoading(false)
      }
    }

    fetchStatus()

    // Polling toutes les 2 secondes si le job n'est pas terminé
    const interval = setInterval(() => {
      if (status?.status === "pending" || status?.status === "running") {
        fetchStatus()
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [jobId, status?.status, onJobComplete])

  const getStatusIcon = () => {
    if (!status) return null

    switch (status.status) {
      case "pending":
      case "running":
        return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
      case "completed":
        return <CheckCircle2 className="h-5 w-5 text-green-500" />
      case "failed":
        return <XCircle className="h-5 w-5 text-red-500" />
    }
  }

  const getStatusBadge = () => {
    if (!status) return null

    const variants: Record<JobStatus["status"], "default" | "secondary" | "destructive"> = {
      pending: "secondary",
      running: "default",
      completed: "default",
      failed: "destructive",
    }

    const labels: Record<JobStatus["status"], string> = {
      pending: "En attente",
      running: "En cours",
      completed: "Terminé",
      failed: "Échoué",
    }

    return (
      <Badge variant={variants[status.status]}>
        {labels[status.status]}
      </Badge>
    )
  }

  const handleDownload = async (filename: string) => {
    try {
      const response = await fetch(`${API_URL}/api/download/${filename}`)
      if (response.ok) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = filename
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      }
    } catch (err) {
      console.error("Erreur lors du téléchargement:", err)
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!status) return null

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              {getStatusIcon()}
              Statut du scraping
            </CardTitle>
            <CardDescription className="mt-1">
              Job ID: {jobId.substring(0, 8)}...
            </CardDescription>
          </div>
          {getStatusBadge()}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {status.progress && (
          <div className="p-3 bg-slate-50 dark:bg-slate-800 rounded-md">
            <p className="text-sm text-slate-700 dark:text-slate-300">
              {status.progress}
            </p>
          </div>
        )}

        {status.error && (
          <div className="p-3 bg-red-50 dark:bg-red-900/20 rounded-md">
            <p className="text-sm text-red-600 dark:text-red-400">
              Erreur: {status.error}
            </p>
          </div>
        )}

        {status.result_files && status.result_files.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium">Fichiers générés:</h4>
            <div className="space-y-2">
              {status.result_files.map((file) => (
                <div
                  key={file}
                  className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800 rounded-md"
                >
                  <span className="text-sm font-mono">{file}</span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDownload(file)}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Télécharger
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="text-xs text-slate-500 dark:text-slate-400">
          <p>Créé: {new Date(status.created_at).toLocaleString("fr-FR")}</p>
          {status.completed_at && (
            <p>Terminé: {new Date(status.completed_at).toLocaleString("fr-FR")}</p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}