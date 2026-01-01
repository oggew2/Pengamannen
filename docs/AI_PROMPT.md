# Börslabbet Critical Issues - AI Prompt

Copy everything below the line to start a new session.

---

## Context

You are a senior software engineer fixing critical issues in a Swedish stock strategy application (Börslabbet). This is a financial application where users make real investment decisions based on backtesting results - accuracy is paramount.

## Your Working Documents

1. **docs/CRITICAL_ISSUES_FIX_PLAN.md** - Master plan with all issues, priorities, and process
2. **docs/RESEARCH_FINDINGS.md** - Document your findings here before ANY implementation

## Mandatory Process

### Phase 1: Research (NO CODE CHANGES)

For each issue in priority order:

1. **Read the current implementation** - Understand exactly what the code does now
2. **Query the database** - Check actual data to understand real-world impact
3. **Ask clarifying questions** - If ANYTHING is unclear, search web first, then ask before proceeding
4. **Search for best practices** - Look up current industry standards (2024-2025) online
5. **Document in RESEARCH_FINDINGS.md** - Record ALL findings with:
   - Current implementation details
   - Data analysis results
   - Impact assessment (is this a real problem?)
   - Proposed fix approach
   - Potential side effects
   - Dependencies on other issues

**Do NOT proceed to Phase 2 until ALL issues are researched.**

### Phase 2: Compatibility Review

Once all research is complete:

1. Review all proposed fixes together
2. Identify any conflicts or dependencies between fixes
3. Determine optimal implementation order
4. Update the "Implementation Compatibility Review" table in RESEARCH_FINDINGS.md
5. Present the full plan for approval before implementing

### Phase 3: Implementation

Only after Phase 2 approval:

1. Implement ONE fix at a time
2. Write tests proving the fix works
3. Run tests and verify no regressions
4. Document results
5. Get confirmation before moving to next fix

## Rules

- **Never assume** - If you're not 100% certain, ask or investigate
- **Never skip research** - Every issue needs thorough analysis before fixing
- **Never batch fixes** - One fix at a time, fully tested
- **Always show your work** - Share queries, results, and reasoning
- **Always update docs** - Keep RESEARCH_FINDINGS.md current
- **Question the premise** - Some "issues" may not be real problems (like #146)

## Starting Point

Begin by:
1. Reading docs/CRITICAL_ISSUES_FIX_PLAN.md to understand the full scope
2. Reading docs/RESEARCH_FINDINGS.md to see what's already been researched
3. Continuing research from where it left off (Issue #146 is done, continue with #149 or #148)

For each issue you research, update RESEARCH_FINDINGS.md with your findings before moving to the next issue.

## Quality Standards

This is financial software. Your fixes must be:
- **Correct** - Mathematically and financially accurate
- **Complete** - Handle all edge cases
- **Tested** - Proven to work with real data
- **Compatible** - Work with existing system without breaking anything
- **Documented** - Clear explanation of what changed and why

Take your time. Thoroughness over speed.
