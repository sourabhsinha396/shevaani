"use client";

import * as React from "react";
import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Bold, Italic, List, ListOrdered } from "lucide-react";

import { looksLikeHtml } from "@/lib/rich-text";
import { cn } from "@/lib/utils";

/**
 * The description editor and its renderer, as a pair - whatever the toolbar
 * can produce, `.rich-text` (globals.css) knows how to draw, in the editor
 * and on the public page alike, so what the admin sees is what learners get.
 *
 * The toolbar is four buttons on purpose. A description is a paragraph or
 * two and a list - headings, tables and colours are how event descriptions
 * end up looking like ransom notes.
 *
 * Trust model: only superusers author this HTML, and the API already lets
 * them edit any row of the database - so rendering their markup verbatim
 * grants nothing they don't have. The moment this editor is offered to
 * instructors or learners, add sanitisation at the API.
 */

export function RichTextEditor({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
}) {
  const editor = useEditor({
    extensions: [StarterKit],
    // Older descriptions are plain text with newlines; feed them to Tiptap as
    // paragraphs rather than letting it swallow the line breaks.
    content: toEditorContent(value),
    // Rendered inside client pages that Next still server-renders once -
    // deferring the first render is what avoids the hydration mismatch.
    immediatelyRender: false,
    editorProps: {
      attributes: {
        // `field-sizing-content`-ish behaviour: grow with the text, but start
        // at textarea height so the form doesn't jump when it mounts.
        class: cn(
          "rich-text min-h-24 w-full px-3 py-2 text-sm outline-none",
          "placeholder:text-muted-foreground",
        ),
      },
    },
    onUpdate: ({ editor }) => {
      onChange(editor.isEmpty ? "" : editor.getHTML());
    },
  });

  // The edit screen loads its session after mount, so the editor starts empty
  // and the value arrives later. Sync only while unfocused - resetting content
  // under a typing cursor would teleport it to the end.
  React.useEffect(() => {
    if (!editor || editor.isFocused) return;
    const current = editor.isEmpty ? "" : editor.getHTML();
    if (value !== current)
      editor.commands.setContent(toEditorContent(value), { emitUpdate: false });
  }, [editor, value]);

  // Tiptap v3 doesn't re-render React on every transaction; this selector is
  // what keeps the toolbar's pressed states honest.
  const active = useEditorState({
    editor,
    selector: ({ editor: e }) =>
      e
        ? {
            bold: e.isActive("bold"),
            italic: e.isActive("italic"),
            bulletList: e.isActive("bulletList"),
            orderedList: e.isActive("orderedList"),
          }
        : null,
  });

  if (!editor) {
    // One frame on the client before the editor exists (immediatelyRender:
    // false). Reserve the box so the form doesn't reflow.
    return <div className="border-input min-h-[8.5rem] rounded-lg border" />;
  }

  const controls = [
    {
      icon: Bold,
      label: "Bold",
      pressed: active?.bold ?? false,
      run: () => editor.chain().focus().toggleBold().run(),
    },
    {
      icon: Italic,
      label: "Italic",
      pressed: active?.italic ?? false,
      run: () => editor.chain().focus().toggleItalic().run(),
    },
    {
      icon: List,
      label: "Bullet list",
      pressed: active?.bulletList ?? false,
      run: () => editor.chain().focus().toggleBulletList().run(),
    },
    {
      icon: ListOrdered,
      label: "Numbered list",
      pressed: active?.orderedList ?? false,
      run: () => editor.chain().focus().toggleOrderedList().run(),
    },
  ];

  return (
    <div className="border-input focus-within:ring-ring/50 rounded-lg border transition-shadow focus-within:ring-2">
      <div className="border-border/60 flex gap-1 border-b p-1">
        {controls.map((control) => (
          <button
            key={control.label}
            type="button"
            aria-label={control.label}
            aria-pressed={control.pressed}
            // Keep focus in the document: a toolbar that steals it collapses
            // the selection you were formatting.
            onMouseDown={(event) => event.preventDefault()}
            onClick={control.run}
            className={cn(
              "rounded-md p-1.5 transition-colors",
              control.pressed
                ? "bg-muted text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <control.icon className="size-4" />
          </button>
        ))}
      </div>
      <EditorContent editor={editor} />
      {editor.isEmpty && placeholder && (
        <p className="text-muted-foreground pointer-events-none -mt-8 px-3 pb-3 text-sm">
          {placeholder}
        </p>
      )}
    </div>
  );
}

/** Old plain-text descriptions become paragraphs; HTML passes through. */
function toEditorContent(value: string): string {
  if (!value) return "";
  if (looksLikeHtml(value)) return value;
  return value
    .split(/\n{2,}|\n/)
    .filter((line) => line.trim().length > 0)
    .map((line) => `<p>${line.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</p>`)
    .join("");
}

/** The public-page renderer. Plain-text rows render exactly as they always
 *  did; HTML rows get the same `.rich-text` styles the editor showed. */
export function RichTextContent({
  value,
  className,
}: {
  value: string;
  className?: string;
}) {
  if (!looksLikeHtml(value)) {
    return (
      <p className={cn("leading-relaxed whitespace-pre-line text-pretty", className)}>
        {value}
      </p>
    );
  }
  return (
    <div
      className={cn("rich-text leading-relaxed text-pretty", className)}
      // Superuser-authored markup; see the trust-model note above.
      dangerouslySetInnerHTML={{ __html: value }}
    />
  );
}
