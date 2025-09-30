"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Download, Trash2, RefreshCw, Loader2 } from "lucide-react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface FileInfo {
  filename: string
  size: number
  created_at: string
  modified_at: string
}

export default function ResultsTable() {
  const [files, setFiles] = useState<FileInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingFile, setDeletingFile] = useState<string | null>(null)

  const fetchFiles = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/api/files`)
      if (response.ok) {
        const data = await response.json()
        setFiles(data.files || [])
      }
    } catch (err) {
      console.error("Erreur lors de la récupération des fichiers:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFiles()

    // Rafraîchir toutes les 10 secondes
    const interval = setInterval(fetchFiles, 10000)
    return () => clearInterval(interval)
  }, [])

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

  const handleDelete = async (filename: string) => {
    if (!confirm(`Êtes-vous sûr de vouloir supprimer ${filename} ?`)) {
      return
    }

    setDeletingFile(filename)
    try {
      const response = await fetch(`${API_URL}/api/files/${filename}`, {
        method: "DELETE",
      })
      if (response.ok) {
        await fetchFiles()
      }
    } catch (err) {
      console.error("Erreur lors de la suppression:", err)
    } finally {
      setDeletingFile(null)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Fichiers de résultats</CardTitle>
            <CardDescription>
              {files.length} fichier{files.length !== 1 ? "s" : ""} disponible{files.length !== 1 ? "s" : ""}
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchFiles}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Rafraîchir
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading && files.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : files.length === 0 ? (
          <div className="text-center py-8 text-slate-500 dark:text-slate-400">
            Aucun fichier de résultat disponible
          </div>
        ) : (
          <div className="border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nom du fichier</TableHead>
                  <TableHead>Taille</TableHead>
                  <TableHead>Date de création</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {files.map((file) => (
                  <TableRow key={file.filename}>
                    <TableCell className="font-mono text-sm">
                      {file.filename}
                    </TableCell>
                    <TableCell>{formatFileSize(file.size)}</TableCell>
                    <TableCell>
                      {new Date(file.created_at).toLocaleString("fr-FR")}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDownload(file.filename)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDelete(file.filename)}
                          disabled={deletingFile === file.filename}
                        >
                          {deletingFile === file.filename ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4 text-red-500" />
                          )}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}