"use client"

import { useEffect, useState, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Download, Trash2 } from "lucide-react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface Log {
  timestamp: string
  message: string
  level: "info" | "warning" | "error" | "success"
}

interface LogsViewerProps {
  jobId: string
}

export default function LogsViewer({ jobId }: LogsViewerProps) {
  const [logs, setLogs] = useState<Log[]>([])
  const logsEndRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (!jobId) return

    // Connexion SSE pour les logs en temps réel
    const eventSource = new EventSource(`${API_URL}/api/logs/${jobId}`)

    eventSource.onmessage = (event) => {
      try {
        const log: Log = JSON.parse(event.data)
        setLogs((prev) => [...prev, log])
      } catch (err) {
        console.error("Error parsing log:", err)
      }
    }

    eventSource.onerror = (error) => {
      console.error("SSE Error:", error)
      eventSource.close()
    }

    return () => {
      eventSource.close()
    }
  }, [jobId])

  useEffect(() => {
    if (autoScroll) {
      logsEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }
  }, [logs, autoScroll])

  const getLevelColor = (level: string) => {
    switch (level) {
      case "success":
        return "text-green-600 dark:text-green-400"
      case "warning":
        return "text-yellow-600 dark:text-yellow-400"
      case "error":
        return "text-red-600 dark:text-red-400"
      default:
        return "text-slate-700 dark:text-slate-300"
    }
  }

  const getLevelIcon = (level: string) => {
    switch (level) {
      case "success":
        return "✅"
      case "warning":
        return "⚠️"
      case "error":
        return "❌"
      default:
        return "ℹ️"
    }
  }

  const clearLogs = () => {
    setLogs([])
  }

  const downloadLogs = () => {
    const logsText = logs
      .map((log) => `[${log.timestamp}] ${log.message}`)
      .join("\n")

    const blob = new Blob([logsText], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `scraper-logs-${jobId}.txt`
    document.body.appendChild(a)
    a.click()
    URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              📋 Logs en temps réel
            </CardTitle>
            <CardDescription>{logs.length} ligne(s)</CardDescription>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={clearLogs}
              disabled={logs.length === 0}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Effacer
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={downloadLogs}
              disabled={logs.length === 0}
            >
              <Download className="h-4 w-4 mr-2" />
              Télécharger
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative">
          <div className="bg-slate-950 dark:bg-slate-900 rounded-lg p-4 h-96 overflow-y-auto font-mono text-sm">
            {logs.length === 0 ? (
              <div className="text-slate-500 text-center py-8">
                En attente des logs...
              </div>
            ) : (
              <div className="space-y-1">
                {logs.map((log, index) => (
                  <div key={index} className="flex gap-2">
                    <span className="text-slate-500 shrink-0">
                      [{log.timestamp}]
                    </span>
                    <span className={getLevelColor(log.level)}>
                      {log.message}
                    </span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>

          {/* Toggle auto-scroll */}
          <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
            <input
              type="checkbox"
              id="autoscroll"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded"
            />
            <label htmlFor="autoscroll" className="cursor-pointer">
              Auto-scroll
            </label>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}