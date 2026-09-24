import { Document, Page, pdfjs } from "react-pdf";
import { useState } from "react";
import { FileText, FileWarning, LoaderCircle, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function PdfPreview({
  file,
  className,
}: {
  file: File | null;
  className?: string;
}) {
  const [numPages, setNumPages] = useState(0);
  const [open, setOpen] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const isPdf =
    file?.type === "application/pdf" ||
    file?.name.toLowerCase().endsWith(".pdf");

  if (!file) return null;

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-secondary/45 p-3",
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <FileText className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{file.name}</p>
          <p className="text-xs text-muted-foreground">
            {isPdf ? "PDF preview ready" : "DOCX ready to analyse"} ·{" "}
            {(file.size / 1024 / 1024).toFixed(2)} MB
          </p>
        </div>
        {isPdf && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setPreviewError("");
              setOpen(true);
            }}
          >
            <Maximize2 data-icon="inline-start" />
            Preview
          </Button>
        )}
      </div>
      {isPdf && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="max-w-3xl bg-secondary/95 p-4">
            <DialogHeader>
              <DialogTitle>Resume preview</DialogTitle>
              <DialogDescription>
                Check that the page is readable before analysis.
              </DialogDescription>
            </DialogHeader>
            <div className="max-h-[65vh] overflow-auto rounded-xl border border-border bg-background p-4">
              <Document
                file={file}
                onLoadSuccess={({ numPages: pages }) => {
                  setNumPages(pages);
                  setPreviewError("");
                }}
                onLoadError={() =>
                  setPreviewError("This PDF could not be previewed. You can still continue with the analysis.")
                }
                loading={
                  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                    <LoaderCircle className="size-4 animate-spin" />
                    Loading PDF
                  </div>
                }
              >
                {Array.from({ length: numPages || 1 }).map((_, index) => (
                  <Page
                    key={index}
                    pageNumber={index + 1}
                    width={620}
                    renderTextLayer={false}
                    renderAnnotationLayer={false}
                    className="mx-auto mb-5 max-w-full overflow-hidden rounded-md shadow-xl"
                  />
                ))}
              </Document>
              {previewError && (
                <div role="alert" className="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  <FileWarning className="mt-0.5 size-4 shrink-0" />
                  {previewError}
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
