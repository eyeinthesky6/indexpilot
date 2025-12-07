# Production Deployment Analysis

## Status

**Current Status**: Early prototype, safe for small deployments (< 100 tenants). Needs hardening for larger scale.

## Production Readiness Assessment

### Safe Modes

- **Advisory Mode (Default)**: System analyzes query patterns and logs candidate indexes to `mutation_log` without creating any DDL. Safe for production use.
- **Bypass System**: 4-level bypass mechanism allows granular control over all features.

### Recommended Production Usage

1. **Start with Advisory Mode**: Run in advisory mode to review candidate indexes before applying.
2. **Manual Review**: Review candidate indexes in `mutation_log` table before enabling `apply` mode.
3. **Gradual Rollout**: Test on small datasets first, then gradually expand.

### Current Limitations

- Tested so far on small datasets in Docker
- Cost estimation formulas are approximations and may need tuning for your workload
- No automatic index removal (indexes are created but never automatically dropped)

## Cost Analysis and Resource Usage

### Database Impact

- **Metadata Tables**: Minimal overhead (genome_catalog, expression_profile, mutation_log, query_stats)
- **Index Creation**: Uses `CREATE INDEX CONCURRENTLY` to minimize lock time
- **CPU Throttling**: Built-in CPU monitoring prevents index creation during high load

### Memory and Storage

- Query stats are batched to reduce write overhead
- Mutation log grows over time - consider periodic archival for long-running systems

## Side Effects and Risk Mitigation

### Potential Risks

1. **Index Bloat**: System creates indexes but doesn't automatically remove unused ones
   - **Mitigation**: Use advisory mode to review before creating, monitor index usage manually

2. **Write Performance**: Each index adds overhead to INSERT/UPDATE operations
   - **Mitigation**: Built-in write performance monitoring, configurable limits per table

3. **CPU Usage During Index Creation**: Creating indexes can be CPU-intensive
   - **Mitigation**: CPU throttling, maintenance windows, concurrent index creation

### Safety Features

- **Advisory Mode**: Default mode prevents accidental DDL
- **Bypass System**: Can disable any feature at runtime
- **Lock Management**: Prevents concurrent index creation on same table
- **Rate Limiting**: Limits index creation rate

## Deployment Checklist

- [ ] Review and customize `schema_config.yaml` for your schema
- [ ] Set `features.auto_indexer.mode: advisory` in `indexpilot_config.yaml`
- [ ] Configure database connection via `INDEXPILOT_DATABASE_URL`
- [ ] Initialize metadata tables (does not touch your schema)
- [ ] Run in advisory mode and review candidate indexes
- [ ] Configure adapters for host monitoring (Datadog, Prometheus, etc.)
- [ ] Set up monitoring alerts for mutation_log growth
- [ ] Test on staging environment first
- [ ] Gradually enable `apply` mode after review

## Future Work

- Automatic index removal for unused indexes
- More sophisticated cost-benefit analysis
- Support for composite/multi-column indexes
- Predictive indexing based on query patterns
- Integration with more monitoring systems

