import { apiClient } from '@/services/apiClient';
import type {
  AnswerValue,
  AssessmentDetail,
  AssessmentSummary,
} from '@/types/assessment';

const BASE = '/api/assessments';

export const assessmentService = {
  async create(symptomText: string): Promise<AssessmentDetail> {
    const { data } = await apiClient.post<AssessmentDetail>(BASE, {
      symptom_text: symptomText,
    });
    return data;
  },

  async get(id: string, signal?: AbortSignal): Promise<AssessmentDetail> {
    const { data } = await apiClient.get<AssessmentDetail>(
      `${BASE}/${id}`,
      signal ? { signal } : undefined,
    );
    return data;
  },

  async list(signal?: AbortSignal): Promise<AssessmentSummary[]> {
    const { data } = await apiClient.get<AssessmentSummary[]>(
      BASE,
      signal ? { signal } : undefined,
    );
    return data;
  },

  /** Answer the outstanding question; returns the updated assessment. */
  async answer(
    id: string,
    questionKey: string,
    value: AnswerValue,
  ): Promise<AssessmentDetail> {
    const { data } = await apiClient.post<AssessmentDetail>(`${BASE}/${id}/messages`, {
      question_key: questionKey,
      value,
    });
    return data;
  },

  /** Consider a report's values as part of this assessment. */
  async attachReport(id: string, reportId: string): Promise<AssessmentDetail> {
    const { data } = await apiClient.post<AssessmentDetail>(
      `${BASE}/${id}/reports/${reportId}`,
    );
    return data;
  },

  async detachReport(id: string, reportId: string): Promise<AssessmentDetail> {
    const { data } = await apiClient.delete<AssessmentDetail>(
      `${BASE}/${id}/reports/${reportId}`,
    );
    return data;
  },

  async analyse(id: string): Promise<AssessmentDetail> {
    const { data } = await apiClient.post<AssessmentDetail>(`${BASE}/${id}/analyze`);
    return data;
  },

  async remove(id: string): Promise<void> {
    await apiClient.delete(`${BASE}/${id}`);
  },
};
