"use client"

import { useState } from "react"
import ScraperForm from "@/components/ScraperForm"
import ScraperStatus from "@/components/ScraperStatus"
import ResultsTable from "@/components/ResultsTable"
import LogsViewer from "@/components/LogsViewer"

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null)
  const [isJobRunning, setIsJobRunning] = useState(false)

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <div className="container mx-auto px-4 py-8">
        <header className="mb-8 text-center">
          <h1 className="text-4xl font-bold text-slate-900 dark:text-slate-100 mb-2">
            HelloAsso Scraper
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            Extraire les données des associations HelloAsso
          </p>
        </header>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Formulaire de scraping */}
          <div className="lg:col-span-2">
            <ScraperForm
              onJobCreated={(id) => {
                setJobId(id)
                setIsJobRunning(true)
              }}
              disabled={isJobRunning}
            />
          </div>

          {/* Statut du job en cours */}
          {jobId && (
            <div className="lg:col-span-2">
              <ScraperStatus
                jobId={jobId}
                onJobComplete={() => setIsJobRunning(false)}
              />
            </div>
          )}

          {/* Logs en temps réel */}
          {jobId && (
            <div className="lg:col-span-2">
              <LogsViewer jobId={jobId} />
            </div>
          )}

          {/* Tableau des résultats */}
          <div className="lg:col-span-2">
            <ResultsTable />
          </div>
        </div>
      </div>
    </div>
  )
}