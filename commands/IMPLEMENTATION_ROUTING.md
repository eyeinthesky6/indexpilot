# IndexPilot - Agent Implementation Routing Guide

**Purpose**: Step-wise routing and implementation guide for AI agents to implement/enhance features  
**Status**: ✅ Active Guide  
**Last Updated**: 07-12-2025

---

## Overview

This document provides a simple, step-wise process for agents to:
1. Understand the codebase architecture and purpose
2. Identify features to enhance or implement
3. Write, wire up, and integrate code
4. Check and fix errors
5. Update documentation
6. Identify next features

**Follow this guide sequentially for each feature implementation/enhancement task.**

---

## Step 1: Read Research Documentation

**Objective**: Understand research context, algorithms, and implementation requirements

**Actions**:
1. Read research documents in `docs/research/`:
   - `IMPLEMENTATION_GUIDE.md` - Standard implementation process
   - `IMPLEMENTATION_QUICK_START.md` - Quick reference
   - `ALGORITHM_TO_FEATURE_MAPPING.md` - Algorithm mappings
   - `USER_PAIN_POINTS_AND_WISHLIST.md` - User needs
   - `COMPETITOR_RESEARCH_SUMMARY.md` - Competitive context
   - Any algorithm-specific research docs

2. Identify:
   - Which algorithms/features are prioritized
   - Implementation requirements
   - Integration points mentioned
   - Dependencies and prerequisites

**Deliverable**: Understanding of research context and requirements

**Checklist**:
- [ ] Read relevant research docs
- [ ] Note algorithm/feature priorities
- [ ] Identify implementation requirements
- [ ] Note integration points

---

## Step 2: Read Features and Tech Documentation

**Objective**: Understand current features, architecture, and technical constraints

**Actions**:
1. Read feature documentation in `docs/features/`:
   - `FEATURES.md` - Complete feature list and status
   - `ENHANCEMENT_ROADMAP.md` - Future enhancements
   - `SYSTEM_VALUE_PROPOSITION.md` - Business value
   - `PRACTICAL_GUIDE.md` - Use cases
   - `FEATURE_STATUS_CHECK.md` - Current status

2. Read technical documentation in `docs/tech/`:
   - `ARCHITECTURE.md` - System architecture (CRITICAL)
   - `TYPE_SAFETY_IMPROVEMENTS.md` - Type safety guidelines
   - `CRITICAL_TYPE_ALIASES.md` - Type definitions
   - `DNA_METAPHOR_EXPLANATION.md` - Core concepts

3. Review `agents.yaml` in project root:
   - Package structure
   - Module locations
   - Routing guidance
   - Key locations

**Deliverable**: Understanding of current system capabilities and architecture

**Checklist**:
- [ ] Read feature documentation
- [ ] Read architecture documentation
- [ ] Review agents.yaml
- [ ] Understand current feature status
- [ ] Note technical constraints

---

## Step 3: Understand Codebase Architecture and Purpose

**Objective**: Deep dive into codebase structure, patterns, and purpose

**Actions**:
1. Read core architecture files:
   - `README.md` - Project overview and purpose
   - `src/schema.py` - Schema setup and business tables
   - `src/genome.py` - Genome catalog operations
   - `src/expression.py` - Per-tenant expression logic
   - `src/auto_indexer.py` - Main auto-indexing logic
   - `src/stats.py` - Query statistics collection

2. Understand key patterns:
   - DNA-inspired architecture (genome, expression, mutations)
   - Multi-tenant design (tenant_id in queries)
   - Cost-benefit analysis (queries × query_cost > build_cost)
   - Production safeguards (bypass system, rate limiting, etc.)
   - Database adapter pattern (PostgreSQL support)

3. Review integration points:
   - How modules interact
   - Data flow (query stats → analysis → index creation)
   - Configuration system (`indexpilot_config.yaml`)
   - Error handling patterns

4. Check existing code structure:
   - Function naming conventions
   - Type hints usage
   - Error handling patterns
   - Logging patterns
   - Test structure

**Deliverable**: Deep understanding of codebase architecture and patterns

**Checklist**:
- [ ] Read core architecture files
- [ ] Understand DNA-inspired concepts
- [ ] Understand multi-tenant design
- [ ] Review integration patterns
- [ ] Note code conventions
- [ ] Understand data flow

---

## Step 4: Identify Feature to Enhance/Implement

**Objective**: Select and scope the feature to work on

**Actions**:
1. Review enhancement roadmap:
   - `docs/features/ENHANCEMENT_ROADMAP.md` - Prioritized enhancements
   - `docs/research/IMPLEMENTATION_GUIDE.md` - Algorithm priorities
   - `docs/research/IMPLEMENTATION_QUICK_START.md` - Quick wins

2. Identify target feature:
   - Check if feature already exists (read `docs/features/FEATURES.md`)
   - Check if feature is marked as "Final" or needs enhancement
   - Review related research docs for requirements
   - Check for existing partial implementations

3. Scope the feature:
   - Define what needs to be implemented
   - Identify affected modules
   - List dependencies
   - Estimate complexity
   - Check for breaking changes

4. Review related code:
   - Find existing similar functionality
   - Identify integration points
   - Check configuration options
   - Review test coverage

**Deliverable**: Clear feature scope and implementation plan

**Checklist**:
- [ ] Review enhancement roadmap
- [ ] Identify target feature
- [ ] Check feature status
- [ ] Scope the feature
- [ ] Identify affected modules
- [ ] Review related code
- [ ] Note dependencies

---

## Step 5: Write Code

**Objective**: Implement the feature following codebase patterns

**Actions**:
1. Set up development environment:
   - Ensure dependencies installed (`pip install -r requirements.txt`)
   - Check database is running (`make init-db` if needed)
   - Review code style (ruff, mypy)

2. Write implementation:
   - Follow existing code patterns
   - Use type hints (see `docs/tech/TYPE_SAFETY_IMPROVEMENTS.md`)
   - Follow naming conventions
   - Add docstrings
   - Use existing utilities (db.py, validation.py, etc.)
   - Follow error handling patterns

3. Key principles:
   - **No mocks/stubs**: Full implementation only
   - **No partial implementation**: Complete feature
   - **Thread-safe**: Use locks for shared resources
   - **SQL injection safe**: Use parameterized queries
   - **Production-ready**: Include error handling, logging

4. Integration points:
   - Use `src/db.py` for database connections
   - Use `src/validation.py` for input validation
   - Use `src/rollback.py` for bypass checks
   - Use `src/audit.py` for audit logging
   - Use `src/config_loader.py` for configuration

**Deliverable**: Complete, production-ready code implementation

**Checklist**:
- [ ] Set up dev environment
- [ ] Write implementation code
- [ ] Follow code patterns
- [ ] Add type hints
- [ ] Add docstrings
- [ ] Use existing utilities
- [ ] Include error handling
- [ ] Add logging

---

## Step 6: Wire It Up

**Objective**: Connect the new code to existing systems

**Actions**:
1. Update existing functions:
   - Modify functions that call new code
   - Update function signatures if needed
   - Add new function calls where appropriate
   - Update imports

2. Add configuration:
   - Update `indexpilot_config.yaml.example` if needed
   - Add feature toggles if applicable
   - Add configuration options
   - Document configuration in comments

3. Update integration points:
   - Connect to query stats collection
   - Connect to auto-indexer if applicable
   - Connect to monitoring/health checks
   - Connect to audit logging

4. Update routing:
   - Update `agents.yaml` if new modules added
   - Update routing guidance if needed

**Deliverable**: Fully integrated code connected to existing systems

**Checklist**:
- [ ] Update existing functions
- [ ] Add configuration options
- [ ] Update integration points
- [ ] Update imports
- [ ] Update routing guidance
- [ ] Test integration points

---

## Step 7: Integrate

**Objective**: Ensure seamless integration with the rest of the system

**Actions**:
1. Integration testing:
   - Test with existing features
   - Test with simulator (`src/simulator.py`)
   - Test with different scenarios
   - Test error cases

2. Update dependent modules:
   - Update modules that depend on new code
   - Update tests if needed
   - Update documentation references

3. Verify integration:
   - Check data flow
   - Verify audit logging
   - Verify configuration loading
   - Verify bypass system integration

4. Performance considerations:
   - Check for performance impact
   - Verify thread safety
   - Check resource usage
   - Verify connection pooling

**Deliverable**: Fully integrated and tested feature

**Checklist**:
- [ ] Test with existing features
- [ ] Test with simulator
- [ ] Update dependent modules
- [ ] Verify data flow
- [ ] Verify audit logging
- [ ] Check performance
- [ ] Verify thread safety

---

## Step 8: Check and Fix Errors

**Objective**: Ensure code quality and correctness

**Actions**:
1. Run linting:
   ```bash
   make lint  # or: ruff check src/ --fix
   ```

2. Run type checking:
   ```bash
   make typecheck  # or: mypy src/
   ```

3. Run tests:
   ```bash
   make run-tests  # or: pytest tests/
   ```

4. Fix errors:
   - Fix linting errors
   - Fix type errors
   - Fix test failures
   - Fix runtime errors

5. Verify fixes:
   - Re-run linting
   - Re-run type checking
   - Re-run tests
   - Test manually if needed

**Deliverable**: Error-free, quality code

**Checklist**:
- [ ] Run linting
- [ ] Run type checking
- [ ] Run tests
- [ ] Fix all errors
- [ ] Verify fixes
- [ ] No linting errors
- [ ] No type errors
- [ ] All tests pass

---

## Step 9: Update Features and Tech Documentation

**Objective**: Keep documentation current with implementation

**Actions**:
1. Update feature documentation (`docs/features/`):
   - Update `FEATURES.md` if new feature added
   - Update `FEATURE_STATUS_CHECK.md` if status changed
   - Update `ENHANCEMENT_ROADMAP.md` if enhancement completed
   - Add feature-specific docs if needed

2. Update technical documentation (`docs/tech/`):
   - Update `ARCHITECTURE.md` if architecture changed
   - Add technical notes if needed
   - Update type definitions if new types added

3. Update research documentation (`docs/research/`):
   - Update implementation status if algorithm implemented
   - Add notes about implementation approach
   - Document any deviations from research

4. Update README if needed:
   - Add new features to feature list
   - Update usage examples
   - Update configuration examples

**Important**: 
- **Append, don't overwrite** to existing docs (per user rules)
- **Check existing docs first** before creating new ones
- **Get user approval** before updating canonical docs

**Deliverable**: Updated documentation reflecting implementation

**Checklist**:
- [ ] Update feature documentation
- [ ] Update technical documentation
- [ ] Update research documentation
- [ ] Update README if needed
- [ ] Verify documentation accuracy
- [ ] Check for duplicates

---

## Step 10: Check for Next Feature to Implement

**Objective**: Identify and prioritize next feature

**Actions**:
1. Review enhancement roadmap:
   - `docs/features/ENHANCEMENT_ROADMAP.md`
   - `docs/research/IMPLEMENTATION_GUIDE.md`
   - `docs/research/IMPLEMENTATION_QUICK_START.md`

2. Check feature status:
   - Review `docs/features/FEATURES.md` for incomplete features
   - Review `docs/features/FEATURE_STATUS_CHECK.md`
   - Check for "TODO" or "In Progress" markers

3. Prioritize next feature:
   - Check dependencies (are prerequisites met?)
   - Check priority (quick wins first)
   - Check complexity (balance quick wins with important features)
   - Check user needs (`docs/research/USER_PAIN_POINTS_AND_WISHLIST.md`)

4. Document next steps:
   - Note which feature to implement next
   - Note any blockers or dependencies
   - Update sprint status if needed

**Deliverable**: Clear next feature to implement

**Checklist**:
- [ ] Review enhancement roadmap
- [ ] Check feature status
- [ ] Prioritize next feature
- [ ] Check dependencies
- [ ] Document next steps

---

## Implementation Workflow Summary

```
1. Read Research Docs → Understand requirements
2. Read Features/Tech Docs → Understand system
3. Understand Codebase → Deep dive into architecture
4. Identify Feature → Select and scope feature
5. Write Code → Implement following patterns
6. Wire It Up → Connect to existing systems
7. Integrate → Ensure seamless integration
8. Check/Fix Errors → Ensure quality
9. Update Docs → Keep documentation current
10. Check Next Feature → Identify next task
```

---

## Key Principles

1. **No Mocks/Stubs**: Full implementation only, no partial code
2. **Follow Patterns**: Use existing code patterns and conventions
3. **Production-Ready**: Include error handling, logging, validation
4. **Documentation**: Keep docs updated, append don't overwrite
5. **Quality**: Fix all linting, type, and test errors
6. **Integration**: Ensure seamless integration with existing systems

---

## Quick Reference

### Key Files to Read First
- `agents.yaml` - Project structure and routing
- `docs/tech/ARCHITECTURE.md` - System architecture
- `docs/features/FEATURES.md` - Feature list and status
- `docs/features/ENHANCEMENT_ROADMAP.md` - Enhancement priorities
- `README.md` - Project overview

### Key Modules
- `src/auto_indexer.py` - Main auto-indexing logic
- `src/stats.py` - Query statistics
- `src/genome.py` - Genome catalog
- `src/expression.py` - Expression profiles
- `src/schema.py` - Schema setup

### Common Commands
```bash
make init-db          # Initialize database
make run-tests        # Run tests
make lint             # Run linting
make typecheck        # Run type checking
make run-sim-baseline # Run baseline simulation
make run-sim-autoindex # Run auto-index simulation
```

### Configuration
- `indexpilot_config.yaml.example` - Configuration template
- `schema_config.yaml.example` - Schema configuration template
- Use `src/config_loader.py` to load configuration

---

## Notes

- **Always read agents.yaml first** to understand project structure
- **Follow user rules**: No mocks, no stubs, no partial implementation
- **Check existing docs** before creating new ones
- **Append to docs**, don't overwrite (unless updating canonical docs with approval)
- **Test thoroughly** before marking as complete
- **Update documentation** as you implement

---

**Last Updated**: 07-12-2025

