/** Medical report contract types, mirroring the backend schemas. */

export type ReportStatus = 'pending' | 'processed' | 'failed';
export type ExtractionMethod = 'text_layer' | 'ocr' | 'mixed' | 'none';
export type ValueFlag = 'normal' | 'low' | 'high' | 'unknown';

export interface ReportValue {
  id: string;
  analyte: string;
  display_name: string;
  value: number;
  unit: string | null;
  reference_low: number | null;
  reference_high: number | null;
  reference_text: string | null;
  flag: ValueFlag;
  /** The printed unit was not recognised; do not compare across reports. */
  unit_unrecognised: boolean;
  source_line: string | null;
}

export interface ReportSummary {
  id: string;
  original_filename: string;
  status: ReportStatus;
  size_bytes: number;
  page_count: number | null;
  extraction_method: ExtractionMethod | null;
  report_date: string | null;
  value_count: number;
  abnormal_count: number;
  created_at: string;
}

export interface ReportDetail {
  id: string;
  original_filename: string;
  status: ReportStatus;
  content_type: string;
  size_bytes: number;
  page_count: number | null;
  extraction_method: ExtractionMethod | null;
  report_date: string | null;
  error_message: string | null;
  values: ReportValue[];
  extracted_text: string | null;
  created_at: string;
  processed_at: string | null;
}

export const EXTRACTION_METHOD_LABEL: Record<ExtractionMethod, string> = {
  text_layer: 'Read from the document text',
  ocr: 'Read by OCR from a scan',
  mixed: 'Partly text, partly OCR',
  none: 'No text found',
};

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Format a value with its unit, e.g. `10.8 g/dL`. */
export function formatValue(value: ReportValue): string {
  const number = Number.isInteger(value.value)
    ? value.value.toLocaleString()
    : value.value.toString();
  return value.unit ? `${number} ${value.unit}` : number;
}
