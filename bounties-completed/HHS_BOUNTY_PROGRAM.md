# Open Source Bounty Program — Draft Documentation

## Overview
This document outlines the proposed open source bounty program for the Simpler Grants Protocol project. It defines how bounties are funded, approved, and paid, establishes scope and award ranges, and describes the contribution process and RFC guidelines.

## 1. Funding & Approval Process

### Funding Sources
- **Federal Grants:** Primary funding through HHS innovation grants and open-source initiatives
- **Agency Partnerships:** Co-funding with other federal agencies (GSA, SSA, etc.)
- **Private Donations:** Accepting donations from organizations aligned with government modernization
- **Matching Funds:** Leverage existing open-source matching programs where applicable

### Budget Allocation
| Category | Allocation | Notes |
|----------|-----------|-------|
| Developer Bounties | 40% | Core development work |
| Documentation | 15% | Technical docs, user guides |
| Security Audits | 20% | Independent security reviews |
| Testing/QA | 15% | Automated testing, user testing |
| Community | 10% | Meetups, training, mentorship |

### Approval Workflow
1. **Issue Submission:** Contributor creates issue with bounty scope
2. **Triage Review:** Project maintainers review for relevance and scope
3. **Budget Approval:** Program manager approves funding allocation
4. **Publication:** Bounty published with clear acceptance criteria
5. **Work Period:** 7-14 day window for completion
6. **Review:** Maintainers review pull request or deliverable
7. **Payment:** Automatic disbursement upon acceptance

### Payment Methods
- Cryptocurrency (USDC on public blockchains)
- Direct bank transfer (for US-based contributors)
- Gift cards (Amazon, developer services)

## 2. Bounty Scope & Sizing

### Bounty Categories

#### Tier 1: Quick Wins ($100-$500)
- Bug fixes
- Documentation improvements
- Minor UI enhancements
- Testing additions
- Dependencies updates

#### Tier 2: Feature Work ($500-$2,500)
- New features
- API improvements
- Security patches
- Performance optimization
- Integration work

#### Tier 3: Major Projects ($2,500-$10,000+)
- Architectural improvements
- New module development
- Security audits
- Complete documentation overhauls
- Cross-platform integration

### Sizing Guidelines

| Complexity | Effort | Award Range | Examples |
|-----------|--------|-------------|----------|
| Simple | 2-4 hours | $50-$200 | Typo fixes, minor updates |
| Medium | 1-2 days | $200-$1,000 | Bug fixes, new docs |
| Complex | 3-7 days | $1,000-$3,000 | New features, refactoring |
| Epic | 1-4 weeks | $3,000-$15,000 | Major modules, security audits |

### Scope Requirements
All bounties must include:
- **Clear acceptance criteria** (what constitutes completion)
- **Technical specifications** (where applicable)
- **Timeline expectations** (reasonable deadlines)
- **Review process** (how deliverables will be evaluated)

## 3. Contribution Process

### Step 1: Discovery
- Browse bounty list at `/bounties` in repository
- Check open/closed status
- Review acceptance criteria
- Verify no duplicate work

### Step 2: Claim
- Comment on bounty issue: "I'm working on this"
- Include brief description of approach
- Project maintainers have 48 hours to respond
- If no response, anyone can claim

### Step 3: Work
- Fork repository and create feature branch
- Follow project coding standards
- Include tests where applicable
- Update documentation as needed

### Step 4: Submit
- Create pull request linking to bounty issue
- Provide clear description of changes
- Include evidence of completion
- Respond to maintainer feedback

### Step 5: Review & Payment
- Maintainers review within 5 business days
- Requests for changes must be actionable
- Upon acceptance, payment processed within 3-5 days
- Disputes escalated to program manager

## 4. RFC (Request for Comments) Guidelines

### When to Use RFCs
- Major architectural changes
- New integration points
- API modifications
- Security-critical changes
- Cross-cutting concerns

### RFC Structure
```markdown
# RFC: [Title]

## Status
DRAFT | UNDER REVIEW | ACCEPTED | DEPRECATED

## Summary
One-paragraph overview of the change

## Motivation
Why is this needed? What problem does it solve?

## Design
Technical details, diagrams where helpful

## Alternatives Considered
What other options were evaluated?

## Implementation Notes
How should this be implemented?

## Dependencies
What else needs to change?

## Timeline
Proposed implementation schedule

## References
Links to issues, discussions, specifications
```

### RFC Process
1. Create RFC in `/rfcs` directory
2. Open issue linking to RFC
3. Community review period: 7-14 days
4. Maintainers provide feedback
5. RFC updated based on feedback
6. Vote by maintainers (2/3 majority)
7. RFC status updated
8. Implementation begins

## 5. Quality Standards

### Code Quality
- Follow project linting rules
- Maintain test coverage (target: 80%+)
- Document public APIs
- No breaking changes without version bump

### Documentation
- All new features documented
- Clear examples provided
- Links between related docs
- Updated changelog

### Security
- No secrets or credentials in code
- Dependencies updated regularly
- Security review for sensitive changes
- Report vulnerabilities privately

## 6. Governance

### Roles
- **Program Manager:** Oversees bounty program, budget, disputes
- **Maintainers:** Review work, approve payments, technical authority
- **Contributors:** Complete bounties, submit work
- **Reviewers:** Peer review (optional but encouraged)

### Decision Making
- Technical decisions: Maintainer consensus
- Budget decisions: Program manager authority
- Disputes: Escalation to program manager
- Policy changes: Community RFC process

### Transparency
- All bounties published publicly
- Payment records maintained (anonymous if requested)
- Quarterly reports on program metrics
- Open issue tracking for disputes

## 7. Launch Checklist

- [ ] Bounty issue template created
- [ ] Documentation published in `/bounties` directory
- [ ] Payment processing configured
- [ ] Review process defined in CONTRIBUTING.md
- [ ] GitHub Actions for automated testing configured
- [ ] Security review checklist established
- [ ] First 3 test bounties created (sizing, scope validation)
- [ ] Program manager on-call schedule established
- [ ] Communication channels set up (Discord/Slack)
- [ ] Legal review of payment terms complete

## 8. Metrics & Success Criteria

### KPIs to Track
- Number of bounties claimed/completed
- Average completion time
- Payment turnaround time
- Contributor satisfaction (survey)
- Code quality metrics
- Bug rates in merged PRs

### Success Benchmarks (First 6 Months)
- 50+ bounties completed
- 20+ unique contributors
- <7 day payment turnaround
- <10% rejected submissions
- Positive contributor feedback

## Appendix A: Sample Bounty Issue Template

```markdown
# Bounty: [Title]

## Status
OPEN | CLOSED | IN REVIEW

## Reward
$[Amount] or [Points]

## Difficulty
EASY | MEDIUM | HARD

## Description
[What needs to be done]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Technical Notes
[Any relevant technical details]

## Resources
[Links to docs, APIs, etc.]

## Timeline
- **Claim by:** [Date]
- **Submit by:** [Date]
- **Review by:** [Date]

## Related Issues
[#123, #456]
```

## Appendix B: Legal Considerations

### Payment Terms
- Payments processed within 5 business days of acceptance
- Tax implications: Contributors responsible for reporting
- Disputes resolved within 10 business days
- Right to reject work not meeting acceptance criteria

### Intellectual Property
- Work submitted becomes project property upon acceptance
- Contributors retain moral rights where applicable
- No licensing conflicts in submitted code
- Third-party dependencies must be compatible

### Privacy
- Contributor information kept confidential
- Payment details secure
- No personal data required beyond payment info
- GDPR compliance for EU contributors

---

**Document Version:** 0.1.0-draft  
**Last Updated:** September 3, 2026  
**Status:** Draft for Team Review  
**Prepared by:** sparkbountybot  
**For Review:** HHS Simpler Grants Protocol Team
