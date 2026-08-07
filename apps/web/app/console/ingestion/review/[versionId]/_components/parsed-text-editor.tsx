"use client"

import { useEditor, EditorContent } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import { useEffect } from "react"

type Props = {
  content: string
  editable: boolean
  onChange: (text: string) => void
}

export function ParsedTextEditor({ content, editable, onChange }: Props) {
  const editor = useEditor({
    extensions: [StarterKit],
    content,
    editable,
    onUpdate: ({ editor: e }) => {
      onChange(e.getText())
    },
  })

  useEffect(() => {
    if (editor && editor.getText() !== content) {
      editor.commands.setContent(content)
    }
  }, [content, editor])

  useEffect(() => {
    if (editor) {
      editor.setEditable(editable)
    }
  }, [editable, editor])

  return (
    <div className="rounded-lg border bg-white shadow-sm">
      <div className="border-b px-4 py-2">
        <span className="text-sm font-semibold text-gray-500">Teks Hasil Parsing</span>
      </div>
      <EditorContent
        editor={editor}
        className="prose prose-sm max-w-none min-h-64 p-4 focus:outline-none"
      />
    </div>
  )
}
