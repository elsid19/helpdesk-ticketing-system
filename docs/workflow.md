# Help Desk Workflow Documentation

## Ticket Lifecycle

This simulator follows a realistic ticket flow used in many IT support teams:

1. **Open**
   - Ticket is submitted by a user/requester.
   - Initial details are captured: category, priority, issue summary, and description.

2. **In Progress**
   - A technician is assigned.
   - Investigation starts (triage, diagnostics, user communication).
   - Internal notes are appended to build a troubleshooting timeline.

3. **Resolved**
   - Root cause is identified and fix is applied.
   - Resolution notes are documented.
   - `resolved_at` timestamp is recorded automatically.

4. **Closed**
   - User confirms issue is resolved or support team closes after validation.

Status transitions are intentionally strict in the app:
`Open → In Progress → Resolved → Closed`

---

## Example Troubleshooting Scenario

### Scenario: VPN Connection Failure

- **Ticket category:** Network
- **Priority:** Critical
- **Symptoms:** User cannot connect remotely; VPN client returns error code.

### Typical Technician Workflow

1. Confirm service impact and urgency.
2. Check VPN gateway/server reachability.
3. Validate user account status and MFA requirements.
4. Verify client configuration/profile on user device.
5. Reproduce/confirm error code.
6. Apply fix (profile refresh, policy update, credential reset, etc.).
7. Document actions in internal notes.
8. Add final resolution notes and move ticket to Resolved.
9. Close after verification.

---

## How this Simulates Real IT Support Work

This project demonstrates core help desk habits:

- **Documentation discipline:** every important update is logged as a note or audit event.
- **Lifecycle control:** ticket status reflects operational reality.
- **Prioritization:** high/critical issues are visible in dashboard metrics.
- **Communication readiness:** issue context and resolution summary are kept in one place.
- **Reporting:** ticket data can be exported to CSV for review and trend analysis.

It is intentionally built with simple tools (Flask + SQLite + vanilla frontend) so the troubleshooting process and support logic are easy to understand in interviews.
