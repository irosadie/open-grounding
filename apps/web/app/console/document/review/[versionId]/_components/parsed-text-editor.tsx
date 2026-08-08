"use client"

import { EditorContent, useEditor } from "@tiptap/react"
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
    immediatelyRender: false,
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
    <div className={`rounded-lg border transition-colors ${editable ? "border-gray-300 ring-1 ring-primary-100 focus-within:ring-primary-300" : "border-gray-200 bg-gray-50"}`}>
      <EditorContent
        editor={editor}
        className="prose prose-sm max-w-none min-h-64 p-4 focus:outline-none"
      />
      {editable && (
        <div className="border-t border-gray-100 px-4 py-2">
          <p className="text-xs text-gray-400">You can edit the parsed text above to correct OCR errors before approving.</p>
        </div>
      )}
    </div>
  )
}
