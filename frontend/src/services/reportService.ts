import { apiClient } from '@/services/apiClient';
import type { ReportDetail, ReportSummary } from '@/types/report';

const BASE = '/api/reports';

export const reportService = {
  async upload(file: File): Promise<ReportDetail> {
    const form = new FormData();
    form.append('file', file);
    // No Content-Type header here on purpose: axios clears it for FormData in
    // the browser so the boundary is generated. Setting it manually omits the
    // boundary and the server cannot parse the body.
    const { data } = await apiClient.post<ReportDetail>(BASE, form, {
      timeout: 120_000, // OCR on a multi-page scan is not instant.
    });
    return data;
  },

  async list(signal?: AbortSignal): Promise<ReportSummary[]> {
    const { data } = await apiClient.get<ReportSummary[]>(
      BASE,
      signal ? { signal } : undefined,
    );
    return data;
  },

  async get(id: string, signal?: AbortSignal): Promise<ReportDetail> {
    const { data } = await apiClient.get<ReportDetail>(
      `${BASE}/${id}`,
      signal ? { signal } : undefined,
    );
    return data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`${BASE}/${id}`);
  },

  /**
   * Download the original file.
   *
   * Fetched through the API client rather than linked to directly: the access
   * token lives in memory, so a plain `<a href>` navigation carries no
   * credentials and the request is rejected. The bytes are turned into a blob
   * URL and handed to a temporary anchor instead.
   */
  async download(id: string, filename: string): Promise<void> {
    const response = await apiClient.get<Blob>(`${BASE}/${id}/file`, {
      responseType: 'blob',
    });
    const url = URL.createObjectURL(response.data);
    try {
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } finally {
      // Revoking immediately can cancel the download in some browsers.
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    }
  },
};
