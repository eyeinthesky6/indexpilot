-- This proposal is intentionally redundant with an index recorded in the
-- sanitized example workload. IndexPilot should flag it for manual review.
CREATE INDEX CONCURRENTLY idx_orders_tenant_created_v2
ON public.orders (tenant_id, created_at);
