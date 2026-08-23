"use client"

import { Markdown } from "@tiptap/markdown"
import { EditorContent, useEditor } from "@tiptap/react"
import StarterKit from "@tiptap/starter-kit"
import { Columns2, Maximize2, Minimize2, SquareSlash } from "lucide-react"
import {
  type KeyboardEvent as ReactKeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

type Props = {
  content: string
  editable: boolean
  onChange: (text: string) => void
}

export function normalizeMarkdown(markdown: string) {
  let inCodeFence = false

  return markdown
    .split("\n")
    .map((line) => {
      if (/^\s{0,3}(```|~~~)/.test(line)) {
        inCodeFence = !inCodeFence
        return line
      }
      if (inCodeFence) return line
      return line.replace(/^(\s{0,3}#{1,6})(?=\S)/, "$1 ")
    })
    .join("\n")
}

const MARKDOWN_INDENT = "  "

export function updateMarkdownIndentation(
  value: string,
  selectionStart: number,
  selectionEnd: number,
  unindent = false,
) {
  const firstLineStart = value.lastIndexOf("\n", selectionStart - 1) + 1
  const nextLineBreak = value.indexOf("\n", selectionEnd)
  const lastLineEnd = nextLineBreak === -1 ? value.length : nextLineBreak
  const selectedLines = value.slice(firstLineStart, lastLineEnd).split("\n")

  const removedPerLine = selectedLines.map((line) => {
    if (line.startsWith("\t")) return 1
    if (line.startsWith(MARKDOWN_INDENT)) return MARKDOWN_INDENT.length
    return line.startsWith(" ") ? 1 : 0
  })
  const nextLines = selectedLines.map((line, index) => {
    if (!unindent) return `${MARKDOWN_INDENT}${line}`
    return line.slice(removedPerLine[index] ?? 0)
  })
  const nextValue =
    value.slice(0, firstLineStart) +
    nextLines.join("\n") +
    value.slice(lastLineEnd)
  const selectionStartDelta = unindent
    ? -(removedPerLine[0] ?? 0)
    : MARKDOWN_INDENT.length
  const selectionEndDelta = unindent
    ? -removedPerLine.reduce((total, removed) => total + removed, 0)
    : MARKDOWN_INDENT.length * selectedLines.length

  return {
    value: nextValue,
    selectionStart: Math.max(
      firstLineStart,
      selectionStart + selectionStartDelta,
    ),
    selectionEnd: Math.max(firstLineStart, selectionEnd + selectionEndDelta),
  }
}

export function ParsedTextEditor({ content, editable, onChange }: Props) {
  const [isSplit, setIsSplit] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [localContent, setLocalContent] = useState(content)
  const wrapperRef = useRef<HTMLDivElement>(null)

  // Sync localContent when prop changes (e.g. initial load from API)
  useEffect(() => {
    setLocalContent(content)
  }, [content])

  // Single-pane WYSIWYG editor
  const editor = useEditor({
    extensions: [StarterKit, Markdown],
    content: normalizeMarkdown(content),
    editable: editable && !isSplit,
    immediatelyRender: false,
    contentType: "markdown",
    onUpdate: ({ editor: e }) => {
      if (!isSplit) onChange(e.getMarkdown())
    },
  })

  // Sync main editor content when localContent changes
  useEffect(() => {
    if (editor && localContent) {
      editor.commands.setContent(normalizeMarkdown(localContent), {
        contentType: "markdown",
      })
    }
  }, [localContent, editor])

  // Sync editable state on main editor
  useEffect(() => {
    if (editor) {
      editor.setEditable(editable && !isSplit)
    }
  }, [editable, isSplit, editor])

  // Escape key exits fullscreen
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) setIsFullscreen(false)
    }
    document.addEventListener("keydown", handleKey)
    return () => document.removeEventListener("keydown", handleKey)
  }, [isFullscreen])

  const handleTextareaChange = (value: string) => {
    setLocalContent(value)
    onChange(value)
  }

  const handleMarkdownKeyDown = (
    event: ReactKeyboardEvent<HTMLTextAreaElement>,
  ) => {
    if (event.key !== "Tab") return

    event.preventDefault()
    const textarea = event.currentTarget
    const next = updateMarkdownIndentation(
      textarea.value,
      textarea.selectionStart,
      textarea.selectionEnd,
      event.shiftKey,
    )
    setLocalContent(next.value)
    onChange(next.value)

    window.requestAnimationFrame(() => {
      textarea.selectionStart = next.selectionStart
      textarea.selectionEnd = next.selectionEnd
    })
  }

  const wrapperClass = isFullscreen
    ? "fixed inset-0 z-50 bg-white flex flex-col"
    : "rounded-lg border flex flex-col transition-colors"

  const editorBorderClass = isFullscreen
    ? ""
    : editable
      ? "border-gray-300 ring-1 ring-primary-100 focus-within:ring-primary-300"
      : "border-gray-200 bg-gray-50"

  return (
    <div
      ref={wrapperRef}
      className={`${wrapperClass} ${!isFullscreen ? editorBorderClass : ""}`}
    >
      {/* Toolbar */}
      <div
        className={`flex items-center justify-between px-3 py-2 border-b ${isFullscreen ? "border-gray-200" : "border-gray-100"}`}
      >
        <span className="text-xs font-medium text-gray-400">
          {isSplit ? "Split View" : "Editor"}
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setIsSplit((v) => !v)}
            className={`flex items-center gap-1.5 rounded px-2 py-1 text-xs transition-colors ${isSplit ? "bg-primary-50 text-primary-600" : "text-gray-400 hover:bg-gray-100 hover:text-gray-600"}`}
            title={isSplit ? "Exit split view" : "Split view"}
          >
            {isSplit ? (
              <SquareSlash className="h-3.5 w-3.5" />
            ) : (
              <Columns2 className="h-3.5 w-3.5" />
            )}
            <span className="hidden sm:inline">
              {isSplit ? "Single" : "Split"}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setIsFullscreen((v) => !v)}
            className="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            title={isFullscreen ? "Exit fullscreen (Esc)" : "Fullscreen"}
          >
            {isFullscreen ? (
              <Minimize2 className="h-3.5 w-3.5" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
            <span className="hidden sm:inline">
              {isFullscreen ? "Exit" : "Fullscreen"}
            </span>
          </button>
        </div>
      </div>

      {/* Editor area */}
      {isSplit ? (
        <div className="flex flex-1 overflow-hidden divide-x divide-gray-200">
          {/* Left: raw markdown textarea */}
          <div className="flex flex-1 flex-col">
            <div className="border-b border-gray-100 px-3 py-1">
              <span className="text-xs text-gray-400">Markdown</span>
            </div>
            <textarea
              value={localContent}
              readOnly={!editable}
              onChange={(e) => handleTextareaChange(e.target.value)}
              onKeyDown={handleMarkdownKeyDown}
              className={`flex-1 resize-none p-4 font-mono text-sm text-gray-700 focus:outline-none ${isFullscreen ? "min-h-0 h-full" : "min-h-64"} ${!editable ? "bg-gray-50 text-gray-500" : "bg-white"}`}
              spellCheck={false}
            />
          </div>

          {/* Right: rendered preview */}
          <div className="flex flex-1 flex-col overflow-auto">
            <div className="border-b border-gray-100 px-3 py-1">
              <span className="text-xs text-gray-400">Preview</span>
            </div>
            <div
              className={`flex-1 overflow-auto p-4 ${isFullscreen ? "" : "min-h-64"}`}
            >
              <div className="prose prose-sm prose-headings:text-main-800 prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg prose-a:text-primary-600 prose-code:rounded prose-code:bg-gray-100 prose-code:px-1 prose-code:py-0.5 prose-code:text-primary-700 prose-pre:bg-main-800 prose-pre:text-gray-100 max-w-none focus:outline-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {normalizeMarkdown(localContent)}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div
          className={`flex-1 overflow-auto ${isFullscreen ? "" : "min-h-64"}`}
        >
          <EditorContent
            editor={editor}
            className="prose prose-sm max-w-none p-4 focus:outline-none h-full"
          />
        </div>
      )}

      {/* Hint bar */}
      {editable && !isFullscreen && (
        <div className="border-t border-gray-100 px-4 py-2">
          <p className="text-xs text-gray-400">
            You can edit the parsed text above to correct OCR errors before
            approving.
          </p>
        </div>
      )}
    </div>
  )
}
