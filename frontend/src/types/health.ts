export interface HealthResponse {
  status: string;
  environment: string;
  postgres: string;
  redis: string;
  pgvector: string;
  minio: string;
}
