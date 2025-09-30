"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2 } from "lucide-react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface ScraperFormProps {
  onJobCreated: (jobId: string) => void
  disabled?: boolean
}

export default function ScraperForm({ onJobCreated, disabled }: ScraperFormProps) {
  const [url, setUrl] = useState("")
  const [dateDebut, setDateDebut] = useState("")
  const [dateFin, setDateFin] = useState("")
  const [searchTerm, setSearchTerm] = useState("")
  const [maxResults, setMaxResults] = useState("50")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const response = await fetch(`${API_URL}/api/scrape`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          url,
          date_debut: dateDebut || null,
          date_fin: dateFin || null,
          search_term: searchTerm || "",
          max_results: parseInt(maxResults) || 50,
        }),
      })

      if (!response.ok) {
        throw new Error(`Erreur HTTP: ${response.status}`)
      }

      const data = await response.json()
      onJobCreated(data.job_id)

      // Réinitialiser le formulaire
      // setUrl("")
      // setDateDebut("")
      // setDateFin("")
      // setSearchTerm("")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Une erreur est survenue")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Configuration du Scraping</CardTitle>
        <CardDescription>
          Entrez les paramètres pour extraire les données HelloAsso
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="url">URL HelloAsso *</Label>
            <Input
              id="url"
              type="url"
              placeholder="https://www.helloasso.com/..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
              disabled={disabled || loading}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="dateDebut">Date de début</Label>
              <Input
                id="dateDebut"
                type="date"
                value={dateDebut}
                onChange={(e) => setDateDebut(e.target.value)}
                disabled={disabled || loading}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="dateFin">Date de fin</Label>
              <Input
                id="dateFin"
                type="date"
                value={dateFin}
                onChange={(e) => setDateFin(e.target.value)}
                disabled={disabled || loading}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="searchTerm">Terme de recherche (optionnel)</Label>
            <Input
              id="searchTerm"
              type="text"
              placeholder="Ex: sport, culture, éducation..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              disabled={disabled || loading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="maxResults">Nombre maximum de résultats</Label>
            <Input
              id="maxResults"
              type="number"
              min="1"
              max="500"
              placeholder="50"
              value={maxResults}
              onChange={(e) => setMaxResults(e.target.value)}
              disabled={disabled || loading}
            />
            <p className="text-xs text-slate-500 dark:text-slate-400">
              ⏱️ Temps estimé: ~{Math.ceil(parseInt(maxResults || "50") * 3 / 60)} minutes
              (3-4 sec par association)
            </p>
          </div>

          {error && (
            <div className="p-3 text-sm text-red-600 bg-red-50 dark:bg-red-900/20 rounded-md">
              {error}
            </div>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={disabled || loading}
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Lancement du scraping...
              </>
            ) : (
              "Lancer le scraping"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}